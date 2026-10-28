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

"""Back-end asincroni di :class:`kongalib.AsyncClient`.

Un back-end esegue le operazioni del client e restituisce per ciascuna un ``asyncio.Future`` già
avviato: il risultato è quello della callback di successo di :class:`_kongalib.Client` (``None``,
un valore o una tupla, vedi ``SUCCESS_VALUES``), oppure un'eccezione :class:`kongalib.Error`;
un'operazione interrotta (``ABORTED``, ``EXECUTE_ABORTED``) annulla il future. La funzione di
progresso ha la forma ``progress(type, completeness, state, userdata)``, può essere una
coroutine, e restituendo ``False`` interrompe l'operazione; annullare il future fa lo stesso.

- :class:`NativeBackend`: il client nativo, le cui callback arrivano dai thread del
  dispatcher di _kongalib e vengono riportate sul loop.
- il trasporto scritto in Python (``kongalib.wire``), che gira sul loop stesso.
"""

import asyncio
import inspect
import traceback

from kongalib import Error, ABORTED, EXECUTE_ABORTED, ensure_text


# Quanti valori, oltre a *userdata*, riceve la callback di successo di ciascun metodo di
# _kongalib.Client: il risultato del future è None, il valore o la tupla dei valori
SUCCESS_VALUES = {
	'list_servers': 1,
	'connect': 1,
	'execute': 1,
	'get_data_dictionary': 1,
	'list_drivers': 1,
	'list_databases': 1,
	'create_database': 1,
	'open_database': 1,
	'close_database': 0,
	'upgrade_database': 3,
	'delete_database': 0,
	'query_database': 3,
	'backup_database': 0,
	'restore_database': 0,
	'list_backups': 1,
	'delete_backup': 0,
	'optimize_database': 0,
	'repair_database': 0,
	'index_database': 0,
	'list_clients': 1,
	'get_client_info': 1,
	'kill_client': 0,
	'authenticate': 1,
	'full_text_search': 1,
}


def make_backend(impl):
	"""Restituisce il back-end asincrono per l'implementazione *impl* di un client: quello che
	essa stessa fornisce (``impl.async_backend()``), altrimenti :class:`NativeBackend`."""
	factory = getattr(impl, 'async_backend', None)
	if factory is not None:
		return factory()
	return NativeBackend(impl)


def _call_soon(loop, callback, *args):
	# Da un thread del dispatcher: il loop può essere già chiuso (l'operazione è finita dopo
	# che chi la aspettava se n'è andato, per esempio dopo un annullamento), e allora non c'è
	# più nessuno da avvisare
	try:
		loop.call_soon_threadsafe(callback, *args)
	except RuntimeError:
		pass


def _set_result(future, result):
	if not future.done():
		future.set_result(result)


def _set_exception(future, e):
	if not future.done():
		future.set_exception(e)


def _cancel(future):
	future.cancel()


def _call_user_message_handler(handler, source, text):
	try:
		result = handler(source, text)
		if inspect.isawaitable(result):
			asyncio.ensure_future(result)
	except Exception:
		traceback.print_exc()


class NativeBackend(object):
	"""Back-end sul client nativo :class:`_kongalib.Client`."""

	def __init__(self, impl):
		self.impl = impl

	def call(self, name, *args, progress=None, userdata=None, **kwargs):
		"""Avvia il metodo *name* del client nativo con gli argomenti posizionali *args* e quelli per
		nome *kwargs* (es. *timeout*), e restituisce il future del risultato."""
		future = asyncio.get_running_loop().create_future()
		getattr(self.impl, name)(*args,
			success=self.make_success(future, SUCCESS_VALUES[name]),
			error=self.make_error(future),
			progress=self.make_progress(future, progress, userdata),
			**kwargs)
		return future

	def disconnect(self):
		self.impl.disconnect()

	def get_id(self):
		return self.impl.get_id()

	def get_connection_info(self):
		return self.impl.get_connection_info()

	def interrupt(self):
		self.impl.interrupt()

	def send_user_message(self, text, targets=None):
		self.impl.send_user_message(text, targets)

	def set_user_message_handler(self, handler):
		"""Il client nativo chiama l'handler da un thread suo: lo si esegue sul loop di chi l'ha
		impostato."""
		if handler is None:
			self.impl.set_user_message_handler(None)
			return
		loop = asyncio.get_running_loop()
		def relay(source, text):
			_call_soon(loop, _call_user_message_handler, handler, source, text)
		self.impl.set_user_message_handler(relay)

	@staticmethod
	def make_progress(future, progress, userdata):
		"""Callback di progresso per il client nativo: chiamata da un thread del dispatcher, esegue
		*progress* sul loop di *future* e ne attende il risultato. Restituisce False (e il client
		interrompe l'operazione) se il future è stato annullato, se *progress* restituisce False o
		se solleva un'eccezione, che diventa il risultato del future."""
		def callback(ptype, completeness, state, dummy):
			loop = future.get_loop()
			try:
				if future.cancelled() or (progress is None):
					result = not future.cancelled()
				else:
					if inspect.iscoroutinefunction(progress):
						coro = progress
					else:
						async def coro(*args):
							return progress(*args)
					result = asyncio.run_coroutine_threadsafe(coro(ptype, completeness, state, userdata), loop).result()
				if result is False:
					return False
			except Exception as e:
				result = False
				_call_soon(loop, _set_exception, future, e)
			return result
		return callback

	@staticmethod
	def make_error(future):
		def error(errno, *args):
			loop = future.get_loop()
			if isinstance(errno, int) and (errno in (ABORTED, EXECUTE_ABORTED)):
				errno = Error(errno, '')
			if isinstance(errno, Error):
				if errno.errno in (ABORTED, EXECUTE_ABORTED):
					_call_soon(loop, _cancel, future)
				else:
					_call_soon(loop, _set_exception, future, errno)
			elif isinstance(errno, Exception):
				_call_soon(loop, _set_exception, future, errno)
			else:
				if len(args) > 0:
					errstr = ensure_text(args[0])
				else:
					errstr = '<unknown>'
				_call_soon(loop, _set_exception, future, Error(errno, errstr))
		return error

	@staticmethod
	def make_success(future, count):
		def success(*args):
			loop = future.get_loop()
			if count == 0:
				_call_soon(loop, _set_result, future, None)
			elif count == 1:
				_call_soon(loop, _set_result, future, args[0])
			else:
				_call_soon(loop, _set_result, future, args[:count])
		return success
