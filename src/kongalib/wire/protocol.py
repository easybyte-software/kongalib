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

"""Pacchetti del protocollo IPC di Konga (lato client), senza I/O.

Riferimento: ``plans/notes/kongalib_wire.md`` nel repository di Konga, e ``src/ebpr/ipc_tcp.cpp``
(``CL_TCPClient``). Ogni pacchetto è un header di 32 byte little-endian seguito da al più
``PACKET_SIZE`` byte di dati; un'operazione (richiesta o risposta) più lunga è divisa in più
pacchetti con la stessa sequenza, il primo con il flag ``FLAG_HEAD``, e ``size`` di ciascuno
pari ai byte che restano compresi i suoi.
"""

import struct
import zlib

from _kongalib import checksum, _Cipher, _clu_encode, _clu_decode


MAGIC = 0xF79BF0B7
VERSION = 0x00010002			# CL_PROTOCOL_VERSION, 1.0.2

TYPE_SERVER_INFO = 2
TYPE_PING = 3
TYPE_AUTH = 4
TYPE_NO_AUTH = 5
TYPE_DATA = 6
TYPE_FAILED = 7
TYPE_ABORT = 8
TYPE_ABORT_ALL = 9
TYPE_USER_MESSAGE = 10

FLAG_TEA = 0x1
FLAG_BLOWFISH = 0x2
FLAG_AES = 0x4
FLAG_COMPRESS = 0x100
FLAG_HEAD = 0x1000

HEADER = struct.Struct('<IIHHII8sI')
HEADER_SIZE = HEADER.size		# 32
PACKET_SIZE = 8192 - HEADER_SIZE
MAX_REQUEST_SIZE = 512 * 1024 * 1024
DEFAULT_PORT = 51965

# Esiti (include/ebpr/errors.h)
OK = 0
TIMED_OUT = 4
ABORTED = 7
PROTOCOL_NOT_SUPPORTED = 101
CANNOT_CONNECT = 107
NOT_CONNECTED = 114
CONNECTION_LOST = 115
BAD_REQUEST = 200
BAD_REPLY = 201
EXECUTE_FAILED = 204
EXECUTE_ABORTED = 205

# Unione degli 8 byte all'offset 20, secondo il tipo di pacchetto
_UNION_DATA = struct.Struct('<II')			# comando, checksum
_UNION_SERVER = struct.Struct('<Q')			# ID del server
_UNION_CONNECTION = struct.Struct('<II')	# ID del client, flag della connessione o errore
_UNION_PING = struct.Struct('<H6x')			# completezza
_UNION_MESSAGE = struct.Struct('<II')		# ID del client mittente, checksum
_NO_UNION = bytes(8)


class ProtocolError(Exception):
	"""Il flusso dal server non è più interpretabile (es. magic errato): la connessione va
	chiusa."""


class Header(object):
	"""Header di un pacchetto. Della versione, dei campi riservati e dei byte inutilizzati
	dell'unione il server non garantisce il contenuto (nei PING sono casuali): non vanno
	controllati."""
	__slots__ = ('magic', 'version', 'type', 'flags', 'sequence', 'size', 'union', 'reserved')

	def __init__(self, type, flags, sequence, size, union=_NO_UNION, magic=MAGIC, version=VERSION, reserved=0):
		self.magic = magic
		self.version = version
		self.type = type
		self.flags = flags
		self.sequence = sequence
		self.size = size
		self.union = union
		self.reserved = reserved

	@classmethod
	def unpack(cls, data):
		magic, version, type, flags, sequence, size, union, reserved = HEADER.unpack_from(data)
		return cls(type, flags, sequence, size, union, magic, version, reserved)

	def pack(self):
		return HEADER.pack(self.magic, self.version, self.type, self.flags, self.sequence, self.size, self.union, self.reserved)

	@property
	def command(self):
		return _UNION_DATA.unpack(self.union)[0]

	@property
	def checksum(self):
		return _UNION_DATA.unpack(self.union)[1]

	@property
	def server_id(self):
		return _UNION_SERVER.unpack(self.union)[0]

	@property
	def client_id(self):
		return _UNION_CONNECTION.unpack(self.union)[0]

	@property
	def error(self):
		# NO_AUTH: codice d'errore; richiesta AUTH: flag della connessione
		return _UNION_CONNECTION.unpack(self.union)[1]

	@property
	def source(self):
		"""Messaggio utente: l'ID del client che l'ha mandato (lo mette il server)."""
		return _UNION_MESSAGE.unpack(self.union)[0]

	@property
	def message_checksum(self):
		return _UNION_MESSAGE.unpack(self.union)[1]

	@property
	def completeness(self):
		"""Completezza di un PING, da 0.0 a 100.0, o -1.0 se indefinita."""
		value = _UNION_PING.unpack(self.union)[0]
		return -1.0 if value == 0xFFFF else value / 655.34

	def __repr__(self):
		return '<Header type=%d flags=0x%x seq=%d size=%d union=%s>' % (self.type, self.flags, self.sequence, self.size, self.union.hex())


