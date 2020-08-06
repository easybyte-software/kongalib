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
from __future__ import absolute_import

import sys
import traceback
import atexit

from .compat import *

DEFAULT_DISCOVER_TIMEOUT	= 5000
DEFAULT_CONNECT_TIMEOUT		= 30000
DEFAULT_EXECUTE_TIMEOUT		= 10000

CRYPT_NONE					= 0
CRYPT_LOW					= 1
CRYPT_NORMAL				= 2
CRYPT_HIGH					= 3

PROGRESS_PROCESS			= 0
PROGRESS_SEND				= 1
PROGRESS_EXECUTE			= 2
PROGRESS_RECEIVE			= 3
PROGRESS_COMPLETE			= 4

NIC_UP						= 0x1
NIC_CAN_BROADCAST			= 0x2
NIC_CAN_MULTICAST			= 0x4
NIC_IS_LOOPBACK				= 0x8

PROGRESS_INDEFINITE			= -1.0

ROUND						= 1
FLOOR						= 2
CEIL						= 3

BACKUP_ON_COMPUTER			= 0x1			#: Il backup è posizionato in locale sulla macchina corrente
BACKUP_ON_CLOUD				= 0x2			#: Il backup è posizionato nel cloud



class Log(object):
	"""La classe Log serve ad immagazzinare i messaggi prodotti dal server durante un'operazione; oggetti di questa classe
	vengono popolati durante le chiamate asincrone della classe :class:`~kongalib.Client`.
	"""
	
	INFO		= 0		#: Costante che identifica i messaggi di tipo informativo
	WARNING		= 1		#: Costante che identifica i messaggi di tipo avviso
	ERROR		= 2		#: Costante che identifica i messaggi di tipo errore
	
	def __init__(self, title=''):
		self.title = title
		self.messages = []
		self.clear()
		self.state_stack = []
	
	def save(self):
		"""Salva lo stato del log"""
		self.state_stack.append((self.errors, self.warnings, len(self.messages)))
	
	def restore(self):
		"""Ripristina il log allo stesso stato in cui si trovava prima dell'ultima chiamata al metodo :meth:`save`."""
		self.errors, self.warning, count = self.state_stack.pop()
		self.messages[count:] = []
	
	def clear(self):
		"""Elimina tutti i messaggi presenti sul log."""
		self.messages[:] = []
		self.errors = False
		self.warnings = False
	
	def add_message(self, type, msg, name=None, row=None, colname=None):
		"""Aggiunge un messaggio *msg* di tipo *type*."""
		if type < Log.INFO or type > Log.ERROR:
			type = Log.ERROR
		self.messages.append((type, msg, name, row, colname))
		if type == Log.WARNING:
			self.warnings = True
		elif type == Log.ERROR:
			self.errors = True
	
	def info(self, message, name=None, row=None, colname=None):
		"""Esattamente come chiamare ``add_message(Log.INFO, message)``."""
		self.add_message(Log.INFO, message, name, row, colname)
	
	def warning(self, message, name=None, row=None, colname=None):
		"""Esattamente come chiamare ``add_message(Log.WARNING, message)``."""
		self.add_message(Log.WARNING, message, name, row, colname)
	
	def error(self, message, name=None, row=None, colname=None):
		"""Esattamente come chiamare ``add_message(Log.ERROR, message)``."""
		self.add_message(Log.ERROR, message, name, row, colname)
	
	def has_messages(self):
		"""Controlla la presenza di messaggi di qualsiasi tipo sul log."""
		return len(self.messages) > 0
	
	def has_warnings(self):
		"""Controlla la presenza di messaggi di tipo :attr:`WARNING` sul log."""
		return self.warnings
	
	def has_errors(self):
		"""Controlla la presenza di messaggi di tipo :attr:`ERROR` sul log."""
		return self.errors
	
	def get_messages(self, type=None):
		"""Ottiene la lista dei messaggi sul log. Se *type* è ``None``, tutti i messaggi vengono restituiti, altrimenti solo i messaggi di
		un determinato tipo."""
		if type is None:
			return self.messages
		return [ msg for msg in self.messages if msg[0] == type ]

	def get_exception(self, klass=RuntimeError):
		error = self.get_messages(Log.ERROR)[0][1]
		return klass(error)
	
	def strip_html(self, html):
		"""Elimina tutto il codice HTML dalla stringa in *html*, lasciando solo le parti testuali."""
		try:
			from HTMLParser import HTMLParser
		except:
			from html.parser import HTMLParser

		class Stripper(HTMLParser):
			def __init__(self):
				self.convert_charrefs = True
				self.reset()
				self.fed = []
				self.feed(html)
			def handle_starttag(self, tag, attrs):
				if tag == 'br':
					self.fed.append('\n')
			def handle_startendtag(self, tag, attrs):
				if tag == 'br':
					self.fed.append('\n')
			def handle_data(self, d):
				self.fed.append(d)
			def get_data(self):
				return ''.join(self.fed)
		return Stripper().get_data()
	
	def format_message(self, message):
		"""Ritorna *message* formattato correttamente per essere visualizzato. *message* deve essere una tupla di almeno due elementi:
		``(tipo, testo)``, dove ``tipo`` è uno tra :attr:`INFO`, :attr:`WARNING` ed :attr:`ERROR`, mentre ``testo`` è il corpo del messaggio,
		che può includere codice HTML (che verrà soppresso nella formattazione)."""
		type = ('INFO', 'WARNING', 'ERROR')
		msg = ensure_text(self.strip_html(message[1]))
		return u'[%s] %s' % (type[message[0]], msg)
	
	def dumps(self):
		"""Esegue un dump dei messaggi presenti sul log e restituisce un'unica stringa. Eventuale codice HTML presente nei messaggi è eliminato
		usando :meth:`strip_html`."""
		return u'\n'.join([ self.format_message(message) for message in self.messages ])
	
	def dump(self, logger=None):
		"""Esattamente come :meth:`dumps` ma stampa il dump su ``stdout``. Se ``logger`` è un'istanza di ``logging.Logger``, verrà usata per l'output
		invece di ``stdout``."""
		if logger is None:
			print(self.dumps())
		else:
			for message in self.get_messages():
				method = {
					Log.ERROR:		logger.error,
					Log.WARNING:	logger.warning,
				}.get(message[0], logger.info)
				method(ensure_text(self.strip_html(message[1])))



