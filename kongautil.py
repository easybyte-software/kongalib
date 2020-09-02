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
import kongalib

try:
	from shlex import quote
except:
	from pipes import quote

from kongalib.scripting import proxy as _proxy


PRINT_TARGET_PREVIEW			= 0		#: Stampa a video
PRINT_TARGET_PAPER				= 1		#: Stampa su carta
PRINT_TARGET_PDF				= 2		#: Stampa su file PDF
PRINT_TARGET_CSV				= 3		#: Stampa su file CSV
PRINT_TARGET_XLS				= 4		#: Stampa su file Excel


_last_client = None
_konga_args = None



class KongaRequiredError(RuntimeError):
	"""Eccezione lanciata quando si esegue una funzione disponibile solo dall'interno di Konga."""
	def __str__(self):
		return "Function requires script to be executed from within Konga"



class PrintError(RuntimeError):
	"""Eccezione lanciata se ci sono errori nell'esecuzione di una stampa con la funzione :func:`print_layout`."""
	def __init__(self, log):
		self._log = log
	def __unicode__(self):
		return u'Log:\n%s' % ('\n'.join([ ('  %s' % line) for line in kongalib.ensure_text(self._log.dumps()).split(u'\n') ]))
	def __str__(self):
		if kongalib.PY3:
			return self.__unicode__()
		else:
			return self.__unicode__().encode('utf-8')
	def get_log(self):
		"""Ottiene un oggetto di classe :class:`kongalib.Log` contenente gli errori di stampa."""
		return self._log



class ScriptContext(object):
	"""	Classe per l'accesso al contesto di esecuzione delle azioni esterne lato client di Konga.
	La classe prevede l'uso di proprietà per accedere alle informazioni in lettura e scrittura."""
	def __init__(self, database, company, tablename, record_id, record_code, record_data, **kwargs):
		self._database = database
		self._company = company
		self._tablename = tablename
		self._record_id = record_id
		self._record_code = record_code
		self._record_data = record_data
		self._params = kwargs
		self._result = None

	@property
	def database(self):
		"""Ritorna un oggetto ``dict`` che contiene informazioni sul database attualmente connesso.
		Contiene le chiavi ``name``, ``driver``, ``desc`` e tutti i nomi dei campi della tabella EB_Master,
		i cui valori sono presi dal database."""
		return self._database

	@property
	def company(self):
		"""Ritorna un oggetto ``dict`` che contiene informazioni sull'azienda attualmente impostata nella
		finestra che sta eseguendo l'azione esterna. Contiene come chiavi tutti i campi delle tabelle EB_Aziende
		e EB_StatoArchivi (al contrario della proprietà ``database`` le cui chiavi sono nella forma ``<nomecampo>``,
		qui i campi sono nella forma ``<nometabella>.<nomecampo>`` per evitare conflitti di nomi tra le tabelle
		EB_Aziende e EB_StatoArchivi) con i relativi valori presi dal database."""
		return self._company

	@property
	def tablename(self):
		"""Ritorna il nome della tabella su cui l'azione esterna sta operando."""
		return self._tablename
	
	@property
	def record_id(self):
		"""Ritorna l'ID (chiave primaria) del record su cui l'azione esterna sta operando. Vedere anche :meth:`.tablename`."""
		return self._record_id
	
	@property
	def record_code(self):
		"""Ritorna il codice del record su cui l'azione esterna sta operando. Vedere anche :meth:`.tablename`."""
		return self._record_code
	
	@property
	def record_data(self):
		"""Ritorna un ``dict`` con i dati del record visibili sulla scheda della finestra che sta eseguendo l'azione esterna."""
		return self._record_data

	@property
	def params(self):
		"""Ritorna un ``dict`` con i parametri che Konga passa allo script per l'esecuzione dell'azione esterna;
		questi parametri variano a seconda del tipo di azione che si sta eseguendo."""
		return self._params

	@property
	def result(self):
		"""Ritorna o imposta il valore di ritorno dell'azione esterna, in modo che Konga possa usarlo al termine dell'esecuzione dell'azione
		stessa. Il tipo ed il valore che andranno impostati dipendono dal tipo di azione esterna che si sta eseguendo."""
		return self._result

	@result.setter
	def result(self, result):
		self._result = result
		_proxy.util.set_script_result(result)



