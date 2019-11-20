# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import os, os.path
import atexit
import threading
import time
import textwrap
import string
import colorama

import kongautil

from kongalib.scripting import proxy as _proxy

PY3 = (sys.version_info[0] >= 3)


if PY3:
	basestring = str
else:
	input = raw_input



BUTTON_OK							= 0x0001
BUTTON_YES							= 0x0002
BUTTON_YES_ALL						= 0x0004
BUTTON_NO							= 0x0008
BUTTON_NO_ALL						= 0x0010
BUTTON_CANCEL						= 0x0020
BUTTON_OPEN							= 0x0040
BUTTON_SAVE							= 0x0080
BUTTON_SAVE_ALL						= 0x0100
BUTTON_CLOSE						= 0x0200
BUTTON_DISCARD						= 0x0400
BUTTON_APPLY						= 0x0800
BUTTON_RESET						= 0x1000
BUTTON_ABORT						= 0x2000
BUTTON_RETRY						= 0x4000
BUTTON_IGNORE						= 0x8000

ICON_ERROR							= 24
ICON_QUESTION						= 25
ICON_WARNING						= 26
ICON_INFORMATION					= 27



def _shutdown():
	try:
		_proxy.ui.shutdown()
	except:
		pass
atexit.register(_shutdown)
colorama.init()



