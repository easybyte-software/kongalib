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

import asyncio
import inspect

from kongalib import *


class AsyncClient(Client):
	"""La classe AsyncClient, analogamente alla classe :class:`~kongalib.Client`, permette di connettersi ad un server Konga e di eseguire
	comandi sullo stesso; la differenza è nel fatto che questa classe è costruita esplicitamente per lavorare con *asyncio* di Python, ed
	è disponibile solo se si usa Python >= 3.6.

	Tutti i metodi che esistono nella classe Client e che possono essere invocati sia in maniera asincrona (specificando le callback di
	*success*, *error* e *progress*) che sincrona (generalmente omettendo di specificare la callback di *success*), nella classe AsyncClient
	accettano eventualmente la sola callback di *progress*, in quanto vengono sempre eseguiti in maniera asincrona tramite l'event loop di
	asyncio, che si assume sia in esecuzione. La *progress* viene eseguita in un thread separato, ed ha la forma ``progress(type, completeness, state, userdata)``;
	i parametri interessanti di questa callback sono *completeness* (percentuale di completamento, ossia un numero che varia da 0.0 a 100.0;
	se -1.0 indica una percentuale di completamento indefinita), *state* (stringa che specifica l'eventuale stato corrente dell'operazione)
	e *userdata*, che è un parametro aggiuntivo che viene normalmente passato alla chiamata asincrona dall'utente per tenere traccia di un
	eventuale stato.

	Come per la classe Client, oggetti di classe AsyncClient possono essere usati come contesti per il costrutto ``with``: all'ingresso del
	blocco verrà iniziata una transazione, mentre in uscita verrà eseguita una commit o una rollback della stessa a seconda che ci sia stata
	o meno un'eccezione all'interno del blocco di istruzioni. Da notare che dal momento che siamo in ambito asincrono, andrà usato il
	costrutto ``async with`` al posto del semplice ``with``.
	"""

	def _safe_set_result(self, future, result):
		if not future.cancelled():
			future.set_result(result)
	
	def _safe_set_exception(self, future, e):
		if not future.cancelled():
			future.set_exception(e)
	
	def _make_progress(self, future, progress, userdata):
		def callback(ptype, completeness, state, data, dummy):
			loop = future.get_loop()
			try:
				if progress is None:
					result = not future.cancelled()
				elif asyncio.iscoroutinefunction(progress):
					result = asyncio.run_coroutine_threadsafe(progress(ptype, completeness, state, userdata), loop).result()
				else:
					result = progress(ptype, completeness, state, userdata)
				if result is False:
					return False
			except Exception as e:
				result = False
				loop.call_soon_threadsafe(self._safe_set_exception, future, e)
			return result
		return callback

	def _make_error(self, future):
		def error(errno, *args):
			loop = future.get_loop()
			if isinstance(errno, Error):
				if errno.errno in (ABORTED, EXECUTE_ABORTED):
					loop.call_soon_threadsafe(future.cancel)
				else:
					loop.call_soon_threadsafe(self._safe_set_exception, future, errno)
			elif isinstance(errno, Exception):
				loop.call_soon_threadsafe(self._safe_set_exception, future, errno)
			else:
				if len(args) > 0:
					errstr = ensure_text(args[0])
				else:
					errstr = '<unknown>'
				loop.call_soon_threadsafe(self._safe_set_exception, future, Error(errno, errstr))
		return error
	
	def _make_success_tuple(self, future, count):
		def success(*args):
			loop = future.get_loop()
			if count == 0:
				loop.call_soon_threadsafe(self._safe_set_result, future, None)
			elif count == 1:
				loop.call_soon_threadsafe(self._safe_set_result, future, args[0])
			else:
				loop.call_soon_threadsafe(self._safe_set_result, future, args[:count])
		return success

	def _make_success(self, future, log=None, finalize_output=None):
		def success(output, *args):
			loop = future.get_loop()
			answer = output[OUT_LOG] or []
			error_list = ErrorList(answer)
			if output[OUT_ERRNO] == OK:
				if len(answer) > 0:
					if log is None:
						loop.call_soon_threadsafe(self._safe_set_exception, future, error_list)
					else:
						error_list.prepare_log(log)
						if log.has_errors():
							loop.call_soon_threadsafe(self._safe_set_exception, future, error_list)
						else:
							if finalize_output is not None:
								output = finalize_output(output)
							loop.call_soon_threadsafe(self._safe_set_result, future, output)
				else:
					if finalize_output is not None:
						output = finalize_output(output)
					loop.call_soon_threadsafe(self._safe_set_result, future, output)
			else:
				loop.call_soon_threadsafe(self._safe_set_exception, future, ErrorList.from_error(output[OUT_ERRNO], output[OUT_ERROR]))
		return success
	
	def _execute(self, cmd, in_params, out_params=None, progress=None, log=None):
		def finalize(output):
			if out_params:
				if callable(out_params):
					return out_params(output)
				elif isinstance(out_params, (tuple, list)):
					return tuple([ output[param] for param in out_params ])
				else:
					return output[out_params]
			else:
				return None
		fut = asyncio.get_running_loop().create_future()
		self._impl.execute(cmd, in_params or {}, DEFAULT_EXECUTE_TIMEOUT, self._make_success(fut, log, finalize), self._make_error(fut), self._make_progress(fut, progress, None))
		return fut

	def __aenter__(self):
		return self.begin_transaction()
	
	def __aexit__(self, exc_type, exc_value, exc_traceback):
		if exc_type is None:
			return self.commit_transaction()
		else:
			return self.rollback_transaction()
		
	def as_sync(self):
		"""Ritorna un oggetto :class:`~kongalib.Client` equivalente a questo client, preservando le connessioni già presenti.
		"""
		return Client(self._impl)

	def list_servers(self, timeout=DEFAULT_DISCOVER_TIMEOUT, port=0, progress=None, userdata=None):
		"""Esegue una scansione della rete locale alla ricerca dei server Konga disponibili, attendendo al massimo *timeout* millisecondi
		per una risposta. *port* specifica la porta da cui far partire la scansione (default = 51967); sono controllate le successive 10
		porte UDP con intervallo di 20 porte (quindi di default vengono scansionate le porte 51967, 51987, 52007, ... 52147). La funzione
		restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà una lista di ``dict``, le cui chiavi principali
		sono *host*, *port*, *name* e *description*.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_servers(timeout, port, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata))
		return fut
	
	def connect(self, server=None, host=None, port=0, options=None, timeout=DEFAULT_CONNECT_TIMEOUT, progress=None, userdata=None):
		"""Tenta una connessione ad un server Konga. Il server a cui ci si vuole connettere può essere specificato in due modi: tramite i
		parametri *host* e *port*, oppure tramite un ``dict`` *server* che deve contenere almeno le chiavi *host* e *port*. Alternativamente,
		se *server* è una stringa e *host* non è specificato, viene assunta come *host*. Se *host* include una specifica di porta e *port* è ``0``,
		*port* viene ottenuta dalla specifica contenuta nella stringa di *host*. Il parametro *options* può essere un ``dict`` contenente opzioni
		aggiuntive per la connessione; al momento le opzioni supportate sono:

		- ``tenant_key`` (*str*): chiave del tenant per stabilire la connessione con un server multitenant.

		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà un ``dict`` contenente le informazioni
		sulla connessione stabilita.
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
		fut = asyncio.get_running_loop().create_future()
		self._impl.connect(server, host or '', port, options, timeout, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata))
		return fut

	def disconnect(self):
		"""Disconnette il server attualmente connesso, oppure non fa nulla se non si è al momento connessi."""
		self._impl.disconnect()
	
	def get_id(self):
		"""Restituisce un ID numerico univoco assegnato dal server alla connessione con questo client, o 0 se non si è connessi."""
		return self._impl.get_id()
	
	def get_connection_info(self):
		"""Restituisce un ``dict`` con informazioni sulla connessione corrente, o ``None`` se non si è connessi."""
		return self._impl.get_connection_info()

	def execute(self, command, data=None, timeout=DEFAULT_EXECUTE_TIMEOUT, progress=None, userdata=None, log=None):
		fut = asyncio.get_running_loop().create_future()
		self._impl.execute(command, data or {}, timeout, self._make_success(fut, log), self._make_error(fut), self._make_progress(fut, progress, userdata))
		return fut
	
	def interrupt(self):
		"""Interrompe tutte le operazioni al momento in esecuzione da parte di questo client."""
		self._impl.interrupt()

	def get_data_dictionary(self, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà il dizionario dei dati disponibile sul server
		attualmente connesso, sotto forma di oggetto di classe :class:`kongalib.DataDictionary`.
		"""
		fut = asyncio.get_running_loop().create_future()
		uuid = self.get_connection_info().get('uuid', None)
		with Client.DATA_DICTIONARY_LOCK:
			if uuid is None:
				data = None
			else:
				data = Client.DATA_DICTIONARY_CACHE.get(uuid, None)
			if data is None:
				def success(d, userdata):
					with Client.DATA_DICTIONARY_LOCK:
						d = DataDictionary(d)
						Client.DATA_DICTIONARY_CACHE[uuid] = d
						fut.get_loop().call_soon_threadsafe(self._safe_set_result, fut, d)
				self._impl.get_data_dictionary(success, self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
			else:
				fut.set_result(data)
		return fut

	def list_drivers(self, configured=True, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà la lista dei driver di database presenti
		sul server attualmente connesso, oppure lancia un'eccezione :class:`~kongalib.Error` su errore. Ogni elemento della lista restituita
		è un ``dict`` che comprende la chiavi *name*, *version* e *description*. Se *configured* è False, tutti i driver installati sul
		server sono restituiti, altrimenti verranno restituite solo le informazioni sui driver configurati correttamente ed in esecuzione
		sul server.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_drivers(configured, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def list_databases(self, driver=None, quick=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà la lista dei database disponibili sul server
		corrente, appartenenti a tutti o ad uno specifico *driver*. La lista viene tornata sotto forma di ``dict``, le cui chiavi sono i nomi
		dei driver e i valori le liste dei database appartenenti allo specifico driver. Ogni database nelle liste è un ``dict`` che contiene
		almeno le chiavi *name*, *desc*, *uuid*, *created_ts* e *modified_ts*. L'eccezione :class:`~kongalib.Error` viene lanciata se si
		verifica un errore. Se *quick* è ``True``, la funzione ritorna il più velocemente possibile ma la scansione dei database disponibili
		potrebbe risultare ancora incompleta.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_databases(driver, quick, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def create_database(self, password, driver, name, desc='', progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Crea un nuovo database sul server attualmente connesso; il database avrà nome *name* e descrizione *desc*.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà l'UUID del nuovo database;
		se si verifica un errore viene lanciata l'eccezione :class:`~kongalib.Error`.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.create_database(password, driver, name, desc, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def open_database(self, driver, name, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Apre un database rendendolo il database attivo per la connessione corrente. La funzione restituisce un oggetto ``asyncio.Future`` il
		cui risultato una volta completato sarà un ``dict`` con le informazioni sul database connesso, oppure viene lanciata l'eccezione
		:class:`~kongalib.Error` in caso di errore.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.open_database(driver, name, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def close_database(self, backup=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Chiude il database attivo sulla connessione corrente, restituendo un oggetto ``asyncio.Future`` per l'esecuzione asincrona; in caso
		di errore verrà lanciata l'eccezione :class:`~kongalib.Error`.
		
		.. note:: Se *backup* è ``True``, il server esegue un backup automatico del database prima di chiuderlo.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.close_database(backup, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def upgrade_database(self, password, driver, name, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Aggiorna il database specificato all'ultima versione disponibile.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà una tupla (log, old_version, new_version),
		dove il log dell'operazione è sotto forma di una lista di stringhe, oppure viene lanciata l'eccezione :class:`~kongalib.Error` in caso
		di errore.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.upgrade_database(password, driver, name, self._make_success_tuple(fut, 3), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def delete_database(self, password, driver, name, delete_cloud_data=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Cancella il database specificato. Se *delete_cloud_data* è ``None`` (valore predefinito) la cancellazione sarà negata nel caso ci siano
		dati binari legati al database al momento presenti nel cloud; in caso contrario i dati binari saranno o meno cancellati dal cloud in base
		al valore del parametro.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.delete_database(password, driver, name, delete_cloud_data, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def query(self, query, native=False, full_column_names=False, collapse_blobs=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue una query SQL sul database attivo nella connessione corrente. Se *native* è ``True``, la query viene passata al driver
		del database senza essere interpretata, permettendo l'esecuzione di query native per l'RDBMS sottostante. La funzione restituisce un oggetto
		``asyncio.Future`` il cui risultato una volta completato sarà una tupla nella forma ``(affected_rows, column_names, result_set)``;
		*affected_rows* è il numero di righe coinvolte nella query di UPDATE/DELETE, *column_names* è una lista di nomi di colonne per il result set,
		mentre *result_set* è una lista di righe risultati della query, dove ogni riga è una lista di valori corrispondenti alle colonne restituite in
		*column_names*. In caso di errore viene lanciata l'eccezione :class:`~kongalib.Error`.
		
		.. note:: Se *full_column_names* è ``False``, *column_names* includerà i nomi delle colonne senza nome tabella, altrimenti saranno
			inclusi i nomi completi delle colonne. Se *collapse_blobs* è ``True``, i dati di tipo BLOB binari verranno restituiti come ``[...]``.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.query_database(query, native, full_column_names, collapse_blobs, self._make_success_tuple(fut, 3), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def backup_database(self, password, backup_name, driver, name, auto=True, overwrite=False, position=0, store_index=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue un backup del database specificato sul server attualmente connesso. Se *auto* è ``False``, è necessario specificare un nome
		per il backup tramite *backup_name*, altrimenti il backup viene considerato automatico ed un nome univoco è assegnato dal server. Se
		*overwrite* è ``False`` ed un backup con lo stesso nome esiste già sul server, non sarà possibile eseguire il backup. *position*
		permette di specificare dove eseguire il backup, ed è una combinazione delle costanti :const:`kongalib.BACKUP_ON_COMPUTER` e
		:const:`kongalib.BACKUP_ON_CLOUD`, mentre *store_index* specifica se includere l'indice di ricerca full-text nel backup.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.backup_database(password, backup_name, driver, name, auto, overwrite, position, store_index, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def restore_database(self, password, backup_name, driver, name, change_uuid=True, overwrite=False, position=0, restore_index=True, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Ripristina un database a partire da un backup effettuato in precedenza sul server connesso. Se *overwrite* è False ed esiste un
		database gestito da *driver* con lo stesso nome, la funzione riporterà errore. *change_uuid* specifica se cambiare l'UUID associato al
		database oppure se ripristinare quello originale; se si hanno database con lo stesso nome gestiti da driver diversi è opportuno che
		almeno l'UUID per essi sia diverso, altrimenti si può incorrere in problemi di aliasing. *position* specifica da dove prendere il
		backup da rispristinare, e deve essere una delle costanti :const:`kongalib.BACKUP_ON_COMPUTER` o :const:`kongalib.BACKUP_ON_CLOUD`;
		*restore_index* invece permette di specificare se ripristinare o meno l'indice di ricerca qualora fosse contenuto all'interno del backup.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.restore_database(password, backup_name, driver, name, change_uuid, overwrite, position, restore_index, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def list_backups(self, position=0, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Ottiene la lista dei backup disponibili sul server connesso.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà una lista di backup; ogni backup è un
		``dict`` che contiene almeno le chiavi *backup_name*, *uuid*, *date* e *size*; se si verifica un errore viene lanciata l'eccezione
		:class:`~kongalib.Error`.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_backups(position, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def delete_backup(self, password, backup_name, position, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Cancella il backup identificato da *backup_name* dal server connesso.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.delete_backup(password, backup_name, position, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def optimize_database(self, password, driver, name, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue una ottimizzazione del database specificato sul server attualmente connesso.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.optimize_database(password, driver, name, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def repair_database(self, password, driver, name, output, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Prova a riparare il database danneggiato specificato, salvando il database recuperato in *output*.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		
		.. note:: Non tutti i driver di database supportano questa operazione, e il recupero del database potrebbe fallire in ogni caso.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.repair_database(password, driver, name, output, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def index_database(self, password, driver, name, reset=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue una indicizzazione del database specificato sul server attualmente connesso. Se *reset* è ``False``, l'indicizzazione è
		incrementale, ovvero l'indice viene modificato per tenere conto solo dei record inseriti, modificati o cancellati dall'ultima
		indicizzazione; se invece *reset* è ``True``, l'indice viene prima cancellato e poi ricreato completamente.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		
		.. warning:: E' necessaria la *password* del server per poter eseguire questa operazione.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.index_database(password, driver, name, reset, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def list_clients(self, full=True, any=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_clients(full, any, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def get_client_info(self, id, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.get_client_info(id, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def kill_client(self, id, password, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.kill_client(id, password, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def authenticate(self, username, password, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT, new_password=None):
		"""Effettua un accesso al database attivo sulla connessione corrente, identificando l'utente tramite i parametri *username* e *password*.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà un ``dict`` con informazioni dettagliate
		sull'utente autenticato, oppure viene lanciata l'eccezione :class:`~kongalib.Error` in caso di errore.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.authenticate(username, password, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout, new_password)
		return fut

	def full_text_search(self, text, limit, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Esegue una ricerca full-text sul database attivo sulla connessione corrente, limitando la ricerca di *text* a *limit* risultati.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà una lista di risultati, dove ogni
		risultato è ``dict`` con almeno le chiavi *score*, *tablename*, *id* e *display*; in caso di errore viene lanciata l'eccezione
		:class:`~kongalib.Error`.
		"""
		fut = asyncio.get_running_loop().create_future()
		self._impl.full_text_search(text, limit, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def get_permissions(self, user_id):
		return self._execute(CMD_GET_PERMISSIONS, {
			IN_USER_ID: user_id
		})
	
	def set_permissions(self, user_id, permissions):
		return self._execute(CMD_SET_PERMISSIONS, {
			IN_USER_ID: user_id,
			IN_PERMISSIONS: permissions
		})
	
	def begin_transaction(self, pause_indexing=False, deferred=False):
		"""Inizia una transazione sul database attivo nella connessione corrente. Se *pause_indexing* è ``True``, l'indicizzazione del
		database è disabilitata sul server.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		"""
		flags = 0
		if pause_indexing:
			flags |= 0x1
		if deferred:
			flags |= 0x2
		return self._execute(CMD_BEGIN_TRANSACTION, {
			IN_FLAGS: flags
		})
	
	def commit_transaction(self, resume_indexing=False):
		"""Esegue una COMMIT della transazione sul database attivo nella connessione corrente. Se *resume_indexing* è ``True``, l'indicizzazione
		del database è abilitata sul server.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		"""
		flags = 0
		if resume_indexing:
			flags |= 0x1
		return self._execute(CMD_COMMIT_TRANSACTION, {
			IN_FLAGS: flags
		})
	
	def rollback_transaction(self, resume_indexing=False):
		"""Esegue un ROLLBACK della transazione sul database attivo nella connessione corrente. Se *resume_indexing* è ``True``, l'indicizzazione
		del database è abilitata sul server.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		"""
		flags = 0
		if resume_indexing:
			flags |= 0x1
		return self._execute(CMD_ROLLBACK_TRANSACTION, {
			IN_FLAGS: flags
		})

	def lock_resource(self, command, row_id=None):
		"""Tenta di eseguire il blocco della risorsa identificata da *command*. Se *row_id* è diverso da ``None``, è possibile eseguire il
		blocco di una singola riga di una tabella del database.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà una tupla ``(result, owner_data)``,
		dove *owner_data* è un ``dict`` contenente informazioni sull'utente che detiene già il blocco della risorsa in caso fosse già bloccata,
		oppure lancia un'eccezione :class:`~kongalib.Error` in caso di errore.
		"""
		return self._execute(CMD_LOCK, {
			IN_COMMAND_NAME: command,
			IN_ROW_ID: row_id
		}, ( OUT_ANSWER, OUT_OWNER_DATA ))
	
	def unlock_resource(self, command, row_id=None):
		"""Rilascia il blocco della risorsa identificata da *tablename* e *row_id*.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona, e verrà lanciata l'eccezione :class:`~kongalib.Error` in
		caso di errore.
		"""
		return self._execute(CMD_UNLOCK, {
			IN_COMMAND_NAME: command,
			IN_ROW_ID: row_id
		}, OUT_ANSWER)
	
	def select_data(self, tablename, fieldnamelist=None, where_expr=None, order_by=None, order_desc=False, offset=0, count=None, get_total=False, exist=None, progress=None):
		"""Genera ed esegue una SELECT sul server per ottenere una lista di risultati, a partire dalla tabella *tablename*.
		*fieldnamelist* è una lista di nomi dei campi da ottenere; se un campo fk_X di *tablename* è una foreign key, si può accedere ai
		campi della tabella collegata Y specificando "fk_X.Campo_di_Y"; la JOIN corrispondente verrà generata e gestita automaticamente dal
		server. Analogamente, si possono creare catene di JOIN implicite facendo riferimenti multipli di campi foreign key, per esempio
		"fk_X.fk_Y.fk_Z.Campo_di_Z".
		
		Se *where_expr* non è ``None``, può essere il corpo di una espressione WHERE SQL, e può contenere riferimenti nella stessa forma di
		*fieldnamelist*, per esempio "(Campo_di_X = 1) AND (fk_X.Campo_di_Y > 5)".
		
		*order_by* può essere un nome di campo per cui ordinare i risultati, dove *order_desc* specifica se ordinare in modo ascendente o discendente.
		*offset* e *count* permettono di restituire risultati solo a partire dal numero *offset*, e limitandosi a *count* risultati.
		
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato dipende dal valore del parametro *get_total*.
		Se *get_total* è ``True``, il risultato sarà una tupla nella forma ``(result_set, total_rows, exist_results)``; *total_rows* sarà il numero
		totale di righe come se *offset* e *limit* non fossero stati specificati, mentre *exist_results* sarà un ``dict`` le cui chiavi saranno gli
		ID specificati nel parametro *exist*, e i valori saranno ``True`` o ``False`` a seconda che il corrispettivo ID sia presente nel database
		per la tabella *tablename* oppure no.
		Se *get_total* è ``False``, il risultato sarà il solo *result_set*, ossia una lista di righe risultato della query, dove ogni riga è una
		lista di valori.
		"""
		if isinstance(fieldnamelist, text_base_types):
			fieldnamelist = [ fieldnamelist ]
		elif fieldnamelist:
			fieldnamelist = list(fieldnamelist)
		return self._execute(CMD_SELECT, {
			IN_TABLE_NAME: tablename,
			IN_COLUMN_NAMES: fieldnamelist,
			IN_WHERE_CLAUSE: where(where_expr),
			IN_ORDER_BY: order_by,
			IN_ORDER_DESC: order_desc,
			IN_OFFSET: offset,
			IN_ROW_COUNT: count,
			IN_GET_TOTAL_ROWS: get_total,
			IN_GET_ROWS_EXIST: exist,
		}, ( OUT_RESULT_SET, OUT_TOTAL_ROWS, OUT_EXIST ) if get_total else OUT_RESULT_SET, progress=progress)
	
	def select_data_as_dict(self, tablename, fieldnamelist=None, where_expr=None, order_by=None, order_desc=False, offset=0, count=None, get_total=False, progress=None):
		"""Esattamente come :meth:`.select_data`, ma l'oggetto ``asyncio.Future`` restituito una volta completato ritornerà un *result_set* sotto
		forma di lista di ``dict``, anzichè una lista di liste."""
		if isinstance(fieldnamelist, text_base_types):
			fieldnamelist = [ fieldnamelist ]
		elif fieldnamelist:
			fieldnamelist = list(fieldnamelist)
		def get_result(output):
			names = output.get(OUT_COLUMN_NAMES, None) or fieldnamelist
			result_set = [dict(list(zip(names, row))) for row in output[OUT_RESULT_SET] ]
			if get_total:
				return ( result_set, output[OUT_TOTAL_ROWS], output[OUT_EXIST] )
			else:
				return result_set
		return self._execute(CMD_SELECT, {
			IN_TABLE_NAME: tablename,
			IN_COLUMN_NAMES: fieldnamelist,
			IN_WHERE_CLAUSE: where(where_expr),
			IN_ORDER_BY: order_by,
			IN_ORDER_DESC: order_desc,
			IN_OFFSET: offset,
			IN_ROW_COUNT: count,
			IN_GET_TOTAL_ROWS: get_total,
		}, get_result, progress=progress)

	def get_record(self, tablename, code=None, id=None, field_names=None, row_extra_field_names=None, code_azienda=None, num_esercizio=None, mode=None, mask_binary=None, flags=GET_FLAG_DEFAULT, progress=None):
		"""Ottiene il record completo della tabella *tablename*, sotto forma di ``dict``. Il record può essere identificato in due modi: o
		tramite il solo *id*, oppure tramite la specifica dei parametri *code*, *code_azienda* e *num_esercizio*.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà un ``dict`` con il record ottenuto;
		verrà lanciata un'eccezione :class:`~kongalib.Error` in caso di errore.
		"""
		if (id is None) and (code is None):
			raise ValueError('Either code or id must be specified')
		def get_result(output):
			data = output[OUT_DICT_DATA]
			data['@checksum'] = output[OUT_CHECKSUM]
			return data
		return self._execute(CMD_GET, {
			IN_TABLE_NAME: tablename,
			IN_ROW_ID: id,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_FLAGS: flags,
			IN_COLUMN_NAMES: field_names,
			IN_ROW_EXTRA_FIELDS: row_extra_field_names,
		}, get_result, progress=progress)

	def insert_record(self, tablename, data, code_azienda=None, num_esercizio=None, log=None, progress=None):
		"""Inserisce un nuovo record nella tabella *tablename*. Il nuovo record, i cui dati sono passati nel ``dict`` *data*, sarà un record
		condiviso con tutte le aziende del database se *code_azienda* e *num_esercizio* sono ``None``, altrimenti apparterrà solo all'azienda e
		all'esercizio specificati.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà una tupla nella forma ``(id, code)``,
		dove *id* è l'ID univoco assegnato al record dal server, mentre *code* è il codice del record (che può essere diverso da quello passato
		in *data* se sono attivi i codici automatici per *tablename*); in caso di errore verrà lanciata un'eccezione di classe
		:class:`~kongalib.Error` o :class:`~kongalib.ErrorList`. Al termine dell'operazione, se *log* è un oggetto di classe :class:`OperationLog`,
		esso riceverà ogni eventuale messaggio di log prodotto dal server durante l'inserimento.
		"""
		return self._execute(CMD_INSERT_FROM_DICT, {
			IN_TABLE_NAME: tablename,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_DICT_DATA: data
		}, ( OUT_ID, OUT_CODE ), progress=progress, log=log)
	
	def update_record(self, tablename, data, code=None, id=None, code_azienda=None, num_esercizio=None, log=None, progress=None):
		"""Aggiorna un record esistente nella tabella *tablename*. Il record, i cui dati da aggiornare sono passati nel ``dict`` *data*, può
		essere identificato in due modi: o tramite il  solo *id*, oppure tramite la specifica dei parametri *code*, *code_azienda* e *num_esercizio*.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona; in caso di errore verrà lanciata un'eccezione di classe
		:class:`~kongalib.Error` o :class:`~kongalib.ErrorList`. Al termine dell'operazione, se *log* è un oggetto di classe :class:`OperationLog`,
		esso riceverà ogni eventuale messaggio di log prodotto dal server durante l'aggiornamento.
		"""
		return self._execute(CMD_UPDATE_FROM_DICT, {
			IN_TABLE_NAME: tablename,
			IN_ROW_ID: id,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_DICT_DATA: data
		}, progress=progress, log=log)
	
	def delete_record(self, tablename, code=None, id=None, code_azienda=None, num_esercizio=None, log=None, progress=None):
		"""Cancella un record dalla tabella *tablename*. Il record può essere identificato in due modi: o tramite il  solo *id*, oppure tramite
		la specifica dei parametri *code*, *code_azienda* e *num_esercizio*.
		La funzione restituisce un oggetto ``asyncio.Future`` per l'esecuzione asincrona; in caso di errore verrà lanciata un'eccezione di classe
		:class:`~kongalib.Error` o :class:`~kongalib.ErrorList`. Al termine dell'operazione, se *log* è un oggetto di classe :class:`OperationLog`,
		esso riceverà ogni eventuale messaggio di log prodotto dal server durante la cancellazione.
		"""
		return self._execute(CMD_DELETE_FROM_CODE, {
			IN_TABLE_NAME: tablename,
			IN_ROW_ID: id,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
		}, progress=progress, log=log)
	
	def code_exists(self, tablename, code, code_azienda, num_esercizio, extra_where=None):
		"""Controlla l'esistenza del codice *code* nella tabella *tablename* per l'azienda e l'esercizio specificati in *code_azienda* e *num_esercizio*.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà un valore booleano; in caso di errore verrà
		lanciata un'eccezione di classe :class:`~kongalib.Error`.
		"""
		return self._execute(CMD_CODE_EXISTS, {
			IN_TABLE_NAME: tablename,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_EXTRA_WHERE: where(extra_where),
		}, OUT_EXISTS)
	
	def get_next_available_code(self, tablename, code_azienda, num_esercizio, dry_run=False):
		return self._execute(CMD_GET_NEXT_CODE, {
			IN_TABLE_NAME: tablename,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_DRY_RUN: dry_run,
		}, OUT_CODE)

	def get_last_npfe(self, code_azienda, num_esercizio):
		return self._execute(CMD_GET_LAST_NPFE, {
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
		}, OUT_NPFE)
	
	def start_elab(self, command, params, code_azienda, num_esercizio, log=None, progress=None, tx=True):
		return self._execute(CMD_START_ELAB, {
			IN_COMMAND: command,
			IN_PARAMS: params,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_TX: tx,
		}, OUT_DATA)

	def list_binaries(self, field_or_tablename, id, type=None, progress=None):
		"""Ottiene la lista dei dati binari associati ad una scheda del database, identificata da *field_or_tablename* (che può essere un nome
		tabella o un campo da cui risolvere il nome tabella) e *id*. La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato
		una volta completato sarà una lista di tuple, in cui la n-esima tupla ha la forma ``( Tipo, NomeAllegato, NomeOriginale )``; *Tipo*
		è un intero ed è uno dei valori della *Choice* ``Resources``, *NomeAllegato* è il nome assegnato internamente a Konga per identificare
		univocamente il contenuto binario, mentre *NomeOriginale* è il nome del file originale da cui è stato caricato il contenuto. Se *type*
		è specificato, la funzione filtrerà i risultati in baso ad esso, ritornando solo le tuple con il *Tipo* corretto.
		"""
		def get_result(output):
			return [ tuple(row) for row in output[OUT_LIST] if ((type is None) or (row[0] == type)) ]
		return self._execute(CMD_LIST_BINARIES, {
			IN_FIELD_NAME: field_or_tablename,
			IN_ROW_ID: id,
		}, get_result, progress=progress)

	def fetch_image(self, fieldname, id, type, progress=None):
		"""Piccolo wrapper alla funzione :meth:`.fetch_binary`, dedicato alle immagini, con l'unica differenza che l'oggetto ``asyncio.Future``
		restituito una volta completato avrà come valore di ritorno direttamente il contenuto binario dell'immagine.
		"""
		return self._execute(CMD_FETCH_BINARY, {
			IN_FIELD_NAME: fieldname,
			IN_ROW_ID: id,
			IN_TYPE: type,
		}, OUT_DATA, progress=progress)

	def fetch_binary(self, field_or_tablename, id, type, filename=None, check_only=False, progress=None):
		"""Carica un contenuto binario dal server. *field_or_tablename* può essere un nome tabella o un campo da cui risolvere il nome tabella;
		questa tabella unita a *id* identificano la scheda del database da cui caricare la risorsa; *type* è uno dei valori della *Choice*
		``Resources``, mentre *filename* ha senso solo per identificare le risorse di tipo documento.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà una tupla di quattro elementi:
		( *dati*, *filename*, *original_filename*, *checksum* ). *dati* sono i dati binari che sono stati caricati dal server; *filename* è
		il nome file interno con cui è identificata la risorsa, *original_filename* è il nome del file originale che è stato specificato
		all'atto del salvataggio della risorsa sul server, mentre *checksum* è un checksum dei dati. Se *check_only* è ``True``, i dati
		binari della risorsa non verranno effettivamente caricati dal dispositivo di archiviazione in cui sono depositati, e *dati* sarà
		``None``; questa modalità è utile per verificare l'esistenza di una risorsa e il suo checksum senza effettivamente caricarla da remoto
		(nel caso di archiviazione su cloud il caricamento potrebbe essere lento)."""
		if (type == 0) and (not filename):
			raise ValueError('filename must be specified for document type resources')
		return self._execute(CMD_FETCH_BINARY, {
			IN_FIELD_NAME: field_or_tablename,
			IN_ROW_ID: id,
			IN_TYPE: type,
			IN_FILENAME: filename,
			IN_CHECK: check_only,
		}, ( OUT_DATA, OUT_FILENAME, OUT_ORIGINAL_FILENAME ), progress=progress)

	def store_binary(self, field_or_tablename, id, type, filename=None, original_filename=None, data=None, desc=None, force_delete=False, code_azienda=None, progress=None):
		"""Salva un contenuto binario sul server. *field_or_tablename* può essere un nome tabella o un campo da cui risolvere il nome tabella;
		questa tabella unita a *id* identificano la scheda a cui abbinare la risorsa; *type* è uno dei valori della *Choice*``Resources``;
		*filename* permette di specificare un nome file interno con cui identificare la risorsa (se ``None`` il server genererà un nome univoco
		automaticamente); *original_filename* è il nome file originale i cui dati si stanno salvando sul server; *data* sono i dati binari
		effettivi; *desc* è la descrizione da abbinare alla risorsa; *code_azienda* infine identifica l'azienda su cui si sta operando.
		La funzione restituisce un oggetto ``asyncio.Future`` il cui risultato una volta completato sarà il nome del file interno usato dal
		server per identificare la risorsa, che come detto sopra è uguale a *filename* se quest'ultimo è diverso da ``None``, altrimenti sarà
		il nome file generato dal server.
		Se *data* è ``None``, la funzione cancella i dati binari associati alla scheda; *force_delete* in questo caso può essere ``True`` se
		si desidera cancellare il riferimento ai dati anche se i dati non sono raggiungibili dal server."""
		return self._execute(CMD_STORE_BINARY, {
			IN_FIELD_NAME: field_or_tablename,
			IN_ROW_ID: id,
			IN_TYPE: type,
			IN_FILENAME: filename,
			IN_ORIGINAL_FILENAME: original_filename,
			IN_CODE_AZIENDA: code_azienda,
			IN_DATA: data,
			IN_DESC: desc,
			IN_FORCE_DELETE: force_delete,
		}, OUT_FILENAME, progress=progress)

	def translate(self, field, value, language):
		return self._execute(CMD_TRANSLATE, {
			IN_FIELD: field,
			IN_VALUE: value,
			IN_LANGUAGE: language
		}, OUT_TEXT)

	def set_database_language(self, language, progress=None):
		return self._execute(CMD_SET_DATABASE_LANGUAGE, {
			IN_LANGUAGE: language,
		}, progress=progress)



if __name__ == '__main__':
	import progress.bar
	import progress.spinner
	
	async def main():
		client = AsyncClient()
		await client.connect('127.0.0.1')
		await client.open_database('sqlite', 'demo')
		await client.authenticate('admin', '')

		# bar = progress.bar.IncrementalBar()
		bar = progress.spinner.Spinner()
		def prog(completeness, state, userdata):
			# bar.goto(completeness)
			bar.next()
			return False

		with bar:
			# async with client:
			try:
				df = await client.select_data('EB_DocumentiFiscali', ['NumeroInterno'], progress=prog)
			except Exception as e:
				df = None
				print(e)

		# print("DONE")
		drivers = client.list_drivers()
		dbs = client.list_databases()
		print(await asyncio.gather(drivers, dbs))
		print(df)


	asyncio.run(main(), debug=True)