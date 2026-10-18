# -*- coding: utf-8 -*-
#  _                           _ _ _
# | |                         | (_) |
# | | _____  _ __   __ _  __ _| |_| |__
# | |/ / _ \| '_ \ / _` |/ _` | | | '_ \
# |   < (_) | | | | (_| | (_| | | | |_) |
# |_|\_\___/|_| |_|\__, |\__,_|_|_|_.__/
#                   __/ |
#                  |___/
#
# Konga client library, by EasyByte Software
#
# https://github.com/easybyte-software/kongalib


from kongalib import Error
from _kongalib import set_interpreter_timeout, set_interpreter_yield
try:
	from _kongalib import _set_process_foreground
except ImportError:
	# modulo ridotto al nucleo (es. nel browser): nessun processo da portare in primo piano
	_set_process_foreground = None

import sys
import math
import os
import collections
import json
import atexit
import io
import threading
import _thread
import queue as _queue
import multiprocessing
import multiprocessing.connection
import multiprocessing.reduction
import asyncio
import inspect
import signal
import logging
import logging.handlers
import time


DEBUG = False

gConnFamily = None
gConnFamilyOverride = False

_DLL_PATHS = []

# Intervallo (ms) con cui l'interruzione chiesta dall'utente viene sollevata di nuovo nello
# script, finché questo non la gestisce
STOP_RETRY_INTERVAL = 500
# Secondi concessi allo script per gestire l'interruzione, prima che l'host arresti
# d'autorità l'interprete
STOP_GRACE = 5

# Chiamata con cui lo script segnala all'host di aver gestito l'interruzione
_STOP_HANDLED = '_timeout_stop_handled'
# Chiamata con cui l'interprete comunica all'host la fine di un'esecuzione e il suo esito
_SCRIPT_DONE = '_script_done'
# Tipo di un messaggio dello script verso l'host, in testa alla chiamata serializzata: una
# chiamata attende la risposta, una notifica no
_CALL = b'C'
_NOTIFY = b'N'
# Rinvio (ms) di un controllo del timeout scaduto dentro questo stesso modulo
_DEFER_INTERVAL = 50
# Riarmo minimo (ms) di un timeout scaduto mentre era sospeso
_MIN_REARM = 0.001
_THIS_FILE = __file__
# Segnale simulato (mai inviato dal sistema operativo) con cui i thread dell'interprete
# fanno eseguire al thread dello script la scadenza del timeout o la richiesta di
# interruzione dell'host
_INTERRUPT_SIGNAL = getattr(signal, 'SIGUSR1', None) or getattr(signal, 'SIGBREAK', None)

# Nel browser (Pyodide, con JSPI) l'interprete è un Web Worker: niente processi né thread
_WEB = sys.platform == 'emscripten'
# Ogni quanti millisecondi lo script nel worker cede il passo, perché arrivino i messaggi dell'host
_YIELD_INTERVAL = 100

#: Nel browser, come caricare un interprete (un Web Worker con la propria Pyodide): ``index_url``
#: (l'URL di Pyodide, con la barra finale), ``packages`` (pacchetti di Pyodide da caricare) e
#: ``wheels`` (URL delle wheel da installare, kongalib compresa). Lo imposta l'applicazione, con gli
#: stessi valori con cui si è caricata lei.
WORKER_CONFIG = None


class BadConnection(Exception):
	"""L'interprete non riesce a collegarsi all'host con la famiglia di connessione in uso."""
	def __init__(self, message=None):
		super().__init__(message or 'Unable to connect the interpreter to the host')
		self._bad_connection = True



class _Terminate(BaseException):
	"""Sollevata nell'interprete quando l'host ne chiede la terminazione (SIGTERM)."""
	pass


class InterpreterTimeout(BaseException):
	"""Sollevata nello script quando l'utente ne chiede l'interruzione allo scadere del
	timeout. Deriva da BaseException perché un generico ``except Exception`` dello script
	non la intercetti; finché lo script non la gestisce viene sollevata di nuovo."""
	pass



class InterpreterError(Exception):
	"""Non più sollevata: l'esito di un'esecuzione è in :class:`ExecutionResult`. Resta per
	compatibilità con il codice che la intercetta."""
	def __init__(self, exc_info):
		self._exc_info = exc_info
	def get_exc_info(self):
		return self._exc_info



class ExecutionResult:
	"""Esito di un'esecuzione, restituito da :func:`execute`. *exc_info* è la tupla
	``(tipo, valore, traceback)`` dell'eccezione riportata, se presente; *exitcode* è il
	codice di uscita del processo dell'interprete, se è terminato inaspettatamente."""
	COMPLETED	= 'completed'	#: lo script è terminato normalmente
	FAILED		= 'failed'		#: lo script è terminato con un'eccezione
	TIMEOUT		= 'timeout'		#: lo script è stato interrotto allo scadere del timeout
	TERMINATED	= 'terminated'	#: l'interprete è stato arrestato dall'host
	CRASHED		= 'crashed'		#: il processo dell'interprete è terminato inaspettatamente

	def __init__(self, status, exc_info=None, exitcode=None):
		self.status = status
		self.exc_info = exc_info
		self.exitcode = exitcode

	def __repr__(self):
		return '<ExecutionResult %s>' % self.status



class _ScriptException(Exception):
	"""Sostituisce, nella comunicazione con l'host, un'eccezione dello script che l'host non
	potrebbe ricostruire (es. di una classe definita dallo script stesso): ne conserva il
	testo come lo stamperebbe Python."""
	def __init__(self, lines):
		super().__init__(''.join(lines).strip())
		self.lines = lines



def _dumps(obj):
	return bytes(multiprocessing.reduction.ForkingPickler.dumps(obj))


def _loads(data):
	return multiprocessing.reduction.ForkingPickler.loads(data)



def _run_coroutine(coro, loop):
	# Esegue *coro* da codice sincrono: sul loop *loop* attendendone la fine, se gira in un
	# altro thread; se gira in questo thread non si può attendere e viene solo avviata.
	# Senza loop la esegue in un loop temporaneo.
	if loop is None:
		return asyncio.run(coro)
	try:
		running = asyncio.get_running_loop()
	except RuntimeError:
		running = None
	if running is loop:
		return loop.create_task(coro)
	return asyncio.run_coroutine_threadsafe(coro, loop).result()



def debug_log(text):
	try:
		_logger.debug(text)
	except:
		try:
			sys.__stderr__.write('%s\n' % text)
		except:
			pass
	# sys.__stderr__.write(text + '\n')



class _TimeoutBlocker:
	"""Sospende il timeout dello script per la durata di una chiamata all'host."""
	def __init__(self):
		self.lock = threading.RLock()
	def __enter__(self):
		self.lock.acquire()
		_pause_timeout()
	def __exit__(self, exc_type, exc_value, exc_traceback):
		try:
			_resume_timeout()
		finally:
			self.lock.release()


class _ConnectionChannel:
	"""Canale delle chiamate dello script verso l'host per il backend a processi, su una
	connessione multiprocessing. Trasporta messaggi già codificati."""
	def __init__(self, conn):
		self.conn = conn

	@classmethod
	def connect(cls, conn_type, address):
		debug_log("[Proxy] init: %s" % repr(address))
		try:
			conn = multiprocessing.connection.Client(address, conn_type)
		except Exception as e:
			import traceback
			_logger.error("[Proxy] init error: %s" % traceback.format_exc())
			raise BadConnection('Unable to connect the interpreter to the host: %s' % e)
		debug_log("[Proxy] connection established")
		return cls(conn)

	def call(self, data):
		"""Invia la chiamata codificata *data* e restituisce la risposta codificata."""
		self.conn.send_bytes(_CALL + data)
		return self.conn.recv_bytes()

	def notify(self, data):
		"""Invia la chiamata codificata *data* senza attendere risposta."""
		self.conn.send_bytes(_NOTIFY + data)

	def close(self):
		self.conn.close()