def split(type, flags, sequence, payload, union=_NO_UNION):
	"""Pacchetti di un'operazione: il primo con ``FLAG_HEAD``, ciascuno con *size* pari ai byte
	che restano; dati vuoti danno un solo header."""
	packets = []
	offset = 0
	total = len(payload)
	head = flags | FLAG_HEAD
	while True:
		chunk = payload[offset:offset + PACKET_SIZE]
		packets.append(Header(type, head, sequence, total - offset, union).pack() + chunk)
		offset += len(chunk)
		head = flags & ~FLAG_HEAD
		if offset >= total:
			break
	return b''.join(packets)


def server_info_request(sequence):
	"""Prima richiesta della stretta di mano: la risposta porta l'ID del server."""
	return split(TYPE_SERVER_INFO, 0, sequence, b'')


def auth_request(sequence, settings, conn_flags):
	"""Seconda richiesta della stretta di mano: *settings* è la tabella delle impostazioni già
	codificata (CLU), in chiaro; *conn_flags* il tipo di client."""
	return split(TYPE_AUTH, 0, sequence, settings, _UNION_CONNECTION.pack(0, conn_flags))


def abort_request(sequence):
	"""Interrompe la richiesta *sequence* in corso."""
	return Header(TYPE_ABORT, FLAG_HEAD, sequence, 0).pack()


def abort_all_request():
	"""Interrompe tutte le richieste in esecuzione (``interrupt()``)."""
	return Header(TYPE_ABORT_ALL, FLAG_HEAD, 0, 0).pack()


def session_key(client_id, server_id):
	"""Chiave dei cifrari di una connessione, come in ConnectJob: ID del client e del server."""
	return struct.pack('<IQ', client_id, server_id)


class Codec(object):
	"""Codifica delle richieste DATA e cifrario di una connessione autorizzata. *flags* sono quelli
	della risposta AUTH (cifrario ed eventuale compressione), che il client ripete in ogni
	richiesta come fa CL_TCPClient."""

	def __init__(self, flags, client_id, server_id):
		self.flags = flags
		self.cipher = _Cipher(flags, session_key(client_id, server_id))

	def data_request(self, sequence, command, data):
		"""Pacchetti della richiesta *command* con i dati *data* (tabella CLU già codificata)."""
		flags = self.flags
		union = _UNION_DATA.pack(command, checksum(data))
		if data:
			if flags & FLAG_COMPRESS:
				try:
					data = zlib.compress(data)
				except zlib.error:
					flags &= ~FLAG_COMPRESS
			data = self.cipher.encrypt(data)
		return split(TYPE_DATA, flags, sequence, data, union)

	def user_message(self, text, targets=()):
		"""Il pacchetto di un messaggio utente per i client *targets* (ID), o per tutti se vuoto:
		uno solo, cifrato come una richiesta e senza risposta. Il server lo inoltra ai client che
		hanno chiesto i messaggi utente alla connessione (``user_messages``)."""
		data = _clu_encode({ 'targets': [ int(target) for target in targets ], 'text': str(text) })
		if len(data) > PACKET_SIZE:
			raise ValueError('user message too long')
		union = _UNION_MESSAGE.pack(0, checksum(data))
		return Header(TYPE_USER_MESSAGE, FLAG_HEAD, 0, len(data), union).pack() + self.cipher.encrypt(data)

	def decode_user_message(self, header, payload):
		"""Un messaggio utente arrivato dal server: ``(mittente, testo)``, o None se non è
		valido."""
		if (not (header.flags & FLAG_HEAD)) or (header.size != len(payload)):
			return None
		data = self.cipher.decrypt(payload) if payload else b''
		if checksum(data) != header.message_checksum:
			return None
		try:
			message = _clu_decode(data)
		except ValueError:
			return None
		return header.source, str(message.get('text') or '')


