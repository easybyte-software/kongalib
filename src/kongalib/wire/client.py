# -*- coding: utf-8 -*-
#	 _                           _ _ _
#	| |                         | (_) |
#	| | _____  _ __   __ _  __ _| |_| |__
#	| |/ / _ \| '_ \ / _` |/ _` | | | '_ \
#	|   < (_) | | | | (_| | (_| | | | |_) |
#	|_|\_\___/|_| |_|\__, |\__,_|_|_|_.__/
#	                  __/ |
#	                 |___/
#
#	Konga client library, by EasyByte Software
#
#	https://github.com/easybyte-software/kongalib

"""Implementazione di :class:`kongalib.Client` sul trasporto scritto in Python: stessa API di
:class:`_kongalib.Client` (argomenti posizionali, modalità sincrona e a callback,
:class:`Deferred`), sopra una :class:`~kongalib.wire.session.Session`.

La sessione vive su un solo loop asyncio: quello dell'applicazione se il client è usato da
:class:`kongalib.AsyncClient`, altrimenti un loop in un thread di servizio del processo. Le
chiamate sincrone attendono il risultato da un altro thread (non dal thread di quel loop, che
resterebbe bloccato); le callback girano in thread di un executor, come quelle del client nativo
nei thread del dispatcher, così possono anche fare chiamate sincrone sullo stesso client.

Nel browser (Pyodide con JSPI) non ci sono thread: la sessione usa il loop di Pyodide, le chiamate
sincrone sospendono lo stack di Python con ``pyodide.ffi.run_sync`` e le callback girano sul loop.

Come nel client nativo, in modalità sincrona i metodi di comodo (tutti tranne ``connect`` ed
``execute``) ignorano *timeout* e *progress* e riportano il solo messaggio generico dell'errore
(``query_database`` anche quello del server).
"""

import asyncio
import concurrent.futures
import inspect
import os
import sys
import threading
import traceback

from _kongalib import _error_message
from kongalib import Error
from kongalib.async_backend import SUCCESS_VALUES
from kongalib.wire import protocol as P
from kongalib.wire.session import Session


# Con i thread (CPython) la sessione gira sempre sul loop del thread di servizio: il loop di
# un'applicazione può non gestire i socket (quello di slew sul backend Qt è un SelectorEventLoop
# che gira sul ciclo di Qt, e il suo selector non viene mai interrogato). Senza thread (Pyodide)
# gira sul loop di chi la usa, con un flusso che non passa dai socket di asyncio (WebSocket).
# KONGALIB_WIRE_THREADS=0 forza il comportamento senza thread anche su CPython, per provarlo.
THREADS = (sys.platform != 'emscripten') and (os.environ.get('KONGALIB_WIRE_THREADS') != '0')
# Nel browser (Pyodide, solo con JSPI): un solo loop, quello di Pyodide, e la modalità sincrona con
# pyodide.ffi.run_sync, che sospende lo stack di Python mentre il loop del browser prosegue
WEB = sys.platform == 'emscripten'

# Timeout dei metodi di comodo in modalità sincrona (MGA_DEFAULT_EXECUTE_TIMEOUT)
SYNC_TIMEOUT = 10000

_CALLBACKS = ('success', 'error', 'progress', 'userdata')