class Proxy:
	"""Gli handler dell'host visti dallo script: ``proxy.<handler>.<metodo>(...)`` chiama il
	metodo sull'host e ne attende il risultato, ``proxy.<handler>.<metodo>.notify(...)`` lo
	chiama senza attendere."""
	def __init__(self):
		self._channel = None
		self._lock = _TimeoutBlocker()

	def _attach(self, channel):
		self.close()
		self._channel = channel

	def is_valid(self):
		return self._channel is not None

	def close(self):
		if self._channel is not None:
			sys.stdout.flush()
			sys.stderr.flush()
			self._channel.close()
			self._channel = None
		debug_log("[Proxy] connection closed")

	def __getattr__(self, name):
		return _MethodHandler(self, name)


class _TraceClock:
	"""Scadenza del timeout misurata dalla trace C di _kongalib, che la controlla a ogni
	evento dello script e alla scadenza chiama timeout_handler(): per dove non ci sono
	thread (Pyodide), e fuori da un interprete di scripting."""
	def arm(self, timeout):
		# la trace conta in millisecondi interi
		set_interpreter_timeout(math.ceil(timeout) if timeout else 0)



class _TimerClock:
	"""Scadenza del timeout misurata da un thread, che alla scadenza sveglia il thread dello
	script (il principale) con un segnale simulato: a differenza della trace, nessun costo
	per ogni riga eseguita."""
	def __init__(self):
		self.cond = threading.Condition()
		self.deadline = None
		self.thread = None

	def arm(self, timeout):
		with self.cond:
			self.deadline = (time.monotonic() + timeout / 1000) if timeout else None
			if (self.thread is None) and (self.deadline is not None):
				self.thread = threading.Thread(target=self._run, name='timeout', daemon=True)
				self.thread.start()
			self.cond.notify()

	def _run(self):
		with self.cond:
			while True:
				if self.deadline is None:
					self.cond.wait()
					continue
				left = self.deadline - time.monotonic()
				if left > 0:
					self.cond.wait(left)
					continue
				self.deadline = None
				_thread.interrupt_main(_INTERRUPT_SIGNAL)



def _select_clock():
	# KONGALIB_TIMEOUT_CLOCK=trace sceglie la trace C anche dove ci sono i thread (prove)
	if (os.environ.get('KONGALIB_TIMEOUT_CLOCK') != 'trace') and (_INTERRUPT_SIGNAL is not None):
		try:
			threading.Thread(target=lambda: None, daemon=True).start()
			return _TimerClock()
		except RuntimeError:
			pass
	return _TraceClock()



class _State:
	io = []
	atexit_registered = False
	# Solo il thread che esegue lo script arma, sospende e ripristina il timeout. None
	# fuori da un interprete di scripting, dove agisce il thread chiamante.
	script_thread = None
	timeout_lock = threading.RLock()
	clock = _TraceClock()
	# Timeout configurato (ms), riarmato quando l'utente sceglie di continuare
	timeout = 0
	# Sospensioni annidate in corso (chiamate all'host) e tempo da riarmare alla fine
	pause_depth = 0
	paused_left = None
	handling_timeout = False
	# L'utente ha chiesto l'interruzione e lo script non l'ha ancora gestita
	stopping = False
	# Uno script è in esecuzione
	running = False
	# Il thread dello script sta comunicando con l'host: la scadenza va rinviata alla fine
	# della comunicazione
	in_channel = 0
	expiry_pending = False
	# Quando e per quanti millisecondi (frazionari) è stato armato l'orologio: il tempo
	# rimasto si conta da qui, non dall'orologio, che arrotonda al millisecondo
	armed_at = None
	armed_for = None


proxy = Proxy()
_logger = logging.getLogger("script")


def _on_script_thread():
	return _State.script_thread in (None, threading.get_ident())


def _clock_arm(timeout):
	# da chiamare con _State.timeout_lock acquisito; *timeout* in millisecondi, anche
	# frazionari; 0 o None disarma
	if timeout:
		_State.armed_at = time.monotonic()
		_State.armed_for = float(timeout)
	else:
		_State.armed_at = _State.armed_for = None
	_State.clock.arm(timeout or 0)


def _clock_left():
	# da chiamare con _State.timeout_lock acquisito: millisecondi esatti alla scadenza (0 o
	# meno se è scaduto ma non ancora gestito), None se l'orologio è disarmato
	if _State.armed_at is None:
		return None
	return _State.armed_for - (time.monotonic() - _State.armed_at) * 1000


def _arm_timeout(timeout):
	# da chiamare con _State.timeout_lock acquisito
	if _State.pause_depth > 0:
		_State.paused_left = timeout or None
	elif _on_script_thread():
		_clock_arm(timeout)


def _time_left():
	# da chiamare con _State.timeout_lock acquisito
	if _State.pause_depth > 0:
		left = _State.paused_left
	else:
		left = _clock_left()
	if left is None:
		return None
	# un timeout scaduto ma non ancora rilevato va comunque riarmato
	return max(int(left), 1)


def _pause_timeout():
	with _State.timeout_lock:
		if not _on_script_thread():
			return
		if _State.pause_depth == 0:
			# il tempo rimasto si conserva esatto: arrotondato al millisecondo, uno script
			# che chiama l'host più volte per millisecondo non arriverebbe mai alla scadenza
			left = None
			if not _State.handling_timeout:
				left = _clock_left()
			try:
				_clock_arm(0)
			except:
				pass
			_State.paused_left = left
		_State.pause_depth += 1


def _resume_timeout():
	with _State.timeout_lock:
		if (not _on_script_thread()) or (_State.pause_depth == 0):
			return
		_State.pause_depth -= 1
		if _State.pause_depth == 0:
			left, _State.paused_left = _State.paused_left, None
			if left is not None:
				if left <= 0:
					# già scaduto: la scadenza arriva alla fine della comunicazione con l'host
					# (_ChannelUse) senza aspettare l'orologio; la trace conta in millisecondi
					# interi e non la vedrebbe mai in uno script che chiama l'host più volte
					# per millisecondo
					_State.expiry_pending = True
				try:
					_clock_arm(max(left, _MIN_REARM))
				except:
					pass


def set_script_timeout(timeout):
	"""Imposta il timeout dello script a *timeout* millisecondi (0 per disattivarlo) e lo
	riarma da subito; è anche il valore usato per riarmarlo quando l'utente sceglie di
	continuare l'esecuzione. Restituisce il timeout configurato in precedenza."""
	with _State.timeout_lock:
		previous = _State.timeout
		_State.timeout = timeout or 0
		_arm_timeout(_State.timeout)
		# reimpostare il timeout vale come gestione dell'interruzione chiesta dall'utente
		stop_handled, _State.stopping = _State.stopping, False
	if stop_handled and proxy.is_valid():
		try:
			getattr(proxy.builtin, _STOP_HANDLED)()
		except:
			pass
	return previous


def suspend_script_timeout():
	"""Sospende il timeout dello script e restituisce i millisecondi che mancavano alla sua
	scadenza, da passare a :func:`resume_script_timeout`, o None se non era attivo."""
	with _State.timeout_lock:
		left = _time_left()
		_arm_timeout(0)
		return left


def resume_script_timeout(timeout):
	"""Riarma il timeout dello script a *timeout* millisecondi; se lo script non ha un
	timeout configurato, *timeout* diventa quello configurato."""
	with _State.timeout_lock:
		if not _State.timeout:
			_State.timeout = timeout or 0
		_arm_timeout(timeout)


def get_script_time_left():
	"""Restituisce i millisecondi che mancano alla scadenza del timeout dello script, o 0
	se non è attivo."""
	with _State.timeout_lock:
		return _time_left() or 0


def _on_expiry_signal(signo=None, frame=None):
	# Sul thread dello script: il timeout è scaduto (_TimerClock) o l'host ha chiesto di
	# interrompere lo script, che vale come la scadenza immediata del timeout
	_expired(frame)


