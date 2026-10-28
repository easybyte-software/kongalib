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

"""Sessione asincrona sul protocollo IPC di Konga: il back-end di :class:`kongalib.AsyncClient`
per il trasporto scritto in Python.

Una :class:`Session` è una connessione a un server; le sue operazioni hanno gli stessi
argomenti, comandi e risultati dei metodi di :class:`_kongalib.Client` (vedi
``plans/notes/kongalib_wire.md`` nel repository di Konga), ma sono coroutine: restituiscono
quello che la callback di successo del client nativo riceverebbe, sollevano
:class:`kongalib.Error`, e un'operazione interrotta (dalla funzione di progresso che restituisce
False, o annullando il task) manda ABORT al server e solleva ``asyncio.CancelledError``.

Gira sul loop che la usa, senza thread. Il flusso di byte è astratto (:class:`Stream`): TCP qui,
un WebSocket nel browser.
"""

import asyncio
import base64
import collections
import datetime
import inspect
import json
import sys
import time
import traceback

from _kongalib import _clu_encode, _clu_decode, _error_message, checksum, hash_password
from kongalib import Error, PROGRESS_EXECUTE, PROGRESS_COMPLETE, constants as C
from kongalib.wire import protocol as P


DEFAULT_TIMEOUT = 5000				# ms, se né la richiesta né la connessione ne indicano uno
CLIENT_FLAG_SCRIPT = 9				# include/mga/konga_client/common.h

# Esiti che chiudono la connessione e azzerano lo stato del client (MGA_Client::CheckResult)
_NETWORK_ERRORS = set(range(100, 111)) | { 112, 113, 114, 115, 117, 200, 201 }


def error(code, message=None):
	"""Un :class:`kongalib.Error` con il messaggio che darebbe il client nativo."""
	return Error(code, message or _error_message(code))


def _is_jwt(text):
	# Come jwt::decode in MGA_Client::_FillCredentials: tre parti base64url, le prime due JSON
	parts = text.split('.')
	if len(parts) != 3:
		return False
	try:
		for part in parts[:2]:
			if not isinstance(json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4))), dict):
				return False
	except Exception:
		return False
	return True


