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


import exceptions
import time
import datetime

from kongalib import Client, Decimal, Error as _Error, ErrorList
from .constants import *
from .compat import *


apilevel = "2.0"			#: Versione delle API, come da specifica
threadsafety = 2			#: E' possibile usare le funzioni di modulo e gli oggetti :class:`.Connection` da thread diversi
paramstyle = "format"		#: Il formato dei parametri nelle query deve essere nello stile printf (WHERE name=%s)


class Error(exceptions.Exception):
	"""Eccezione base, come da specifica."""
	def __init__(self, msg):
		self.msg = msg
	def __str__(self):
		return self.msg

class Warning(exceptions.Exception):
	pass

class InterfaceError(Error):
	pass

class DatabaseError(Error):
	pass

class InternalError(DatabaseError):
	"""Errore interno."""
	pass

class OperationalError(DatabaseError):
	"""Eccezione che viene lanciata su errori di connessione e/o comunicazione con il server Konga."""
	pass

class ProgrammingError(DatabaseError):
	"""Eccezione che viene lanciata se l'esecuzione di una query SQL ha generato un errore."""
	pass

class IntegrityError(DatabaseError):
	pass

class DataError(DatabaseError):
	pass

class NotSupportedError(DatabaseError):
	pass


class STRING(object):
	def __init__(self, string):
		self.string = string

class BINARY(object):
	def __init__(self, binary):
		self.binary = binary

class NUMBER(object):
	def __init__(self, number):
		self.number = number

class DATETIME(object):
	def __init__(self, datetime):
		self.datetime = datetime

class ROWID(object):
	pass


class Connection(Client):
	"""Classe che gestisce una connessione ad un server Konga. Viene usata per instanziare oggetti :class:`.Cursor` su cui poi operare, oppure
	per gestire le transazioni.
	"""
	def close(self):
		"""Chiude la connessione con il server Konga."""
		self.disconnect()
	
	def commit(self):
		"""Esegue una ``COMMIT`` per la transazione SQL corrente."""
		self.query("COMMIT")
	
	def rollback(self):
		"""Esegue una ``ROLLBACK`` per la transazione SQL corrente."""
		self.query("ROLLBACK")
	
	def cursor(self):
		"""Crea un nuovo oggetto :class:`Cursor` associato a questa connessione."""
		return Cursor(self)