def _read_control(conn, requests):
	# Legge la pipe di controllo anche mentre il thread principale esegue uno script, per
	# ricevere le richieste di interruzione
	try:
		while True:
			request = conn.recv()
			if request[0] == 'interrupt':
				if _INTERRUPT_SIGNAL is not None:
					_thread.interrupt_main(_INTERRUPT_SIGNAL)
			else:
				requests.put(request)
	except (EOFError, OSError):
		pass
	requests.put(('quit',))


def timeout_handler():
	# Chiamata dalla trace C di _kongalib (_TraceClock) a timeout scaduto, con la trace già
	# rimossa: il timeout resta quello che viene armato da qui
	_expired(sys._getframe(1))


def _expired(frame):
	# Scadenza del timeout sul thread dello script; *frame* è il codice che stava girando
	with _State.timeout_lock:
		if (not _State.running) or _State.handling_timeout:
			return
		if (_State.in_channel > 0) or ((frame is not None) and (frame.f_code.co_filename == _THIS_FILE)):
			# mai interrompere una comunicazione con l'host o il codice di questo modulo: la
			# scadenza arriva alla fine della comunicazione (_ChannelUse), altrimenti si
			# ripete a breve
			_State.expiry_pending = True
			if _State.pause_depth > 0:
				_State.paused_left = 1
			else:
				_clock_arm(_DEFER_INTERVAL)
			return
		if _State.pause_depth > 0:
			# lo script attende l'host: la scadenza arriva quando la chiamata finisce
			_State.paused_left = 1
			return
		_State.expiry_pending = False
		stopping = _State.stopping
		_State.handling_timeout = not stopping
	# La domanda all'host tiene lo script fermo finché l'utente non risponde
	if not stopping:
		try:
			stop = proxy.builtin.handle_timeout()
		except:
			with _State.timeout_lock:
				_arm_timeout(0)
			raise
		finally:
			with _State.timeout_lock:
				_State.handling_timeout = False
		if not stop:
			with _State.timeout_lock:
				_arm_timeout(_State.timeout)
			return
		with _State.timeout_lock:
			_State.stopping = True
	with _State.timeout_lock:
		_arm_timeout(STOP_RETRY_INTERVAL)
	raise InterpreterTimeout



def init_interpreter(channel):
	saved_io = (sys.stdout, sys.stderr, sys.stdin)
	try:
		proxy._attach(channel)
		sys.stdout = _ProxyStdOut()
		sys.stderr = _ProxyStdErr()
	#   sys.stdout = io.TextIOWrapper(_ProxyStdOut(), 'utf-8', line_buffering=True)
	#   sys.stderr = io.TextIOWrapper(_ProxyStdErr(), 'utf-8', line_buffering=True)
		sys.stdin = _ProxyStdIn()
		sys.prefix, sys.exec_prefix = proxy.builtin.get_prefixes()
		sys.is_kongalib_interpreter = True
	except Exception as e:
		sys.stdout, sys.stderr, sys.stdin = saved_io
		try:
			proxy.close()
		except:
			pass
		raise BadConnection('Unable to connect the interpreter to the host: %s' % e)
	_State.io.append(saved_io)

	import getpass
	getpass.getpass = proxy.builtin.getpass

	def excepthook(type, value, tb):
		import traceback
		# debug_log('EXCEPTHOOK:\n%s' % '\n'.join(traceback.format_exception(type, value, tb)))
		tb = traceback.extract_tb(tb)
		def do_filter(entry):
			filename = entry[0].replace('\\', '/')
			if filename.endswith('kongalib/scripting.py'):
				return False
			return True
		tb = list(filter(do_filter, tb))
		try:
			proxy.builtin.print_exception(type, value, tb)
		except:
			debug_log('proxy.builtin.print_exception exception:\n%s' % traceback.format_exc())
	sys.excepthook = excepthook

	def close_proxy():
		try:
			proxy.close()
		except:
			pass
	if not _State.atexit_registered:
		_State.atexit_registered = True
		atexit.register(close_proxy)


def exit_interpreter():
	sys.stdout, sys.stderr, sys.stdin = _State.io.pop()


def _current_exc_info():
	import traceback
	exc_type, exc_value, exc_tb = sys.exc_info()
	return ( exc_type, exc_value, [ tuple(tb) for tb in traceback.extract_tb(exc_tb) ] )


def _portable_exc_info(exc_info):
	import traceback
	exc_type, exc_value, exc_tb = exc_info
	try:
		lines = traceback.format_exception_only(exc_type, exc_value)
	except:
		lines = [ '%s\n' % getattr(exc_type, '__name__', 'Exception') ]
	return ( _ScriptException, _ScriptException(lines), list(exc_tb) )


def _send_done(exc_info):
	# Comunica all'host la fine dell'esecuzione; se l'eccezione non può arrivare all'host
	# così com'è, la manda nella forma testuale. Restituisce False se l'host non è
	# raggiungibile.
	done = getattr(proxy.builtin, _SCRIPT_DONE)
	try:
		done(exc_info)
		return True
	except Exception:
		if exc_info is None:
			_logger.error('[Interpreter] unable to notify the end of the script')
			return False
	try:
		done(_portable_exc_info(exc_info))
		return True
	except Exception:
		import traceback
		_logger.error('[Interpreter] unable to notify the end of the script: %s' % traceback.format_exc())
		return False



def _run_job(job, channel):
	"""Esegue lo script descritto da *job* con *channel* per le chiamate all'host, e ne
	notifica la fine; non dipende dal backend. Solleva :class:`BadConnection` se l'host non
	risponde all'avvio, e restituisce False se non è più raggiungibile alla fine."""
	args, path, timeout, script, cwd = job
	sys.argv = args
	sys.path = path
	filename = args[0]
	if cwd:
		os.chdir(cwd)
	init_interpreter(channel)
	with _State.timeout_lock:
		_State.script_thread = threading.get_ident()
		_State.pause_depth = 0
		_State.paused_left = None
		_State.handling_timeout = False
		_State.stopping = False
		_State.running = True
		_State.in_channel = 0
		_State.expiry_pending = False
		_State.armed_at = _State.armed_for = None
	exc_info = None
	try:
		script = compile(script, filename, 'exec', dont_inherit=1)
		set_script_timeout(timeout)
		exec(script, { '__file__': filename, '__name__': '__main__' })
	except SystemExit as e:
		# sys.exit() termina lo script, non l'interprete
		if e.code not in (None, 0):
			exc_info = _current_exc_info()
	except (Exception, InterpreterTimeout):
		exc_info = _current_exc_info()
	with _State.timeout_lock:
		_State.stopping = False
		_State.running = False
	set_script_timeout(0)
	exit_interpreter()
	sent = _send_done(exc_info)
	proxy.close()
	return sent



