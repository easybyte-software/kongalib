Interfacciamento con Konga
==========================


Quando si installa Kongalib, oltre al modulo Python ``kongalib``, vengono installati anche due moduli aggiuntivi: ``kongautil`` e ``kongaui``.
Questi moduli permettono una maggiore integrazione con Konga, e assumono che Konga stesso sia in esecuzione durante l'esecuzione del vostro script;
in particolare si comportano in modo diverso se lo script è eseguito dall'interno di Konga stesso (dal menu *Script* o dall'editor di script) o
dall'esterno (invocando lo script con Python da terminale).

Se le funzioni di ``kongautil`` e ``kongaui`` vengono usate dall'interno di Konga, l'input e l'output verranno gestiti da Konga tramite interfaccia
grafica, altrimenti le funzioni opereranno sull'I/O del terminale da cui lo script è eseguito. Alcune funzionalità non saranno disponibili al di fuori
di Konga, ed in tali casi verrà ritornata l'eccezione :class:`kongautil.KongaRequiredError`.

.. note::
	``kongalib``, ``kongautil`` e ``kongaui`` sono pre-installate e sempre disponibili dall'interno di Konga.



kongautil
---------


.. automodule:: kongautil
	:members: PRINT_TARGET_PREVIEW, PRINT_TARGET_PAPER, PRINT_TARGET_PDF, PRINT_TARGET_CSV, PRINT_TARGET_XLS, KongaRequiredError, connect, get_window_vars, print_layout, print_log, suspend_timeout, resume_timeout, set_timeout, get_external_images_path, get_external_attachments_path, get_site_packages, notify_data_changes, get_context
	:member-order: bysource



kongaui
-------


.. automodule:: kongaui
	:members: BUTTON_OK, BUTTON_YES, BUTTON_YES_ALL, BUTTON_NO, BUTTON_NO_ALL, BUTTON_CANCEL, BUTTON_OPEN, BUTTON_SAVE, BUTTON_SAVE_ALL, BUTTON_CLOSE, BUTTON_DISCARD, BUTTON_APPLY, BUTTON_RESET, BUTTON_ABORT, BUTTON_RETRY, BUTTON_IGNORE, ICON_ERROR, ICON_QUESTION, ICON_WARNING, ICON_INFORMATION, message_box, open_file, save_file, choose_directory, select_record, open_progress, close_progress, set_progress, is_progress_aborted, open_window, execute_form
	:member-order: bysource


