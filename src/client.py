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


from __future__ import absolute_import

import threading

from kongalib import Error, ErrorList
from .constants import *
from .expression import *
from .data_dictionary import *
from .compat import *

from ._kongalib import Client as ClientImpl
from ._kongalib import start_timer


DEFAULT_DISCOVER_TIMEOUT		= 5000
DEFAULT_CONNECT_TIMEOUT			= 30000
DEFAULT_EXECUTE_TIMEOUT			= 180000

OUT_ERROR						= 'ERROR'
OUT_ERRNO						= 'ERRNO'

GET_FLAG_GET_MASK				= 0x000000FF
GET_FLAG_GET_IMAGES				= 0x00000001
GET_FLAG_GET_ATTACHMENTS		= 0x00000002
GET_FLAG_GET_NOTES				= 0x00000004
GET_FLAG_GET_EVENTS				= 0x00000008
GET_FLAG_GET_TRANSLATIONS		= 0x00000010
GET_FLAG_ACTION_MASK			= 0x00000F00
GET_FLAG_ACTION_COUNT			= 0x00000100
GET_FLAG_ACTION_LIST			= 0x00000200
GET_FLAG_ACTION_CONTENTS		= 0x00000400
GET_FLAG_SKIP_MASK				= 0x000FF000
GET_FLAG_SKIP_SPECIAL_FIELDS	= 0x00001000
GET_FLAG_SKIP_ROWS				= 0x00002000
GET_FLAG_SKIP_NORMAL_FIELDS		= 0x00004000


GET_FLAG_DEFAULT				= GET_FLAG_GET_IMAGES | GET_FLAG_GET_ATTACHMENTS | GET_FLAG_GET_NOTES | GET_FLAG_GET_EVENTS | GET_FLAG_GET_TRANSLATIONS | GET_FLAG_ACTION_COUNT

IMAGE_NORMAL					= 1
IMAGE_WEB						= 2
IMAGE_THUMBNAIL					= 3


def make_callbacks(success, error, log=None):
	def callback(output, dummy):
		answer = output[OUT_LOG] or []
		error_list = ErrorList(answer)
		if output[OUT_ERRNO] == OK:
			if len(answer) > 0:
				if log is None:
					if error is not None:
						error(error_list)
				else:
					error_list.prepare_log(log)
					if log.has_errors():
						if error is not None:
							error(error_list)
					else:
						success(output)
			else:
				success(output)
		elif error is not None:
			if error_list.errno == OK:
				error(ErrorList.from_error(output[OUT_ERRNO], output[OUT_ERROR]))
			else:
				error(error_list)
	def errback(errno, errstr, dummy):
		if error is not None:
			error(ErrorList.from_error(errno, errstr))
	return callback, errback



def _check_result(output, result_callback=None):
	answer = output[OUT_LOG] or []
	e = ErrorList(answer)
	if e.errno != OK:
		raise e
	elif output[OUT_ERRNO] == OK:
		if result_callback is not None:
			return result_callback()
		return None
	raise Error(output[OUT_ERRNO], output[OUT_ERROR])