def _trampoline(conn, foreground, env, dll_paths, queue, level):
	# Punto d'ingresso del processo dell'interprete (backend a processi)
	logging.getLogger().setLevel(level)
	logger = logging.getLogger('script._trampoline')
	handler = logging.handlers.QueueHandler(queue)
	handler.setLevel(level)
	logger.addHandler(handler)
	logger.debug('entering interpreter process')
	try:
		if _set_process_foreground is not None:
			_set_process_foreground(foreground)
		for path in dll_paths:
			try:
				os.add_dll_directory(path)
				logger.debug('added DLL directory: %s' % path)
			except:
				if sys.platform == 'win32':
					logger.error('error adding DLL directory: %s' % path)
		for key, value in (env or {}).items():
			key = str(key)
			value = str(value)
			os.environ[key] = value
			logger.debug('added env variable %s=%s' % (key, value))

		def terminate(signo=None, stack_frame=None):
			raise _Terminate
		signal.signal(signal.SIGTERM, terminate)
		_State.clock = _select_clock()
		logger.debug('timeout clock: %s' % type(_State.clock).__name__)
		if _INTERRUPT_SIGNAL is not None:
			signal.signal(_INTERRUPT_SIGNAL, _on_expiry_signal)
		requests = _queue.Queue()
		threading.Thread(target=_read_control, args=(conn, requests), name='control', daemon=True).start()

		while True:
			request = requests.get()
			if request[0] == 'quit':
				break
			_, job, (conn_type, address) = request
			try:
				sent = _run_job(job, _ConnectionChannel.connect(conn_type, address))
			except BadConnection as e:
				# l'host riproverà, se può, con un'altra famiglia di connessione
				logger.error(str(e))
				conn.send(('bad_connection', str(e)))
				continue
			if not sent:
				break
	except _Terminate:
		logger.debug('terminated by the host')
	except KeyboardInterrupt:
		logger.debug('user issued a keyboard interrupt')
	except Exception:
		import traceback
		logger.critical('unhandled error in interpreter process: %s' % traceback.format_exc())
	finally:
		# il timeout non deve restare armato mentre l'interprete si chiude
		try:
			_State.clock.arm(0)
			set_interpreter_timeout(0)
		except:
			pass
		if conn is not None:
			try:
				conn.close()
			except:
				pass
		logger.debug('exiting interpreter process')
	

# --- interprete nel browser: lato worker (scripting_worker.mjs) -------------------------------

class _Worker:
	"""Stato del Web Worker dell'interprete (lato interprete, nel browser)."""
	# risposte attese dall'host, per id della chiamata
	pending = {}
	next_id = 0
	# l'host ha chiesto di interrompere lo script: si vede al prossimo punto di yield
	interrupt = False
	# sys.path del worker, da tenere oltre a quello dell'host
	path = []


def _worker_post(kind, id, payload=b''):
	import js
	from pyodide.ffi import to_js
	js.postMessage(to_js([ kind, id, to_js(memoryview(payload)) ]))


class _WorkerChannel:
	"""Canale delle chiamate dello script verso l'host nel browser: messaggi del worker, con la
	risposta attesa sospendendo lo stack dello script (``run_sync``)."""
	def call(self, data):
		from pyodide.ffi import run_sync
		_Worker.next_id += 1
		id = _Worker.next_id
		future = asyncio.get_event_loop().create_future()
		_Worker.pending[id] = future
		try:
			_worker_post('call', id, _CALL + data)
			return run_sync(future)
		finally:
			_Worker.pending.pop(id, None)

	def notify(self, data):
		_worker_post('call', 0, _NOTIFY + data)

	def close(self):
		pass


def _worker_setup():
	# Una volta, a worker pronto (Pyodide, i pacchetti e le wheel caricati)
	_State.clock = _select_clock()
	_Worker.path = list(sys.path)


def _worker_message(kind, id, payload):
	# Messaggi dell'host che arrivano anche mentre lo script è sospeso in attesa di una risposta
	if kind == 'reply':
		future = _Worker.pending.get(id)
		if (future is not None) and (not future.done()):
			future.set_result(payload.to_bytes())
	elif kind == 'interrupt':
		_Worker.interrupt = True


def _worker_yield():
	# Punto di yield, chiamato dall'aggancio periodico della trace C: i messaggi dell'host arrivano
	# solo mentre lo script cede il passo; un'interruzione chiesta dall'host vale come la scadenza
	# immediata del timeout, come il segnale simulato su CPython
	from pyodide.ffi import run_sync
	run_sync(asyncio.sleep(0))
	if _Worker.interrupt:
		_Worker.interrupt = False
		_expired(sys._getframe(1))


def _worker_control(payload):
	# Una richiesta di controllo dell'host (run, quit); con callPromising, così lo script può
	# sospendere lo stack
	request = _loads(payload.to_bytes())
	if request[0] != 'run':
		return
	_, job, connection = request
	args, path, timeout, script, cwd = job
	# i percorsi vengono dall'host: si tengono anche quelli del worker, e la cartella di lavoro solo
	# se esiste anche qui (il filesystem del worker è un altro)
	path = list(path) + [ entry for entry in _Worker.path if entry not in path ]
	if cwd and (not os.path.isdir(cwd)):
		cwd = None
	_Worker.interrupt = False
	set_interpreter_yield(_YIELD_INTERVAL, _worker_yield)
	try:
		_run_job((args, path, timeout, script, cwd), _WorkerChannel())
	except BadConnection as e:
		_logger.error(str(e))
		_worker_post('control', 0, _dumps(('bad_connection', str(e))))
	finally:
		set_interpreter_yield(0, None)
		try:
			_State.clock.arm(0)
		except:
			pass



class _ProcessBackend:
	"""Backend dell'interprete per CPython: un processo multiprocessing, con una pipe per i
	messaggi di controllo e una coda per i log; le chiamate dello script arrivano all'host
	tramite :class:`_ServerProxy`."""
	def __init__(self, foreground, env):
		self.foreground = foreground
		self.env = env
		self.process = None
		self.conn = None
		self.queue = multiprocessing.Queue()
		self.logger_listener = logging.handlers.QueueListener(self.queue, *logging.getLogger().handlers, respect_handler_level=True)

	def start(self):
		self.conn, child_conn = multiprocessing.Pipe()
		self.logger_listener.start()
		self.process = multiprocessing.Process(target=_trampoline, args=(child_conn, self.foreground, self.env, _DLL_PATHS, self.queue, logging.getLogger().level), daemon=True)
		self.process.start()
		# l'estremità del figlio resta solo al figlio: se muore, la pipe si chiude
		child_conn.close()
		exitcode = self.process.exitcode
		if exitcode is not None:
			raise RuntimeError('Unable to start interpreter process: exit code %d' % exitcode)

	def send(self, message):
		"""Invia un messaggio di controllo all'interprete."""
		self.conn.send(message)

	def receive(self):
		"""Restituisce il prossimo messaggio di controllo dell'interprete, se ce n'è uno."""
		try:
			return self.conn.recv() if self.conn.poll() else None
		except (EOFError, OSError):
			return None

	def is_alive(self):
		return self.process.is_alive()

	@property
	def exitcode(self):
		return self.process.exitcode

	def terminate(self):
		"""Chiede al processo di terminare (SIGTERM su POSIX, d'autorità su Windows)."""
		try:
			self.process.terminate()
		except:
			pass

	def kill(self):
		"""Termina il processo d'autorità."""
		try:
			self.process.kill()
		except Exception as e:
			debug_log('Interpreter.stop() failed with error: %s' % str(e))

	def join(self, timeout=None):
		self.process.join(timeout)

	def close(self):
		try:
			self.logger_listener.stop()
		except:
			pass



