# -*- coding: utf-8 -*-

import importlib.resources

from . import json


OK = 0                                                         #: Nessun errore
ERROR = -1                                                     #: Errore generico
INTERNAL_ERROR = 1                                             #: Errore interno
OUT_OF_MEMORY = 2                                              #: Memoria esaurita
ACCESS_DENIED = 3                                              #: Accesso negato
TIMED_OUT = 4                                                  #: Tempo scaduto
INTERRUPTED = 5                                                #: Operazione interrotta
NOT_INITIALIZED = 6                                            #: Oggetto non inizializzato
ABORTED = 7                                                    #: Operazione annullata
TOO_MANY_OPEN_FILES = 8                                        #: Troppi file aperti
FILE_NOT_FOUND = 9                                             #: File non trovato
IO_ERROR = 10                                                  #: Errore di input/output
FILE_EXISTS = 11                                               #: Il file già esiste
RESOURCE_UNAVAILABLE = 12                                      #: La risorsa non è disponibile
DISK_FULL = 13                                                 #: Disco pieno
WOULD_BLOCK = 14                                               #: L'operazione sarebbe bloccante
INVALID_RESOURCE = 15                                          #: Risorsa non valida
BROKEN_PIPE = 16                                               #: Pipe terminata
CANNOT_CREATE_SOCKET = 100                                     #: Impossibile creare il socket
PROTOCOL_NOT_SUPPORTED = 101                                   #: Protocollo non supportato
BAD_ADDRESS = 102                                              #: Indirizzo dell'host non valido
CONNECTION_REFUSED = 103                                       #: Connessione rifiutata
NETWORK_IS_UNREACHABLE = 104                                   #: La rete non è raggiungibile
HOST_IS_UNREACHABLE = 105                                      #: L'host non è raggiungibile
ADDRESS_ALREADY_IN_USE = 106                                   #: Indirizzo già in uso
CANNOT_CONNECT = 107                                           #: Impossibile connettersi
CANNOT_CONFIGURE_SOCKET = 108                                  #: Impossibile configurare il socket
CANNOT_BIND_SOCKET = 109                                       #: Impossibile effettuare il bind del socket
CANNOT_LISTEN_SOCKET = 110                                     #: Impossibile mettere il socket in ascolto
WINSOCK_VERSION_NOT_SUPPORTED = 111                            #: Versione di Winsock non supportata
ERROR_READING_SOCKET = 112                                     #: Errore in lettura dal socket
ERROR_WRITING_SOCKET = 113                                     #: Errore in scrittura sul socket
NOT_CONNECTED = 114                                            #: Non connesso
CONNECTION_LOST = 115                                          #: La connessione è stata persa
ALREADY_CONNECTED = 116                                        #: Connessione già stabilita
BAD_SOCKET = 117                                               #: Socket non valido
NO_NICS_FOUND = 118                                            #: Nessuna interfaccia di rete trovata
BAD_REQUEST = 200                                              #: Richiesta di esecuzione non valida
BAD_REPLY = 201                                                #: Risposta dal server non valida
NOT_AUTHORIZED = 202                                           #: Autorizzazione fallita
AUTHORIZATION_DATA_TOO_BIG = 203                               #: Dati di autorizzazione troppo grandi
EXECUTE_FAILED = 204                                           #: La richiesta di esecuzione è fallita sul server
EXECUTE_ABORTED = 205                                          #: Richiesta di esecuzione annullata dall'utente
LISTENER_PORT_UNAVAILABLE = 206                                #: Porta di ascolto non disponibile
RESPONDER_PORT_UNAVAILABLE = 207                               #: Porta di risposta non disponibile
CLIENT_NOT_FOUND = 208                                         #: Client ID non trovato
SKIP_REQUEST = 209                                             #: Non registrare la richiesta al server
OK_NO_TRANSACTION = 212                                        #: Completa la richiesta con successo senza commit/rollback di transazione
ARCHIVE_NOT_FOUND = 300                                        #: Archivio non trovato
MALFORMED_RESOURCE_INDEX = 301                                 #: Indice delle risorse non valido nell'archivio
MALFORMED_RESOURCE_DEFINITION = 302                            #: Definizione della risorsa non valida
CANNOT_FIND_RESOURCE_IN_ARCHIVE = 303                          #: Risorsa non trovata nell'archivio
CANNOT_READ_RESOURCE = 304                                     #: Impossibile leggere la risorsa
CONFLICTING_RESOURCE_FILE_NAME = 305                           #: Il nome del file di risorsa è in conflitto con un altro file nell'archivio
CANNOT_WRITE_RESOURCE = 306                                    #: Impossibile scrivere la risorsa
ARCHIVE_NOT_LOADED = 307                                       #: Archivio non caricato
BAD_STREAM = 400                                               #: Flusso dati corrotto
END_STREAM = 401                                               #: Flusso dati terminato
NO_MATCH = 500                                                 #: Nessun risultato


