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


if not PY3:
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
			print('  ' + colorama.Style.BRIGHT + textwrap.fill(title) + colorama.Style.RESET_ALL)
			print()
		print(textwrap.fill(text))
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
			print(colorama.Style.BRIGHT + textwrap.fill(message) + colorama.Style.RESET_ALL)
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
			print(colorama.Style.BRIGHT + textwrap.fill(message) + colorama.Style.RESET_ALL)
		filename = input('Enter filename to be saved or none to cancel: ')
		return filename or None



def choose_directory(message=None, path=''):
	if _proxy.is_valid():
		return _proxy.ui.choose_directory(message, path)
	else:
		if message:
			print(colorama.Style.BRIGHT + textwrap.fill(message) + colorama.Style.RESET_ALL)
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
			print(colorama.Style.BRIGHT + textwrap.fill(title) + colorama.Style.RESET_ALL)
		set_progress()



def close_progress():
	if _proxy.is_valid():
		_proxy.ui.close_progress()
	else:
		print('\033[80D\033[2K', end='')
		sys.stdout.flush()



def set_progress(progress=None, message=None, state=None):
	if _proxy.is_valid():
		_proxy.ui.set_progress(progress, message, state)
	else:
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
			bar = '%s %s' % (elide(', '.join(text), 77), tick)
		else:
			progress = (progress * 30) // 100
			bar = '|%-30s| %s' % (('#' * progress), elide(', '.join(text), 46))
		print('\033[80D\033[2K' + bar, end='')
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
	return _proxy.ui.execute_form(form_data, title=None)

