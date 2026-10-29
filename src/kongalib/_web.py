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
import re
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


# Come lo descrive il CL_GetComputerInfo() nativo di EBPR ("Windows 11, x86, 64 bit"), ma al posto del
# sistema il browser, che sul web conta di più, con il sistema tra parentesi ("Google Chrome
# 141.0.7390.55 (Windows 11), x86, 64 bit"). Le client hints di
# Chromium dicono la versione del sistema (lo user agent dice Windows 10 anche per l'11, e quello di
# Safari e Firefox macOS 10.15 per ogni macOS): chieste all'import, arrivano prima che servano; fino ad
# allora, e negli altri browser, vale lo user agent, che dice meno (solo "macOS", solo "Windows")
_hinted_system_info = None

_BROWSERS = (
	('Edge', re.compile(r'\b(?:Edg|EdgA|EdgiOS)/([\d.]+)')),
	('Opera', re.compile(r'\bOPR/([\d.]+)')),
	('Firefox', re.compile(r'\b(?:Firefox|FxiOS)/([\d.]+)')),
	('Chrome', re.compile(r'\b(?:Chrome|CriOS)/([\d.]+)')),
	('Safari', re.compile(r'\bVersion/([\d.]+).*Safari/')),
)


def _system_info(system, arch, bits, browser):
	"""Come il fOSSpec nativo, con il browser (e il sistema tra parentesi) al posto del sistema; poi
	l'architettura (``x86``, ``ARM``) e i bit (``64 bit``) dove si sanno."""
	if browser and system:
		system = '%s (%s)' % (browser, system)
	return ', '.join(part for part in (system or browser, arch, bits) if part)


def _parse_user_agent(ua, touch_points=0):
	"""Il browser e il sistema dallo user agent (lo user agent stesso se non ne dice nessuno)."""
	browser = ''
	for name, regexp in _BROWSERS:
		match = regexp.search(ua)
		if match:
			browser = '%s %s' % (name, match.group(1))
			break
	system = ''
	ios = re.search(r'\b(?:iPhone|iPad|iPod).*? OS (\d+(?:_\d+)*)', ua)
	if ios:
		system = 'iOS %s' % ios.group(1).replace('_', '.')
	elif re.search(r'\bMacintosh\b', ua):
		# (un iPad chiede i siti desktop come un Mac, con lo schermo touch)
		system = 'iPadOS' if touch_points > 1 else 'macOS'
	elif re.search(r'\bWindows\b', ua):
		system = 'Windows'
	elif re.search(r'\bAndroid\b', ua):
		android = re.search(r'\bAndroid ([\d.]+)', ua)
		system = ('Android %s' % android.group(1)) if android else 'Android'
	elif re.search(r'\bCrOS\b', ua):
		system = 'ChromeOS'
	elif re.search(r'\bLinux\b', ua):
		system = 'Linux'
	if not (browser or system):
		return ua
	# (Safari sui Mac con Apple Silicon dice Intel: dal Mac non si deduce nulla)
	if re.search(r'\b(?:x86_64|x64|Win64|amd64)\b', ua, re.I):
		arch, bits = 'x86', '64 bit'
	elif re.search(r'\b(?:aarch64|arm64)\b', ua, re.I):
		arch, bits = 'ARM', '64 bit'
	else:
		arch = bits = ''
	return _system_info(system, arch, bits, browser)


def _version(version):
	"""Come il nativo: major.minor, e la revisione se non è zero."""
	parts = (version.split('.') + [ '0', '0' ])[:3]
	return '.'.join(parts if parts[2] not in ('', '0') else parts[:2])


def _from_client_hints(values, brands, platform):
	"""Il browser e il sistema dalle client hints (i valori ad alta entropia, e i ``brands`` e la
	``platform`` di ``navigator.userAgentData``)."""
	# (il brand vero: non Chromium, che lo sono tutti, né quello GREASE)
	brands = [ (str(b.brand), str(b.version)) for b in (getattr(values, 'fullVersionList', None) or brands) ]
	brands = [ b for b in brands if not re.search(r'not.?a.?brand', b[0], re.I) ]
	brand = next((b for b in brands if b[0] != 'Chromium'), brands[0] if brands else None)
	platform = str(getattr(values, 'platform', None) or platform)
	version = str(getattr(values, 'platformVersion', None) or '')
	try:
		major = int(version.split('.')[0])
	except ValueError:
		major = 0
	system = platform
	if platform == 'Windows':
		system = 'Windows 11' if major >= 13 else ('Windows 10' if major > 0 else 'Windows')
	elif major and (platform in ('macOS', 'Android')):
		system = '%s %s' % (platform, _version(version))
	elif platform == 'Chrome OS':
		system = 'ChromeOS'
	arch = { 'arm': 'ARM', 'x86': 'x86' }.get(str(getattr(values, 'architecture', None) or ''), '')
	bitness = str(getattr(values, 'bitness', None) or '')
	bits = ('%s bit' % bitness) if bitness in ('32', '64') else ''
	return _system_info(system, arch, bits, ('%s %s' % brand) if brand else '') or None


def _ask_client_hints():
	js = _js()
	data = getattr(getattr(js, 'navigator', None), 'userAgentData', None) if js is not None else None
	if data is None:
		return
	def received(values):
		global _hinted_system_info
		_hinted_system_info = _from_client_hints(values, data.brands, data.platform)
	try:
		from pyodide.ffi import to_js
		data.getHighEntropyValues(to_js([ 'platformVersion', 'architecture', 'bitness', 'fullVersionList' ])).then(received)
	except Exception:
		# (vale lo user agent)
		pass


def get_system_info():
	"""Come quello nativo, con il browser in uso al posto del sistema, tra parentesi (``Google Chrome
	141.0.7390.55 (Windows 11), x86, 64 bit``)."""
	if _hinted_system_info:
		return _hinted_system_info
	js = _js()
	navigator = getattr(js, 'navigator', None) if js is not None else None
	ua = str(getattr(navigator, 'userAgent', '') or '')
	if not ua:
		return 'Pyodide'
	return _parse_user_agent(ua, int(getattr(navigator, 'maxTouchPoints', 0) or 0))


_ask_client_hints()


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
