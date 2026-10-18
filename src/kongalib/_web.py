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

"""Le funzioni di sistema di :mod:`_kongalib` dove il modulo è ridotto al nucleo (``CORE_ONLY``),
cioè nel browser (Pyodide): qui non ci sono rete, processi né sistema operativo, e queste versioni
tengono il comportamento più vicino possibile a quello desktop o non fanno nulla."""

import os
import uuid


_MACHINE_UUID_KEY = 'kongalib.machine_uuid'
_machine_uuid = None


def _js():
	try:
		import js
		return js
	except ImportError:
		# modulo ridotto su CPython (prove senza browser)
		return None


class NamedSemaphore(object):
	"""Semaforo con nome: nel browser c'è un solo processo, e non serve a nulla."""

	def __init__(self, *args, **kwargs):
		pass

	def acquire(self):
		pass

	def release(self):
		pass


def host_lookup(address):
	"""Nel browser non si risolvono nomi: restituisce l'indirizzo così com'è."""
	return address


def get_network_interfaces():
	"""Nel browser le interfacce di rete non sono visibili."""
	return ()


def get_machine_uuid():
	"""UUID della "macchina": generato al primo uso e conservato nel ``localStorage`` del browser, dove
	c'è (non nei worker); altrimenti vale per la sessione."""
	global _machine_uuid
	if _machine_uuid is None:
		js = _js()
		storage = getattr(js, 'localStorage', None) if js is not None else None
		value = None
		if storage is not None:
			try:
				value = storage.getItem(_MACHINE_UUID_KEY)
			except Exception:
				storage = None
		if not value:
			value = str(uuid.uuid4()).upper()
			if storage is not None:
				try:
					storage.setItem(_MACHINE_UUID_KEY, value)
				except Exception:
					pass
		_machine_uuid = value
	return _machine_uuid


def get_system_info():
	"""Il browser in uso (``navigator.userAgent``)."""
	js = _js()
	navigator = getattr(js, 'navigator', None) if js is not None else None
	return str(getattr(navigator, 'userAgent', '') or 'Pyodide')


def get_application_log_path():
	"""I log dell'applicazione: nel browser, sotto la cartella home di Pyodide."""
	return os.path.join(os.path.expanduser('~'), 'Logs')


def _set_process_foreground(foreground):
	pass


def set_default_idle_callback(callback):
	pass


def set_power_callbacks(suspend, resume):
	pass


def _apply_stylesheet(xml, xslt):
	"""Come quella nativa (libxslt), ma con :mod:`lxml`, che usa la stessa libxslt."""
	from lxml import etree
	try:
		transform = etree.XSLT(etree.fromstring(xslt.encode('utf-8') if isinstance(xslt, str) else xslt))
		output = str(transform(etree.fromstring(xml.encode('utf-8') if isinstance(xml, str) else xml)))
	except (etree.Error, ValueError) as e:
		raise ValueError('Error applying stylesheet: %s' % e)
	if not output:
		raise ValueError('Error applying stylesheet: empty result')
	return output
