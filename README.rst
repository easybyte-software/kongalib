Kongalib
========

.. image:: https://img.shields.io/pypi/v/kongalib.svg
   :alt: Current version
   :target: https://pypi.python.org/pypi/kongalib/
.. image:: https://img.shields.io/pypi/pyversions/kongalib.svg
   :alt: Supported Python versions
   :target: https://pypi.python.org/pypi/kongalib/
.. image:: https://img.shields.io/badge/License-LGPLv3-blue.svg
   :alt: LGPL v3 License
   :target: https://www.gnu.org/licenses/lgpl-3.0.en.html
.. image:: https://github.com/easybyte-software/kongalib/actions/workflows/build_wheels.yml/badge.svg?event=workflow_dispatch
   :alt: Build Status
   :target: https://github.com/easybyte-software/kongalib/actions/workflows/build_wheels.yml

Libreria Python di comunicazione con i server `EasyByte Konga`_. Tramite
*kongalib* è possibile connettersi ad un server Konga (integrato in Konga Pro o
standalone in Konga Server), eseguire query sui database e manipolarne i dati
facilmente. La libreria comprende anche i moduli aggiuntivi ``kongaui`` e
``kongautil``, utili ad interfacciarsi ed integrarsi con Konga e Konga Client.


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

Sono supportate le versioni di Windows dalla 10 in su. Come prerequisiti è
necessario installare:

	- Microsoft Visual Studio 2017 o successiva
	- `SDK di Konga`_


**MacOS X**

Sono supportate le versioni di macOS dalla 10.9 in su. Come prerequisiti è
necessario installare:

	- XCode (assicurarsi di aver installato anche i tool da linea di comando)
	- `SDK di Konga`_


**Linux**
	
Benchè il pacchetto binario wheel per Linux supporti tutte le distribuzioni
Linux moderne (specifica `manylinux_2_28`), al momento la compilazione da parte di
terzi è supportata ufficialmente solo se si usa una distribuzione Linux basata su
Debian, in particolare Ubuntu Linux dalla versione 20.04 in su. Sono necessari i
seguenti pacchetti *deb*:

	- build-essential
	- g++
	- python-dev
	- `easybyte-konga-dev`_

La compilazione come da standard Python è possibile sempre tramite *pip*, eseguendo
dalla directory dei sorgenti::

	pip install .


.. note:: Sotto piattaforma Windows per la corretta compilazione è necessario
	impostare la variabile d'ambiente `KONGASDK` alla directory d'installazione
	dell'`SDK di Konga`_.


Risorse
-------

`Documentazione di kongalib`_

	La documentazione della libreria per la versione ufficiale corrente e per
	le versioni	ufficiali passate è sempre accessibile da qui.


`Documentazione del dizionario dei dati`_

	Per informazioni circa la struttura dei database Konga (nozione necessaria
	per accedere correttamente ai dati)


`Script di utilità comune per Konga`_

	Gli script contenuti in questo repository possono essere utati come esempi
	nell'uso di kongalib.
	

.. _EasyByte Konga: http://www.easybyte.it/it/pro
.. _Documentazione di kongalib: http://public.easybyte.it/docs/kongalib
.. _Documentazione del dizionario dei dati: http://public.easybyte.it/docs/datadict
.. _Script di utilità comune per Konga: https://github.com/easybyte-software/konga_scripts
.. _SDK di Konga: http://public.easybyte.it/downloads/current
.. _easybyte-konga-dev: http://public.easybyte.it/downloads/current
.. _manylinux_2_28: https://github.com/pypa/manylinux

