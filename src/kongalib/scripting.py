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
from _kongalib import get_application_log_path, set_interpreter_timeout, get_interpreter_timeout, get_interpreter_time_left, _set_process_foreground

import sys
import os
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
_THIS_FILE = __file__
# Segnale simulato (mai inviato dal sistema operativo) con cui il thread di controllo
# dell'interprete fa eseguire al thread dello script la richiesta di interruzione dell'host
_INTERRUPT_SIGNAL = getattr(signal, 'SIGUSR1', None) or getattr(signal, 'SIGBREAK', None)


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


class _State:
	handler = None
	io = []
	atexit_registered = False
	# Il timeout è controllato dalla trace C, che è installata per thread: solo il thread
	# che esegue lo script lo arma, lo sospende e lo ripristina. None fuori da un
	# interprete di scripting, dove agisce il thread chiamante.
	script_thread = None
	timeout_lock = threading.RLock()
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


proxy = Proxy()
_logger = logging.getLogger("script")


def _on_script_thread():
	return _State.script_thread in (None, threading.get_ident())


def _arm_timeout(timeout):
	# da chiamare con _State.timeout_lock acquisito
	if _State.pause_depth > 0:
		_State.paused_left = timeout or None
	elif _on_script_thread():
		set_interpreter_timeout(timeout or 0)


def _time_left():
	# da chiamare con _State.timeout_lock acquisito
	if _State.pause_depth > 0:
		return _State.paused_left
	if get_interpreter_timeout() is None:
		return None
	# un timeout scaduto ma non ancora rilevato dalla trace va comunque riarmato
	return max(get_interpreter_time_left() or 0, 1)


def _pause_timeout():
	with _State.timeout_lock:
		if not _on_script_thread():
			return
		if _State.pause_depth == 0:
			left = None
			if not _State.handling_timeout:
				try:
					left = _time_left()
				except:
					pass
			try:
				set_interpreter_timeout(0)
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
			if left:
				try:
					set_interpreter_timeout(left)
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


def _interrupt_script(signo=None, stack_frame=None):
	# Eseguita sul thread dello script alla richiesta di interruzione dell'host: fa scadere
	# subito il timeout, così lo script viene fermato come allo scadere del timeout
	with _State.timeout_lock:
		if _State.running:
			_arm_timeout(1)


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
	# Chiamata dalla trace C a timeout scaduto, con la trace già rimossa; il timeout resta
	# quello che viene armato qui. La domanda all'host tiene lo script fermo finché
	# l'utente non risponde.
	if sys._getframe(1).f_code.co_filename == _THIS_FILE:
		# mai interrompere il codice di questo modulo (es. a metà di una chiamata
		# all'host): il controllo si ripete appena torna a girare lo script
		with _State.timeout_lock:
			_arm_timeout(_DEFER_INTERVAL)
		return
	with _State.timeout_lock:
		stopping = _State.stopping
		_State.handling_timeout = not stopping
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
	# proxy.close()


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
		if _INTERRUPT_SIGNAL is not None:
			signal.signal(_INTERRUPT_SIGNAL, _interrupt_script)
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
	except Exception as e:
		import traceback
		logger.critical('unhandled error in interpreter process: %s' % traceback.format_exc())
	finally:
		if conn is not None:
			try:
				conn.close()
			except:
				pass
		logger.debug('exiting interpreter process')
	

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
				backend = _ProcessBackend(self.foreground, self.env)
				backend.start()
				self.backend = backend
				self.started = True

	def execute(self, script=None, filename=None, argv=None, path=None, timeout=None, run=None, connection=None):
		"""Esegue lo script e ne attende la fine; restituisce un :class:`ExecutionResult`.
		*connection* è la coppia ``(famiglia, indirizzo)`` del listener a cui l'interprete si
		collega per chiamare l'host durante l'esecuzione. Solleva :class:`BadConnection` se
		l'interprete non riesce a collegarsi."""
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
		with proxy._lock.lock:
			proxy._channel.notify(data)



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
		kind, payload = data[:1], data[1:]
		try:
			handler, name, args, kwargs = _loads(payload)
		except Exception as e:
			# es. un argomento di una classe che solo lo script può importare
			_logger.error("[ServerProxy] unable to decode the call from the script: %s" % e)
			return self._reply(kind, (('Unable to decode the call from the script: %s' % e, None), None))
		func = self._lookup(handler, name)
		try:
			if func is None:
				raise RuntimeError('Method "%s" unavailable in this context' % name)
			result = func(*args, **kwargs)
			if asyncio.iscoroutine(result):
				if self.loop is None:
					result = asyncio.run(result)
				else:
					result = asyncio.run_coroutine_threadsafe(result, self.loop).result()
			if (handler == 'builtin') and (name == 'handle_timeout') and result and (self.watchdog is not None):
				self.watchdog.start()
		except (Exception, InterpreterTimeout) as e:
			import traceback
			_logger.error("[ServerProxy] method error: %s" % traceback.format_exc())
			if isinstance(e, Error):
				errno = e.errno
			else:
				errno = None
			return self._reply(kind, ((str(e), errno), None))
		return self._reply(kind, (None, result))

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
	def __init__(self, dispatcher):
		self.dispatcher = dispatcher
		self.listener = None
		self.conn = None
		super().__init__()

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

	def stop(self):
		if self.listener is not None:
			self.listener.close()
			self.listener = None
		if self.conn is not None:
			self.conn.close()
		if self.is_alive():
			self.join()

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
		if interpreter is None:
			interpreter = Interpreter()
		self.args = (script, filename, argv, path or [], timeout)
		self.interpreter = interpreter
		self.handlers = { 'builtin': BuiltinHandler() }
		self.handlers.update(handlers or {})
		self.builtin = self.handlers['builtin']
		self.builtin._set_interpreter(interpreter)
		self.run = run
		self.watchdog = _StopWatchdog(interpreter)
		self.dispatcher = _CallDispatcher(self.handlers, loop, self.watchdog, run)

	def start_server(self):
		"""Avvia il listener a cui l'interprete si collegherà per questa esecuzione;
		restituisce il server e la coppia ``(famiglia, indirizzo)`` da passare all'interprete."""
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
			self.builtin.print_exception(type, value, tb)
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
					server.stop()
			break
	finally:
		ex.close()
		await ex.builtin._atexit_async()
		debug_log("[ServerProxy] done")
	return result
