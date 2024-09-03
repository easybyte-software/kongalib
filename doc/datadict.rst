Dizionario dei dati
===================

E' possibile ottenere informazioni sul dizionario dei dati del server Konga attualmente connesso ad una istanza di classe :class:`Client`;
la classe :class:`DataDictionary` contiene una serie di metodi utili allo scopo.


.. _field_types:

Tipi di campo
-------------

.. automodule:: kongalib.data_dictionary
	:member-order: bysource
	:members: TYPE_TINYINT, TYPE_SMALLINT, TYPE_INT, TYPE_BIGINT, TYPE_FLOAT, TYPE_DOUBLE, TYPE_DECIMAL, TYPE_DATE, TYPE_TIME, TYPE_TIMESTAMP, TYPE_YEAR, TYPE_CHAR, TYPE_VARCHAR, TYPE_TINYTEXT, TYPE_TEXT, TYPE_LONGTEXT, TYPE_TINYBLOB, TYPE_BLOB, TYPE_LONGBLOB, TYPE_JSON


.. _table_flags:

Flag di tabella
---------------

.. autodata:: kongalib.data_dictionary.TABLE_HAS_IMAGES
.. autodata:: kongalib.data_dictionary.TABLE_IS_INDEXED


.. _field_flags:

Flag di campo
-------------

.. autodata:: kongalib.data_dictionary.FIELD_UNSIGNED
.. autodata:: kongalib.data_dictionary.FIELD_UNIQUE
.. autodata:: kongalib.data_dictionary.FIELD_NOT_NULL
.. autodata:: kongalib.data_dictionary.FIELD_PRIMARY_KEY
.. autodata:: kongalib.data_dictionary.FIELD_FOREIGN_KEY
.. autodata:: kongalib.data_dictionary.FIELD_AUTO_INCREMENT
.. autodata:: kongalib.data_dictionary.FIELD_DEFAULT_NULL
.. autodata:: kongalib.data_dictionary.FIELD_DEFAULT_CURRENT_TS
.. autodata:: kongalib.data_dictionary.FIELD_DEFAULT
.. autodata:: kongalib.data_dictionary.FIELD_ON_UPDATE_CURRENT_TS
.. autodata:: kongalib.data_dictionary.FIELD_ON_DELETE_CASCADE
.. autodata:: kongalib.data_dictionary.FIELD_ON_DELETE_SET_NULL


Classe DataDictionary
---------------------

.. autoclass:: kongalib.DataDictionary
   :members:

