Introduzione
============

Kongalib è una libreria per connettersi a server Konga tramite script Python; è quindi necessario avere un server
Konga disponibile per poter essere operativi.

La connessione e l'esecuzione di comandi sul server avviene principalmente tramite la classe :class:`~kongalib.Client`;
i dati scambiati con il server possono includere date e/o valori decimali; i primi sono sempre oggetti di classe :class:`datetime.datetime`,
mentre per i valori numerici vengono usati oggetti di classe :class:`~kongalib.Decimal`, che è una classe di Kongalib simile alla classe
:class:`decimal.Decimal` di Python (in quanto offre precisione esatta nei calcoli e grandezza dei numeri limitata dalla sola memoria del
computer) ma ottimizzata per le prestazioni.


Classe Decimal
--------------

.. class:: kongalib.Decimal(value=0.0)
	
	La classe Decimal viene usata per descrivere e lavorare con numeri decimali con un numero variabile di cifre e precisione fino a 38
	cifre decimali. *value* è il valore di default che viene assegnato all'oggetto durante l'inizializzazione; può essere un ``float``, un
	``int``, un ``long``, un :class:`decimal.Decimal`, una stringa che contiene il numero sotto forma di testo, oppure un altro
	:class:`~kongalib.Decimal` da cui prendere il valore iniziale. Gli oggetti di questa classe si comportano come numeri ed hanno quindi
	il supporto per tutte le operazioni numeriche standard Python, e possono quindi essere usati insieme ad altri numeri.
	
	Inoltre, gli oggetti Decimal offrono i seguenti metodi:
	
	.. method:: round(value=1.0)
		
		Arrotonda al numero *value*, arrotondando verso 0 se l'ultima cifra dopo l'arrotondamento è compresa tra 0 e 5,
		altrimenti arrotonda allontanadosi da 0. Restituisce un oggetto :class:`~kongalib.Decimal`.
	
	.. method:: floor(value=1.0)
		
		Arrotonda al numero *value*, arrotondando verso 0. Restituisce un nuovo oggetto :class:`~kongalib.Decimal`.
	
	.. method:: ceil(value=1.0)
		
		Arrotonda al numero *value*, arrotondando allontanandosi da 0. Restituisce un nuovo oggetto :class:`~kongalib.Decimal`.

	.. method:: format(precision=5, width=0, sep=False, padzero=False)
		
		Formatta il numero decimale in una stringa riportando al più *precision* cifre decimali. *width* se diverso da 0 indica la larghezza
		della parte intera; se *padzero* è ``True``, e *width* è più grande della parte intera, saranno inseriti ``0`` iniziali in modo da avere
		una parte intera lunga *width* caratteri. Se *sep* è ``True``, la parte intera includerà il separatore delle migliaia se necessario.


Compatibilità con decimal.Decimal
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

E' possibile lavorare indistintamente sia con :class:`~kongalib.Decimal` che con :class:`decimal.Decimal`, anche mischiandoli tra loro. Quando
però si passano i dati al server Konga tramite la classe :class:`~kongalib.Client`, è sicuramente più efficiente che i valori decimali siano
passati come :class:`~kongalib.Decimal`. Inoltre, le chiamate al server ritorneranno sempre valori di tipo :class:`~kongalib.Decimal`.



Classe Deferred
---------------

.. class:: kongalib.Deferred
	
	Un oggetto della classe Deferred viene sempre restituito da tutte le chiamate asincrone di Kongalib, e rappresenta una operazione che
	verrà eseguita in futuro. Gli oggetti Deferred hanno i seguenti attributi:
	
	.. attribute:: aborted
	
		Attributo in sola lettura che è ``True`` o ``False`` a seconda che l'operazione associata all'oggetto sia stata annullata o no.
	
	.. attribute:: executed
	
		Attributo in sola lettura che è ``True`` o ``False`` a seconda che l'operazione associata all'oggetto sia stata già eseguita o no.
	
	Inoltre, oggetti della classe Deferred hanno il seguente metodo:
	
	.. method:: cancel()
	
		Permette di annullare l'operazione associata all'oggetto, nel caso non sia stata già eseguita.



Funzioni di modulo
------------------

Il modulo kongalib prevede le seguenti funzioni di uso comune:



.. automodule:: kongalib
	:members: round, floor, ceil
	


.. function:: start_timer(millisecs, callback, userdata=None)
	
	Restituisce immediatamente un oggetto di classe :class:`~kongalib.Deferred`, ed esegue *callback* dopo *millisecs* millisecondi
	in un thread separato. *callback* deve essere una funzione nella forma ``callback(userdata)``.



Costanti
--------


.. automodule:: kongalib
	:members: BACKUP_ON_COMPUTER, BACKUP_ON_CLOUD