# Parametri di ciascun metodo, nell'ordine di _kongalib.Client (client.cpp): (nome, default);
# REQUIRED se obbligatorio
REQUIRED = object()
_SIGNATURES = {
	'list_servers': [ ('timeout', 5000), ('port', 0), ('success', None), ('error', None), ('progress', None), ('userdata', None) ],
	'connect': [ ('server', None), ('host', None), ('port', 0), ('options', None), ('timeout', 30000), ('success', None), ('error', None), ('progress', None), ('userdata', None) ],
	'execute': [ ('command', REQUIRED), ('data', None), ('timeout', SYNC_TIMEOUT), ('success', None), ('error', None), ('progress', None), ('idle', None), ('userdata', None) ],
	'get_data_dictionary': [],
	'list_drivers': [ ('configured', True) ],
	'list_databases': [ ('driver', None), ('quick', True) ],
	'create_database': [ ('password', REQUIRED), ('driver', REQUIRED), ('name', REQUIRED), ('desc', '') ],
	'open_database': [ ('driver', REQUIRED), ('name', REQUIRED) ],
	'close_database': [ ('backup', False) ],
	'upgrade_database': [ ('password', REQUIRED), ('driver', REQUIRED), ('name', REQUIRED) ],
	'delete_database': [ ('password', REQUIRED), ('driver', REQUIRED), ('name', REQUIRED), ('delete_cloud_data', None) ],
	'query_database': [ ('query', REQUIRED), ('native', False), ('full_column_names', False), ('collapse_blobs', False) ],
	'backup_database': [ ('password', REQUIRED), ('backupName', REQUIRED), ('driver', ''), ('name', ''), ('auto', True), ('overwrite', False), ('position', 0), ('storeindex', False) ],
	'restore_database': [ ('password', REQUIRED), ('backupName', REQUIRED), ('driver', ''), ('name', ''), ('changeUUID', 1), ('overWrite', 0), ('position', 0), ('restoreindex', 1) ],
	'list_backups': [ ('position', 0) ],
	'delete_backup': [ ('password', REQUIRED), ('backupName', REQUIRED), ('position', REQUIRED) ],
	'optimize_database': [ ('password', REQUIRED), ('driver', ''), ('name', '') ],
	'repair_database': [ ('password', REQUIRED), ('driver', ''), ('name', ''), ('output', '') ],
	'index_database': [ ('password', REQUIRED), ('driver', ''), ('name', ''), ('reset', False), ('run', True) ],
	'list_clients': [ ('full', False), ('any', False) ],
	'get_client_info': [ ('id', REQUIRED) ],
	'kill_client': [ ('id', REQUIRED), ('password', REQUIRED) ],
	'authenticate': [ ('username', REQUIRED), ('password', REQUIRED) ],
	'full_text_search': [ ('text', REQUIRED), ('limit', 0) ],
}
# i metodi di comodo hanno in fondo le callback e il timeout; authenticate anche new_password
for _name, _params in _SIGNATURES.items():
	if _name not in ('list_servers', 'connect', 'execute'):
		_params.extend([ ('success', None), ('error', None), ('progress', None), ('userdata', None), ('timeout', SYNC_TIMEOUT) ])
_SIGNATURES['authenticate'].append(('new_password', None))

# parametri che non vanno alla sessione come argomenti dell'operazione
_NOT_OPERATION = set(_CALLBACKS) | { 'timeout', 'idle', 'new_password' }
# metodi il cui timeout è uno degli argomenti dell'operazione
_TIMEOUT_IN_ARGS = { 'list_servers', 'connect', 'execute' }


_service_lock = threading.Lock()
_service_loop = None


def service_loop():
	"""Il loop del thread di servizio del processo, avviato al primo uso; nel browser il loop di Pyodide."""
	global _service_loop
	if WEB:
		return asyncio.get_event_loop()
	with _service_lock:
		if _service_loop is None:
			loop = asyncio.new_event_loop()
			threading.Thread(target=loop.run_forever, name='kongalib-wire', daemon=True).start()
			_service_loop = loop
		return _service_loop


def _web_run_sync(coro):
	"""Una chiamata sincrona nel browser: sospende lo stack di Python (JSPI) finché *coro* non finisce
	sul loop di Pyodide. Possibile solo partendo da un punto d'ingresso che lo consente
	(``runPythonAsync``, un gestore asincrono, un'applicazione di slew)."""
	from pyodide.ffi import can_run_sync
	if not can_run_sync():
		coro.close()
		raise RuntimeError('synchronous kongalib call where the stack cannot be suspended: use kongalib.AsyncClient, or call it from code started by runPythonAsync')
	return web_wait(coro)


def web_wait(awaitable):
	"""Attende *awaitable* nel browser sospendendo lo stack (``run_sync``) e ne restituisce il risultato,
	o ne solleva l'eccezione. L'esito è preso qui e non da ``run_sync``: un'eccezione che torna da lì passa
	per JavaScript, dove Pyodide la dà a ``sys.excepthook`` (la segnalazione di crash) anche se poi chi
	chiama la gestisce."""
	from pyodide.ffi import run_sync
	future = asyncio.ensure_future(awaitable)
	async def settled():
		await asyncio.wait({ future })
	run_sync(settled())
	return future.result()


def _running_loop():
	try:
		return asyncio.get_running_loop()
	except RuntimeError:
		return None


def _bind(name, args, kwargs):
	# associa gli argomenti ai parametri del metodo, come PyArg_ParseTupleAndKeywords
	params = _SIGNATURES[name]
	if len(args) > len(params):
		raise TypeError('%s() takes at most %d arguments (%d given)' % (name, len(params), len(args)))
	values = {}
	for (param, default), value in zip(params, args):
		values[param] = value
	for key, value in kwargs.items():
		if key in values:
			raise TypeError("%s() got multiple values for argument '%s'" % (name, key))
		if key not in dict(params):
			raise TypeError("%s() got an unexpected keyword argument '%s'" % (name, key))
		values[key] = value
	for param, default in params:
		if param not in values:
			if default is REQUIRED:
				raise TypeError("%s() missing required argument '%s'" % (name, param))
			values[param] = default
	return values