class PacketReader(object):
	"""Divide in pacchetti i byte che arrivano dal server."""

	def __init__(self):
		self.buffer = bytearray()

	def feed(self, data):
		"""Aggiunge *data* e restituisce i pacchetti completi come coppie ``(header, payload)``.
		Solleva :class:`ProtocolError` se un header non ha il magic giusto."""
		self.buffer += data
		packets = []
		while len(self.buffer) >= HEADER_SIZE:
			header = Header.unpack(self.buffer)
			if header.magic != MAGIC:
				raise ProtocolError('bad packet magic 0x%08x' % header.magic)
			length = min(header.size, PACKET_SIZE)
			if len(self.buffer) < HEADER_SIZE + length:
				break
			payload = bytes(self.buffer[HEADER_SIZE:HEADER_SIZE + length])
			del self.buffer[:HEADER_SIZE + length]
			packets.append((header, payload))
		return packets


class Ping(object):
	"""Avanzamento di una richiesta in esecuzione sul server."""
	__slots__ = ('completeness', 'message')

	def __init__(self, completeness, message):
		self.completeness = completeness
		self.message = message


class Reply(object):
	"""Risposta completa a una richiesta: *status* è ``OK``, ``EXECUTE_FAILED`` (con i dati, la
	tabella d'errore del server), ``EXECUTE_ABORTED``, ``BAD_REPLY``, oppure l'esito della
	stretta di mano; *header* è quello del primo pacchetto."""
	__slots__ = ('status', 'header', 'data')

	def __init__(self, status, header, data):
		self.status = status
		self.header = header
		self.data = data


class ReplyAssembler(object):
	"""Ricompone la risposta a una richiesta dai suoi pacchetti (tutti con la stessa sequenza).
	*cipher* decifra ogni pacchetto (None per le risposte della stretta di mano, in chiaro anche
	se portano il flag di compressione); *check* controlla il checksum delle risposte DATA,
	FAILED e ABORT."""

	def __init__(self, cipher=None, check=True):
		self.cipher = cipher
		self.check = check
		self.header = None
		self.remaining = 0
		self.parts = []
		self.inflater = None
		self.message = ''

	@property
	def receiving(self):
		"""True dopo il primo pacchetto della risposta (i PING non contano più)."""
		return self.header is not None

	def feed(self, header, payload):
		"""Elabora un pacchetto: restituisce un :class:`Ping`, la :class:`Reply` completa, o None
		se la risposta non è ancora completa."""
		if self.header is None:
			if header.type == TYPE_PING:
				if header.size > 0:
					self.message = payload.split(b'\0', 1)[0].decode('utf-8', 'replace')
				return Ping(header.completeness, self.message)
			if not (header.flags & FLAG_HEAD):
				return None
			self.header = header
			self.remaining = header.size
			if (self.cipher is not None) and (header.flags & FLAG_COMPRESS):
				self.inflater = zlib.decompressobj()
		elif header.type == TYPE_PING:
			# un PING può ancora arrivare mentre arriva la risposta: non conta
			return None
		self.remaining -= len(payload)
		if payload:
			if self.cipher is not None:
				payload = self.cipher.decrypt(payload)
			if self.inflater is not None:
				try:
					payload = self.inflater.decompress(payload)
				except zlib.error:
					return Reply(BAD_REPLY, self.header, b'')
			self.parts.append(payload)
		if self.remaining > 0:
			return None
		return self._complete()

	def _complete(self):
		header = self.header
		data = b''.join(self.parts)
		if self.cipher is None:
			# stretta di mano: SERVER_INFO, AUTH, NO_AUTH
			return Reply(OK, header, data)
		# Una risposta ABORT non ha dati ma porta il checksum della richiesta: il tipo va
		# guardato prima del checksum
		if header.type == TYPE_ABORT:
			return Reply(EXECUTE_ABORTED, header, b'')
		if self.check and (checksum(data) != header.checksum):
			return Reply(BAD_REPLY, header, data)
		if header.type == TYPE_DATA:
			return Reply(OK, header, data)
		if header.type == TYPE_FAILED:
			return Reply(EXECUTE_FAILED, header, data)
		return Reply(BAD_REPLY, header, data)
