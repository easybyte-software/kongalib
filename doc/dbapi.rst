Python Database API
===================


Kongalib supporta le specifiche 2.0 delle API Python per database, come definito sul :pep:`0249`.
Per poter usare le API Python DB, occorre includere ``kongalib.db``, dove è definita la funzione :func:`~.kongalib.db.connect`. Tramite
questa si può ottenere un oggetto ``Connection`` (vedere :pep:`0249#connection-objects`) su cui operare.
Le API Python DB possono essere comode se tutto quello che si vuole fare è eseguire delle query SQL direttamente sul server; in tal caso
questo approccio evita di dover instanziare ed usare un oggetto :class:`kongalib.Client`.


.. automodule:: kongalib.db
	:members: apilevel, threadsafety, paramstyle, Error, InternalError, OperationalError, ProgrammingError, Connection, Cursor, connect
	:member-order: bysource