class _WorkerBackend:
	"""Backend dell'interprete nel browser: un Web Worker con la propria Pyodide
	(``scripting_worker.mjs``, da un URL ``blob:``), caricato secondo :data:`WORKER_CONFIG`; i
	messaggi di controllo e le chiamate dello script viaggiano negli stessi messaggi del worker."""
	process = None
	# worker avviati e non ancora terminati, riserve comprese
	live = 0

	def __init__(self, foreground, env):
		self.env = env
		self.worker = None
		self.url = None
		self.proxies = []
		self.messages = collections.deque()
		self.alive = False
		self.exitcode = None
		# il trasporto delle chiamate dell'esecuzione in corso (_WorkerCalls)
		self.calls = None

	def start(self):
		import js
		from pyodide.ffi import create_proxy, to_js
		if not WORKER_CONFIG:
			raise RuntimeError('kongalib.scripting.WORKER_CONFIG is not set: the application must say how to load an interpreter')
		with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripting_worker.mjs'), encoding='utf-8') as f:
			source = f.read()
		def options(value):
			return to_js(value, dict_converter=js.Object.fromEntries)
		self.url = js.URL.createObjectURL(js.Blob.new(to_js([ source ]), options({ 'type': 'text/javascript' })))
		self.worker = js.Worker.new(self.url, options({ 'type': 'module' }))
		on_message = create_proxy(self._on_message)
		on_error = create_proxy(self._on_error)
		self.proxies = [ on_message, on_error ]
		self.worker.onmessage = on_message
		self.worker.onerror = on_error
		self.alive = True
		_WorkerBackend.live += 1
		self._post('init', 0, json.dumps(WORKER_CONFIG).encode('utf-8'))

	def _post(self, kind, id, payload=b''):
		from pyodide.ffi import to_js
		self.worker.postMessage(to_js([ kind, id, to_js(memoryview(payload)) ]))

	def _on_message(self, event):
		data = event.data
		kind, id, payload = str(data[0]), int(data[1]), data[2].to_bytes()
		if kind == 'call':
			calls = self.calls
			if calls is not None:
				calls.feed(id, payload)
		elif kind == 'control':
			self.messages.append(_loads(payload))
		elif kind == 'error':
			self._died(payload.decode('utf-8', 'replace'))

	def _on_error(self, event):
		self._died(str(getattr(event, 'message', '') or 'worker error'))

	def _died(self, message):
		# il worker non può più eseguire nulla: va trattato come un processo terminato
		_logger.error('[Interpreter] worker error: %s' % message)
		if self.alive:
			self.alive = False
			self.exitcode = 1
			_WorkerBackend.live -= 1
			try:
				self.worker.terminate()
			except:
				pass

	def send(self, message):
		"""Invia un messaggio di controllo all'interprete."""
		if not self.alive:
			raise OSError('the interpreter worker is not running')
		if message[0] == 'interrupt':
			# non in coda dietro all'esecuzione in corso, che deve riceverlo
			self._post('interrupt', 0)
		elif message[0] == 'quit':
			# un processo esce da sé; un worker va terminato
			self.terminate()
		else:
			self._post('control', 0, _dumps(message))

	def reply(self, id, data):
		if self.alive:
			self._post('reply', id, data)

	def receive(self):
		"""Restituisce il prossimo messaggio di controllo dell'interprete, se ce n'è uno."""
		return self.messages.popleft() if self.messages else None

	def is_alive(self):
		return self.alive

	def terminate(self):
		"""Termina il worker: nel browser non c'è una richiesta più gentile che lo script possa
		vedere mentre gira."""
		if self.worker is not None:
			try:
				self.worker.terminate()
			except:
				pass
		if self.alive:
			self.alive = False
			_WorkerBackend.live -= 1

	def kill(self):
		self.terminate()

	def join(self, timeout=None):
		pass

	def close(self):
		import js
		if self.url is not None:
			js.URL.revokeObjectURL(self.url)
			self.url = None
		for proxy in self.proxies:
			proxy.destroy()
		self.proxies = []



class _WorkerReserve:
	"""Riserve di interpreti nel browser: worker già avviati (Pyodide e pacchetti caricati, ~1 s) e
	mai usati, da cui un nuovo :class:`Interpreter` parte subito. Il numero si adatta: cresce di uno
	(fino a *maximum*) ogni volta che una richiesta le trova esaurite, come durante una raffica di
	trigger, e torna verso *minimum* dopo :attr:`IDLE` secondi senza richieste. Un worker passa da
	riserva a interprete una volta sola: non torna mai riserva."""
	IDLE = 60
	minimum = 0
	maximum = 0
	target = 0
	ready = collections.deque()
	last_take = 0.0

	@classmethod
	def configure(cls, minimum, maximum):
		cls.minimum = max(0, minimum)
		cls.maximum = max(cls.minimum, maximum)
		cls.target = cls.minimum
		while len(cls.ready) > cls.maximum:
			cls.ready.pop().terminate()
		cls.fill()

	@classmethod
	def take(cls):
		now = time.monotonic()
		if (now - cls.last_take > cls.IDLE) and (cls.target > cls.minimum):
			cls.target -= 1
		cls.last_take = now
		backend = None
		while cls.ready and (backend is None):
			candidate = cls.ready.popleft()
			if candidate.is_alive():
				backend = candidate
			else:
				candidate.close()
		if (backend is None) and (cls.target < cls.maximum):
			cls.target += 1
		cls.fill()
		return backend

	@classmethod
	def fill(cls):
		if not WORKER_CONFIG:
			return
		while len(cls.ready) < cls.target:
			backend = _WorkerBackend(None, None)
			backend.start()
			cls.ready.append(backend)


def set_worker_reserve(minimum=1, maximum=3):
	"""Nel browser: quanti interpreti tenere pronti (vedi :class:`_WorkerReserve`); da chiamare
	dopo aver impostato :data:`WORKER_CONFIG`. Senza effetto altrove."""
	if _WEB:
		_WorkerReserve.configure(minimum, maximum)



class _WorkerCalls:
	"""Trasporto delle chiamate dello script nel browser, al posto di :class:`_ServerProxy`: i
	messaggi ``call`` del worker, eseguiti in ordine da un task sul loop; i metodi degli handler
	girano sul loop (main thread), le coroutine attese."""
	def __init__(self, dispatcher, backend):
		self.dispatcher = dispatcher
		self.backend = backend
		self.queue = asyncio.Queue()
		self.task = None

	def start(self):
		self.backend.calls = self
		self.task = asyncio.get_event_loop().create_task(self._run())

	def feed(self, id, payload):
		self.queue.put_nowait((id, payload))

	async def _run(self):
		while True:
			id, data = await self.queue.get()
			reply = await self.dispatcher.dispatch_async(data)
			if reply is not None:
				self.backend.reply(id, reply)
			self.dispatcher.replied()

	def close(self):
		if self.backend.calls is self:
			self.backend.calls = None
		if self.task is not None:
			self.task.cancel()
			self.task = None

	def stop(self):
		self.close()

	async def stop_async(self):
		self.close()



