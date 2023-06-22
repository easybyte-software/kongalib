Gestione degli errori
=====================

Per gestire gli errori, Kongalib definisce una classe :class:`~kongalib.Log` e due eccezioni: :exc:`~kongalib.Error` e :exc:`~kongalib.ErrorList`.


Classe Log
----------

.. autoclass:: kongalib.Log
	

Eccezione Error
---------------

.. autoclass:: kongalib.Error
	

Eccezione ErrorList
-------------------

.. autoclass:: kongalib.ErrorList
	

.. _error_codes:

Codici di errore
----------------

Sono definite le seguenti costanti di errore che possono apparire nell'attributo :attr:`Error.errno` o :attr:`ErrorList.errno`. Da notare
che queste costanti sono definite anche nel modulo :mod:`kongalib`.

.. note:: Ulteriori codici di errore che non sono riportati qui di seguito potranno essere riportati da Konga.


.. automodule:: kongalib.constants
	:member-order: bysource
	:members:

