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


from kongalib import Error, ErrorList
from .constants import *
from .compat import *


TYPE_TINYINT				= 1				#: Tipo di campo SQL TINYINT; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``int``.
TYPE_SMALLINT				= 2				#: Tipo di campo SQL SMALLINT; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``int``.
TYPE_INT					= 3				#: Tipo di campo SQL INT; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``int``.
TYPE_BIGINT					= 4				#: Tipo di campo SQL BIGINT; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``int``.
TYPE_FLOAT					= 5				#: Tipo di campo SQL FLOAT; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``float``.
TYPE_DOUBLE					= 6				#: Tipo di campo SQL DOUBLE; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``float``.
TYPE_DECIMAL				= 7
"""Tipo di campo SQL DECIMAL; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo :class:`kongalib.Decimal`.

.. warning:: Konga Server traduce automaticamente questo tipo di dato in BIGINT sul database SQL, e salva i valori decimali come se
	fossero interi moltiplicati per 1000000. Questo consente una precisione fino a 6 cifre decimali, e permette a Konga Server di operare anche
	con driver SQL che non supportano nativamente il tipo dato DECIMAL (come SQLite). La traduzione è completamente trasparente per kongalib, in
	quanto i metodi della classe :class:`kongalib.Client` ricevono e restituiscono oggetti di clase :class:`kongalib.Decimal` per gestire
	i decimali.
"""

TYPE_DATE					= 8				#: Tipo di campo SQL DATE; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``datetime.date``.
TYPE_TIME					= 9				#: Tipo di campo SQL TIME; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``datetime.time``.
TYPE_TIMESTAMP				= 10			#: Tipo di campo SQL TIMESTAMP; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``datetime.datetime``.
TYPE_YEAR					= 11			#: Tipo di campo SQL YEAR; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``int``.
TYPE_CHAR					= 12			#: Tipo di campo SQL CHAR; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``unicode``.
TYPE_VARCHAR				= 13			#: Tipo di campo SQL VARCHAR; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``unicode``.
TYPE_TINYTEXT				= 14			#: Tipo di campo SQL TINYTEXT; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``unicode``.
TYPE_TEXT					= 15			#: Tipo di campo SQL TEXT; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``unicode``.
TYPE_LONGTEXT				= 16			#: Tipo di campo SQL LONGTEXT; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``unicode``.
TYPE_TINYBLOB				= 17			#: Tipo di campo SQL TINYBLOB; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``bytes``.
TYPE_BLOB					= 18			#: Tipo di campo SQL BLOB; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``bytes``.
TYPE_LONGBLOB				= 19			#: Tipo di campo SQL LONGBLOB; i valori ottenuti dalla :meth:`~kongalib.Client.select_data` saranno di tipo ``bytes``.


TABLE_HAS_IMAGES			= 0x1			#: Flag informativo di tabella del data dictionary. Se specificato, i record della tabella possono avere immagini collegate.
TABLE_IS_INDEXED			= 0x2			#: Flag informativo di tabelle del data dictionary. Se specificato, la tabella è indicizzata per la ricerca full-text.

FIELD_UNSIGNED				= 0x1			#: Flag informativo di campo del data dictionary. Se specificato, il tipo dato è senza segno.
FIELD_UNIQUE				= 0x2			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL è UNIQUE.
FIELD_NOT_NULL				= 0x4			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL non può essere NULL.
FIELD_PRIMARY_KEY			= 0x8			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL è una PRIMARY KEY.
FIELD_FOREIGN_KEY			= 0x10			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL è una FOREIGN KEY.
FIELD_AUTO_INCREMENT		= 0x20			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL è un intero incrementato automaticamente.
FIELD_DEFAULT_NULL			= 0x40			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL ha NULL come valore di default.
FIELD_DEFAULT_CURRENT_TS	= 0x80			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL ha il timestamp corrente come valore di default.
FIELD_DEFAULT				= 0xC0			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL ha un valore di default.
FIELD_ON_UPDATE_CURRENT_TS	= 0x100			#: Flag informativo di campo del data dictionary. Se specificato, il campo SQL viene aggiornato automaticamente al timestamp corrente su UPDATE.
FIELD_ON_DELETE_CASCADE		= 0x200			#: Flag informativo di campo del data dictionary. Se specificato, su cancellazione di un record tutti i record ad esso collegati verranno cancellati a loro volta.
FIELD_ON_DELETE_SET_NULL	= 0x400			#: Flag informativo di campo del data dictionary. Se specificato, su cancellazione di un record tutti i record ad esso collegati avranno il collegamento impostato a NULL.

FIELD_HIDDEN				= 0x10000
FIELD_READ_ONLY				= 0x20000
FIELD_CHOICE				= 0x40000
FIELD_CODES					= 0x80000
FIELD_REQUIRED				= 0x100000