class Cursor(object):
	"""Questa classe permette di eseguire query SQL sulla connessione *conn* ad essa associata. Per instanziare oggetti di classe :class:`Cursor`
	si usa il metodo :meth:`.Connection.cursor`.
	La classe può essere anche usato come iteratore; in tal caso per ogni ciclo verrà restituita la prossima riga del result set derivante
	dall'ultima query eseguita sul cursore stesso.
	"""
	def __init__(self, conn):
		self.__connection = conn
		self.__description = None
		self.__rowcount = -1
		self.__rownumber = 0
		self.__arraysize = 1
		self.__result = None
		self.__valid = True
	
	def close(self):
		"""Termina l'utilizzo di questo cursore; chiamate successive ai metodi di questo oggetto lanceranno un eccezione di tipo :exc:`.InternalError`."""
		self.__valid = False
	
	def execute(self, command, *args):
		"""Esegue la query SQL *command* sulla connessione associata al cursore; *command* può essere nel formato printf, e in tal caso
		*args* sono gli argomenti che vengono sostituiti nella stringa di formato.
		"""
		if not self.__valid:
			raise InternalError('cursor is not valid anymore')
		try:
			self.__rowcount, fields, self.__result = self.__connection.query(command % args)
		except _Error as e:
			if e.errno in (NOT_CONNECTED, CONNECTION_LOST, TIMED_OUT, BAD_REPLY):
				raise OperationalError(str(e))
			else:
				raise ProgrammingError(str(e))
		if len(self.__result) > 0:
			self.__rowcount = len(self.__result)
			self.__description = []
			row = self.__result[0]
			for field, data in zip(fields, row):
				if isinstance(data, int_types) or isinstance(data, (float, Decimal)):
					t = NUMBER
				elif isinstance(data, (datetime.date, datetime.datetime)):
					t = DATETIME
				elif isinstance(data, text_type):
					t = STRING
				else:
					t = BINARY
				self.__description.append((field, t, None, None, None, None, None))
			self.__rownumber = 0
		else:
			self.__result = None
			self.__description = None
			self.__rownumber = None
	
	def executemany(self, operation, seq):
		"""Esegue la stessa query SQL tante volte quanta la lunghezza della sequenza *seq*; l'elemento *N* di *seq* deve essere una tupla
		di argomenti da passare come *args* al metodo :meth:`execute` per eseguire la query *N*-esima.
		"""
		for args in seq:
			self.execute(operation, *tuple(args))
	
	def fetchone(self):
		"""Restituisce la prossima riga del result set ottenuto dall'ultima query eseguita su questo cursore. La riga è restituita sotto forma di
		tupla di valori."""
		if self.__result is None:
			raise InternalError('no valid result set')
		if self.__rownumber >= len(self.__result):
			return None
		self.__rownumber += 1
		return tuple(self.__result[self.__rownumber - 1])
	
	def fetchmany(self, size=None):
		"""Restituisce una lista di righe in cui ogni riga è nello stesso formato restituito da :meth:`fetchone`. La lista includerà al massimo
		*size* righe; se *size* è ``None``, verranno incluse al massimo :attr:`arraysize` righe.
		"""
		if size is None:
			size = self.__arraysize
		result = []
		for c in range(0, size):
			result.append(self.fetchone())
		return result
	
	def fetchall(self):
		"""Restituisce tutte le righe del result set corrente."""
		size = len(self.__result or []) - (self.__rownumber or 0)
		return self.fetchmany(size)
	
	def __iter__(self):
		return self
	
	def __next__(self):
		row = self.fetchone()
		if row is None:
			raise StopIteration
		return row

	def next(self):
		return self.__next__()
	
	def setinputsizes(self, sizes):
		pass
	
	def setoutputsize(self, size, column):
		pass
	
	@property
	def connection(self):
		"""Proprietà in sola lettura che restituisce l'oggetto :class:`Connection` associato a questo cursore."""
		return self.__connection
	
	@property
	def rowcount(self):
		"""Proprietà in sola lettura che restituisce il numero di righe del result set corrente."""
		return self.__rowcount
	
	@property
	def rownumber(self):
		"""Proprietà in sola lettura che restituisce il numero di riga corrente all'interno del result set."""
		return self.__rownumber
	
	@property
	def arraysize(self):
		"""Proprietà in lettura/scrittura che specifica il numero massimo di righe da includere nel risultato di :meth:`fetchmany` se *size* è ``None``."""
		return self.__arraysize
	
	@arraysize.setter
	def arraysize(self, size):
		self.__arraysize = size


def Date(year, month, day):
	return datetime.date(year, month, day)

def Time(hour, minute, second):
	return datetime.time(hour, minute, second)

def Timestamp(year, month, day, hour, minute, second):
	return datetime.datetime(year, month, day, hour, minute, second)

def DateFromTicks(ticks):
	return Date(*time.localtime(ticks)[:3])

def TimeFromTicks(ticks):
	return Time(*time.localtime(ticks)[3:6])

def TimestampFromTicks(ticks):
	return Timestamp(*time.localtime(ticks)[:6])

def connect(host, port=0, driver=None, database=None, user=None, password=None):
	"""Esegue una connessione al server Konga identificato da *host* e *port*, apre *database* usando il *driver* specificato,
	ed infine si autentica usando *user* e *password*. Restituisce un oggetto :class:`Connection`; da questo è possibile ottenere un oggetto
	:class:`Cursor` che permette di eseguire query SQL sul database aperto sulla connessione.
	"""
	conn = Connection()
	try:
		conn.connect({ 'host': host, 'port': port })
		conn.open_database(driver, database)
		conn.authenticate(user, password)
	except _Error as e:
		raise OperationalError(str(e))
	return conn