def connect(host=None, port=None, driver=None, database=None, username=None, password=None, tenant_key=None, config=None):
	"""Restituisce un oggetto :class:`kongalib.Client` già connesso. Se eseguito dall'interno di Konga, la connessione sarà stabilita
	con il server, il database e l'utenza correntemente aperti sul programma, e i parametri passati a questa funzione saranno ignorati.
	Se eseguita fuori da Konga, la funzione proverà a collegarsi al primo server disponibile sulla rete locale, aprendo il primo
	database disponibile autenticandosi col l'utenza *admin* con password vuota; ogni parametro di connessione può essere forzato
	tramite i parametri passati a questa funzione, oppure da linea di comando specificando gli argomenti ``--host``, ``--port``,
	``--driver``, ``-d|--database``, ``-u|--username``, ``-p|--password`` e ``-k|--tenant-key``. Inoltre, è possibile definire i
	parametri come variabili all'interno di un file di configurazione, nella sezione ``[kongautil.connect]``; tale file deve avere
	il nome passato a questa funzione con il parametro ``config``, altrimenti verranno ricercati nell'ordine anche il file con lo
	stesso nome dello script lanciato da terminale, ma con estensione ``.cfg``, il file ``kongalib.cfg`` sempre nella stessa directory
	da cui si esegue lo script e infine il file ``~/.kongalib`` (sotto Unix) o ``%userprofile%\kongalib.cfg`` (sotto Windows)."""
	if _proxy.is_valid():
		info = _proxy.util.get_connection_info()
		if info is not None:
			host, port, driver, database, username, password, tenant_key = info
			client = kongalib.Client()
			client.connect(host=host, port=port, options={ 'tenant_key': tenant_key })
			client.open_database(driver, database)
			client.authenticate(username, password)
			return client
	else:
		global _last_client
		global _konga_args
		client = kongalib.Client()
		if host is None:
			import argparse
			try:
				import configparser
			except:
				import ConfigParser as configparser
			files = [
				os.path.splitext(sys.argv[0])[0] + '.cfg',
				os.path.join(os.path.abspath(os.path.dirname(__file__)), 'kongalib.cfg'),
				os.path.expanduser(os.path.join('~', 'kongalib.cfg' if sys.platform == 'win32' else '.kongalib')),
			]
			if config:
				files.insert(0, config)
			config = configparser.RawConfigParser({
				'host':			host or '',
				'port':			str(port or ''),
				'driver':		driver or '',
				'database':		database or '',
				'username':		username or '',
				'password':		password or '',
				'tenant_key':	tenant_key or '',
			})
			config.add_section('kongautil.connect')
			config.add_section('kongautil.print_layout')
			for filename in files:
				try:
					config.read(filename)
				except:
					pass
				else:
					break
			host = config.get('kongautil.connect', 'host') or None
			try:	port = int(config.get('kongautil.connect', 'port'))
			except:	pass
			driver = config.get('kongautil.connect', 'driver') or None
			database = config.get('kongautil.connect', 'database') or None
			username = config.get('kongautil.connect', 'username') or None
			password = config.get('kongautil.connect', 'password') or None
			tenant_key = config.get('kongautil.connect', 'tenant_key') or None

			_konga_args = config.get('kongautil.print_layout', 'konga_args') or None

			class ArgumentParser(argparse.ArgumentParser):
				def exit(self, status=0, message=None):
					if status:
						raise RuntimeError
			parser = ArgumentParser()
			parser.add_argument('--host', default=host)
			parser.add_argument('--port', type=int, default=port)
			parser.add_argument('--driver', default=driver)
			parser.add_argument('-d', '--database', default=database)
			parser.add_argument('-u', '--username', default=username)
			parser.add_argument('-p', '--password', default=password)
			parser.add_argument('-k', '--tenant-key', default=tenant_key)
			try:
				args = parser.parse_args()
				host = args.host
				port = args.port
				driver = args.driver
				database = args.database
				username = args.username
				password = args.password
				tenant_key = args.tenant_key
			except:
				pass
		if host is None:
			servers_list = client.list_servers(timeout=500)
			if servers_list:
				host = servers_list[0]['host']
				port = servers_list[0]['port']
		if host is not None:
			client.connect(host=host, port=port or 0, options={ 'tenant_key': tenant_key })
			db_list = None
			if driver is None:
				if database is not None:
					db_list = client.list_databases(timeout=500)
					for driver, dbs in db_list.items():
						if database in [ db['name'] for db in dbs ]:
							break
					else:
						driver = None
				if driver is None:
					drivers_list = client.list_drivers(timeout=500)
					if drivers_list:
						driver = drivers_list[0]['name']
			if (driver is not None) and (database is None):
				if db_list is None:
					db_list = client.list_databases(driver, timeout=500)
				if db_list and (len(db_list[driver]) > 0):
					database = db_list[driver][0]['name']
			if (driver is not None) and (database is not None):
				client.open_database(driver, database)
				client.authenticate(username or 'admin', password or '')
				_last_client = client
				return client
	raise kongalib.Error(kongalib.DATABASE_NOT_CONNECTED, "No database connected")



def get_window_vars():
	"""Restituisce un ``dict`` contenente una serie di costanti definite per la finestra di navigazione correntemente aperta su Konga, incluse informazioni
	sull'azienda corrente, l'eventuale selezione se la finestra mostra una vista a lista, e molto altro. Se la funzione è eseguita fuori da Konga, il ``dict``
	restituito sarà vuoto."""
	if _proxy.is_valid():
		return _proxy.util.get_window_vars()
	else:
		return {}



def _run_script(script, log):
	import tempfile, subprocess
	client_exe = None
	if sys.platform == 'win32':
		files = ( 'kongaclient.com', 'konga.com' )
	else:
		files = ( 'easybyte-konga-client', 'easybyte-konga' )
	path = os.environ.get("PATH", None)
	if path is None:
		try:
			path = os.confstr("CS_PATH")
		except (AttributeError, ValueError):
			path = os.defpath
	if path is not None:
		path = path.split(os.pathsep)
		for exe in files:
			seen = set()
			for dir in path:
				normdir = os.path.normcase(dir)
				if not normdir in seen:
					seen.add(normdir)
					name = os.path.join(dir, exe)
					if os.path.exists(name) and os.access(name, os.F_OK | os.X_OK) and not os.path.isdir(name):
						client_exe = exe
						break
			if client_exe is not None:
				break
	if client_exe is None:
		raise RuntimeError('Cannot find Konga executable')
	if _last_client is not None:
		info = _last_client.get_connection_info()
		lines = [
			'.connect "%s" -p %d' % (info['host'], info['port']),
			'.user "%s" -p "%s"' % (info['user']['name'], info['user']['password']),
			'.open_database "%s" -d "%s"' % (info['database']['name'], info['database']['driver']),
		]
	else:
		lines = []
	temp = tempfile.NamedTemporaryFile(mode='w', delete=False)
	with temp:
		temp.write('\n'.join(lines + script))
	try:
		output = subprocess.check_output('%s %s --script "%s"' % (client_exe, _konga_args or '', temp.name), stderr=subprocess.STDOUT, shell=True, universal_newlines=True).splitlines()
		for line in output:
			log.info(line)
	except subprocess.CalledProcessError as e:
		log.warning("Errors running script:")
		output = e.output.splitlines()
		for line in output:
			log.error(line)
		log.info("Original script was:")
		for line in script:
			log.info("    %s" % line)
	finally:
		os.unlink(temp.name)