class DataDictionary(object):
	"""La classe DataDictionary contiene informazioni sul dizionario dei dati usato da un server Konga. Tramite questa classe è possibile
	ottenere la lista delle tabelle e dei campi, e informazioni specifiche su ogni campo.
	"""

	class Choice(object):
		"""Piccola classe che descrive le opzioni associate ad una scelta fissa del dizionario dei dati."""

		def __init__(self, data):
			self.__data = data
		
		def __getattr__(self, key):
			"""Ottiene il valore associato alla chiave *key*."""
			return self.__data[key][0]
		
		def get_label(self, key):
			"""Ottiene la descrizione della chiave *key* sotto forma di ``dict`` con le traduzioni corrispondenti a ciascuna lingua."""
			if isinstance(key, text_base_types):
				return self.__data[key][1]
			for value, label in self.__data.values():
				if value == key:
					return label

		def keys(self):
			"""Ottiene la lista delle chiavi supportate da questa *Choice*."""
			return list(self.__data.keys())
	
	
	def __init__(self, data):
		self.__data = data
		self.__table_data = {}
		tables = self.__data['tables']
		for name, tabledata in tables.items():
			self.__table_data[name.lower()] = tabledata
		missing_table = { 'fields': {} }

		self.__views = {
			'EB_CodiciFissi': {
				'desc': tables['EB_CodiciFissi1']['desc'],
				'flags': tables['EB_CodiciFissi1']['flags'],
				'EB_CodiciFissi1': tables['EB_CodiciFissi1']['fields'].keys(),
				'EB_CodiciFissi2': list(set(tables['EB_CodiciFissi2']['fields'].keys()) - set(tables['EB_CodiciFissi1']['fields'].keys())),
				'EB_CodiciFissi3': list(set(tables.get('EB_CodiciFissi3', missing_table)['fields'].keys()) - set(tables['EB_CodiciFissi1']['fields'].keys())),
			},
			'EB_Clienti': {
				'desc': tables['EB_ClientiFornitori']['desc'],
				'flags': tables['EB_ClientiFornitori']['flags'],
				'EB_ClientiFornitori': tables['EB_ClientiFornitori']['fields'].keys(),
			},
			'EB_Fornitori': {
				'desc': tables['EB_ClientiFornitori']['desc'],
				'flags': tables['EB_ClientiFornitori']['flags'],
				'EB_ClientiFornitori': tables['EB_ClientiFornitori']['fields'].keys(),
			},
		}
		for view in self.__views.values():
			fields = {}
			for component, cfields in view.items():
				if not component.startswith('EB_'):
					continue
				fields.update(tables.get(component, missing_table)['fields'])
			view.update({
				'fields': fields,
			})
		for view, viewinfo in self.__views.items():
			self.__table_data[view.lower()] = viewinfo

	def get_version(self):
		"""Ottiene la versione del dizionario dei dati come intero nella forma ``(major << 16) | (minor << 8) | revision``."""
		return self.__data['version']
	
	def get_tables_list(self):
		"""Ottiene la lista delle tabelle del dizionario dei dati."""
		return [ table for table in self.__data['tables'].keys() if table not in self.__views ]
	
	def get_table_info(self, tablename):
		"""Ottiene un ``dict`` con le informazioni sulla tabella *tablename*. Le chiavi significative sono *desc* (un ``dict`` con le traduzioni
		della descrizione della tabella) e *flags* (flag informativi sulla tabella; vedere le costanti :ref:`flag di tabella <table_flags>`).
		"""
		data = self.__table_data[tablename.lower()]
		return {
			'desc': data['desc'],
			'flags': data['flags']
		}
	
	def get_fields_list(self, tablename):
		"""Ottiene la lista dei campi per la tabella *tablename*. I nomi dei campi restituiti non includono il nome tabella."""
		return list(self.__table_data[tablename.lower()]['fields'].keys())
	
	def get_field_info(self, fieldname):
		"""Ottiene un ``dict`` con le informazioni sul campo *fieldname*. Il nome del campo deve essere nella forma ``<NomeTabella>.<NomeCampo>``.
		Le chiavi significative sono *desc* (un ``dict`` con le traduzioni della descrizione del campo), *type* (tipo di campo; vedere le
		costanti :ref:`tipi di campo <field_types>`), *default* (valore di default) e *flags* (flag informativi sul campo; vedere le costanti
		:ref:`flag di campo <field_flags>`).
		"""
		table, field = self.resolve_field(fieldname).split('.')
		return self.__table_data[table.lower()]['fields'][field].copy()
	
	def resolve_field(self, fieldname):
		"""Converte un nome campo dalla forma ``<NomeTabella>.[<CampoRef>.*]<NomeCampo>`` nella forma ``<NomeTabella>.<NomeCampo>``, risolvendo
		eventuali campi ref_* intermedi."""
		parts = fieldname.split('.')
		table = parts.pop(0)
		if len(parts) == 0:
			raise ValueError("Invalid field name")
		while True:
			fields_data = self.__table_data[table.lower()]['fields']
			field = parts.pop(0)
			if field not in fields_data:
				raise ValueError("Field '%s' not found in table '%s'" % (field, table))
			if len(parts) == 0:
				break
			table = fields_data[field]['reference']['table']
		return '%s.%s' % (table, field)
	
	def get_choice(self, choicename):
		"""Ottiene un oggetto ``Choice`` a partire dal nome della scelta *choicename*. L'oggetto può successivamente essere interrogato per
		ottenere informazioni su ogni opzione disponibile nella scelta."""
		data = {}
		options = self.__data['choices'][choicename]['options']
		for value, option_data in options.items():
			data[option_data['define']] = (int(value), option_data['option'])
		return DataDictionary.Choice(data)
	
	def get_translation_context(self, fieldname):
		try:
			table, fieldname = self.resolve_field(fieldname).split('.')
			context = '%s(%s)' % (table, fieldname)
			if context in self.__data['contexts']:
				return '%s.%s' % (table, fieldname)
		except:
			pass
		return None
	
	def get_data(self):
		return self.__data
	