def _get_term_width():
	if PY3:
		import shutil
		return shutil.get_terminal_size(fallback=(80, 24))[0]
	else:
		# from https://stackoverflow.com/questions/566746/how-to-get-linux-console-window-width-in-python
		if sys.platform == 'win32':
			try:
				from ctypes import windll, create_string_buffer
				h = windll.kernel32.GetStdHandle(-12)
				csbi = create_string_buffer(22)
				res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
			except:
				res = None
			if res:
				import struct
				(bufx, bufy, curx, cury, wattr, left, top, right, bottom, maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
				return right - left + 1
			else:
				return 80
		else:
			def ioctl_GWINSZ(fd):
				try:
					import fcntl, termios, struct
					cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
				except:
					return None
				return cr
			cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
			if not cr:
				try:
					fd = os.open(os.ctermid(), os.O_RDONLY)
					cr = ioctl_GWINSZ(fd)
					os.close(fd)
				except:
					pass
			if not cr:
				try:
					cr = (env['LINES'], env['COLUMNS'])
				except:
					return 80
			return int(cr[1])



def message_box(text, title='', buttons=BUTTON_OK, icon=ICON_INFORMATION):
	if _proxy.is_valid():
		return _proxy.ui.message_box(text, title, buttons, icon)
	else:
		print()
		if icon == ICON_WARNING:
			title = colorama.Fore.YELLOW + "WARNING" + (': ' if title else '') + colorama.Fore.RESET + (title or '')
		elif icon == ICON_ERROR:
			title = colorama.Fore.RED + "ERROR" + (': ' if title else '') + colorama.Fore.RESET + (title or '')
		if title:
			print('  ' + colorama.Style.BRIGHT + textwrap.fill(title, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
			print()
		print(textwrap.fill(text, width=_get_term_width() - 1))
		print()
		buttons_info = [
			( BUTTON_OK,		'ok'		),
			( BUTTON_YES,		'yes'		),
			( BUTTON_YES_ALL,	'yes all'	),
			( BUTTON_NO,		'no'		),
			( BUTTON_NO_ALL,	'no all'	),
			( BUTTON_CANCEL,	'cancel'	),
			( BUTTON_OPEN,		'open'		),
			( BUTTON_SAVE,		'save'		),
			( BUTTON_SAVE_ALL,	'save_all'	),
			( BUTTON_CLOSE,		'close'		),
			( BUTTON_DISCARD,	'discard'	),
			( BUTTON_APPLY,		'apply'		),
			( BUTTON_RESET,		'reset'		),
			( BUTTON_ABORT,		'abort'		),
			( BUTTON_RETRY,		'retry'		),
			( BUTTON_IGNORE,	'ignore'	),
		]
		buttons_map = {}
		labels = []
		for bit, label in buttons_info:
			if buttons & bit:
				for i, c in enumerate(label):
					if c not in buttons_map:
						buttons_map[c] = bit
						labels.append('%s(%s)%s' % (label[:i], c, label[i+1:]))
						break
				else:
					for c in string.ascii_letters:
						if c not in buttons_map:
							buttons_map[c] = bit
							labels.append('%s (%s)' % (label, c))
							break
		answer = None
		while answer not in buttons_map:
			answer = input(', '.join(labels) + ': ')
		return buttons_map[answer]



def open_file(message=None, specs=None, path='', multi=False):
	if _proxy.is_valid():
		return _proxy.ui.open_file(message, specs, path, multi)
	else:
		if message:
			print(colorama.Style.BRIGHT + textwrap.fill(message, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		while True:
			filename = input('Enter an existing filename to open or none to cancel: ')
			if not filename:
				return None
			if os.path.exists(filename) and os.path.isfile(filename):
				break
		return filename



def save_file(message=None, spec=None, path=''):
	if _proxy.is_valid():
		return _proxy.ui.save_file(message, spec, path)
	else:
		if message:
			print(colorama.Style.BRIGHT + textwrap.fill(message, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		filename = input('Enter filename to be saved or none to cancel: ')
		return filename or None



def choose_directory(message=None, path=''):
	if _proxy.is_valid():
		return _proxy.ui.choose_directory(message, path)
	else:
		if message:
			print(colorama.Style.BRIGHT + textwrap.fill(message, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		while True:
			dirname = input('Enter an existing directory to open or none to cancel: ')
			if not dirname:
				return None
			if os.path.exists(dirname) and os.path.isdir(dirname):
				break
		return dirname



def select_record(tablename, multi=False, size=None, where_expr=None, code_azienda=None, num_esercizio=None):
	if _proxy.is_valid():
		return _proxy.ui.select_record(tablename, multi, size, where_expr, code_azienda=code_azienda, num_esercizio=num_esercizio)
	else:
		raise kongautil.KongaRequiredError



def open_progress(title=None, cancellable=True):
	if _proxy.is_valid():
		_proxy.ui.open_progress(title or u'Operazione in corso…', cancellable)
	else:
		if title:
			print(colorama.Style.BRIGHT + textwrap.fill(title, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		set_progress()



def close_progress():
	if _proxy.is_valid():
		_proxy.ui.close_progress()
	else:
		print('\033[2K\r', end='')
		sys.stdout.flush()



def set_progress(progress=None, message=None, state=None):
	if _proxy.is_valid():
		_proxy.ui.set_progress(progress, message, state)
	else:
		term_width = _get_term_width()
		def elide(s, width):
			if len(s) > width:
				parts = s.split(' ')
				mid = len(parts) // 2
				before = parts[:mid]
				after = parts[mid:]
				while before or after:
					if len(before) > len(after):
						del before[-1]
					elif after:
						del after[-1]
					s = ' '.join(before) + ' [...] ' + ' '.join(after)
					if len(s) <= width:
						break
			if len(s) > width:
				s = s[:width - 6] + ' [...]'
			return s
		text = []
		if message:
			text.append(message)
		if state:
			text.append(state)
		if not text:
			text.append('Operazione in corso...')
		if (progress is None) or (progress < 0):
			tick = ('\\', '|', '/', '-')[int(time.time() * 5) % 4]
			bar = '%s %s' % (elide(', '.join(text), term_width - 3), tick)
		else:
			if PY3:
				block = u'\u2588'
			else:
				block = '#'
			progress = (block * ((progress * 30) // 100))
			bar = '|%-30s| %s' % (progress, elide(', '.join(text), term_width - 34))
		print('\033[2K\r' + bar, end='')
		sys.stdout.flush()



def is_progress_aborted():
	if _proxy.is_valid():
		return _proxy.ui.is_progress_aborted()
	else:
		return False



def open_window(command, key_id=None, key_code=None, code_azienda=None, num_esercizio=None):
	if _proxy.is_valid():
		_proxy.ui.open_window(command, key_id, key_code, code_azienda, num_esercizio)
	else:
		raise kongautil.KongaRequiredError



def execute_form(form_data, title=None):
	if _proxy.is_valid():
		return _proxy.ui.execute_form(form_data, title=None)
	else:
		import kongalib, decimal, datetime, getpass
		class InvalidInput(RuntimeError):
			pass
		if title:
			print(colorama.Style.BRIGHT + textwrap.fill(title, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		result = {}
		for entry in form_data:
			if not isinstance(entry, dict):
				raise RuntimeError("Expected dict as form data entry")
			if 'name' not in entry:
				raise RuntimeError("Expected 'name' key in form data entry dict")
			name = str(entry['name'])
			label = str(entry.get('label', name))
			prompt = input
			wtype = entry.get('type', str)
			if wtype in ('decimal', kongalib.Decimal, decimal.Decimal):
				try:
					default = str(kongalib.Decimal(entry.get('default', 0)))
				except:
					default = str(kongalib.Decimal(0))
				def validate(text):
					try:
						return kongalib.Decimal(text)
					except:
						raise InvalidInput('Expected decimal number')
			elif wtype in ('range', 'slider'):
				try:
					default = str(int(entry.get('default', 0)))
				except:
					default = '0'
				try:
					min_value = int(entry.get('min', 0))
				except:
					min_value = 0
				try:
					max_value = int(entry.get('max', 100))
				except:
					max_value = 100
				label += ' (%d-%d)' % (min_value, max_value)
				def validate(text):
					try:
						value = int(text)
						if (value < min_value) or (value > max_value):
							raise RuntimeError
						return value
					except:
						raise InvalidInput('Expected integer number between %d and %d' % (min_value, max_value))
			elif wtype in ('bool', 'boolean', bool, 'check'):
				try:
					default = 'Y' if bool(entry.get('default', False)) else 'N'
				except:
					default = 'N'
				def validate(text):
					if text.lower() in ('t', 'true', 'y', 'yes', '1'):
						return True
					if text.lower() in ('f', 'false', 'n', 'no', '0'):
						return False
					raise InvalidInput('Expected boolean value')
			elif wtype in ('date', datetime.date):
				try:
					default = datetime.datetime.strptime(entry.get('default', datetime.date.today()), '%Y-%m-%d').date().isoformat()
				except:
					default = datetime.date.today().isoformat()
				def validate(text):
					try:
						return datetime.datetime.strptime(text, '%Y-%m-%d').date()
					except:
						raise InvalidInput('Expected iso date (YYYY-MM-DD)')
			elif wtype in ('choice', 'listbox', 'combobox'):
				items = entry.get('items', [])
				if (not isinstance(items, (tuple, list))) or (not all([ isinstance(item, basestring) for item in items ])):
					raise RuntimeError("Expected list of strings as 'items' value")
				print(label)
				for index, item in enumerate(items):
					print("%d) %s" % (index + 1, item))
				label = 'Enter selection'
				try:
					default = str(int(entry.get('default', 0)) + 1)
				except:
					default = '1'
				def validate(text):
					try:
						value = int(text)
						if (value < 1) or (value > len(items)):
							raise RuntimeError
						return value - 1
					except:
						raise InvalidInput('Expected integer number between %d and %d' % (1, len(items)))
			else:
				if wtype == 'password':
					prompt = getpass.getpass
					default = None
				else:
					try:
						default = str(entry.get('default', ''))
					except:
						default = ''
				try:
					length = int(entry.get('length', 0))
				except:
					length = 0
				def validate(text):
					if length and (len(text) > length):
						raise InvalidInput('String lengths exceeds maximum size of %d characters' % length)
					return text
			if default is not None:
				label += ' [%s]' % default
			while True:
				try:
					value = prompt(label + ': ')
				except KeyboardInterrupt:
					return None
				if (not value) and (default is not None):
					value = default
				try:
					value = validate(value)
					break
				except InvalidInput as e:
					print(colorama.Fore.RED + str(e) + colorama.Fore.RESET)
			result[name] = value
		return result



