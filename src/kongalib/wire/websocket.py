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

"""Il flusso verso kongad nel browser (Pyodide): un ``WebSocket`` del browser verso il gateway del
servizio web di kongad (``/socket/client``), che inoltra i byte del protocollo IPC così come sono.

Il client web parla sempre con il server che lo ha servito: l'URL viene dalla pagina (o dal worker),
``wss://`` se la pagina è in https. :data:`URL` lo sostituisce (per le prove, con la pagina servita
da un altro server)."""

import asyncio

from .session import Stream


PATH = '/socket/client'

#: Dove il server che ha servito la pagina dice di sé quello che direbbe a una scoperta in UDP
DISCOVERY_PATH = '/client/discovery'

#: URL esplicito del gateway; ``None`` lo ricava dalla posizione della pagina
URL = None

# Oltre questo, i dati già affidati al WebSocket fanno attendere drain()
_HIGH_WATER = 4 * 1024 * 1024


def default_url():
	"""L'URL del gateway del server che ha servito la pagina (``location`` esiste anche nei worker)."""
	import js
	location = js.location
	scheme = 'wss:' if str(location.protocol) == 'https:' else 'ws:'
	return '%s//%s%s' % (scheme, location.host, PATH)


async def discover():
	"""Il server che ha servito la pagina come lo darebbe ``list_servers()``: una tupla con un
	dizionario (``host`` è quello della pagina), vuota se il server non si fa trovare."""
	import js
	response = await js.fetch(DISCOVERY_PATH, js.Object.fromEntries([ [ 'cache', 'no-store' ] ]))
	if not response.ok:
		return ()
	info = (await response.json()).to_py()
	info['host'] = str(js.location.hostname)
	return ( info, )


class WebSocketStream(Stream):
	"""Flusso su un ``WebSocket`` del browser: i messaggi binari arrivano in una coda, la chiusura è la
	fine del flusso."""

	def __init__(self, socket):
		self.socket = socket
		self.queue = asyncio.Queue()
		self.ended = False
		self.proxies = []

	@classmethod
	async def open(cls, host=None, port=None):
		"""Apre il WebSocket; *host* e *port* non contano (il server è quello della pagina)."""
		from js import WebSocket
		from pyodide.ffi import create_proxy

		socket = WebSocket.new(URL or default_url())
		socket.binaryType = 'arraybuffer'
		stream = cls(socket)
		opened = asyncio.get_running_loop().create_future()

		def on_open(event):
			if not opened.done():
				opened.set_result(None)

		def on_message(event):
			data = event.data
			if not isinstance(data, str):
				stream.queue.put_nowait(data.to_bytes())

		def on_close(event):
			# un rifiuto della stretta di mano (origine, servizio spento, tetto) chiude prima di aprire
			if not opened.done():
				opened.set_exception(ConnectionRefusedError('WebSocket closed (%s)' % event.code))
			stream.queue.put_nowait(b'')

		for name, handler in (('onopen', on_open), ('onmessage', on_message), ('onclose', on_close)):
			proxy = create_proxy(handler)
			stream.proxies.append(proxy)
			setattr(socket, name, proxy)
		try:
			await opened
		except BaseException:
			stream.close()
			raise
		return stream

	async def read(self):
		if self.ended:
			return b''
		data = await self.queue.get()
		if not data:
			self.ended = True
		return data

	def write(self, data):
		from pyodide.ffi import to_js
		self.socket.send(to_js(memoryview(data)))

	async def drain(self):
		while (self.socket is not None) and (not self.ended) and (self.socket.bufferedAmount > _HIGH_WATER):
			await asyncio.sleep(0.01)

	def close(self):
		socket, self.socket = self.socket, None
		if socket is None:
			return
		for name in ('onopen', 'onmessage', 'onclose'):
			setattr(socket, name, None)
		try:
			socket.close()
		except Exception:
			pass
		for proxy in self.proxies:
			proxy.destroy()
		self.proxies = []
		self.ended = True
		self.queue.put_nowait(b'')