CMD_GET_PERMISSIONS = 33
CMD_SET_PERMISSIONS = 34
CMD_BEGIN_TRANSACTION = 28
CMD_COMMIT_TRANSACTION = 29
CMD_ROLLBACK_TRANSACTION = 30
CMD_LOCK = 48
CMD_UNLOCK = 49
CMD_SELECT = 37
CMD_GET = 39
CMD_INSERT_FROM_DICT = 44
CMD_UPDATE_FROM_DICT = 45
CMD_DELETE_FROM_CODE = 47
CMD_CODE_EXISTS = 42
CMD_GET_NEXT_CODE = 43
CMD_GET_LAST_NPFE = 89
CMD_START_ELAB = 54
CMD_LIST_BINARIES = 86
CMD_FETCH_BINARY = 55
CMD_STORE_BINARY = 74
CMD_TRANSLATE = 66
CMD_SET_DATABASE_LANGUAGE = 67

IN_CHECK = 'CHECK'
IN_CODE = 'CODE'
IN_CODE_AZIENDA = 'CODE_AZIENDA'
IN_COLUMN_NAMES = 'COLUMN_NAMES'
IN_COMMAND = 'COMMAND'
IN_COMMAND_NAME = 'COMMAND_NAME'
IN_DATA = 'DATA'
IN_DESC = 'DESC'
IN_DICT_DATA = 'DICT_DATA'
IN_DRY_RUN = 'DRY_RUN'
IN_EXTRA_WHERE = 'EXTRA_WHERE'
IN_FIELD = 'FIELD'
IN_FIELD_NAME = 'FIELD_NAME'
IN_FILENAME = 'FILENAME'
IN_FLAGS = 'FLAGS'
IN_FORCE_DELETE = 'FORCE_DELETE'
IN_GET_ROWS_EXIST = 'GET_ROWS_EXIST'
IN_GET_TOTAL_ROWS = 'GET_TOTAL_ROWS'
IN_LANGUAGE = 'LANGUAGE'
IN_NUM_ESERCIZIO = 'NUM_ESERCIZIO'
IN_OFFSET = 'OFFSET'
IN_ORDER_BY = 'ORDER_BY'
IN_ORDER_DESC = 'ORDER_DESC'
IN_ORIGINAL_FILENAME = 'ORIGINAL_FILENAME'
IN_PARAMS = 'PARAMS'
IN_PERMISSIONS = 'PERMISSIONS'
IN_ROW_COUNT = 'ROW_COUNT'
IN_ROW_EXTRA_FIELDS = 'ROW_EXTRA_FIELDS'
IN_ROW_ID = 'ROW_ID'
IN_TABLE_NAME = 'TABLE_NAME'
IN_TRANSACTION = 'TRANSACTION'
IN_TX = 'TX'
IN_TYPE = 'TYPE'
IN_USER_ID = 'USER_ID'
IN_VALUE = 'VALUE'
IN_WHERE_CLAUSE = 'WHERE_CLAUSE'
IN_LABEL = 'LABEL'
IN_METADATA = 'METADATA'
IN_CODE_TIPOLOGIA = 'CODE_TIPOLOGIA'

OUT_CHECKSUM = 'CHECKSUM'
OUT_CODE = 'CODE'
OUT_COLUMN_NAMES = 'COLUMN_NAMES'
OUT_DATA = 'DATA'
OUT_DATA_CHECKSUM = 'DATA_CHECKSUM'
OUT_DICT_DATA = 'DICT_DATA'
OUT_ERRNO = 'ERRNO'
OUT_ERROR = 'ERROR'
OUT_EXIST = 'EXIST'
OUT_FILENAME = 'FILENAME'
OUT_ID = 'ID'
OUT_LIST = 'LIST'
OUT_LOG = 'LOG'
OUT_NPFE = 'NPFE'
OUT_ORIGINAL_FILENAME = 'ORIGINAL_FILENAME'
OUT_PERMISSIONS = 'PERMISSIONS'
OUT_RESULT_SET = 'RESULT_SET'
OUT_TEXT = 'TEXT'
OUT_TOTAL_ROWS = 'TOTAL_ROWS'
OUT_METADATA = 'METADATA'
OUT_CODE_TIPOLOGIA = 'CODE_TIPOLOGIA'


_CONSTANTS = { key: value for key, value in locals().items() if key.isupper() }

_EXTERNAL = {}


def _ensure():
	if not _EXTERNAL.get('@fetched', False):
		try:
			data = json.loads(importlib.resources.files('kongalib').joinpath('constants.json').read_bytes())
		except:
			data = None
		if isinstance(data, dict):
			existing = globals()
			for key, value in data.items():
				if (key in existing) and (value != existing[key]) and (key not in ('IO_ERROR','DISK_FULL')):
					raise RuntimeError(f"Value '{value}' for {key} in constants.json mismatch (should be '{existing[key]}')")
			_EXTERNAL.update(data)
		_CONSTANTS.update(_EXTERNAL)
		_EXTERNAL['@fetched'] = True
	return _CONSTANTS.keys()
__all__ = list(_ensure())



def __getattr__(name):
	if name in _CONSTANTS:
		return _CONSTANTS[name]
	else:
		raise AttributeError(f"module {__name__!r} has no attribute {name!r} (!)")



def __dir__():
	return __all__