class Error(Exception):
	"""Rappresenza un errore generico generato dal server Konga. Eccezioni di questo tipo hanno due attributi:
	
	.. attribute:: errno
		
		Codice identificativo dell'errore
	
	.. attribute:: error
		
		Stringa che descrive l'errore
	"""
	def __init__(self, errno, msg):
		self.errno = errno
		self.error = self.msg = msg
	def __unicode__(self):
		msg = self.msg and ('%s' % self.msg) or '(internal error)'
		return ensure_text(msg)
	def __str__(self):
		if PY3:
			return self.__unicode__()
		else:
			return self.__unicode__().encode('utf-8')
	def __repr__(self):
		return '<Error %d: %s>' % (self.errno, str(self))



class ErrorList(Error):
	"""Rappresenza una lista di errori generati dal server Konga. Eccezioni di questo tipo hanno tre attributi:
	
	.. attribute:: errno
		
		Codice identificativo dell'ultimo errore
	
	.. attribute:: error
		
		Stringa che descrive l'ultimo errore
	
	.. attribute:: errors
	
		Lista degli errori, in cui ogni errore è una tupla nella forma ``(type, errno, prefix, error)``; *type* è uno tra :attr:`Log.INFO`,
		:attr:`Log.WARNING` e :attr:`Log.ERROR`; *errno* ed *error* sono il codice e la descrizione dell'errore, e *prefix* un eventuale
		prefisso che identifica il contesto dell'errore.
	"""
	
	PREPARE_CALLBACK = None

	def __init__(self, errors=None):
		self.errors = errors or []
		self.errno = OK
		self.error = 'No error'
		for type, errno, prefix, error in self.errors:
			if type == Log.ERROR:
				self.errno = errno
				self.error = error
				break
	
	def __unicode__(self):
		return u'\n'.join([ ensure_text(e) for e in self.get_errors() ])

	def __str__(self):
		if PY3:
			return self.__unicode__()
		else:
			return self.__unicode__().encode('utf-8')

	def __repr__(self):
		return '<ErrorList: %s>' % repr(self.get_errors())
	
	def __iter__(self):
		return iter(self.errors)
	
	def get_errors(self):
		return [ Error(errno, error) for type, errno, prefix, error in self.errors ]
	
	def add_error(self, errno, error, prefix=''):
		"""Aggiunge un errore (tipo :attr:`Log.ERROR`) al log, assegnando il codice e la descrizione da *errno* ed *error*.
		*prefix* è una stringa di prefisso e può essere usato per dare un contesto all'errore.
		"""
		self.errors.append((Log.ERROR, errno, prefix, error))
		self.errno = errno
		self.error = error
	
	def prepare_log(self, log=None):
		"""Trasferisce la lista degli errori su *log* e restituisce il log aggiornato. *log* deve essere un oggetto di classe :class:`~kongalib.Log`;
		se ``None``, un nuovo oggetto :class:`~kongalib.Log` verrà creato e popolato con gli errori.
		"""
		if ErrorList.PREPARE_CALLBACK is not None:
			return ErrorList.PREPARE_CALLBACK(self, log)
		if log is None:
			log = Log()
		for type, errno, prefix, error in self.errors:
			message = '%s (%d)' % (error, errno)
			if prefix:
				message = '%s %s' % (prefix, message)
			log.add_message(type, message)
		return log
	
	@classmethod
	def from_error(cls, errno, error, prefix=''):
		"""Costruisce un nuovo oggetto :class:`ErrorList` contenente un singolo errore (tipo :attr:`Log.ERROR`), assegnando il codice e la
		descrizione da *errno* ed *error*. *prefix* è una stringa di prefisso e può essere usato per dare un contesto all'errore.
		"""
		res = ErrorList()
		res.add_error(errno, error, prefix)
		return res
	
	@classmethod
	def from_exception(cls, e=None):
		"""Costruisce un nuovo oggetto :class:`ErrorList` contenente un singolo errore (tipo :attr:`Log.ERROR`), a partire dall'eccezione *e*;
		se *e* è ``None``, viene assunta l'eccezione corrente. L'errore creato avrà un codice *errno* valido se *e* è un'eccezione di classe
		:exc:`Error`, altrimenti sarà ``-1``.
		"""
		if e is None:
			e = sys.exc_info()[1]
		if isinstance(e, ErrorList):
			return e
		elif isinstance(e, Error):
			errno = e.errno
			error = e.msg
		else:
			errno = -1
			error = str(e)
		return cls.from_error(errno, error)
	
	@classmethod
	def set_prepare_callback(cls, callback):
		cls.PREPARE_CALLBACK = callback


