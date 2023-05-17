# -*- coding: utf-8 -*-

import pkg_resources

from . import json


_CONSTANTS = {
	'OK': 0,                                                         #: Nessun errore
	'ERROR': -1,                                                     #: Errore generico
	'INTERNAL_ERROR': 1,                                             #: Errore interno
	'OUT_OF_MEMORY': 2,                                              #: Memoria esaurita
	'ACCESS_DENIED': 3,                                              #: Accesso negato
	'TIMED_OUT': 4,                                                  #: Tempo scaduto
	'INTERRUPTED': 5,                                                #: Operazione interrotta
	'NOT_INITIALIZED': 6,                                            #: Oggetto non inizializzato
	'ABORTED': 7,                                                    #: Operazione annullata
	'TOO_MANY_OPEN_FILES': 8,                                        #: Troppi file aperti
	'FILE_NOT_FOUND': 9,                                             #: File non trovato
	'IO_ERROR': 10,                                                  #: Errore di input/output
	'FILE_EXISTS': 11,                                               #: Il file già esiste
	'RESOURCE_UNAVAILABLE': 12,                                      #: La risorsa non è disponibile
	'DISK_FULL': 13,                                                 #: Disco pieno
	'WOULD_BLOCK': 14,                                               #: L'operazione sarebbe bloccante
	'INVALID_RESOURCE': 15,                                          #: Risorsa non valida
	'BROKEN_PIPE': 16,                                               #: Pipe terminata
	'CANNOT_CREATE_SOCKET': 100,                                     #: Impossibile creare il socket
	'PROTOCOL_NOT_SUPPORTED': 101,                                   #: Protocollo non supportato
	'BAD_ADDRESS': 102,                                              #: Indirizzo dell'host non valido
	'CONNECTION_REFUSED': 103,                                       #: Connessione rifiutata
	'NETWORK_IS_UNREACHABLE': 104,                                   #: La rete non è raggiungibile
	'HOST_IS_UNREACHABLE': 105,                                      #: L'host non è raggiungibile
	'ADDRESS_ALREADY_IN_USE': 106,                                   #: Indirizzo già in uso
	'CANNOT_CONNECT': 107,                                           #: Impossibile connettersi
	'CANNOT_CONFIGURE_SOCKET': 108,                                  #: Impossibile configurare il socket
	'CANNOT_BIND_SOCKET': 109,                                       #: Impossibile effettuare il bind del socket
	'CANNOT_LISTEN_SOCKET': 110,                                     #: Impossibile mettere il socket in ascolto
	'WINSOCK_VERSION_NOT_SUPPORTED': 111,                            #: Versione di Winsock non supportata
	'ERROR_READING_SOCKET': 112,                                     #: Errore in lettura dal socket
	'ERROR_WRITING_SOCKET': 113,                                     #: Errore in scrittura sul socket
	'NOT_CONNECTED': 114,                                            #: Non connesso
	'CONNECTION_LOST': 115,                                          #: La connessione è stata persa
	'ALREADY_CONNECTED': 116,                                        #: Connessione già stabilita
	'BAD_SOCKET': 117,                                               #: Socket non valido
	'NO_NICS_FOUND': 118,                                            #: Nessuna interfaccia di rete trovata
	'BAD_REQUEST': 200,                                              #: Richiesta di esecuzione non valida
	'BAD_REPLY': 201,                                                #: Risposta dal server non valida
	'NOT_AUTHORIZED': 202,                                           #: Autorizzazione fallita
	'AUTHORIZATION_DATA_TOO_BIG': 203,                               #: Dati di autorizzazione troppo grandi
	'EXECUTE_FAILED': 204,                                           #: La richiesta di esecuzione è fallita sul server
	'EXECUTE_ABORTED': 205,                                          #: Richiesta di esecuzione annullata dall'utente
	'LISTENER_PORT_UNAVAILABLE': 206,                                #: Porta di ascolto non disponibile
	'RESPONDER_PORT_UNAVAILABLE': 207,                               #: Porta di risposta non disponibile
	'CLIENT_NOT_FOUND': 208,                                         #: Client ID non trovato
	'SKIP_REQUEST': 209,                                             #: Non registrare la richiesta al server
	'OK_NO_TRANSACTION': 212,                                        #: Completa la richiesta con successo senza commit/rollback di transazione
	'ARCHIVE_NOT_FOUND': 300,                                        #: Archivio non trovato
	'MALFORMED_RESOURCE_INDEX': 301,                                 #: Indice delle risorse non valido nell'archivio
	'MALFORMED_RESOURCE_DEFINITION': 302,                            #: Definizione della risorsa non valida
	'CANNOT_FIND_RESOURCE_IN_ARCHIVE': 303,                          #: Risorsa non trovata nell'archivio
	'CANNOT_READ_RESOURCE': 304,                                     #: Impossibile leggere la risorsa
	'CONFLICTING_RESOURCE_FILE_NAME': 305,                           #: Il nome del file di risorsa è in conflitto con un altro file nell'archivio
	'CANNOT_WRITE_RESOURCE': 306,                                    #: Impossibile scrivere la risorsa
	'ARCHIVE_NOT_LOADED': 307,                                       #: Archivio non caricato
	'BAD_STREAM': 400,                                               #: Flusso dati corrotto
	'END_STREAM': 401,                                               #: Flusso dati terminato
	'NO_MATCH': 500,                                                 #: Nessun risultato
}

_EXTERNAL = {}


def _ensure():
	if not _EXTERNAL.get('@fetched', False):
		if pkg_resources.resource_exists('kongalib', 'constants.json'):
			with pkg_resources.resource_stream('kongalib', 'constants.json') as f:
				data = json.loads(f)
			if isinstance(data, dict):
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