def print_layout(command_or_layout, builtins=None, code_azienda=None, code_esercizio=None, target=None, filename=None, progress=True):
	"""Esegue una stampa su Konga. *command_or_layout* può essere un nome di comando di Konga, oppure un sorgente XML contenente la struttura stessa del layout da
	stampare; *builtins* è un ``dict`` i cui valori verranno passati al motore di stampa e saranno disponibili all'interno degli script del layout; *code_azienda* e
	*code_esercizio* identificano l'azienda e l'esercizio per cui eseguire la stampa, mentre *target* è una delle costanti ``PRINT_TARGET_*`` definite sopra, che
	specificano la destinazione della stampa (se non specificata e la funzione è eseguita all'interno di Konga, verrà assunta ``PRINT_TARGET_PREVIEW``,
	altrimenti ``PRINT_TARGET_PDF``); *filename* è il nome del file da salvare ed ha un senso solo quando si stampa su file. Se *progress* è ``True`` verrà mostrata
	a video una barra di progresso dell'operazione di stampa.
	La funzione restituisce un oggetto di classe :class:`kongalib.Log` con il resoconto dell'operazione di stampa, oppure lancia un'eccezione di classe
	:class:`kongautil.PrintError` in caso di errori.
	
	.. warning::
	   Se eseguita fuori da Konga, questa funzione richiede che sull'host sia stato installato Konga Client (o Konga), e non supporta come *target* i valori
	   ``PRINT_TARGET_PREVIEW`` e ``PRINT_TARGET_PAPER``.
	"""
	if _proxy.is_valid():
		if target is None:
			target = PRINT_TARGET_PREVIEW
		log = _proxy.util.print_layout(command_or_layout, builtins or {}, code_azienda, code_esercizio, target, filename, progress)
	else:
		log = kongalib.Log()
		if not filename:
			raise ValueError("Output filename must be specified")
		if isinstance(command_or_layout, kongalib.text_base_types) and (command_or_layout.strip().startswith('<?xml') or command_or_layout.strip().startswith('<layout')):
			import tempfile
			temp = tempfile.NamedTemporaryFile(mode='w', delete=False)
			with temp:
				temp.write(command_or_layout)
			command_or_layout = temp.name
		else:
			temp = None
		target = {
			PRINT_TARGET_PDF:		'pdf',
			PRINT_TARGET_CSV:		'csv',
			PRINT_TARGET_XLS:		'xls',
		}.get(target, 'pdf')
		builtins = builtins or {}
		if code_azienda:
			builtins['COMPANY_CODE'] = code_azienda
		if code_esercizio:
			builtins['ACCOUNTING_YEAR_CODE'] = code_esercizio
		script = [
			'.print "%s" %s -o %s -f "%s"' % (command_or_layout, ' '.join([ '%s=%s' % (key, quote(str(value))) for key, value in builtins.items() ]), target, filename)
		]
		try:
			_run_script(script, log)
		finally:
			if temp is not None:
				os.unlink(temp)
	if log.has_errors():
		raise PrintError(log)
	return log



