Operazioni asincrone
====================

Come visto precedentemente, la classe :class:`~.kongalib.Client` già supporta l'esecuzione asincrona di gran parte dei suoi metodi,
tramite l'uso delle callback *success*, *error* e *progress*. Esiste però anche un approccio più moderno all'esecuzione asincrona
che supporta direttamente il modulo ``asyncio`` di Python, in modo da poter usare costrutti come ``async`` e ``await``; per fare
questo è stata introdotta la classe :class:`~.kongalib.AsyncClient`.

.. note:: La classe :class:`~.kongalib.AsyncClient` è disponibile solo se si usa Python versione 3.6 o successive.


Classe AsyncClient
------------------

.. autoclass:: kongalib.AsyncClient
   :members:



Esempi
------

Di seguito vengono riportati alcuni esempi di utilizzo della classe :class:`~.kongalib.AsyncClient`; si assume che ci sia un server
Konga disponibile su localhost e che esista su di esso un database SQLite "demo" inizializzato con i dati di esempio.

Esempio di connessione e lista dell'archivio clienti presenti sul database::

	import asyncio
	import kongalib
	
	async def main():
		c = kongalib.Client()
		await c.connect(host='localhost')
		await c.open_database('sqlite', 'demo')
		await c.authenticate('admin', '')
		results = await c.select_data('EB_ClientiFornitori', ['Codice', 'RagioneSociale'], 'Tipo = 1')
		for row in results:
			print(row)
	
	asyncio.run(main())

Esempio di come ottenere tutto il record di un documento fiscale (testata e righe)::

	import asyncio
	import kongalib
	
	def print_data(data, indent=1):
		# Stampa i dati, tralasciando le chiavi speciali (che cominciano con '@')
		lines = [ '%s: %s' % (key, value) for key, value in data.items() if not key.startswith('@') ]
		print("\n".join((indent * "\t") + line for line in lines))
	
	async def main():
		c = kongalib.Client()
		await c.connect(host='localhost')
		await c.open_database('sqlite', 'demo')
		await c.authenticate('admin', '')
		record = await c.get_record('EB_DocumentiFiscali', 11, code_azienda='00000001')
		print("Testata:")
		print_data(record)
		rows = record.get('@rows', [])
		for i, row in enumerate(rows):
			print("\tRiga %d:" % (i + 1))
			print_data(row, 2)

	asyncio.run(main())
	