class Interpreter:
	"""Interprete separato in cui eseguire gli script con :func:`execute`; può essere riusato
	per più esecuzioni."""
	def __init__(self, foreground=True, env=None):
		self.backend = None
		self.started = False
		self.exc_info = None
		self.lock = threading.RLock()
		self.foreground = foreground
		self.env = env

	@property
	def proc(self):
		"""Il processo dell'interprete, o None se non è avviato."""
		backend = self.backend
		return backend.process if backend is not None else None

	def __del__(self):
		backend = self.backend
		if backend is not None:
			if backend.is_alive():
				try:
					backend.send(('quit',))
				except:
					pass
			backend.close()

	def ensure_proc(self):
		with self.lock:
			if self.backend is None:
				backend = None
				if _WEB:
					backend = _WorkerReserve.take()
				if backend is None:
					backend = (_WorkerBackend if _WEB else _ProcessBackend)(self.foreground, self.env)
					backend.start()
				self.backend = backend
				self.started = True

	def execute(self, script=None, filename=None, argv=None, path=None, timeout=None, run=None, connection=None):
		"""Esegue lo script e ne attende la fine; restituisce un :class:`ExecutionResult`.
		*connection* è la coppia ``(famiglia, indirizzo)`` del listener a cui l'interprete si
		collega per chiamare l'host durante l'esecuzione. Solleva :class:`BadConnection` se
		l'interprete non riesce a collegarsi."""
		if _WEB:
			# nel browser l'attesa sospende lo stack (run_sync) mentre il loop prosegue
			from pyodide.ffi import run_sync
			return run_sync(self.execute_async(script, filename, argv, path, timeout, run, connection))
		if run is None:
			run = _Run()
		backend = self._start_run(script, filename, argv, path, timeout, connection)
		state = {}
		while True:
			result = self._check(backend, run, state)
			if result is not None:
				break
			run.finished.wait(0.05)
		with self.lock:
			self.exc_info = result.exc_info
		return result

	async def execute_async(self, script=None, filename=None, argv=None, path=None, timeout=None, run=None, connection=None):
		"""Come :meth:`execute`, ma attende la fine dell'esecuzione senza bloccare il loop
		corrente."""
		if run is None:
			run = _Run(asyncio.get_running_loop())
		backend = self._start_run(script, filename, argv, path, timeout, connection)
		state = {}
		while True:
			result = self._check(backend, run, state)
			if result is not None:
				break
			await run.wait_async(0.05)
		with self.lock:
			self.exc_info = result.exc_info
		return result

	def _start_run(self, script, filename, argv, path, timeout, connection):
		with self.lock:
			self.ensure_proc()
			backend = self.backend
			self.exc_info = None
			args = argv
			if not args:
				args = [ filename or '<script>' ]
			if (script is None) and filename:
				with open(filename, 'r') as f:
					script = f.read()
			try:
				cwd = os.path.dirname(os.path.abspath(filename))
			except:
				cwd = None
			job = (args, path, timeout, script or '', cwd)
			backend.send(('run', job, connection or (None, None)))
			return backend

	def _check(self, backend, run, state):
		# Un passo dell'attesa della fine di un'esecuzione: restituisce l'esito se è finita,
		# altrimenti None. *state* è conservato tra un passo e l'altro.
		if run.finished.is_set():
			exc_info = run.exc_info
			if exc_info is None:
				return ExecutionResult(ExecutionResult.COMPLETED)
			if exc_info[0] is InterpreterTimeout:
				return ExecutionResult(ExecutionResult.TIMEOUT, exc_info)
			return ExecutionResult(ExecutionResult.FAILED, exc_info)
		message = backend.receive()
		if (message is not None) and (message[0] == 'bad_connection'):
			raise BadConnection(message[1])
		with self.lock:
			stopped = self.backend is not backend
		if stopped:
			return ExecutionResult(ExecutionResult.TERMINATED)
		if not backend.is_alive():
			# la notifica della fine dell'esecuzione potrebbe essere ancora in viaggio
			now = time.monotonic()
			dead_since = state.setdefault('dead_since', now)
			if now - dead_since > 0.5:
				return ExecutionResult(ExecutionResult.CRASHED, exitcode=backend.exitcode)
		return None

	def stop(self):
		"""Arresta l'interprete: prima con una richiesta, poi d'autorità dopo 3 secondi."""
		with self.lock:
			backend, self.backend = self.backend, None
		if backend is not None:
			backend.terminate()
			backend.join(3)
			if backend.is_alive():
				backend.kill()
				backend.join(3)
			backend.close()

	async def stop_async(self):
		"""Come :meth:`stop`, senza bloccare il loop corrente."""
		with self.lock:
			backend, self.backend = self.backend, None
		if backend is not None:
			backend.terminate()
			if not await self._wait_exit(backend, 3):
				backend.kill()
				await self._wait_exit(backend, 3)
			backend.close()

	@staticmethod
	async def _wait_exit(backend, timeout):
		deadline = time.monotonic() + timeout
		while backend.is_alive():
			if time.monotonic() > deadline:
				return False
			await asyncio.sleep(0.05)
		return True

	def interrupt(self):
		"""Chiede all'interprete di interrompere al più presto lo script in esecuzione, come
		se ne fosse scaduto il timeout: l'handler ``builtin`` riceve ``handle_timeout()`` e
		lo script viene fermato se questo restituisce True. Senza effetto se nessuno script
		è in esecuzione."""
		with self.lock:
			backend = self.backend
			if (backend is None) or (not backend.is_alive()):
				return
			try:
				backend.send(('interrupt',))
			except (OSError, EOFError):
				pass

	def is_running(self):
		backend = self.backend
		return (not self.started) or ((backend is not None) and backend.is_alive())

	def get_exc_info(self):
		with self.lock:
			return self.exc_info


class _ProxyStdIn(io.StringIO):
	def readline(self, size=-1):
		return proxy.builtin.read_line()


class _ProxyStdOut(io.StringIO):
	def write(self, text):
		proxy.builtin.write_stdout.notify(str(text))
		return len(text)

	def flush(self):
		try:
			proxy.builtin.flush_stdout.notify()
		except:
			pass


class _ProxyStdErr(io.StringIO):
	def write(self, text):
		if sys.__stderr__ is not None:
			sys.__stderr__.write(str(text))
		try:
			proxy.builtin.write_stderr.notify(str(text))
		except:
			pass
		return len(text)

	def flush(self):
		try:
			proxy.builtin.flush_stderr.notify()
		except:
			pass



class _MethodHandler:
	def __init__(self, proxy, name):
		self._proxy = proxy
		self._name = name

	def __getattr__(self, name):
		return _Method(self, name)



class _Method:
	def __init__(self, handler, name):
		self.handler = handler
		self.name = name

	def _encode(self, args, kwargs):
		return _dumps((self.handler._name, self.name, args, kwargs))

	def __call__(self, *args, **kwargs):
		data = self._encode(args, kwargs)
		proxy = self.handler._proxy
		with _ChannelUse():
			with proxy._lock:
				if DEBUG:
					s = time.time()
					debug_log('[Proxy] call: %s' % str((self.handler._name, self.name, args, kwargs)))
				reply = proxy._channel.call(data)
				if DEBUG:
					debug_log('[Proxy] got reply in %f secs: %s' % (time.time() - s, str((self.handler._name, self.name))))
		e, result = _loads(reply)
		if e is None:
			return result
		errmsg, errno = e
		if errno is None:
			raise RuntimeError(errmsg)
		else:
			raise Error(errno, errmsg)

	def notify(self, *args, **kwargs):
		"""Chiama il metodo sull'host senza attenderne la fine: eventuali errori vengono solo
		registrati dall'host. Chiamate e notifiche arrivano all'host nell'ordine in cui sono
		fatte."""
		data = self._encode(args, kwargs)
		proxy = self.handler._proxy
		with _ChannelUse():
			with proxy._lock.lock:
				proxy._channel.notify(data)



class _ChannelUse:
	# Segna che il thread dello script sta comunicando con l'host (vedi _expired())
	def __enter__(self):
		self.counted = threading.get_ident() == _State.script_thread
		if self.counted:
			_State.in_channel += 1
	def __exit__(self, exc_type, exc_value, exc_traceback):
		if self.counted:
			_State.in_channel -= 1
			if (_State.in_channel == 0) and _State.expiry_pending:
				_expired(None)



class _StopWatchdog:
	"""Arresta d'autorità l'interprete se lo script non gestisce entro STOP_GRACE secondi
	l'interruzione chiesta dall'utente allo scadere del timeout."""
	def __init__(self, interpreter):
		self.interpreter = interpreter
		self.lock = threading.Lock()
		self.timer = None
		self.fired = False

	def start(self):
		with self.lock:
			if self.timer is None:
				if _WEB:
					# nel browser niente thread: un timer del loop
					self.timer = asyncio.get_event_loop().call_later(STOP_GRACE, self._fire)
				else:
					self.timer = threading.Timer(STOP_GRACE, self._fire)
					self.timer.daemon = True
					self.timer.start()

	def cancel(self):
		with self.lock:
			if self.timer is not None:
				self.timer.cancel()
				self.timer = None

	def _fire(self):
		with self.lock:
			if self.timer is None:
				return
			self.timer = None
			self.fired = True
		debug_log("[ServerProxy] script did not handle the stop request: stopping interpreter")
		self.interpreter.stop()



class _Run:
	"""Un'esecuzione in corso: l'interprete ne notifica la fine con il suo esito. Con *loop*
	la fine si può anche attendere da una coroutine su quel loop."""
	def __init__(self, loop=None):
		self.finished = threading.Event()
		self.exc_info = None
		self.loop = loop
		self.async_finished = asyncio.Event() if loop is not None else None

	def set_done(self, exc_info):
		self.exc_info = exc_info
		self.finished.set()
		if self.loop is not None:
			try:
				self.loop.call_soon_threadsafe(self.async_finished.set)
			except RuntimeError:
				# il loop è già chiuso
				pass

	async def wait_async(self, timeout):
		try:
			await asyncio.wait_for(self.async_finished.wait(), timeout)
		except asyncio.TimeoutError:
			pass