class Deferred(object):
	"""Una richiesta in modalità a callback, come :class:`_kongalib.Deferred`."""

	def __init__(self):
		self._aborted = False
		self._executed = False
		self._pending = True
		self._future = None
		self._task = None

	def cancel(self):
		"""Interrompe la richiesta."""
		# Si annulla il task dell'operazione, non quello che la esegue: annullato prima di partire, quello non
		# eseguirebbe nulla, neanche la callback d'errore. Se il task non c'è ancora, lo annulla chi lo crea
		self._aborted = True
		task = self._task
		if task is not None:
			loop = task.get_loop()
			if _running_loop() is loop:
				task.cancel()
			else:
				try:
					loop.call_soon_threadsafe(task.cancel)
				except RuntimeError:
					pass

	@property
	def aborted(self):
		return self._aborted

	@property
	def executed(self):
		return self._executed

	@property
	def pending(self):
		return self._pending


class _LoopBackend(object):
	"""Back-end di :class:`kongalib.AsyncClient` su un :class:`WireClient`: la sessione gira sul
	loop di chi la usa, oppure su quello a cui è già legata."""

	def __init__(self, client):
		self.client = client

	def call(self, name, *args, progress=None, userdata=None, **kwargs):
		loop = asyncio.get_running_loop()
		session_loop = self.client._use(loop)
		if session_loop is loop:
			return asyncio.ensure_future(getattr(self.client.session, name)(*args, progress=progress, userdata=userdata, **kwargs))
		if progress is not None:
			# la funzione di progresso gira sul loop di chi ha fatto la richiesta, come con il
			# client nativo
			user_progress = progress
			async def progress(*args):
				async def run():
					result = user_progress(*args)
					if inspect.isawaitable(result):
						result = await result
					return result
				return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(run(), loop))
		coro = getattr(self.client.session, name)(*args, progress=progress, userdata=userdata, **kwargs)
		return asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, session_loop))

	def disconnect(self):
		self.client.disconnect()

	def get_id(self):
		return self.client.get_id()

	def get_connection_info(self):
		return self.client.get_connection_info()

	def interrupt(self):
		self.client.interrupt()

	def send_user_message(self, text, targets=None):
		self.client.send_user_message(text, targets)

	def set_user_message_handler(self, handler):
		if handler is None:
			self.client.session.set_user_message_handler(None)
			return
		loop = asyncio.get_running_loop()
		session_loop = self.client._use(loop)
		if session_loop is loop:
			self.client.session.set_user_message_handler(handler)
			return
		# l'handler gira sul loop di chi l'ha impostato, come con il client nativo
		def relay(source, text):
			loop.call_soon_threadsafe(_call_user_message_handler, handler, source, text)
		self.client.session.set_user_message_handler(relay)


def _call_user_message_handler(handler, source, text):
	try:
		result = handler(source, text)
		if inspect.isawaitable(result):
			asyncio.ensure_future(result)
	except Exception:
		traceback.print_exc()


