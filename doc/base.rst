Operazioni base
===============

Per poter eseguire comandi su un server Konga, si deve instanziare ed usare un oggetto di classe :class:`~.kongalib.Client`.


Classe Client
-------------

.. autoclass:: kongalib.Client
   :members:



Esempi
------

Di seguito vengono riportati alcuni esempi di utilizzo della classe :class:`~.kongalib.Client`; si assume che ci sia un server Konga
disponibile su localhost e che esista su di esso un database SQLite "demo" inizializzato con i dati di esempio.

Esempio di connessione e lista dell'archivio clienti presenti sul database::

	import kongalib
	
	c = kongalib.Client()
	c.connect(host='localhost')
	c.open_database('sqlite', 'demo')
	c.authenticate('admin', '')
	results = c.select_data('EB_ClientiFornitori', ['Codice', 'RagioneSociale'], 'Tipo = 1')
	for row in results:
		print row

Esempio di come ottenere tutto il record di un documento fiscale (testata e righe)::

	import kongalib
	
	def print_data(data, indent=1):
		# Stampa i dati, tralasciando le chiavi speciali (che cominciano con '@')
		lines = [ '%s: %s' % (key, value) for key, value in data.iteritems() if not key.startswith('@') ]
		print "\n".join((indent * "\t") + line for line in lines)
	
	c = kongalib.Client()
	c.connect(host='localhost')
	c.open_database('sqlite', 'demo')
	c.authenticate('admin', '')
	record = c.get_record('EB_DocumentiFiscali', 11, code_azienda='00000001')
	print "Testata:"
	print_data(record)
	rows = record.get('@rows', [])
	for i, row in enumerate(rows):
		print "\tRiga %d:" % (i + 1)
		print_data(row, 2)
	