class _CallDispatcher:
	"""Esegue sugli handler dell'host le chiamate dello script durante un'esecuzione; non
	dipende dal trasporto, che gli passa i messaggi ricevuti e invia le risposte."""
	def __init__(self, handlers, loop=None, watchdog=None, run=None):
		self.handlers = handlers
		self.loop = loop
		self.watchdog = watchdog
		self.run = run
		self.done = False
		self.done_exc_info = None

	def dispatch(self, data):
		"""Esegue la chiamata nel messaggio *data*; restituisce la risposta da inviare
		all'interprete, o None se il messaggio è una notifica."""
		kind, call, error = self._decode(data)
		if call is None:
			return error
		handler, name, func, args, kwargs = call
		try:
			if func is None:
				raise RuntimeError('Method "%s" unavailable in this context' % name)
			result = func(*args, **kwargs)
			if asyncio.iscoroutine(result):
				result = _run_coroutine(result, self.loop)
		except (Exception, InterpreterTimeout) as e:
			return self._failed(kind, e)
		return self._done(kind, handler, name, result)

	async def dispatch_async(self, data):
		"""Come :meth:`dispatch`, sul loop: le coroutine degli handler sono attese (backend Web
		Worker, dove tutto gira sul loop)."""
		kind, call, error = self._decode(data)
		if call is None:
			return error
		handler, name, func, args, kwargs = call
		try:
			if func is None:
				raise RuntimeError('Method "%s" unavailable in this context' % name)
			result = func(*args, **kwargs)
			if inspect.isawaitable(result):
				result = await result
		except (Exception, InterpreterTimeout) as e:
			return self._failed(kind, e)
		return self._done(kind, handler, name, result)

	def _decode(self, data):
		# (tipo, (handler, nome, funzione, args, kwargs), None), o (tipo, None, risposta d'errore)
		kind, payload = data[:1], data[1:]
		try:
			handler, name, args, kwargs = _loads(payload)
		except Exception as e:
			# es. un argomento di una classe che solo lo script può importare
			_logger.error("[ServerProxy] unable to decode the call from the script: %s" % e)
			return kind, None, self._reply(kind, (('Unable to decode the call from the script: %s' % e, None), None))
		return kind, (handler, name, self._lookup(handler, name), args, kwargs), None

	def _done(self, kind, handler, name, result):
		if (handler == 'builtin') and (name == 'handle_timeout') and result and (self.watchdog is not None):
			self.watchdog.start()
		return self._reply(kind, (None, result))

	def _failed(self, kind, e):
		import traceback
		_logger.error("[ServerProxy] method error: %s" % traceback.format_exc())
		if isinstance(e, Error):
			errno = e.errno
		else:
			errno = None
		return self._reply(kind, ((str(e), errno), None))

	def replied(self):
		"""Da chiamare dopo aver inviato all'interprete la risposta dell'ultima chiamata."""
		# la fine dell'esecuzione si notifica solo dopo aver risposto all'interprete:
		# chiudendo prima la connessione, lui la crederebbe persa
		if self.done and (self.run is not None):
			self.done = False
			self.run.set_done(self.done_exc_info)

	def close(self):
		self.handlers = {}

	def _lookup(self, handler, name):
		if handler == 'builtin':
			if name == _STOP_HANDLED:
				return self._stop_handled
			if name == _SCRIPT_DONE:
				return self._script_done
		if handler in self.handlers:
			return getattr(self.handlers[handler], name, None)
		return None

	def _reply(self, kind, reply):
		if kind == _NOTIFY:
			return None
		try:
			return _dumps(reply)
		except Exception as e:
			# il risultato non è serializzabile: lo script riceve un errore al suo posto
			_logger.error("[ServerProxy] unable to send the result to the script: %s" % e)
			return _dumps((('Unable to send the result to the script: %s' % e, None), None))

	def _stop_handled(self):
		if self.watchdog is not None:
			self.watchdog.cancel()

	def _script_done(self, exc_info):
		self.done_exc_info = exc_info
		self.done = True



class _ServerProxy(threading.Thread):
	"""Trasporto delle chiamate dello script per il backend a processi: un listener a cui
	l'interprete si collega per un'esecuzione, servito da questo thread."""
	# Quanto attendere il thread alla fine dell'esecuzione: può essere fermo su un handler
	# dell'host che non ritorna (es. una finestra lasciata aperta)
	STOP_TIMEOUT = 5

	def __init__(self, dispatcher):
		self.dispatcher = dispatcher
		self.listener = None
		self.conn = None
		super().__init__(daemon=True)

	def start(self):
		if gConnFamilyOverride:
			family = None
		else:
			family = gConnFamily
		try:
			self.listener = multiprocessing.connection.Listener(family=family)
		except:
			raise BadConnection()
		super().start()

	def close(self):
		"""Chiude il listener e la connessione; il thread esce appena possibile."""
		if self.listener is not None:
			self.listener.close()
			self.listener = None
		if self.conn is not None:
			self.conn.close()

	def stop(self):
		self.close()
		if self.is_alive():
			self.join(self.STOP_TIMEOUT)

	async def stop_async(self):
		# il thread potrebbe attendere una coroutine di un handler, che gira sul loop: non
		# va atteso bloccando il loop
		self.close()
		deadline = time.monotonic() + self.STOP_TIMEOUT
		while self.is_alive() and (time.monotonic() < deadline):
			await asyncio.sleep(0.01)

	def run(self):
		debug_log("[ServerProxy] run")
		try:
			self.conn = self.listener.accept()
			debug_log("[ServerProxy] got proxy")
			while True:
				ready = multiprocessing.connection.wait([ self.conn ], 0.5)
				if ready:
					reply = self.dispatcher.dispatch(self.conn.recv_bytes())
					if reply is not None:
						self.conn.send_bytes(reply)
					self.dispatcher.replied()
		except IOError:
			if self.listener is not None:
				import traceback
				debug_log("[ServerProxy] IOError: %s" % traceback.format_exc())
		except EOFError:
			pass
		finally:
			debug_log("[ServerProxy] exiting")


class BuiltinHandler:
	def __init__(self):
		self.__interpreter = None
		self.__exit_funcs = []
	
	def _set_interpreter(self, interpreter):
		self.__interpreter = interpreter
	
	def _get_interpreter(self):
		return self.__interpreter
	
	def write_stdout(self, text):
		sys.__stdout__.write(text)
	
	def write_stderr(self, text):
		sys.__stderr__.write(text)

	def flush_stdout(self):
		pass

	def flush_stderr(self):
		pass
	
	def read_line(self):
		sys.__stdin__.readline()

	def getpass(self, prompt='Password: ', stream=None):
		import getpass
		return getpass.getpass(prompt, stream)
	
	def get_prefixes(self):
		return os.getcwd(), os.getcwd()
	
	def format_exception(self, type, value, tb):
		import traceback
		if not all([ isinstance(x, str) for x in tb ]):
			tb = traceback.format_list(tb)
		if isinstance(value, _ScriptException):
			last = value.lines
		else:
			last = traceback.format_exception_only(type, value)
		if tb:
			text = [ 'Traceback (most recent call last):\n' ] + tb + last
		else:
			text = last
		return ''.join(text)
	
	def print_exception(self, type, value, tb):
		"""Riporta un'eccezione dello script; nelle sottoclassi può essere una coroutine."""
		print(self.format_exception(type, value, tb))
	
	def handle_timeout(self):
		"""Chiamata allo scadere del timeout dello script, che resta fermo fino al ritorno:
		True ne chiede l'interruzione, False lo lascia continuare per un altro timeout."""
		return True
	
	def noop(self):
		pass

	def atexit(self, func, *args, **kwargs):
		self.__exit_funcs.append((func, args, kwargs))
	
	def _atexit(self):
		while self.__exit_funcs:
			func, args, kwargs = self.__exit_funcs.pop()
			func(*args, **kwargs)

	async def _atexit_async(self):
		# come _atexit(), ma sul loop: le funzioni che restituiscono una coroutine vengono attese
		while self.__exit_funcs:
			func, args, kwargs = self.__exit_funcs.pop()
			result = func(*args, **kwargs)
			if inspect.isawaitable(result):
				await result