class Client(object):
	"""La classe Client permette di connettersi ad un server Konga e di eseguire comandi sullo stesso.
	
	Molti dei metodi di questa classe possono eseguire operazioni sia in maniera sincrona (bloccante) che asincrona tramite
	l'uso di una callback. Nel caso un metodo sia eseguito in modo asincrono, viene sempre restituito immediatamente un oggetto
	di classe :class:`~kongalib.Deferred`, e la callback viene eseguita a tempo debito in un thread separato.
	
	.. note:: Nelle chiamate asincrone spesso è possibile specificare una callback di *progress* e una di *error*. La *progress* deve
		essere nella forma ``progress(type, completeness, state, partial, userdata)``; i parametri interessanti di questa callback sono
		*completeness* (percentuale di completamento, ossia un numero che varia da 0.0 a 100.0; se -1.0 indica una percentuale di completamento
		indefinita) e *state* (stringa che specifica l'eventuale stato corrente dell'operazione). *userdata* è un parametro aggiuntivo che
		viene normalmente passato alla chiamata asincrona dall'utente per tenere traccia di un eventuale stato. La *error* deve essere nella
		forma ``error(errno, errstr, userdata)``; fare riferimento ai :ref:`codici di errore <error_codes>` per il significato dei parametri
		*errno* e del corrispettivo *errstr*.
	
	Oggetti di classe Client possono essere usati come contesti per il costrutto ``with``: all'ingresso del blocco verrà iniziata una
	transazione, mentre in uscita verrà eseguita una commit o una rollback della stessa a seconda che ci sia stata o meno un'eccezione
	all'interno del blocco di istruzioni.
	"""
	
	DATA_DICTIONARY_CACHE = {}
	DATA_DICTIONARY_LOCK = threading.RLock()
	
	def __init__(self):
		self._impl = ClientImpl()
	
	def __enter__(self):
		self.begin_transaction()
		return self

	def __exit__(self, exc_type, exc_value, exc_traceback):
		if exc_type is None:
			self.commit_transaction()
		else:
			self.rollback_transaction()
	
	def list_servers(self, timeout=DEFAULT_DISCOVER_TIMEOUT, port=0, success=None, progress=None, userdata=None):
		"""Esegue una scansione della rete locale alla ricerca dei server Konga disponibili, attendendo al massimo *timeout* millisecondi
		per una risposta. *port* specifica la porta da cui far partire la scansione (default = 51967); sono controllate le successive 10
		porte UDP con intervallo di 20 porte (quindi di default vengono scansionate le porte 51967, 51987, 52007, ... 52147). Se *success*
		è ``None``, la funzione è bloccante e scaduto il *timeout* restituisce una lista di ``dict``, le cui chiavi principali sono *host*,
		*port*, *name* e *description*. Al contrario, se *success* è una funzione nella forma ``success(servers, userdata)``, ``list_servers``
		restituisce immediatamente un oggetto :class:`~kongalib.Deferred` e la chiamata viene eseguita in modo asincrono; la callback *success*
		verrà invocata a tempo debito con la lista dei risultati (come nel risultato del caso sincrono) ed il parametro *userdata*.
		"""
		return self._impl.list_servers(timeout, port, success, progress, userdata)
	
	def connect(self, server=None, host=None, port=0, options=None, timeout=DEFAULT_CONNECT_TIMEOUT, success=None, error=None, progress=None, userdata=None):
		"""Tenta una connessione ad un server Konga. Il server a cui ci si vuole connettere può essere specificato in due modi: tramite i
		parametri *host* e *port*, oppure tramite un ``dict`` *server* che deve contenere almeno le chiavi *host* e *port*. Alternativamente,
		se *server* è una stringa e *host* non è specificato, viene assunta come *host*. Se *host* include una specifica di porta e *port* è ``0``,
		*port* viene ottenuta dalla specifica contenuta nella stringa di *host*. Se *success* è ``None``, la funzione è bloccante; su errore o
		scaduto il *timeout* una eccezione di tipo :class:`~kongalib.Error` è lanciata, altrimenti viene restituito un ``dict`` con informazioni
		sulla connessione appena stabilita. Se *success* è una funzione nella forma ``success(info, userdata)`` allora ``connect`` restituisce
		immediatamente un oggetto :class:`~kongalib.Deferred` e la chiamata viene eseguita in modo asincrono; la callback *success* verrà
		invocata con le informazioni sulla connessione e *userdata* se e quando la connessione viene stabilita.
		Il parametro *options* può essere un ``dict`` contenente opzioni aggiuntive per la connessione; al momento le opzioni supportate sono:

		- ``tenant_key`` (*str*): chiave del tenant per stabilire la connessione con un server multitenant.
		"""
		if (server is None) and (host is None):
			raise ValueError("either 'host' or 'server' parameter must be specified")
		if isinstance(server, text_base_types) and (host is None):
			host = server
			server = None
		if isinstance(host, text_base_types) and (port is None) and (':' in host):
			pos = host.rfind(':')
			host = host[:pos]
			try:
				port = int(host[pos+1:])
			except:
				raise ValueError("Invalid port value embedded in host string")
		return self._impl.connect(server, host or '', port, options, timeout, success, error, progress, userdata)
	
	def disconnect(self):
		"""Disconnette il server attualmente connesso, oppure non fa nulla se non si è al momento connessi."""
		self._impl.disconnect()
	
	def get_id(self):
		"""Restituisce un ID numerico univoco assegnato dal server alla connessione con questo client, o 0 se non si è connessi."""
		return self._impl.get_id()
	
	def get_connection_info(self):
		"""Restituisce un ``dict`` con informazioni sulla connessione corrente, o ``None`` se non si è connessi."""
		return self._impl.get_connection_info()
	
	def execute(self, command, data=None, timeout=DEFAULT_EXECUTE_TIMEOUT, success=None, error=None, progress=None, idle=None, userdata=None):
		return self._impl.execute(command, data or {}, timeout, success, error, progress, idle, userdata)
	
	def interrupt(self):
		"""Interrompe tutte le operazioni al momento in esecuzione da parte di questo client."""
		self._impl.interrupt()

	def get_data_dictionary(self, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Restituisce il dizionario dei dati disponibile sul server attualmente connesso, sotto forma di oggetto di classe
		:class:`kongalib.DataDictionary`.
		"""
		uuid = self.get_connection_info().get('uuid', None)
		with Client.DATA_DICTIONARY_LOCK:
			if uuid is None:
				data = None
			else:
				data = Client.DATA_DICTIONARY_CACHE.get(uuid, None)
			if data is None:
				def cache(d):
					Client.DATA_DICTIONARY_CACHE[uuid] = d
					return d
				if success is not None:
					def callback(d, dummy):
						with Client.DATA_DICTIONARY_LOCK:
							success(cache(DataDictionary(d)))
					self._impl.get_data_dictionary(callback, error, progress, userdata, timeout)
				else:
					return cache(DataDictionary(self._impl.get_data_dictionary(success, error, progress, userdata, timeout)))
			else:
				if success is not None:
					def callback(dummy):
						success(data)
					start_timer(0, callback)
				else:
					return data
	
	def list_drivers(self, configured=True, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Restituisce la lista dei driver di database presenti sul server attualmente connesso, oppure lancia un'eccezione :class:`~kongalib.Error`
		su errore. Ogni elemento della lista restituita è un ``dict`` che comprende la chiavi *name*, *version* e *description*.
		Se *success* è ``None`` la funzione è bloccante, altrimenti se è una funzione nella forma ``success(drivers, userdata)``, restituisce
		immediatamente un oggetto :class:`~kongalib.Deferred` e la chiamata viene eseguita in modo asincrono; la callback *success* verrà
		invocata a tempo debito con la lista dei driver ed il parametro *userdata*. Se *configured* è False, tutti i driver installati sul
		server sono restituiti, altrimenti verranno restituite solo le informazioni sui driver configurati correttamente ed in esecuzione
		sul server.
		"""
		return self._impl.list_drivers(configured, success, error, progress, userdata, timeout)
	
	def list_databases(self, driver=None, quick=False, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Restituisce la lista dei database disponibili sul server corrente, appartenenti a tutti o ad uno specifico *driver*. La lista viene tornata
		sotto forma di ``dict``, le cui chiavi sono i nomi dei driver e i valori le liste dei database appartenenti allo specifico driver. Ogni
		database nelle liste è un ``dict`` che contiene almeno le chiavi *name*, *desc*, *uuid*, *created_ts* e *modified_ts*. L'eccezione
		:class:`~kongalib.Error` viene lanciata se si verifica un errore. Se *success* è una funzione nella forma ``success(databases, userdata)``,
		``list_databases`` restituisce immediatamente un oggetto :class:`~kongalib.Deferred` e la chiamata viene eseguita in modo asincrono; la
		callback *success* verrà invocata a tempo debito con la lista dei database ed il parametro *userdata*.
		"""
		return self._impl.list_databases(driver, quick, success, error, progress, userdata, timeout)
	
	def create_database(self, password, driver, name, desc='', success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Crea un nuovo database sul server attalmente connesso; il database avrà nome *name* e descrizione *desc*.
		Se *success* è ``None`` la chiamata è bloccante e se il database viene creato con successo viene restituito l'UUID del nuovo database;
		se si verifica un errore viene lanciata l'eccezione :class:`~kongalib.Error`.
		Se *success* è una funzione nella forma ``success(databases, userdata)``, ``create_database`` restituisce immediatamente un oggetto
		:class:`~kongalib.Deferred` e la chiamata viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con la
		lista dei database ed il parametro *userdata*.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.create_database(password, driver, name, desc, success, error, progress, userdata, timeout)
	
	def open_database(self, driver, name, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Apre un database rendendolo il database attivo per la connessione corrente. Se *success* è ``None``, la chiamata è bloccante e
		viene tornato un ``dict`` con le informazioni sul database connesso, oppure viene lanciata l'eccezione :class:`~kongalib.Error` in caso
		di errore. Se *success* è una funzione nella forma ``success(info, userdata)``, ``open_database`` restituisce immediatamente un oggetto
		:class:`~kongalib.Deferred` e la chiamata viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con le
		informazioni sul database ed il parametro *userdata*.
		"""
		return self._impl.open_database(driver, name, success, error, progress, userdata, timeout)
	
	def close_database(self, backup=False, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Chiude il database attivo sulla connessione corrente.
		Se *success* è ``None``, la chiamata è bloccante e viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con il parametro *userdata*.
		
		.. note:: Se *backup* è ``True``, il server esegue un backup automatico del database prima di chiuderlo.
		"""
		return self._impl.close_database(backup, success, error, progress, userdata, timeout)
	
	def upgrade_database(self, password, driver, name, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Aggiorna il database specificato all'ultima versione disponibile.
		Se *success* è ``None``, la chiamata è bloccante e viene restituita una tupla (log, old_version, new_version), dove il log dell'operazione
		è sotto forma di una lista di stringhe, oppure viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore. Se *success* è una
		funzione nella forma ``success(log, old_version, new_version, userdata)``, ``upgrade_database`` restituisce immediatamente un oggetto
		:class:`~kongalib.Deferred` e la chiamata viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con il
		log dell'operazione, la vecchia versione dati, la nuova versione dati ed il parametro *userdata*.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.upgrade_database(password, driver, name, success, error, progress, userdata, timeout)
	
	def delete_database(self, password, driver, name, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Cancella il database specificato.
		Se *success* è ``None``, la chiamata è bloccante e viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con il parametro *userdata*.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.delete_database(password, driver, name, success, error, progress, userdata, timeout)
	
	def query(self, query, native=False, full_column_names=False, collapse_blobs=False, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue una query SQL sul database attivo nella connessione corrente. Se *native* è ``True``, la query viene passata al driver
		del database senza essere interpretata, permettendo l'esecuzione di query native per l'RDBMS sottostante. Se *success* è ``None``, la
		chiamata è bloccante e viene restituita una tupla ``(affected_rows, column_names, result_set)``; *affected_rows* è il numero di righe
		coinvolte nella query di UPDATE/DELETE, *column_names* è una lista di nomi di colonne per il result set, mentre *result_set* è una lista
		di righe risultati della query, dove ogni riga è una lista di valori corrispondenti alle colonne restituite in *column_names*. In caso di
		errore viene lanciata l'eccezione :class:`~kongalib.Error`. Se *success* è una funzione nella forma
		``success(affected_rows, column_names, result_set, userdata)``, ``query`` restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e la chiamata viene eseguita in modo asincrono.
		
		.. note:: Se *full_column_names* è ``False``, *column_names* includerà i nomi delle colonne senza nome tabella, altrimenti saranno
			inclusi i nomi completi delle colonne. Se *collapse_blobs* è ``True``, i dati di tipo BLOB binari verranno restituiti come ``[...]``.
		"""
		return self._impl.query_database(query, native, full_column_names, collapse_blobs, success, error, progress, userdata, timeout)
	
	def backup_database(self, password, backup_name, driver, name, auto=True, overwrite=False, position=0, store_index=False, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue un backup del database specificato sul server attualmente connesso. Se *auto* è ``False``, è necessario specificare un nome
		per il backup tramite *backup_name*, altrimenti il backup viene considerato automatico ed un nome univoco è assegnato dal server. Se
		*overwrite* è ``False`` ed un backup con lo stesso nome esiste già sul server, non sarà possibile eseguire il backup. *position*
		permette di specificare dove eseguire il backup, ed è una combinazione delle costanti :const:`kongalib.BACKUP_ON_COMPUTER` e
		:const:`kongalib.BACKUP_ON_CLOUD`, mentre *store_index* specifica se includere l'indice di ricerca full-text nel backup.
		Se *success* è ``None``, la chiamata è bloccante e viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con il parametro *userdata*.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.backup_database(password, backup_name, driver, name, auto, overwrite, position, store_index, success, error, progress, userdata, timeout)
	
	def restore_database(self, password, backup_name, driver, name, change_uuid=True, overwrite=False, position=0, restore_index=True, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Ripristina un database a partire da un backup effettuato in precedenza sul server connesso. Se *overwrite* è False ed esiste un
		database gestito da *driver* con lo stesso nome, la funzione riporterà errore. *change_uuid* specifica se cambiare l'UUID associato al
		database oppure se ripristinare quello originale; se si hanno database con lo stesso nome gestiti da driver diversi è opportuno che
		almeno l'UUID per essi sia diverso, altrimenti si può incorrere in problemi di aliasing. *position* specifica da dove prendere il
		backup da rispristinare, e deve essere una delle costanti :const:`kongalib.BACKUP_ON_COMPUTER` o :const:`kongalib.BACKUP_ON_CLOUD`;
		*restore_index* invece permette di specificare se ripristinare o meno l'indice di ricerca qualora fosse contenuto all'interno del backup.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.restore_database(password, backup_name, driver, name, change_uuid, overwrite, position, restore_index, success, error, progress, userdata, timeout)
	
	def list_backups(self, position=0, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Ottiene la lista dei backup disponibili sul server connesso.
		Se *success* è ``None``, la chiamata è bloccante e restituisce una lista di backup; ogni backup è un ``dict`` che contiene almeno le chiavi
		*backup_name*, *uuid*, *date* e *size*; se si verifica un errore viene lanciata l'eccezione :class:`~kongalib.Error`.
		Se *success* è una funzione nella forma ``success(backups, userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con la lista dei backup ed il
		parametro *userdata*.
		"""
		return self._impl.list_backups(position, success, error, progress, userdata, timeout)
	
	def delete_backup(self, password, backup_name, position, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Cancella il backup identificato da *backup_name* dal server connesso.
		Se *success* è ``None``, la chiamata è bloccante e viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con il parametro *userdata*.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.delete_backup(password, backup_name, position, success, error, progress, userdata, timeout)
	
	def optimize_database(self, password, driver, name, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue una ottimizzazione del database specificato sul server attualmente connesso.
		Se *success* è ``None``, la chiamata è bloccante e viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con il parametro *userdata*.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.optimize_database(password, driver, name, success, error, progress, userdata, timeout)
	
	def repair_database(self, password, driver, name, output, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Prova a riparare il database danneggiato specificato, salvando il database recuperato in *output*.
		Se *success* è ``None``, la chiamata è bloccante e viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con il parametro *userdata*.
		
		.. note:: Non tutti i driver di database supportano questa operazione, e il recupero del database potrebbe fallire in ogni caso.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.repair_database(password, driver, name, output, success, error, progress, userdata, timeout)

	def index_database(self, password, driver, name, reset=False, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue una indicizzazione del database specificato sul server attualmente connesso. Se *reset* è ``False``, l'indicizzazione è
		incrementale, ovvero l'indice viene modificato per tenere conto solo dei record inseriti, modificati o cancellati dall'ultima
		indicizzazione; se invece *reset* è ``True``, l'indice viene prima cancellato e poi ricreato completamente.
		Se *success* è ``None``, la chiamata è bloccante e viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con il parametro *userdata*.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		return self._impl.index_database(password, driver, name, reset, success, error, progress, userdata, timeout)
	
	def list_clients(self, full=True, any=False, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		return self._impl.list_clients(full, any, success, error, progress, userdata, timeout)
	
	def get_client_info(self, id, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		return self._impl.get_client_info(id, success, error, progress, userdata, timeout)
	
	def kill_client(self, id, password, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		return self._impl.kill_client(id, password, success, error, progress, userdata, timeout)
	
	def authenticate(self, username, password, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT, new_password=None):
		"""Effettua un accesso al database attivo sulla connessione corrente, identificando l'utente tramite i parametri *username* e *password*.
		Se *success* è ``None``, la chiamata è bloccante e restituisce un ``dict`` con informazioni dettagliate sull'utente autenticato, oppure
		viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(info, userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con le informazioni sull'utente ed
		il parametro *userdata*.
		"""
		return self._impl.authenticate(username, password, success, error, progress, userdata, timeout, new_password)
	
	def full_text_search(self, text, limit, success=None, error=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue una ricerca full-text sul database attivo sulla connessione corrente, limitando la ricerca di *text* a *limit* risultati.
		Se *success* è ``None``, la chiamata è bloccante e restituisce una lista di risultati, dove ogni risultato è ``dict`` con almeno le chiavi
		*score*, *tablename*, *id* e *display*; in caso di errore viene lanciata l'eccezione :class:`~kongalib.Error`.
		Se *success* è una funzione nella format ``success(hits, userdata)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con i risultati della ricerca ed
		il parametro *userdata*.
		"""
		return self._impl.full_text_search(text, limit, success, error, progress, userdata, timeout)
	
	def get_permissions(self, user_id):
		output = self.execute(CMD_GET_PERMISSIONS, {
			IN_USER_ID: user_id
		})
		if output[OUT_ERRNO] != OK:
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
		return output[OUT_PERMISSIONS]
	
	def set_permissions(self, user_id, permissions):
		output = self.execute(CMD_SET_PERMISSIONS, {
			IN_USER_ID: user_id,
			IN_PERMISSIONS: permissions
		})
		if output[OUT_ERRNO] != OK:
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
	
	def begin_transaction(self, pause_indexing=False, deferred=False):
		"""Inizia una transazione sul database attivo nella connessione corrente. Se *pause_indexing* è ``True``, l'indicizzazione del
		database è disabilitata sul server. In caso di errore viene lanciata l'eccezione :class:`~kongalib.Error`.
		"""
		flags = 0
		if pause_indexing:
			flags |= 0x1
		if deferred:
			flags |= 0x2
		output = self.execute(CMD_BEGIN_TRANSACTION, {
			IN_FLAGS: flags
		})
		if output[OUT_ERRNO] != OK:
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
	
	def commit_transaction(self, resume_indexing=False):
		"""Esegue una COMMIT della transazione sul database attivo nella connessione corrente. Se *resume_indexing* è ``True``, l'indicizzazione
		del database è abilitata sul server. In caso di errore viene lanciata l'eccezione :class:`~kongalib.Error`.
		"""
		flags = 0
		if resume_indexing:
			flags |= 0x1
		output = self.execute(CMD_COMMIT_TRANSACTION, {
			IN_FLAGS: flags
		})
		if output[OUT_ERRNO] != OK:
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
	
	def rollback_transaction(self, resume_indexing=False):
		"""Esegue un ROLLBACK della transazione sul database attivo nella connessione corrente. Se *resume_indexing* è ``True``, l'indicizzazione
		del database è abilitata sul server. In caso di errore viene lanciata l'eccezione :class:`~kongalib.Error`.
		"""
		flags = 0
		if resume_indexing:
			flags |= 0x1
		output = self.execute(CMD_ROLLBACK_TRANSACTION, {
			IN_FLAGS: flags
		})
		if output[OUT_ERRNO] != OK:
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])

	def lock_resource(self, command, row_id=None):
		"""Tenta di eseguire il blocco della risorsa identificata da *command*. Se *row_id* è diverso da ``None``, è possibile eseguire il
		blocco di una singola riga di una tabella del database.
		Restituisce una tupla ``(result, owner_data)``, dove *owner_data* è un ``dict`` contenente informazioni sull'utente che detiene già il blocco
		della risorsa in caso fosse già bloccata, oppure lancia un'eccezione :class:`~kongalib.Error` in caso di errore.
		"""
		output = self.execute(CMD_LOCK, {
			IN_COMMAND_NAME: command,
			IN_ROW_ID: row_id
		})
		return output['ANSWER'], output['OWNER_DATA']
	
	def unlock_resource(self, command, row_id=None):
		"""Rilascia il blocco della risorsa identificata da *tablename* e *row_id*.
		"""
		output = self.execute(CMD_UNLOCK, {
			IN_COMMAND_NAME: command,
			IN_ROW_ID: row_id
		})
		return output['ANSWER']
	
	def select_data(self, tablename, fieldnamelist=None, where_expr=None, order_by=None, order_desc=False, offset=0, count=None, get_total=False, exist=None, success=None, error=None, progress=None):
		"""Genera ed esegue una SELECT sul server per ottenere una lista di risultati, a partire dalla tabella *tablename*.
		*fieldnamelist* è una lista di nomi dei campi da ottenere; se un campo fk_X di *tablename* è una foreign key, si può accedere ai
		campi della tabella collegata Y specificando "fk_X.Campo_di_Y"; la JOIN corrispondente verrà generata e gestita automaticamente dal
		server. Analogamente, si possono creare catene di JOIN implicite facendo riferimenti multipli di campi foreign key, per esempio
		"fk_X.fk_Y.fk_Z.Campo_di_Z".
		
		Se *where_expr* non è ``None``, può essere il corpo di una espressione WHERE SQL, e può contenere riferimenti nella stessa forma di
		*fieldnamelist*, per esempio "(Campo_di_X = 1) AND (fk_X.Campo_di_Y > 5)".
		
		*order_by* può essere un nome di campo per cui ordinare i risultati, dove *order_desc* specifica se ordinare in modo ascendente o discendente.
		*offset* e *count* permettono di restituire risultati solo a partire dal numero *offset*, e limitandosi a *count* risultati.
		
		Se *get_total* è ``True``, il valore di ritorno (o gli argomenti della callback *success*) sarà una tupla nella forma ``(result_set, total_rows, exist_results)``;
		*total_rows* sarà il numero totale di righe come se *offset* e *limit* non fossero stati specificati, mentre *exist_results* sarà un
		``dict`` le cui chiavi saranno gli ID specificati nel parametro *exist*, e i valori saranno ``True`` o ``False`` a seconda che il
		corrispettivo ID sia presente nel database per la tabella *tablename* oppure no.
		
		Se *success* è ``None`` la chiamata è bloccante e verrà restituito un risultato come descritto sopra, altrimenti verrà lanciata un'eccezione
		:class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(result_set)`` oppure ``success(result_set, total_rows, exist_results)`` (a seconda del
		parametro *get_total* come descritto sopra), la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred` e l'operazione
		viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito.
		"""
		if isinstance(fieldnamelist, text_base_types):
			fieldnamelist = [ fieldnamelist ]
		elif fieldnamelist:
			fieldnamelist = list(fieldnamelist)
		if success is not None:
			def callback(output, dummy):
				if output[OUT_ERRNO] == OK:
					if get_total:
						success(output[OUT_RESULT_SET], output[OUT_TOTAL_ROWS], output[OUT_EXIST])
					else:
						success(output[OUT_RESULT_SET])
				elif error is not None:
					error(ErrorList.from_error(output[OUT_ERRNO], output[OUT_ERROR]))
			def errback(errno, errstr, dummy):
				if error is not None:
					error(ErrorList.from_error(errno, errstr))
			return self.execute(CMD_SELECT, {
				IN_TABLE_NAME: tablename,
				IN_COLUMN_NAMES: fieldnamelist,
				IN_WHERE_CLAUSE: where(where_expr),
				IN_ORDER_BY: order_by,
				IN_ORDER_DESC: order_desc,
				IN_OFFSET: offset,
				IN_ROW_COUNT: count,
				IN_GET_TOTAL_ROWS: get_total,
				IN_GET_ROWS_EXIST: exist,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_SELECT, {
				IN_TABLE_NAME: tablename,
				IN_COLUMN_NAMES: fieldnamelist,
				IN_WHERE_CLAUSE: where(where_expr),
				IN_ORDER_BY: order_by,
				IN_ORDER_DESC: order_desc,
				IN_OFFSET: offset,
				IN_ROW_COUNT: count,
				IN_GET_TOTAL_ROWS: get_total,
				IN_GET_ROWS_EXIST: exist,
			})
			if output[OUT_ERRNO] == OK:
				if get_total:
					return output[OUT_RESULT_SET], output[OUT_TOTAL_ROWS], output[OUT_EXIST]
				else:
					return output[OUT_RESULT_SET]
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
	
	def select_data_as_dict(self, tablename, fieldnamelist=None, where_expr=None, order_by=None, order_desc=False, offset=0, count=None, get_total=False, success=None, error=None, progress=None):
		"""Esattamente come :meth:`.select_data`, ma restituisce il *result_set* come una lista di ``dict``, anzichè una lista di liste."""
		if isinstance(fieldnamelist, text_base_types):
			fieldnamelist = [ fieldnamelist ]
		elif fieldnamelist:
			fieldnamelist = list(fieldnamelist)
		def get_result_set(output):
			names = output.get(OUT_COLUMN_NAMES, None) or fieldnamelist
			return [dict(list(zip(names, row))) for row in output[OUT_RESULT_SET] ]
		if success is not None:
			def callback(output, dummy):
				if output[OUT_ERRNO] == OK:
					if get_total:
						success(get_result_set(output), output[OUT_TOTAL_ROWS], output[OUT_EXIST])
					else:
						success(get_result_set(output))
				elif error is not None:
					error(ErrorList.from_error(output[OUT_ERRNO], output[OUT_ERROR]))
			def errback(errno, errstr, dummy):
				if error is not None:
					error(ErrorList.from_error(errno, errstr))
			return self.execute(CMD_SELECT, {
				IN_TABLE_NAME: tablename,
				IN_COLUMN_NAMES: fieldnamelist,
				IN_WHERE_CLAUSE: where(where_expr),
				IN_ORDER_BY: order_by,
				IN_ORDER_DESC: order_desc,
				IN_OFFSET: offset,
				IN_ROW_COUNT: count,
				IN_GET_TOTAL_ROWS: get_total,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_SELECT, {
				IN_TABLE_NAME: tablename,
				IN_COLUMN_NAMES: fieldnamelist,
				IN_WHERE_CLAUSE: where(where_expr),
				IN_ORDER_BY: order_by,
				IN_ORDER_DESC: order_desc,
				IN_OFFSET: offset,
				IN_ROW_COUNT: count,
				IN_GET_TOTAL_ROWS: get_total,
			})
			if output[OUT_ERRNO] == OK:
				if get_total:
					return get_result_set(output), output[OUT_TOTAL_ROWS], output[OUT_EXIST]
				else:
					return get_result_set(output)
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
	
	def get_record(self, tablename, code=None, id=None, field_names=None, row_extra_field_names=None, code_azienda=None, num_esercizio=None, mode=None, mask_binary=None, flags=GET_FLAG_DEFAULT, success=None, error=None, progress=None):
		"""Ottiene il record completo della tabella *tablename*, sotto forma di ``dict``. Il record può essere identificato in due modi: o
		tramite il solo *id*, oppure tramite la specifica dei parametri *code*, *code_azienda* e *num_esercizio*.
		Se *success* è ``None`` la chiamata è bloccante, altrimenti verrà lanciata un'eccezione :class:`~kongalib.Error` in caso di errore.
		Se *success* è una funzione nella forma ``success(data)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred` e
		l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con i dati del record.
		"""
		if (id is None) and (code is None):
			raise ValueError('Either code or id must be specified')
		if success is not None:
			def callback(output):
				data = output[OUT_DICT_DATA]
				data['@checksum'] = output[OUT_CHECKSUM]
				success(data)
			callback, errback = make_callbacks(callback, error, None)
			return self.execute(CMD_GET, {
				IN_TABLE_NAME: tablename,
				IN_ROW_ID: id,
				IN_CODE: code,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
				IN_FLAGS: flags,
				IN_COLUMN_NAMES: field_names,
				IN_ROW_EXTRA_FIELDS: row_extra_field_names,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_GET, {
				IN_TABLE_NAME: tablename,
				IN_ROW_ID: id,
				IN_CODE: code,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
				IN_FLAGS: flags,
				IN_COLUMN_NAMES: field_names,
				IN_ROW_EXTRA_FIELDS: row_extra_field_names,
			})
			def callback():
				data = output[OUT_DICT_DATA]
				data['@checksum'] = output[OUT_CHECKSUM]
				return data
			return _check_result(output, callback)
	
	def insert_record(self, tablename, data, code_azienda=None, num_esercizio=None, log=None, success=None, error=None, progress=None):
		"""Inserisce un nuovo record nella tabella *tablename*. Il nuovo record, i cui dati sono passati nel ``dict`` *data*, sarà un record
		condiviso con tutte le aziende del database se *code_azienda* e *num_esercizio* sono ``None``, altrimenti apparterrà solo all'azienda e
		all'esercizio specificati.
		Se *success* è ``None`` la chiamata è bloccante e ritornerà una tupla nella forma ``(id, code)``, dove *id* è l'ID univoco assegnato
		al record dal server, mentre *code* è il codice del record (che può essere diverso da quello passato in *data* se sono attivi i codici
		automatici per *tablename*); in caso di errore verrà lanciata un'eccezione di classe :class:`~kongalib.Error` o :class:`~kongalib.ErrorList`.
		Se *success* è una funzione nella forma ``success(id, code)``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred`
		e l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito con l'ID ed il codice del nuovo
		record. In modalità asincrona se *log* è un oggetto di classe :class:`OperationLog`, esso riceverà ogni eventuale messaggio di log
		prodotto dal server durante l'inserimento.
		"""
		if success is not None:
			callback, errback = make_callbacks(lambda output: success(output[OUT_ID], output[OUT_CODE]), error, log)
			return self.execute(CMD_INSERT_FROM_DICT, {
				IN_TABLE_NAME: tablename,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
				IN_DICT_DATA: data
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_INSERT_FROM_DICT, {
				IN_TABLE_NAME: tablename,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
				IN_DICT_DATA: data
			})
			return _check_result(output, lambda: (output[OUT_ID], output[OUT_CODE]))
	
	def update_record(self, tablename, data, code=None, id=None, code_azienda=None, num_esercizio=None, log=None, success=None, error=None, progress=None):
		"""Aggiorna un record esistente nella tabella *tablename*. Il record, i cui dati da aggiornare sono passati nel ``dict`` *data*, può
		essere identificato in due modi: o tramite il  solo *id*, oppure tramite la specifica dei parametri *code*, *code_azienda* e *num_esercizio*.
		Se *success* è ``None`` la chiamata è bloccante, e in caso di errore verrà lanciata un'eccezione di classe :class:`~kongalib.Error` o
		:class:`~kongalib.ErrorList`.
		Se *success* è una funzione nella forma ``success()``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred` e
		l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito. In modalità asincrona se *log* è un
		oggetto di classe :class:`OperationLog`, esso riceverà ogni eventuale messaggio di log prodotto dal server durante l'aggiornamento.
		"""
		if success is not None:
			callback, errback = make_callbacks(lambda output: success(), error, log)
			return self.execute(CMD_UPDATE_FROM_DICT, {
				IN_TABLE_NAME: tablename,
				IN_ROW_ID: id,
				IN_CODE: code,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
				IN_DICT_DATA: data
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_UPDATE_FROM_DICT, {
				IN_TABLE_NAME: tablename,
				IN_ROW_ID: id,
				IN_CODE: code,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
				IN_DICT_DATA: data
			})
			return _check_result(output)
	
	def delete_record(self, tablename, code=None, id=None, code_azienda=None, num_esercizio=None, log=None, success=None, error=None, progress=None):
		"""Cancella un record dalla tabella *tablename*. Il record può essere identificato in due modi: o tramite il  solo *id*, oppure tramite
		la specifica dei parametri *code*, *code_azienda* e *num_esercizio*.
		Se *success* è ``None`` la chiamata è bloccante, e in caso di errore verrà lanciata un'eccezione di classe :class:`~kongalib.Error` o
		:class:`~kongalib.ErrorList`.
		Se *success* è una funzione nella forma ``success()``, la chiamata restituisce immediatamente un oggetto :class:`~kongalib.Deferred` e
		l'operazione viene eseguita in modo asincrono; la callback *success* verrà invocata a tempo debito. In modalità asincrona se *log* è un
		oggetto di classe :class:`OperationLog`, esso riceverà ogni eventuale messaggio di log prodotto dal server durante l'aggiornamento.
		"""
		if success is not None:
			callback, errback = make_callbacks(lambda output: success(), error, log)
			return self.execute(CMD_DELETE_FROM_CODE, {
				IN_TABLE_NAME: tablename,
				IN_ROW_ID: id,
				IN_CODE: code,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_DELETE_FROM_CODE, {
				IN_TABLE_NAME: tablename,
				IN_ROW_ID: id,
				IN_CODE: code,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
			})
			return _check_result(output)
	
	def code_exists(self, tablename, code, code_azienda, num_esercizio, extra_where=None):
		"""Controlla l'esistenza del codice *code* nella tabella *tablename* per l'azienda e l'esercizio specificati in *code_azienda* e *num_esercizio*."""
		output = self.execute(CMD_CODE_EXISTS, {
			IN_TABLE_NAME: tablename,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_EXTRA_WHERE: where(extra_where),
		})
		return output['EXISTS']
	
	def get_next_available_code(self, tablename, code_azienda, num_esercizio, dry_run=False):
		return self.execute(CMD_GET_NEXT_CODE, {
			IN_TABLE_NAME: tablename,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_DRY_RUN: dry_run,
		})[OUT_CODE]

	def get_last_npfe(self, code_azienda, num_esercizio):
		return self.execute(CMD_GET_LAST_NPFE, {
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
		})[OUT_NPFE]
	
	def start_elab(self, command, params, code_azienda, num_esercizio, log=None, success=None, error=None, progress=None, tx=True):
		if success is not None:
			def callback(output, dummy):
				if output[OUT_ERRNO] == OK:
					answer = output[OUT_LOG]
					if len(answer) > 0:
						error_list = ErrorList(answer)
						if log is None:
							if error is not None:
								error(error_list)
						else:
							error_list.prepare_log(log)
							success(output[OUT_DATA])
					else:
						success(output[OUT_DATA])
				elif error is not None:
					error(ErrorList.from_error(output[OUT_ERRNO], output[OUT_ERROR]))
			def errback(errno, errstr, dummy):
				if error is not None:
					error(ErrorList.from_error(errno, errstr))
			
			return self.execute(CMD_START_ELAB, {
				IN_COMMAND: command,
				IN_PARAMS: params,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
				IN_TX: tx,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_START_ELAB, {
				IN_COMMAND: command,
				IN_PARAMS: params,
				IN_CODE_AZIENDA: code_azienda,
				IN_NUM_ESERCIZIO: num_esercizio,
				IN_TX: tx,
			})
			if output[OUT_ERRNO] == OK:
				answer = output[OUT_LOG]
				e = ErrorList(answer)
				if (log is not None) and (len(answer) > 0):
					e.prepare_log(log)
				if e.errno != OK:
					raise e
				return output[OUT_DATA]
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
	
	def fetch_image(self, fieldname, id, type, success=None, error=None, progress=None):
		if success is not None:
			def callback(output, dummy):
				if output[OUT_ERRNO] == OK:
					success(output[OUT_DATA])
				elif error is not None:
					error(Error(output[OUT_ERRNO], output[OUT_ERROR]))
			def errback(errno, errstr, dummy):
				if error is not None:
					error(Error(errno, errstr))
			
			return self.execute(CMD_FETCH_BINARY, {
				IN_FIELD_NAME: fieldname,
				IN_ROW_ID: id,
				IN_TYPE: type,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_FETCH_BINARY, {
				IN_FIELD_NAME: fieldname,
				IN_ROW_ID: id,
				IN_TYPE: type,
			})
			if output[OUT_ERRNO] == OK:
				return output[OUT_DATA]
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
	
	def fetch_binary(self, fieldname, id, type, filename, storage_type=None, success=None, error=None, progress=None):
		if success is not None:
			def callback(output, dummy):
				if output[OUT_ERRNO] == OK:
					success(output[OUT_DATA])
				elif error is not None:
					error(Error(output[OUT_ERRNO], output[OUT_ERROR]))
			def errback(errno, errstr, dummy):
				if error is not None:
					error(Error(errno, errstr))
			
			return self.execute(CMD_FETCH_BINARY, {
				IN_FIELD_NAME: fieldname,
				IN_ROW_ID: id,
				IN_TYPE: type,
				IN_FILENAME: filename,
				IN_STORAGE_TYPE: storage_type,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_FETCH_BINARY, {
				IN_FIELD_NAME: fieldname,
				IN_ROW_ID: id,
				IN_TYPE: type,
				IN_FILENAME: filename,
				IN_STORAGE_TYPE: storage_type,
			})
			if output[OUT_ERRNO] == OK:
				return output[OUT_DATA]
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])

	def store_binary(self, fieldname, id, type, filename, storage_type=None, data=None, success=None, error=None, progress=None):
		if success is not None:
			def callback(output, dummy):
				if output[OUT_ERRNO] == OK:
					success()
				elif error is not None:
					error(Error(output[OUT_ERRNO], output[OUT_ERROR]))
			def errback(errno, errstr, dummy):
				if error is not None:
					error(Error(errno, errstr))
			
			return self.execute(CMD_STORE_BINARY, {
				IN_FIELD_NAME: fieldname,
				IN_ROW_ID: id,
				IN_TYPE: type,
				IN_FILENAME: filename,
				IN_STORAGE_TYPE: storage_type,
				IN_DATA: data,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_STORE_BINARY, {
				IN_FIELD_NAME: fieldname,
				IN_ROW_ID: id,
				IN_TYPE: type,
				IN_FILENAME: filename,
				IN_STORAGE_TYPE: storage_type,
				IN_DATA: data,
			})
			if output[OUT_ERRNO] == OK:
				return
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])

	def translate(self, field, value, language):
		output = self.execute(CMD_TRANSLATE, {
			IN_FIELD: field,
			IN_VALUE: value,
			IN_LANGUAGE: language
		})
		if output[OUT_ERRNO] != OK:
			raise Error(output[OUT_ERRNO], output[OUT_ERROR])
		return output[OUT_TEXT]

	def set_database_language(self, language, success=None, error=None, progress=None):
		if success is not None:
			def callback(output, dummy):
				if output[OUT_ERRNO] == OK:
					success()
				elif error is not None:
					error(Error(output[OUT_ERRNO], output[OUT_ERROR]))
			def errback(errno, errstr, dummy):
				if error is not None:
					error(Error(errno, errstr))
			self.execute(CMD_SET_DATABASE_LANGUAGE, {
				IN_LANGUAGE: language,
			}, success=callback, error=errback, progress=progress)
		else:
			output = self.execute(CMD_SET_DATABASE_LANGUAGE, {
				IN_LANGUAGE: language,
			})
			if output[OUT_ERRNO] != OK:
				raise Error(output[OUT_ERRNO], output[OUT_ERROR])