class JSONError(Exception):
	def __init__(self, msg):
		self.msg = msg
	def __unicode__(self):
		return ensure_text(self.msg)
	def __str__(self):
		if PY3:
			return self.__unicode__()
		else:
			return self.__unicode__().encode('utf-8')


class InterpreterTimeout(Exception):
	pass


from ._kongalib import Decimal, Deferred, JSONEncoder, JSONDecoder, Interpreter, start_timer, hash_password, host_lookup, get_network_interfaces, get_machine_uuid, get_system_info, set_interpreter_timeout, _cleanup, lock, unlock, set_default_idle_callback, checksum, _aes_set_key, _aes_set_key, _aes_encrypt, _aes_decrypt, _apply_stylesheet
from .constants import *
from .client import *
from .expression import *
from .data_dictionary import *


class ErrorMessage(object):
	def __init__(self, errno, error):
		self.errno = errno
		self.error = error
		exc = sys.exc_info()
		if exc is None:
			self.traceback = None
		else:
			self.traceback = ''.join(traceback.format_exception(*exc))
	
	def __unicode__(self):
		return ensure_text(self.error if self.traceback is None else self.traceback)

	def __str__(self):
		if PY3:
			return self.__unicode__()
		else:
			return self.__unicode__().encode('utf-8')


class _AES(object):
	def set_key(self, key):
		_aes_set_key(key)
	def encrypt(self, data):
		return _aes_encrypt(data)
	def decrypt(self, data):
		return _aes_decrypt(data)
aes = _AES()


def _on_destroy_thread():
	import threading
	thread = threading.current_thread()
	thread._Thread__delete()


def round(number, ndigits=2):
	"""Arrotonda *number* a *ndigits* cifre decimali, arrotondando verso 0 se l'ultima cifra dopo l'arrotondamento è compresa tra 0
	e 5, altrimenti arrotonda allontanadosi da 0. Restituisce un oggetto :class:`~kongalib.Decimal`.
	"""
	return Decimal(number).round(10**(-ndigits))

def floor(number, ndigits=2):
	"""Arrotonda *number* a *ndigits* cifre decimali, arrotondando verso 0. Restituisce un oggetto :class:`~kongalib.Decimal`."""
	return Decimal(number).floor(10**(-ndigits))

def ceil(number, ndigits=2):
	"""Arrotonda *number* a *ndigits* cifre decimali, arrotondando allontanandosi da 0. Restituisce un oggetto :class:`~kongalib.Decimal`."""
	return Decimal(number).ceil(10**(-ndigits))

def multiply_and_round(x, y, ndigits=2):
	return Decimal(x).multiply(Decimal(y), 10**(-ndigits), ROUND)

def multiply_and_floor(x, y, ndigits=2):
	return Decimal(x).multiply(Decimal(y), 10**(-ndigits), FLOOR)

def multiply_and_ceil(x, y, ndigits=2):
	return Decimal(x).multiply(Decimal(y), 10**(-ndigits), CEIL)

def divide_and_round(x, y, ndigits=2):
	return Decimal(x).divide(Decimal(y), 10**(-ndigits), ROUND)

def divide_and_floor(x, y, ndigits=2):
	return Decimal(x).divide(Decimal(y), 10**(-ndigits), FLOOR)

def divide_and_ceil(x, y, ndigits=2):
	return Decimal(x).divide(Decimal(y), 10**(-ndigits), CEIL)

def escape(query):
	"""Sostituisce `'` con `''` per preparare una stringa all'inserimento SQL."""
	return query.replace("'", "''")


atexit.register(_cleanup)

