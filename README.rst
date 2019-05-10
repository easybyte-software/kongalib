Kongalib
========

Libreria Python di comunicazione con i server `EasyByte Konga`_. Tramite
*kongalib* è possibile connettersi ad un server Konga (integrato in Konga Pro o
standalone in Konga Server), eseguire query sui database e manipolarne i dati
facilmente.


Installazione
-------------

Sono forniti pacchetti wheel binari per sistemi operativi Windows, macOS e Linux;
l'installazione per questi sistemi è pertanto banale e si effettua tramite *pip*::

	pip install kongalib


Compilazione manuale
--------------------

Se si desidera è possibile compilare i sorgenti. I prerequisiti per compilare
*kongalib* sono i seguenti:


**Windows**

Sono supportate le versioni di Windows dalla 7 in su. Come prerequisiti è
necessario installare:

	- Microsoft Visual Studio (versione 2015 o successiva)
	- `SDK di Konga`_


**MacOS X**

Sono supportate le versioni di macOS dalla 10.8 in su. Come prerequisiti è
necessario installare:

	- XCode (assicurarsi di aver installato anche i tool da linea di comando)
	- `SDK di Konga`_


**Linux**
	
Benchè il pacchetto binario wheel per Linux supporti tutte le distribuzioni
Linux moderne (specifica `manylinux`), al momento la compilazione da parte di
terzi è supportata ufficialmente solo se si usa una distribuzione Linux basata su
Debian, in particolare Ubuntu Linux dalla versione 16.04 in su. Sono necessari i
seguenti pacchetti *deb*:

	- build-essential
	- g++
	- python-dev
	- `easybyte-konga-dev`_

La compilazione è possibile tramite la usuale procedura dei pacchetti Python::

	python setup.py install


Da notare che sotto piattaforma Windows per la corretta compilazione è necessario
impostare la variabile d'ambiente ``KONGASDK`` alla directory d'installazione
dell'`SDK di Konga`_.


Risorse
-------

`Versioni stable e nightly`_

	L'ultima versione ufficiale è sempre disponibile su PyPI; se tuttavia si
	desidera scaricare una versione *stable* o *nightly* specifica oppure una
	vecchia versione, è possibile farlo da qui.


`Documentazione di kongalib`_

	La documentazione della libreria per la versione ufficiale corrente e per
	le versioni	ufficiali passate è sempre accessibile da qui.


`Documentazione del dizionario dei dati`_

	Per informazioni circa la struttura dei database Konga (nozione necessaria
	per accedere correttamente ai dati)

	

.. _Versioni stable e nightly: http://public.easybyte.it/downloads
.. _EasyByte Konga: http://www.easybyte.it/it/pro
.. _Documentazione di kongalib: http://public.easybyte.it/docs/kongalib
.. _Documentazione del dizionario dei dati: http://public.easybyte.it/docs/datadict
.. _SDK di Konga: http://public.easybyte.it/downloads/current
.. _easybyte-konga-dev: http://public.easybyte.it/downloads/current
.. _manylinux: https://github.com/pypa/manylinux