def _timezone():
	# minuti dall'UTC dell'ora locale (CL_TimeStamp::GetTimeZoneMinutesFromUTC)
	return int(datetime.datetime.now().astimezone().utcoffset().total_seconds() // 60)


class Stream(object):
	"""Flusso di byte verso il server. ``read()`` restituisce b'' alla chiusura."""

	async def read(self):
		raise NotImplementedError

	def write(self, data):
		raise NotImplementedError

	async def drain(self):
		pass

	def close(self):
		raise NotImplementedError


class TCPStream(Stream):
	"""Flusso su una connessione TCP di asyncio."""

	def __init__(self, reader, writer):
		self.reader = reader
		self.writer = writer

	@classmethod
	async def open(cls, host, port):
		import socket
		host = host or '127.0.0.1'
		# Come il client nativo (CL_NetAddress): il primo indirizzo IPv4, e IPv6 solo se non ce n'è.
		# Nell'ordine del sistema, su Windows "localhost" prova prima ::1, che il server può non
		# ascoltare: il rifiuto arriva dopo un paio di secondi, oltre il timeout di molte connessioni
		try:
			reader, writer = await asyncio.open_connection(host, port, family=socket.AF_INET)
		except socket.gaierror:
			reader, writer = await asyncio.open_connection(host, port)
		return cls(reader, writer)

	async def read(self):
		return await self.reader.read(65536)

	def write(self, data):
		self.writer.write(data)

	async def drain(self):
		await self.writer.drain()

	def close(self):
		self.writer.close()


class _Request(object):
	# Una richiesta in attesa di risposta: gli eventi (Ping, Reply, eccezioni) arrivano dal
	# compito che legge il flusso, e svegliano chi aspetta (waiter)
	__slots__ = ('assembler', 'events', 'waiter')

	def __init__(self, cipher):
		self.assembler = P.ReplyAssembler(cipher)
		self.events = collections.deque()
		self.waiter = None

	def post(self, event):
		self.events.append(event)
		waiter = self.waiter
		if (waiter is not None) and (not waiter.done()):
			waiter.set_result(None)


class Session(object):
	"""Una connessione a un server Konga. *open_stream* è una coroutine ``(host, port) ->
	Stream``; di default una connessione TCP."""

	def __init__(self, open_stream=None):
		if open_stream is None:
			if sys.platform == 'emscripten':
				# nel browser: il WebSocket verso il gateway del server che ha servito la pagina
				from .websocket import WebSocketStream
				open_stream = WebSocketStream.open
			else:
				open_stream = TCPStream.open
		self.open_stream = open_stream
		self.stream = None
		self.reader_task = None
		self.packets = None
		self.requests = {}
		self.next_sequence = 1
		self.codec = None
		self.client_id = 0
		self.timeout = DEFAULT_TIMEOUT
		self.last_activity = 0.0
		self.info = None
		self.database = None
		self.user = None
		self.user_message_handler = None

	# --- connessione -------------------------------------------------------------------------

	def _settings(self, server, host, port, options, timeout):
		# La tabella dell'AUTH, come in MGA_Client::Connect
		settings = dict(options or {})
		settings['host'] = host
		settings['port'] = port
		settings['timeout'] = timeout
		settings['conn_flags'] = int(settings.get('flags', CLIENT_FLAG_SCRIPT))
		settings['parent_client_id'] = int(settings.get('parent_client_id') or 0)
		settings['sid'] = str(settings.get('sid') or '')
		settings['remote_address'] = str(settings.get('remote_address') or '')
		settings['timezone'] = _timezone()
		return settings

	async def connect(self, server=None, host=None, port=0, options=None, timeout=30000, progress=None, userdata=None):
		if server is not None:
			if not isinstance(server, dict):
				raise TypeError('server must be a dict')
			host = server['host']
			port = int(server['port']) & 0xFFFF
		elif host is None:
			raise ValueError("either 'host' or 'server' parameter must be specified")
		port = port or P.DEFAULT_PORT
		self.disconnect()
		self.timeout = timeout or DEFAULT_TIMEOUT
		try:
			self.stream = await asyncio.wait_for(self.open_stream(host, port), (timeout or DEFAULT_TIMEOUT) / 1000)
		except ConnectionRefusedError:
			raise error(103)
		except (OSError, asyncio.TimeoutError):
			raise error(P.CANNOT_CONNECT)
		self.packets = P.PacketReader()
		self.last_activity = time.monotonic()
		self.reader_task = asyncio.ensure_future(self._read())
		try:
			reply = await self._exchange(lambda seq: P.server_info_request(seq), None, timeout)
			server_id = reply.header.server_id
			settings = self._settings(server, host, port, options, timeout)
			reply = await self._exchange(lambda seq: P.auth_request(seq, _clu_encode(settings), settings['conn_flags']), None, timeout)
			if reply.header.type == P.TYPE_NO_AUTH:
				raise error(reply.header.error)
			if reply.header.type == P.TYPE_ABORT:
				raise error(P.ABORTED)
			if reply.header.type != P.TYPE_AUTH:
				raise error(P.BAD_REPLY)
			info = _clu_decode(reply.data) if reply.data else {}
		except BaseException:
			self.disconnect()
			raise
		self.client_id = reply.header.client_id
		self.codec = P.Codec(reply.header.flags, self.client_id, server_id)
		info['host'] = host
		info['port'] = port
		self.info = info
		self.database = None
		self.user = None
		return info

	def disconnect(self, code=P.NOT_CONNECTED):
		"""Chiude la connessione (senza avvisare il server, come il client nativo) e azzera lo
		stato; le richieste in attesa falliscono con *code*."""
		if self.reader_task is not None:
			self.reader_task.cancel()
			self.reader_task = None
		if self.stream is not None:
			try:
				self.stream.close()
			except Exception:
				pass
			self.stream = None
		for request in self.requests.values():
			request.post(error(code))
		self.requests.clear()
		self.codec = None
		self.client_id = 0
		self.info = None
		self.database = None
		self.user = None

	def get_id(self):
		return self.client_id

	def get_connection_info(self):
		if (not self.info) or (not self.info.get('uuid')):
			return None
		info = dict(self.info)
		info['database'] = dict(self.database) if self.database else None
		info['user'] = dict(self.user) if self.user else None
		return info

	def interrupt(self):
		"""Interrompe tutte le richieste in esecuzione sul server; ciascuna termina con
		l'annullamento."""
		if self.stream is not None:
			self.stream.write(P.abort_all_request())

	# --- messaggi utente ---------------------------------------------------------------------

	def set_user_message_handler(self, handler):
		"""*handler(source, text)* riceve i messaggi utente (anche una coroutine), se alla
		connessione le opzioni avevano ``user_messages``; *source* è l'ID del client che l'ha
		mandato. None smette di riceverli."""
		self.user_message_handler = handler

	def send_user_message(self, text, targets=None):
		"""Manda il messaggio *text* ai client *targets* (un ID o una lista di ID), o a tutti se
		None; senza risposta: chi non li ha chiesti alla connessione non lo riceve."""
		if (self.stream is None) or (self.codec is None):
			raise error(P.NOT_CONNECTED)
		if targets is None:
			targets = ()
		elif isinstance(targets, int):
			targets = (targets,)
		elif isinstance(targets, (str, bytes)) or not all(isinstance(target, int) for target in targets):
			raise TypeError("'targets' must be a client ID, a sequence of them or None")
		self.stream.write(self.codec.user_message(text, targets))

	def _user_message(self, header, payload):
		handler = self.user_message_handler
		if (handler is None) or (self.codec is None):
			return
		message = self.codec.decode_user_message(header, payload)
		if message is None:
			return
		try:
			result = handler(*message)
			if inspect.isawaitable(result):
				asyncio.ensure_future(result)
		except Exception:
			traceback.print_exc()

	async def list_servers(self, timeout=5000, port=0, progress=None, userdata=None):
		# la scoperta dei server in broadcast UDP non esiste nel browser: il client web vede solo il
		# server che lo serve, che risponde in HTTP; come in una scoperta, la risposta arriva allo
		# scadere di *timeout* (chi cerca i server di continuo non gira a vuoto)
		if sys.platform != 'emscripten':
			return ()
		from .websocket import discover
		start = time.monotonic()
		try:
			servers = await discover()
		except Exception:
			servers = ()
		rest = (timeout / 1000) - (time.monotonic() - start)
		if rest > 0:
			await asyncio.sleep(rest)
		return servers

	# --- lettura e richieste -----------------------------------------------------------------

	async def _read(self):
		code = P.CONNECTION_LOST
		try:
			while True:
				data = await self.stream.read()
				if not data:
					code = P.NOT_CONNECTED
					break
				self.last_activity = time.monotonic()
				for header, payload in self.packets.feed(data):
					if header.type == P.TYPE_USER_MESSAGE:
						self._user_message(header, payload)
						continue
					request = self.requests.get(header.sequence)
					if request is None:
						# risposta o PING di una richiesta finita, scaduta o interrotta
						continue
					event = request.assembler.feed(header, payload)
					if event is not None:
						if isinstance(event, P.Reply):
							del self.requests[header.sequence]
						request.post(event)
		except asyncio.CancelledError:
			return
		except (P.ProtocolError, OSError):
			pass
		self.reader_task = None
		self.disconnect(code)

	def _send(self, build, cipher):
		if self.stream is None:
			raise error(P.NOT_CONNECTED)
		sequence = self.next_sequence
		self.next_sequence = (self.next_sequence + 1) & 0xFFFFFFFF or 1
		request = self.requests[sequence] = _Request(cipher)
		self.stream.write(build(sequence))
		return sequence, request

	async def _exchange(self, build, cipher, timeout, progress=None, userdata=None):
		"""Invia una richiesta e ne attende la risposta: timeout di inattività (si azzera a ogni
		pacchetto ricevuto, anche di altre richieste), progresso dai PING, interruzione."""
		timeout = (timeout or self.timeout) / 1000
		loop = asyncio.get_running_loop()
		sequence, request = self._send(build, cipher)
		started = time.monotonic()
		timer = None

		def check():
			# un solo timer per richiesta: allo scadere guarda quando è arrivato l'ultimo
			# pacchetto, e se è recente si riarma per il resto del tempo
			nonlocal timer
			last = max(self.last_activity, started)
			left = timeout - (time.monotonic() - last)
			if left > 0:
				timer = loop.call_later(left, check)
			else:
				timer = None
				request.post(error(P.TIMED_OUT))

		timer = loop.call_later(timeout, check)
		try:
			await self.stream.drain()
			events = request.events
			while True:
				while events:
					event = events.popleft()
					if isinstance(event, BaseException):
						raise event
					if isinstance(event, P.Ping):
						if progress is not None:
							result = progress(PROGRESS_EXECUTE, event.completeness, event.message, userdata)
							if inspect.isawaitable(result):
								result = await result
							if result is False:
								raise asyncio.CancelledError()
						continue
					return event
				request.waiter = loop.create_future()
				await request.waiter
				request.waiter = None
		except asyncio.CancelledError:
			# annullata (o interrotta dal progresso): il server la ferma, la sua risposta
			# verrà scartata
			if self.requests.pop(sequence, None) is not None and self.stream is not None:
				self.stream.write(P.abort_request(sequence))
			raise
		except BaseException:
			self.requests.pop(sequence, None)
			raise
		finally:
			if timer is not None:
				timer.cancel()

	async def execute(self, command, data=None, timeout=10000, progress=None, userdata=None, idle=None):
		"""Esegue *command* con i dati *data* e restituisce l'intera tabella di risposta;
		solleva :class:`kongalib.Error` se il server riporta un errore (``ERRNO``)."""
		if self.codec is None:
			raise error(P.NOT_CONNECTED)
		input = _clu_encode(data or {})
		try:
			reply = await self._exchange(lambda seq: self.codec.data_request(seq, command, input), self.codec.cipher, timeout, progress, userdata)
		except Error as e:
			if e.errno in _NETWORK_ERRORS:
				self.disconnect(e.errno)
			raise
		if reply.status == P.EXECUTE_ABORTED:
			raise asyncio.CancelledError()
		if reply.status not in (P.OK, P.EXECUTE_FAILED):
			self.disconnect(reply.status)
			raise error(reply.status)
		try:
			output = _clu_decode(reply.data) if reply.data else {}
		except ValueError:
			self.disconnect(P.BAD_REPLY)
			raise error(P.BAD_REPLY)
		output.setdefault(C.OUT_CHECKSUM, checksum(reply.data))
		errno = output.get(C.OUT_ERRNO) or (P.EXECUTE_FAILED if reply.status == P.EXECUTE_FAILED else P.OK)
		if errno != P.OK:
			raise error(errno, output.get(C.OUT_ERROR))
		if command == C.CMD_LOGIN_SSO:
			info = output.get(C.OUT_USERINFO) or {}
			self.user = { 'name': info.get('NickName'), 'password': info.get('ParolaChiave') }
		if progress is not None:
			result = progress(PROGRESS_COMPLETE, 100.0, '', userdata)
			if inspect.isawaitable(result):
				await result
		return output

	# --- operazioni (come i metodi di _kongalib.Client) -----------------------------------------

	async def _command(self, command, input, timeout, progress, userdata):
		return await self.execute(command, input, timeout, progress, userdata)

	async def get_data_dictionary(self, progress=None, userdata=None, timeout=10000):
		return (await self._command(C.CMD_GET_DATA_DICTIONARY, {}, timeout, progress, userdata)).get(C.OUT_DICTIONARY)

	async def list_drivers(self, configured=True, progress=None, userdata=None, timeout=10000):
		return (await self._command(C.CMD_LIST_DRIVERS, { C.IN_CONFIGURED: bool(configured) }, timeout, progress, userdata)).get(C.OUT_DRIVERS)

	async def list_databases(self, driver=None, quick=True, progress=None, userdata=None, timeout=10000):
		output = await self._command(C.CMD_LIST_DATABASES, { C.IN_DRIVER: driver or '', C.IN_QUICK: bool(quick) }, timeout, progress, userdata)
		return output.get(C.OUT_DATABASES)

	async def create_database(self, password, driver, name, desc='', progress=None, userdata=None, timeout=10000):
		output = await self._command(C.CMD_CREATE_DATABASE, {
			C.IN_PASSWORD: password, C.IN_DRIVER: driver, C.IN_NAME: name, C.IN_DESC: desc,
		}, timeout, progress, userdata)
		return output.get(C.OUT_INFO)

	async def open_database(self, driver, name, progress=None, userdata=None, timeout=10000):
		output = await self._command(C.CMD_OPEN_DATABASE, { C.IN_DRIVER: driver, C.IN_NAME: name }, timeout, progress, userdata)
		info = output.get(C.OUT_INFO) or {}
		self.database = { 'driver': driver, 'name': name, 'uuid': info.get('uuid') }
		return info

	async def close_database(self, backup=False, progress=None, userdata=None, timeout=10000):
		await self._command(C.CMD_CLOSE_DATABASE, { C.IN_BACKUP: bool(backup) }, timeout, progress, userdata)
		self.database = None
		self.user = None

	async def upgrade_database(self, password, driver, name, progress=None, userdata=None, timeout=10000):
		output = await self._command(C.CMD_UPGRADE_DATABASE, { C.IN_PASSWORD: password, C.IN_DRIVER: driver, C.IN_NAME: name }, timeout, progress, userdata)
		log = [ entry[3] for entry in (output.get(C.OUT_LOG) or []) ]
		return log, int(output.get(C.OUT_OLD_VERSION) or 0), int(output.get(C.OUT_NEW_VERSION) or 0)

	async def delete_database(self, password, driver, name, delete_cloud_data=None, progress=None, userdata=None, timeout=10000):
		input = { C.IN_PASSWORD: password, C.IN_DRIVER: driver, C.IN_NAME: name }
		if delete_cloud_data is not None:
			input[C.IN_DELETE_CLOUD_DATA] = bool(delete_cloud_data)
		await self._command(C.CMD_DELETE_DATABASE, input, timeout, progress, userdata)

	async def query_database(self, query, native=False, full_column_names=False, collapse_blobs=False, progress=None, userdata=None, timeout=10000):
		output = await self._command(C.CMD_QUERY_DATABASE_NATIVELY if native else C.CMD_QUERY_DATABASE, {
			C.IN_QUERY: query, C.IN_FULL_COLUMNS_LIST: bool(full_column_names), C.IN_COLLAPSE_BLOBS: bool(collapse_blobs),
		}, timeout, progress, userdata)
		return int(output.get(C.OUT_AFFECTED_ROWS) or 0), output.get(C.OUT_COLUMNS_LIST), output.get(C.OUT_RESULT_SET)

	async def backup_database(self, password, backup_name, driver='', name='', auto=True, overwrite=False, position=0, store_index=False, progress=None, userdata=None, timeout=10000, include_empty_database=False):
		input = { C.IN_PASSWORD: password }
		if driver or include_empty_database:
			# come il client nativo: in modalità asincrona il database solo se indicato, in
			# quella sincrona sempre
			input[C.IN_DRIVER] = driver
			input[C.IN_NAME] = name
		input.update({
			C.IN_BACKUP_NAME: backup_name, C.IN_AUTO_BACKUP: bool(auto), C.IN_OVERWRITE: bool(overwrite),
			C.IN_POSITION: int(position), C.IN_STORE_INDEX: bool(store_index),
		})
		await self._command(C.CMD_BACKUP_DATABASE, input, timeout, progress, userdata)

	async def restore_database(self, password, backup_name, driver='', name='', change_uuid=True, overwrite=False, position=0, restore_index=True, progress=None, userdata=None, timeout=10000):
		await self._command(C.CMD_RESTORE_DATABASE, {
			C.IN_PASSWORD: password, C.IN_DRIVER: driver, C.IN_NAME: name, C.IN_BACKUP_NAME: backup_name,
			C.IN_CHANGE_UUID: bool(change_uuid), C.IN_OVERWRITE: bool(overwrite), C.IN_POSITION: int(position),
			C.IN_RESTORE_INDEX: bool(restore_index),
		}, timeout, progress, userdata)

	async def list_backups(self, position=0, progress=None, userdata=None, timeout=10000):
		return (await self._command(C.CMD_LIST_BACKUPS, { C.IN_POSITION: int(position) }, timeout, progress, userdata)).get(C.OUT_BACKUPS)

	async def delete_backup(self, password, backup_name, position, progress=None, userdata=None, timeout=10000):
		if (not isinstance(backup_name, str)) and backup_name:
			backup_name = [ str(name) for name in backup_name ]
		await self._command(C.CMD_DELETE_BACKUP, { C.IN_PASSWORD: password, C.IN_BACKUP_NAME: backup_name, C.IN_POSITION: int(position) }, timeout, progress, userdata)

	async def optimize_database(self, password, driver='', name='', progress=None, userdata=None, timeout=10000):
		await self._command(C.CMD_OPTIMIZE_DATABASE, { C.IN_PASSWORD: password, C.IN_DRIVER: driver, C.IN_NAME: name }, timeout, progress, userdata)

	async def repair_database(self, password, driver='', name='', output='', progress=None, userdata=None, timeout=10000):
		await self._command(C.CMD_REPAIR_DATABASE, { C.IN_PASSWORD: password, C.IN_DRIVER: driver, C.IN_NAME: name, C.IN_OUTPUT: output }, timeout, progress, userdata)

	async def index_database(self, password, driver='', name='', reset=False, run=True, progress=None, userdata=None, timeout=10000):
		await self._command(C.CMD_INDEX_DATABASE, {
			C.IN_PASSWORD: password, C.IN_DRIVER: driver, C.IN_NAME: name, C.IN_RESET: bool(reset), C.IN_RUN: bool(run),
		}, timeout, progress, userdata)

	async def list_clients(self, full=False, any=False, progress=None, userdata=None, timeout=10000):
		return (await self._command(C.CMD_GET_CLIENT_LIST, { C.IN_FULL: bool(full), C.IN_ANY: bool(any) }, timeout, progress, userdata)).get(C.OUT_CLIENT_LIST)

	@staticmethod
	def _client_id(id):
		if isinstance(id, str):
			return id if id else 0
		return int(id)

	async def get_client_info(self, id, progress=None, userdata=None, timeout=10000):
		return (await self._command(C.CMD_GET_CLIENT_INFO, { C.IN_CLIENT_ID: self._client_id(id) }, timeout, progress, userdata)).get(C.OUT_CLIENT_INFO)

	async def kill_client(self, id, password, progress=None, userdata=None, timeout=10000):
		await self._command(C.CMD_KILL_CLIENT, { C.IN_CLIENT_ID: self._client_id(id), C.IN_PASSWORD: password }, timeout, progress, userdata)

	async def authenticate(self, username, password, progress=None, userdata=None, timeout=10000, new_password=None):
		input = { C.IN_USERNAME: username }
		# come MGA_Client::_FillCredentials: in chiaro per gli utenti di dominio e i token JWT
		if ('\\' in username) or _is_jwt(password):
			input[C.IN_PASSWORD] = password
		else:
			input[C.IN_PASSWORD] = hash_password(password)
		if new_password is not None:
			input[C.IN_NEW_PASSWORD] = hash_password(new_password)
		output = await self._command(C.CMD_AUTHENTICATE, input, timeout, progress, userdata)
		self.user = { 'name': username, 'password': password }
		return output.get(C.OUT_USERINFO)

	async def full_text_search(self, text, limit=0, progress=None, userdata=None, timeout=10000):
		input = { C.IN_QUERY: text }
		if limit and limit > 0:
			input[C.IN_LIMIT] = int(limit)
		return (await self._command(C.CMD_SEARCH, input, timeout, progress, userdata)).get(C.OUT_HITS)


class WireBackend(object):
	"""Back-end di :class:`kongalib.AsyncClient` su una :class:`Session` (vedi
	:mod:`kongalib.async_backend`)."""

	def __init__(self, session):
		self.session = session

	def call(self, name, *args, progress=None, userdata=None, **kwargs):
		return asyncio.ensure_future(getattr(self.session, name)(*args, progress=progress, userdata=userdata, **kwargs))

	def disconnect(self):
		self.session.disconnect()

	def get_id(self):
		return self.session.get_id()

	def get_connection_info(self):
		return self.session.get_connection_info()

	def interrupt(self):
		self.session.interrupt()

	def send_user_message(self, text, targets=None):
		self.session.send_user_message(text, targets)

	def set_user_message_handler(self, handler):
		self.session.set_user_message_handler(handler)