def print_log(log, title, target=PRINT_TARGET_PREVIEW, filename=None):
	"""Stampa il contenuto dell'oggetto *log* di classe :class:`kongalib.Log`; se si esegue questa funzione dall'interno di Konga, verrà usata la funzione
	:func:`print_layout`, passando i parametri *target* e *filename*; viceversa se si esegue fuori da Konga, il log verrà stampato su terminale."""
	if _proxy.is_valid():
		template = """<?xml version='1.0' encoding='utf-8'?>
			<layout version="2" name="%(title)s" title="%(title)s" orientation="vertical" margin_top="75" margin_right="75" margin_bottom="75" margin_left="75">
				<init>
					<![CDATA[set_datasource(Datasource(['id', 'type', 'message'], DATA, 'Master'))
]]></init>
				<header width="100%%" height="175" only_first="true">
					<label width="100%%" height="100" align="center" font_size="14" bgcolor="#EEE" border_edges="left|right|top|bottom">%(title)s</label>
				</header>
				
				<module width="100%%" alt_bgcolor="#EEE" condition="iterate('id')">
					<field top="0" width="10%%" align="top" type="data">type</field>
					<field left="10%%" top="0" width="90%%" align="top" wrapping="wrap" type="data">message</field>
				</module>
				<module width="100%%">
					<init>
						<![CDATA[this.visible = (len(DATA) == 0)
]]></init>
					<label width="100%%" align="center">
						<text>
							<it>Operazione completata con successo</it>
						</text>
					</label>
				</module>
				
				<footer width="100%%" font_size="7" height="175">
					<rect top="75" width="100%%" height="100" />
					<field padding_left="50" top="75" left="0" width="30%%" height="50" align="bottom" type="expr">DATABASE_NAME</field>
					<field padding_left="50" top="125" left="0" width="30%%" height="50" align="top" type="expr">COMPANY_NAME</field>
					<field top="75" left="30%%" width="40%%" height="50" align="hcenter|bottom" type="expr">TITLE</field>
					<datetime top="125" left="30%%" width="40%%" height="50" align="hcenter|top" format="PdmyHM">
						<text>
							<it>Stampato da $USER_NAME il %%d alle %%t</it>
							<nl>Afgedrukt door $USER_NAME op %%d om %%t uur</nl>
						</text>
					</datetime>
					<page padding_right="50" top="75" left="80%%" width="20%%" height="100" align="vcenter|right">
						<text>
							<it>Pagina %%p di %%t</it>
							<nl>Pagina %%p van %%t</nl>
						</text>
					</page>
				</footer>
			</layout>
		""" % {
			'title':	title,
		}
		data = []
		for index, message in enumerate(log.get_messages()):
			msg = log.strip_html(message[1])
			if isinstance(msg, bytes):
				msg = msg.decode('utf-8', 'replace')
			data.append((index, ('INFO', 'WARNING', 'ERROR')[message[0]], msg))
		
		print_layout(template, { 'DATA': data }, target=target, filename=filename)
	else:
		import colorama
		print(colorama.Style.BRIGHT + title + colorama.Style.RESET_ALL)
		status = {
			kongalib.Log.INFO:		colorama.Style.BRIGHT + "INFO      " + colorama.Style.RESET_ALL,
			kongalib.Log.WARNING:	colorama.Style.BRIGHT + colorama.Fore.YELLOW + "WARNING   " + colorama.Style.RESET_ALL,
			kongalib.Log.ERROR:		colorama.Style.BRIGHT + colorama.Fore.RED + "ERROR     " + colorama.Style.RESET_ALL,
		}
		for message in log.get_messages():
			print('%s%s' % (status[message[0]], message[1]))



def suspend_timeout():
	"""Sospende il timeout di esecuzione dello script. La funzione non comporta eccezioni ma non ha alcun effetto se eseguita al di fuori di Konga."""
	if _proxy.is_valid():
		return _proxy.builtin.set_timeout()



def resume_timeout(timeout):
	"""Ripristina il timeout di esecuzione dello script. La funzione non comporta eccezioni ma non ha alcun effetto se eseguita al di fuori di Konga."""
	if _proxy.is_valid():
		_proxy.builtin.set_timeout(timeout)



def set_timeout(timeout):
	"""Imposta il timeout di esecuzione dello script in secondi, passati i quali verrà mostrata una finestra di avviso. La funzione non comporta eccezioni ma non ha alcun effetto se eseguita al di fuori di Konga."""
	if _proxy.is_valid():
		_proxy.builtin.set_timeout(timeout * 1000)



