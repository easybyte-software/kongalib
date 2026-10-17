# -*- coding: utf-8 -*-
#	 _                           _ _ _
#	| |                         | (_) |
#	| | _____  _ __   __ _  __ _| |_| |__
#	| |/ / _ \| '_ \ / _` |/ _` | | | '_ \
#	|   < (_) | | | | (_| | (_| | | | |_) |
#	|_|\_\___/|_| |_|\__, |\__,_|_|_|_.__/
#	                  __/ |
#	                 |___/
#
#	Konga client library, by EasyByte Software
#
#	https://github.com/easybyte-software/kongalib

"""Client del protocollo IPC di Konga scritto in Python, sopra le primitive native di
_kongalib (codifica CLU, cifrari, checksum): il trasporto di kongalib nel browser, dove il
client nativo non c'è, e sul desktop con ``KONGALIB_TRANSPORT=wire``.

- :mod:`kongalib.wire.protocol`: pacchetti, richieste e risposte, senza I/O.
"""
