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



BUTTON_OK							= 0x0001		#: Bottone "Ok"
BUTTON_YES							= 0x0002		#: Bottone "Si"
BUTTON_YES_ALL						= 0x0004		#: Bottone "Si tutti"
BUTTON_NO							= 0x0008		#: Bottone "No"
BUTTON_NO_ALL						= 0x0010		#: Bottone "No tutti"
BUTTON_CANCEL						= 0x0020		#: Bottone "Annulla"
BUTTON_OPEN							= 0x0040		#: Bottone "Apri"
BUTTON_SAVE							= 0x0080		#: Bottone "Salva"
BUTTON_SAVE_ALL						= 0x0100		#: Bottone "Salva tutti"
BUTTON_CLOSE						= 0x0200		#: Bottone "Chiudi"
BUTTON_DISCARD						= 0x0400		#: Bottone "Tralascia"
BUTTON_APPLY						= 0x0800		#: Bottone "Applica"
BUTTON_RESET						= 0x1000		#: Bottone "Ripristina"
BUTTON_ABORT						= 0x2000		#: Bottone "Interrompi"
BUTTON_RETRY						= 0x4000		#: Bottone "Riprova"
BUTTON_IGNORE						= 0x8000		#: Bottone "Ignora"

ICON_ERROR							= 24			#: Icona di errore
ICON_QUESTION						= 25			#: Icona di domanda
ICON_WARNING						= 26			#: Icona di avviso
ICON_INFORMATION					= 27			#: Icona informativa



def _shutdown():
	try:
		_proxy.ui.shutdown()
	except:
		pass
atexit.register(_shutdown)

if not _proxy.is_valid():
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
	"""Mostra una finestra di dialogo modale con titolo *title*, messaggio *text* e icona *icon* (una delle costanti ``ICON_*``). La finestra mostrerà i bottoni identificati
	da *buttons*, che può contenere uno o più costanti ``BUTTON_*`` in *or* tra loro, e ritornerà la costante relativa al bottone selezionato dall'utente per chiudere la
	finestra."""
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
			try:
				answer = input(', '.join(labels) + ': ')
			except KeyboardInterrupt:
				print(colorama.Fore.YELLOW + "aborted" + colorama.Fore.RESET)
				if buttons & BUTTON_CANCEL:
					return BUTTON_CANCEL
				elif buttons & BUTTON_NO:
					return BUTTON_NO
				elif buttons & BUTTON_CLOSE:
					return BUTTON_CLOSE
				elif buttons & BUTTON_DISCARD:
					return BUTTON_DISCARD
				elif buttons & BUTTON_ABORT:
					return BUTTON_ABORT
				return buttons & ~(buttons - 1)
		return buttons_map[answer]