def _get_external_path(images, table_name, code_azienda):
	import os, os.path
	client = _last_client or connect()
	paths = client.select_data('EB_Master', ['PathFileLocali'])[0][0].split(chr(0))
	for path in paths:
		path = os.path.normpath(path)
		if os.access(path, os.F_OK|os.R_OK|os.W_OK):
			if code_azienda:
				business_path = os.path.join(path, 'aziende', client.select_data('EB_Aziende', ['RagioneSociale'], "Codice = '%s'" % code_azienda)[0][0])
			else:
				business_path = None
			table_type = client.execute(kongalib.CMD_GET_TABLE_TYPES)[kongalib.OUT_TYPES].get(table_name, 1)
			if (table_type == 2) and (business_path is None):
				raise ValueError('Business code required for business tables')
			if (table_type == 2) or ((table_type == 3) and (code_azienda is not None)):
				path = business_path
			else:
				path = os.path.join(path, 'common')
			return os.path.join(path, 'Immagini' if images else 'Allegati', table_name)
	else:
		raise RuntimeError('Unable to autodetect external data path')



def get_external_images_path(table_name, code_azienda):
	"""Restituisce il percorso per accedere ai file delle immagini associate ai record della tabella *table_name* per il database corrente e l'azienda specificata da *code_azienda* (passando ``None`` come
	*code_azienda* verrà restituito il percorso dei file comuni a tutte le aziende); se nessun database è attualmente connesso, la funzione restituirà ``None``.
	"""
	if _proxy.is_valid():
		return _proxy.util.get_external_path(True, table_name, code_azienda)
	else:
		return _get_external_path(True, table_name, code_azienda)



def get_external_attachments_path(table_name, code_azienda):
	"""Restituisce il percorso per accedere ai file degli allegati associati ai record della tabella *table_name* per il database corrente e l'azienda specificata da *code_azienda* (passando ``None`` come
	*code_azienda* verrà restituito il percorso dei file comuni a tutte le aziende); se nessun database è attualmente connesso, la funzione restituirà ``None``.
	"""
	if _proxy.is_valid():
		return _proxy.util.get_external_path(False, table_name, code_azienda)
	else:
		return _get_external_path(False, table_name, code_azienda)



def get_site_packages():
	"""Restituisce una lista di percorsi di installazione dei pacchetti Python."""
	if _proxy.is_valid():
		return [ _proxy.util.get_site_packages() ]
	else:
		import site
		return site.getsitepackages()



def notify_data_changes(table_name, row_id=None):
	"""Notifica Konga che uno o tutti i record di una tabella sono stati modificati, causando un aggiornamento a tutti quei client Konga che stanno operando su tali record. Se *row_id* è ``None``, tutti
	i record della tabella *table_name* verranno marcati come modificati, altrimenti il solo record con *ID* *row_id*. La funzione non comporta eccezioni ma non ha alcun effetto se eseguita al di fuori di Konga."""
	if _proxy.is_valid():
		_proxy.util.notify_data_changes(table_name, row_id)



def open_uri(uri):
	"""Tenta di aprire l'URI specificato con l'applicazione predefinita di sistema (se configurata)."""
	import subprocess
	if sys.platform == 'darwin':
		subprocess.call(('open', uri))
	elif sys.platform == 'win32':
		os.startfile(uri)
	else:
		subprocess.call(('xdg-open', uri))



def get_context():
	"""Restituisce un oggetto di classe :class:`kongautil.ScriptContext` da usare per la gestione dell'I/O da parte degli script usati come azioni esterne di Konga.

	.. warning::
	   Questa funzione è disponibile solo all'interno di Konga; eseguendola da fuori verrà lanciata l'eccezione :class:`kongautil.KongaRequiredError`.
	"""
	if _proxy.is_valid():
		return _proxy.util.get_context()
	else:
		raise KongaRequiredError



def is_batch():
	"""Restituisce ``True`` se lo script è eseguito con Python da linea di comando, ``False`` se è eseguito dall'interno di Konga."""
	return not _proxy.is_valid()