def set_connection_family(family):
	global gConnFamily
	gConnFamily = family


def add_dll_directory(path):
	if path not in _DLL_PATHS:
		_DLL_PATHS.append(path)


class _Execution:
	"""Preparazione, esito e chiusura di un'esecuzione, comuni a :func:`execute` e
	:func:`execute_async`."""
	def __init__(self, script, filename, argv, path, timeout, handlers, interpreter, loop, run):
		if (script is None) and (filename is None):
			raise ValueError('Either script or filename must be specified')
		if filename is None:
			filename = '<script>'
		if argv is None:
			argv = [ filename ]
		# un interprete creato per questa esecuzione: nel browser si termina alla fine (il suo worker
		# altrimenti resterebbe in vita finché il garbage collector non raccoglie l'Interpreter)
		self.owned = interpreter is None
		if interpreter is None:
			interpreter = Interpreter()
		self.args = (script, filename, argv, path or [], timeout)
		self.interpreter = interpreter
		self.handlers = { 'builtin': BuiltinHandler() }
		self.handlers.update(handlers or {})
		self.builtin = self.handlers['builtin']
		self.builtin._set_interpreter(interpreter)
		self.run = run
		self.loop = loop
		self.watchdog = _StopWatchdog(interpreter)
		self.dispatcher = _CallDispatcher(self.handlers, loop, self.watchdog, run)
		# print_exception() dell'handler builtin può essere una coroutine
		self.pending = []

	def start_server(self):
		"""Avvia il listener a cui l'interprete si collegherà per questa esecuzione;
		restituisce il server e la coppia ``(famiglia, indirizzo)`` da passare all'interprete."""
		if _WEB:
			# nel browser le chiamate viaggiano nei messaggi del worker dell'interprete
			self.interpreter.ensure_proc()
			server = _WorkerCalls(self.dispatcher, self.interpreter.backend)
			server.start()
			return server, ('worker', None)
		server = _ServerProxy(self.dispatcher)
		server.start()
		address = server.listener.address
		debug_log("[ServerProxy] listener address is: %s" % repr(address))
		return server, (multiprocessing.connection.address_type(address), address)

	def finished(self, result):
		if self.watchdog.fired:
			result = ExecutionResult(ExecutionResult.TIMEOUT, (InterpreterTimeout, InterpreterTimeout(), []))
		elif result.status == ExecutionResult.CRASHED:
			error = RuntimeError('The interpreter process exited unexpectedly (exit code %s)' % result.exitcode)
			result.exc_info = (RuntimeError, error, [])
		if result.exc_info is not None:
			self.report(result.exc_info)
		return result

	def failed(self, e):
		"""Gestisce un errore dell'esecuzione: restituisce None se va ritentata, altrimenti
		l'esito."""
		global gConnFamilyOverride
		import traceback
		# se la famiglia di connessione scelta non funziona (es. bloccata da un antivirus) si
		# ripiega una volta per tutte su quella predefinita
		if getattr(e, '_bad_connection', False) and (not gConnFamilyOverride) and (gConnFamily is not None):
			debug_log("[ServerProxy] bad connection (%s), trying default connection family" % e)
			gConnFamilyOverride = True
			set_connection_family(None)
			return None
		debug_log("[ServerProxy] unhandled execute exception: %s" % traceback.format_exc())
		type, value, tb = sys.exc_info()
		result = ExecutionResult(ExecutionResult.FAILED, (type, value, [ tuple(entry) for entry in traceback.extract_tb(tb) ]))
		self.report(result.exc_info)
		return result

	def report(self, exc_info):
		import traceback
		type, value, tb = exc_info
		def do_filter(entry):
			filename = entry[0].replace('\\', '/')
			if filename.endswith('kongalib/scripting.py') or filename.endswith('__script_host__.py'):
				return False
			return True
		tb = list(filter(do_filter, tb))
		try:
			result = self.builtin.print_exception(type, value, tb)
			if inspect.isawaitable(result):
				self.pending.append(result)
		except:
			debug_log('proxy.builtin.print_exception exception:\n%s' % traceback.format_exc())

	def complete(self):
		# porta a termine le segnalazioni restituite come coroutine
		import traceback
		pending, self.pending = self.pending, []
		for coro in pending:
			try:
				_run_coroutine(coro, self.loop)
			except:
				debug_log('proxy.builtin.print_exception exception:\n%s' % traceback.format_exc())

	async def complete_async(self):
		import traceback
		pending, self.pending = self.pending, []
		for coro in pending:
			try:
				await coro
			except:
				debug_log('proxy.builtin.print_exception exception:\n%s' % traceback.format_exc())

	def close(self):
		self.watchdog.cancel()
		self.dispatcher.close()
		self.builtin._set_interpreter(None)



def execute(script=None, filename=None, argv=None, path=None, timeout=0, handlers=None, interpreter=None, loop=None):
	"""Esegue uno script in un interprete separato e ne attende la fine; le eccezioni dello
	script vengono riportate tramite ``print_exception()`` dell'handler ``builtin``.
	Restituisce un :class:`ExecutionResult`. I metodi degli handler vengono eseguiti in un
	thread dedicato; quelli che restituiscono una coroutine, sul loop *loop* (predefinito:
	quello in esecuzione nel thread chiamante, se c'è)."""
	if _WEB:
		# nel browser l'attesa sospende lo stack (run_sync) mentre il loop prosegue
		from pyodide.ffi import run_sync
		return run_sync(execute_async(script, filename, argv, path, timeout, handlers, interpreter))
	if loop is None:
		try:
			loop = asyncio.get_running_loop()
		except RuntimeError:
			pass
	ex = _Execution(script, filename, argv, path, timeout, handlers, interpreter, loop, _Run())
	result = None
	try:
		while True:
			server = None
			try:
				server, connection = ex.start_server()
				result = ex.finished(ex.interpreter.execute(*ex.args, run=ex.run, connection=connection))
			except Exception as e:
				result = ex.failed(e)
				if result is None:
					continue
			finally:
				if server is not None:
					server.stop()
			break
	finally:
		ex.complete()
		ex.close()
		ex.builtin._atexit()
		debug_log("[ServerProxy] done")
	return result



async def execute_async(script=None, filename=None, argv=None, path=None, timeout=0, handlers=None, interpreter=None):
	"""Come :func:`execute`, ma attende la fine dello script senza bloccare il loop corrente,
	su cui vengono eseguiti i metodi degli handler che restituiscono una coroutine e le
	funzioni registrate con ``atexit()`` dell'handler ``builtin`` (attese, se restituiscono
	una coroutine)."""
	loop = asyncio.get_running_loop()
	ex = _Execution(script, filename, argv, path, timeout, handlers, interpreter, loop, _Run(loop))
	result = None
	try:
		while True:
			server = None
			try:
				server, connection = ex.start_server()
				result = ex.finished(await ex.interpreter.execute_async(*ex.args, run=ex.run, connection=connection))
			except Exception as e:
				result = ex.failed(e)
				if result is None:
					continue
			finally:
				if server is not None:
					await server.stop_async()
			break
	finally:
		await ex.complete_async()
		ex.close()
		await ex.builtin._atexit_async()
		if _WEB and ex.owned:
			await ex.interpreter.stop_async()
		debug_log("[ServerProxy] done")
	return result