def open_file(message=None, specs=None, path='', multi=False):
	"""Mostra una finestra di caricamento file con titolo *message. *specs* può essere una lista di tuple ``(extension, description)`` per permettere di caricare solo
	file di tipi specifici; *path* è il percorso predefinito, e *multi* permette di selezionare più di un file da caricare.
	Se *multi* è ``False``, la funzione restituisce il percorso del file selezionato o ``None`` se l'utente ha annullato il caricamento, altrimenti restituisce la lista di file
	selezionati. Se eseguita al di fuori di Konga, questa funzione ignora i parametri *specs*, *path* e *multi*, e l'utente dovrà inserire il percorso completo del file da caricare;
	se verrà inserito un percorso vuoto, la funzione restituirà ``None``."""
	if _proxy.is_valid():
		return _proxy.ui.open_file(message, specs, path, multi)
	else:
		if message:
			print(colorama.Style.BRIGHT + textwrap.fill(message, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		while True:
			try:
				filename = input('Enter an existing filename to open or none to cancel: ')
			except KeyboardInterrupt:
				print(colorama.Fore.YELLOW + "aborted" + colorama.Fore.RESET)
				return None
			if not filename:
				return None
			if os.path.exists(filename) and os.path.isfile(filename):
				break
		return filename



def save_file(message=None, spec=None, path=''):
	"""Mostra una finestra di salvataggio file con titolo *message. *spec* può essere una tupla nella forma ``(extension, description)`` per permettere di salvare file di un
	tipo specifico; *path* è il percorso predefinito. La funzione restituisce il percorso del file da salvare oppure ``None`` se l'utente ha annullato il salvataggio.
	Se eseguita al di fuori di Konga, questa funzione ignora i parametri *specs* e *path*, e l'utente dovrà inserire il percorso completo del file da salvare;
	se verrà inserito un percorso vuoto, la funzione restituirà ``None``."""
	if _proxy.is_valid():
		return _proxy.ui.save_file(message, spec, path)
	else:
		if message:
			print(colorama.Style.BRIGHT + textwrap.fill(message, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		try:
			filename = input('Enter filename to be saved or none to cancel: ')
		except KeyboardInterrupt:
			print(colorama.Fore.YELLOW + "aborted" + colorama.Fore.RESET)
			return None
		return filename or None



def choose_directory(message=None, path=''):
	"""Mostra una finestra di selezione directory con titolo *message* e percorso iniziale *path*. La funzione restituisce il percorso della directory selezionata oppure ``None``
	se l'utente ha annullato l'operazione.
	Se eseguita al di fuori di Konga, questa funzione ignora il parametro *path*, e l'utente dovrà inserire il percorso completo della directory; se verrà inserito un percorso
	vuoto, la funzione restituirà ``None``."""
	if _proxy.is_valid():
		return _proxy.ui.choose_directory(message, path)
	else:
		if message:
			print(colorama.Style.BRIGHT + textwrap.fill(message, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		while True:
			try:
				dirname = input('Enter an existing directory to open or none to cancel: ')
			except KeyboardInterrupt:
				print(colorama.Fore.YELLOW + "aborted" + colorama.Fore.RESET)
				return None
			if not dirname:
				return None
			if os.path.exists(dirname) and os.path.isdir(dirname):
				break
		return dirname



def select_record(tablename, multi=False, size=None, where_expr=None, code_azienda=None, num_esercizio=None):
	"""Mostra una finestra di selezione record di Konga; la finestra mostrerà i record della tabella *tablename* e avrà dimensione *size* (tupla di due elementi nella forma
	``(width, height)``). *where_expr* può essere un'espressione SQL *WHERE* per filtrare i record selezionabili; *code_azienda* e *code_esercizio* filtrano ulteriormente
	i record visualizzati usando l'azienda e l'esercizio specificati.
	Se *multi* è ``True``, la funzione restituisce una lista di record selezionati sotto forma di ``dict``, altrimenti restituisce il ``dict`` del singolo record selezionato.
	In tutti i casi se l'utente annulla l'operazione, la funzione restituirà ``None``.
	
	.. warning::
	   Questa funzione è disponibile solo all'interno di Konga; eseguendola da fuori verrà lanciata l'eccezione :class:`kongautil.KongaRequiredError`.
	"""
	if _proxy.is_valid():
		return _proxy.ui.select_record(tablename, multi, size, where_expr, code_azienda=code_azienda, num_esercizio=num_esercizio)
	else:
		raise kongautil.KongaRequiredError



def open_progress(title=None, cancellable=True):
	"""Mostra una finestra di progresso con titolo *title*, potenzialmente annullabile dall'utente se *cancellable* è ``True``; la funzione ritorna immediatamente.
	Se eseguita fuori da Konga, questa funzione ignora il parametro *cancellable*."""
	if _proxy.is_valid():
		_proxy.ui.open_progress(title or u'Operazione in corso…', cancellable)
	else:
		if title:
			print(colorama.Style.BRIGHT + textwrap.fill(title, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		set_progress()



def close_progress():
	"""Nasconde la finestra di progresso precedentemente mostrata con :func:`kongaui.open_progress`."""
	if _proxy.is_valid():
		_proxy.ui.close_progress()
	else:
		print('\033[2K\r', end='')
		sys.stdout.flush()



def set_progress(progress=None, message=None, state=None):
	"""Imposta l'avanzamento corrente nella finestra di progresso precedentemente mostrata con :func:`kongaui.open_progress`. *progress* può essere ``None``
	per specificare un avanzamento indefinito, oppure un valore compreso tra 0 e 100 per specificare la percentuale di avanzamento completata. *message* e
	*state* sono messaggi aggiuntivi da mostrare nella finestra di avanzamento."""
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
			progress = (block * int((progress * 30) // 100))
			bar = '|%-30s| %s' % (progress, elide(', '.join(text), term_width - 34))
		print('\033[2K\r' + bar, end='')
		sys.stdout.flush()



def is_progress_aborted():
	"""Restituisce ``True`` se l'utente ha annullato la finestra di progresso precedentemente mostrata con :func:`kongaui.open_progress`."""
	if _proxy.is_valid():
		return _proxy.ui.is_progress_aborted()
	else:
		return False



def open_window(command, key_id=None, key_code=None, code_azienda=None, num_esercizio=None):
	"""Apre una finestra di Konga mostrando il comando *command*, ed eventualmente aprendo il record identificato univocamente o da *key_id* (ID del record), o
	dalla tupla (*key_code*, *code_azienda*, *code_esercizio*) (Codice del record, codice dell'azienda e codice dell'esercizio).
	
	.. warning::
	   Questa funzione è disponibile solo all'interno di Konga; eseguendola da fuori verrà lanciata l'eccezione :class:`kongautil.KongaRequiredError`.
	"""
	if _proxy.is_valid():
		_proxy.ui.open_window(command, key_id, key_code, code_azienda, num_esercizio)
	else:
		raise kongautil.KongaRequiredError



def execute_form(form_data, title=None, message=None, condition=None):
	"""Apre un form di immissione dati con titolo *title*; se *message* è specificato, il testo corrispondente sarà visualizzato in alto nella finestra del form.
	*form_data* deve essere una lista di ``dict`` con le specifiche dei campi da mostrare; nel ``dict``	di un singolo campo, l'unica chiave richiesta è ``name``,
	che deve identificare univocamente il nome del campo. E' possibile specificare l'etichetta da mostrare accando al campo stesso tramite la chiave ``label``;
	la tipologia di dato consentità è specificata tramite la chiave ``type``, che può assumere i valori:

	* ``str``: testo semplice, con possibile lunghezza massima ``length`` se la chiave è specificata;
	* ``password``: parola chiave;
	* ``int``: valore intero;
	* ``decimal``: valore decimale (:class:`kongalib.Decimal`);
	* ``range``: valore intero compreso tra un valore minimo (specificato dalla chiave ``min`` con valore predefinito ``0``) e un valore massimo (specificato dalla chiave ``max`` con valore predefinito ``100``);
	* ``slider``: simile a ``range`` ma viene visualizzato come cursore di selezione valore scorrevole;
	* ``bool``: valore booleano;
	* ``date``: data (``datetime.date``);
	* ``choice``: valore interno che identifica l'indice di una scelta tra quelle specificate nella chiave ``items`` (lista di stringhe);
	* ``listbox``: simile a ``choice`` ma viene visualizzato come lista di elementi da cui fare una scelta;
	* ``load``: nome di file esistente da caricare;
	* ``save``: nome di file da salvare;
	* ``dir``: nome di directory esistente;
	* ``code``: stringa di testo che identifica il codice di un record, la cui tabella è indicata dalla chiave ``table``;
	* ``company_code``: simile a ``code``, specifica l'azienda su cui gli altri campi ``code`` possono essere ricercati;
	* ``accounting_year_code``: simile a ``code``, specifica l'esercizio su cui gli altri campi ``code`` possono essere ricercati;

	Se presente, la chiave ``default`` permette di specificare il valore predefinito per un dato campo; inoltre se è presente la chiave ``focus`` (con qualsiasi
	valore), il campo corrispondente prenderà il focus all'avvio della finestra. Se l'utente annulla il form la funzione restituisce ``None``, altrimenti un
	``dict`` le cui chiavi sono i nome dei campi e i valori i dati immessi dall'utente.
	Il parametro *condition*, se presente, permette di specificare una condizione di validazione per il form sotto forma di espressione Python; i nomi dei campi
	specificati in *form_data* saranno disponibili come variabili nell'esecuzione di questa condizione, il cui esito determinerà se consentire o meno l'uscita
	dal form con successo."""
	if _proxy.is_valid():
		return _proxy.ui.execute_form(form_data, title, message, condition)
	else:
		import kongalib, decimal, datetime, getpass
		class InvalidInput(RuntimeError):
			pass
		if title:
			print(colorama.Style.BRIGHT + textwrap.fill(title, width=_get_term_width() - 1) + colorama.Style.RESET_ALL)
		if message:
			print(textwrap.fill(message, width=_get_term_width() - 1))
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
			if wtype in ('integer', 'int'):
				try:
					default = str(int(entry.get('default', 0)))
				except:
					default = '0'
				def validate(text):
					try:
						return int(text)
					except:
						raise InvalidInput('Expected integer number')
			elif wtype in ('decimal', kongalib.Decimal, decimal.Decimal):
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
					print(colorama.Fore.YELLOW + "aborted" + colorama.Fore.RESET)
					return None
				if (not value) and (default is not None):
					value = default
				try:
					value = validate(value)
					break
				except InvalidInput as e:
					print(colorama.Fore.RED + str(e) + colorama.Fore.RESET)
			result[name] = value
		if condition is not None:
			if not eval(condition, result.copy()):
				print(colorama.Style.BRIGHT + colorama.Fore.RED + "Form input data validation failed; aborted" + colorama.Style.RESET_ALL)
				result = None
		return result