class WireClient(object):
	"""Implementazione di :class:`kongalib.Client` sul trasporto scritto in Python."""

	def __init__(self, open_stream=None):
		self.session = Session(open_stream)
		self.loop = None
		self._lock = threading.Lock()
		self._user_messages = None

	def async_backend(self):
		return _LoopBackend(self)

	def _use(self, loop=None):
		"""Il loop della sessione: quello a cui è legata, se gira ancora; altrimenti (o se non è
		connessa e la usa un altro loop) *loop*, o in mancanza quello di servizio."""
		with self._lock:
			if THREADS:
				if self.loop is None:
					self.loop = service_loop()
				return self.loop
			current = self.loop
			usable = (current is not None) and (not current.is_closed()) and current.is_running()
			connected = self.session.stream is not None
			if (not usable) or ((not connected) and (loop is not None) and (loop is not current)):
				self.loop = loop if loop is not None else service_loop()
			return self.loop

	def _run_sync(self, coro_factory):
		loop = self._use()
		if WEB:
			return _web_run_sync(coro_factory())
		if _running_loop() is loop:
			raise RuntimeError('synchronous kongalib call from the event loop of its own connection')
		return asyncio.run_coroutine_threadsafe(coro_factory(), loop).result()

	def _call_soon(self, callback):
		# esegue callback() sul loop della sessione e ne attende la fine
		loop = self.loop
		if WEB or (loop is None) or loop.is_closed() or (_running_loop() is loop) or not loop.is_running():
			return callback()
		async def run():
			return callback()
		return asyncio.run_coroutine_threadsafe(run(), loop).result()

	# --- metodi senza callback -------------------------------------------------------------

	def disconnect(self):
		self._call_soon(self.session.disconnect)

	def get_id(self):
		return self.session.get_id()

	def get_connection_info(self):
		return self.session.get_connection_info()

	def interrupt(self):
		loop = self.loop
		if WEB or (loop is None) or loop.is_closed() or (_running_loop() is loop) or not loop.is_running():
			self.session.interrupt()
		else:
			loop.call_soon_threadsafe(self.session.interrupt)

	def send_user_message(self, text, targets=None):
		self._call_soon(lambda: self.session.send_user_message(text, targets))

	def set_user_message_handler(self, handler):
		"""*handler(source, text)* gira, come le callback, in un thread (sempre lo stesso, così i messaggi
		arrivano in ordine); nel browser sul loop."""
		if (handler is None) or WEB:
			self.session.set_user_message_handler(handler)
			return
		with self._lock:
			if self._user_messages is None:
				self._user_messages = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='kongalib-user-messages')
			executor = self._user_messages
		def relay(source, text):
			executor.submit(_call_user_message_handler, handler, source, text)
		self.session.set_user_message_handler(relay)

	# --- metodi con modalità sincrona e a callback --------------------------------------------

	def _invoke(self, name, args, kwargs):
		values = _bind(name, args, kwargs)
		operation = [ values[param] for param, _ in _SIGNATURES[name] if param not in _NOT_OPERATION or (param == 'timeout' and name in _TIMEOUT_IN_ARGS) ]
		extra = {}
		if name not in _TIMEOUT_IN_ARGS:
			extra['timeout'] = values['timeout']
		if name == 'authenticate':
			extra['new_password'] = values['new_password']
		if values['success'] is None:
			return self._sync(name, operation, extra)
		return self._callback(name, operation, extra, values)

	def _sync(self, name, operation, extra):
		convenience = name not in _TIMEOUT_IN_ARGS
		if convenience:
			extra['timeout'] = SYNC_TIMEOUT
		if name == 'backup_database':
			extra['include_empty_database'] = True
		session = self.session
		try:
			result = self._run_sync(lambda: getattr(session, name)(*operation, **extra))
		except (asyncio.CancelledError, concurrent.futures.CancelledError):
			raise Error(P.EXECUTE_ABORTED, _error_message(P.EXECUTE_ABORTED))
		except Error as e:
			if name == 'close_database':
				session.database = None
				session.user = None
			if convenience and name != 'query_database':
				raise Error(e.errno, _error_message(e.errno))
			raise
		if name == 'create_database':
			return (result or {}).get('uuid')
		return result

	def _callback(self, name, operation, extra, values):
		success, error, progress, userdata = (values[key] for key in _CALLBACKS)
		deferred = Deferred()
		loop = self._use()

		async def call(callback, *args):
			# le callback girano in un thread dell'executor, come quelle del client nativo (nel
			# browser, senza thread, sul loop); le eccezioni sono stampate e ignorate
			def run():
				try:
					return callback(*args)
				except Exception:
					traceback.print_exc()
					raise
			if WEB:
				return run()
			return await loop.run_in_executor(None, run)

		async def on_progress(ptype, completeness, state, data):
			if deferred._aborted or deferred._executed:
				return False
			if progress is None:
				return True
			try:
				result = await call(progress, ptype, completeness, state, data)
			except Exception:
				result = False
			if (result is not None) and (not result):
				deferred._aborted = True
				return False
			return True

		async def on_error(code, message):
			deferred._pending = False
			if error is not None:
				try:
					await call(error, code, message or _error_message(code), userdata)
				except Exception:
					pass
			deferred._executed = True

		async def run():
			task = None
			if not deferred._aborted:
				task = deferred._task = asyncio.ensure_future(getattr(self.session, name)(*operation, progress=on_progress, userdata=userdata, **extra))
				# (a cancel() meanwhile found no task to cancel)
				if deferred._aborted:
					task.cancel()
			try:
				if task is None:
					raise asyncio.CancelledError()
				result = await task
			except asyncio.CancelledError:
				deferred._aborted = True
				await on_error(P.EXECUTE_ABORTED, None)
				return
			except Error as e:
				await on_error(e.errno, e.msg)
				return
			except Exception as e:
				await on_error(-1, str(e))
				return
			count = SUCCESS_VALUES[name]
			if count == 0:
				results = ()
			elif count == 1:
				results = (result,)
			else:
				results = tuple(result)
			deferred._pending = False
			try:
				await call(success, *(results + (userdata,)))
			except Exception:
				pass
			if not deferred._aborted:
				deferred._executed = True

		if _running_loop() is loop:
			deferred._future = loop.create_task(run())
		else:
			deferred._future = asyncio.run_coroutine_threadsafe(run(), loop)
		return deferred


def _method(name):
	def method(self, *args, **kwargs):
		return self._invoke(name, args, kwargs)
	method.__name__ = name
	return method


for _name in _SIGNATURES:
	setattr(WireClient, _name, _method(_name))
