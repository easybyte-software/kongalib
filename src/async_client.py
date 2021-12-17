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


from __future__ import absolute_import

import asyncio
import inspect

from kongalib import *


class AsyncClient(Client):
	def _make_progress(self, future, progress, userdata):
		if progress is None:
			return None
		else:
			def callback(ptype, completeness, state, data, dummy):
				loop = future.get_loop()
				if ptype == PROGRESS_EXECUTE:
					try:
						if inspect.iscoroutinefunction(progress):
							result = asyncio.run_coroutine_threadsafe(progress(completeness, state, userdata), loop).result()
						else:
							result = progress(completeness, state, userdata)
						if result is False:
							raise Error(ABORTED, 'Operation aborted by user')
					except Exception as e:
						result = False
						loop.call_soon_threadsafe(future.set_exception, e)
				else:
					result = True
				return result
			return callback

	def _make_error(self, future):
		def error(errno, *args):
			loop = future.get_loop()
			if isinstance(errno, Error):
				if errno.errno in (ABORTED, EXECUTE_ABORTED):
					loop.call_soon_threadsafe(future.cancel)
				else:
					loop.call_soon_threadsafe(future.set_exception, errno)
			elif isinstance(errno, Exception):
				loop.call_soon_threadsafe(future.set_exception, errno)
			else:
				if len(args) > 0:
					errstr = ensure_text(args[0])
				else:
					errstr = '<unknown>'
				loop.call_soon_threadsafe(future.set_exception, Error(errno, errstr))
		return error
	
	def _make_success_tuple(self, future, count):
		def success(*args):
			loop = future.get_loop()
			if count == 0:
				loop.call_soon_threadsafe(future.set_result, None)
			elif count == 1:
				loop.call_soon_threadsafe(future.set_result, args[0])
			else:
				loop.call_soon_threadsafe(future.set_result, args[:count])
		return success

	def _make_success(self, future, log=None, finalize_output=None):
		def success(output, *args):
			loop = future.get_loop()
			answer = output[OUT_LOG] or []
			error_list = ErrorList(answer)
			if output[OUT_ERRNO] == OK:
				if len(answer) > 0:
					if log is None:
						loop.call_soon_threadsafe(future.set_exception, error_list)
					else:
						error_list.prepare_log(log)
						if log.has_errors():
							loop.call_soon_threadsafe(future.set_exception, error_list)
						else:
							if finalize_output is not None:
								output = finalize_output(output)
							loop.call_soon_threadsafe(future.set_result, output)
				else:
					if finalize_output is not None:
						output = finalize_output(output)
					loop.call_soon_threadsafe(future.set_result, output)
			else:
				loop.call_soon_threadsafe(future.set_exception, ErrorList.from_error(output[OUT_ERRNO], output[OUT_ERROR]))
		return success
	
	def _execute(self, cmd, in_params, out_params=None, progress=None, log=None):
		def finalize(output):
			if out_params:
				if callable(out_params):
					return out_params(output)
				elif isinstance(out_params, (tuple, list)):
					return tuple([ output[param] for param in out_params ])
				else:
					return output[out_params]
			else:
				return None
		fut = asyncio.get_running_loop().create_future()
		self._impl.execute(cmd, in_params or {}, DEFAULT_EXECUTE_TIMEOUT, self._make_success(fut, log, finalize), self._make_error(fut), self._make_progress(fut, progress, None))
		return fut

	def __aenter__(self):
		return self.begin_transaction()
	
	def __aexit__(self, exc_type, exc_value, exc_traceback):
		if exc_type is None:
			return self.commit_transaction()
		else:
			return self.rollback_transaction()
	
	def list_servers(self, timeout=DEFAULT_DISCOVER_TIMEOUT, port=0, progress=None, userdata=None):
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_servers(timeout, port, self._make_success_tuple(fut, 1), self._make_progress(fut, progress, userdata))
		return fut
	
	def connect(self, server=None, host=None, port=0, options=None, timeout=DEFAULT_CONNECT_TIMEOUT, progress=None, userdata=None):
		if (server is None) and (host is None):
			raise ValueError("either 'host' or 'server' parameter must be specified")
		if isinstance(server, text_base_types) and (host is None):
			host = server
			server = None
		if isinstance(host, text_base_types) and (port is None) and (':' in host):
			pos = host.rfind(':')
			host = host[:pos]
			try:
				port = int(host[pos+1:])
			except:
				raise ValueError("Invalid port value embedded in host string")
		fut = asyncio.get_running_loop().create_future()
		self._impl.connect(server, host or '', port, options, timeout, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata))
		return fut

	def disconnect(self):
		"""Disconnette il server attualmente connesso, oppure non fa nulla se non si è al momento connessi."""
		self._impl.disconnect()
	
	def get_id(self):
		"""Restituisce un ID numerico univoco assegnato dal server alla connessione con questo client, o 0 se non si è connessi."""
		return self._impl.get_id()
	
	def get_connection_info(self):
		"""Restituisce un ``dict`` con informazioni sulla connessione corrente, o ``None`` se non si è connessi."""
		return self._impl.get_connection_info()

	def execute(self, command, data=None, timeout=DEFAULT_EXECUTE_TIMEOUT, progress=None, userdata=None, log=None):
		fut = asyncio.get_running_loop().create_future()
		self._impl.execute(command, data or {}, timeout, self._make_success(fut, log), self._make_error(fut), self._make_progress(fut, progress, userdata))
		return fut
	
	def interrupt(self):
		"""Interrompe tutte le operazioni al momento in esecuzione da parte di questo client."""
		self._impl.interrupt()

	def get_data_dictionary(self, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		"""Restituisce il dizionario dei dati disponibile sul server attualmente connesso, sotto forma di oggetto di classe
		:class:`kongalib.DataDictionary`.
		"""
		fut = asyncio.get_running_loop().create_future()
		uuid = self.get_connection_info().get('uuid', None)
		with Client.DATA_DICTIONARY_LOCK:
			if uuid is None:
				data = None
			else:
				data = Client.DATA_DICTIONARY_CACHE.get(uuid, None)
			if data is None:
				def success(d, userdata):
					with Client.DATA_DICTIONARY_LOCK:
						d = DataDictionary(d)
						Client.DATA_DICTIONARY_CACHE[uuid] = d
						fut.get_loop().call_soon_threadsafe(fut.set_result, d)
				self._impl.get_data_dictionary(success, self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
			else:
				fut.set_result(data)
		return fut

	def list_drivers(self, configured=True, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_drivers(configured, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def list_databases(self, driver=None, quick=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_databases(driver, quick, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def create_database(self, password, driver, name, desc='', progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.create_database(password, driver, name, desc, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def open_database(self, driver, name, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.open_database(driver, name, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def close_database(self, backup=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.close_database(backup, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def upgrade_database(self, password, driver, name, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.upgrade_database(password, driver, name, self._make_success_tuple(fut, 3), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def delete_database(self, password, driver, name, delete_cloud_data=None, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.delete_database(password, driver, name, delete_cloud_data, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def query(self, query, native=False, full_column_names=False, collapse_blobs=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.query_database(query, native, full_column_names, collapse_blobs, self._make_success_tuple(fut, 3), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def backup_database(self, password, backup_name, driver, name, auto=True, overwrite=False, position=0, store_index=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.backup_database(password, backup_name, driver, name, auto, overwrite, position, store_index, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def restore_database(self, password, backup_name, driver, name, change_uuid=True, overwrite=False, position=0, restore_index=True, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.restore_database(password, backup_name, driver, name, change_uuid, overwrite, position, restore_index, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def list_backups(self, position=0, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_backups(position, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def delete_backup(self, password, backup_name, position, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.delete_backup(password, backup_name, position, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def optimize_database(self, password, driver, name, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.optimize_database(password, driver, name, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def repair_database(self, password, driver, name, output, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.repair_database(password, driver, name, output, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def index_database(self, password, driver, name, reset=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.index_database(password, driver, name, reset, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def list_clients(self, full=True, any=False, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.list_clients(full, any, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def get_client_info(self, id, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.get_client_info(id, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def kill_client(self, id, password, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.kill_client(id, password, self._make_success_tuple(fut, 0), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut
	
	def authenticate(self, username, password, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT, new_password=None):
		fut = asyncio.get_running_loop().create_future()
		self._impl.authenticate(username, password, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout, new_password)
		return fut

	def full_text_search(self, text, limit, progress=None, userdata=None, timeout=DEFAULT_EXECUTE_TIMEOUT):
		fut = asyncio.get_running_loop().create_future()
		self._impl.full_text_search(text, limit, self._make_success_tuple(fut, 1), self._make_error(fut), self._make_progress(fut, progress, userdata), None, timeout)
		return fut

	def get_permissions(self, user_id):
		return self._execute(CMD_GET_PERMISSIONS, {
			IN_USER_ID: user_id
		})
	
	def set_permissions(self, user_id, permissions):
		return self._execute(CMD_SET_PERMISSIONS, {
			IN_USER_ID: user_id,
			IN_PERMISSIONS: permissions
		})
	
	def begin_transaction(self, pause_indexing=False, deferred=False):
		flags = 0
		if pause_indexing:
			flags |= 0x1
		if deferred:
			flags |= 0x2
		return self._execute(CMD_BEGIN_TRANSACTION, {
			IN_FLAGS: flags
		})
	
	def commit_transaction(self, resume_indexing=False):
		flags = 0
		if resume_indexing:
			flags |= 0x1
		return self._execute(CMD_COMMIT_TRANSACTION, {
			IN_FLAGS: flags
		})
	
	def rollback_transaction(self, resume_indexing=False):
		flags = 0
		if resume_indexing:
			flags |= 0x1
		return self._execute(CMD_ROLLBACK_TRANSACTION, {
			IN_FLAGS: flags
		})

	def lock_resource(self, command, row_id=None):
		return self._execute(CMD_LOCK, {
			IN_COMMAND_NAME: command,
			IN_ROW_ID: row_id
		}, ( OUT_ANSWER, OUT_OWNER_DATA ))
	
	def unlock_resource(self, command, row_id=None):
		return self._execute(CMD_UNLOCK, {
			IN_COMMAND_NAME: command,
			IN_ROW_ID: row_id
		}, OUT_ANSWER)
	
	def select_data(self, tablename, fieldnamelist=None, where_expr=None, order_by=None, order_desc=False, offset=0, count=None, get_total=False, exist=None, progress=None):
		if isinstance(fieldnamelist, text_base_types):
			fieldnamelist = [ fieldnamelist ]
		elif fieldnamelist:
			fieldnamelist = list(fieldnamelist)
		return self._execute(CMD_SELECT, {
			IN_TABLE_NAME: tablename,
			IN_COLUMN_NAMES: fieldnamelist,
			IN_WHERE_CLAUSE: where(where_expr),
			IN_ORDER_BY: order_by,
			IN_ORDER_DESC: order_desc,
			IN_OFFSET: offset,
			IN_ROW_COUNT: count,
			IN_GET_TOTAL_ROWS: get_total,
			IN_GET_ROWS_EXIST: exist,
		}, ( OUT_RESULT_SET, OUT_TOTAL_ROWS, OUT_EXIST ) if get_total else OUT_RESULT_SET, progress=progress)
	
	def select_data_as_dict(self, tablename, fieldnamelist=None, where_expr=None, order_by=None, order_desc=False, offset=0, count=None, get_total=False, progress=None):
		if isinstance(fieldnamelist, text_base_types):
			fieldnamelist = [ fieldnamelist ]
		elif fieldnamelist:
			fieldnamelist = list(fieldnamelist)
		def get_result(output):
			names = output.get(OUT_COLUMN_NAMES, None) or fieldnamelist
			result_set = [dict(list(zip(names, row))) for row in output[OUT_RESULT_SET] ]
			if get_total:
				return ( result_set, output[OUT_TOTAL_ROWS], output[OUT_EXIST] )
			else:
				return result_set
		return self._execute(CMD_SELECT, {
			IN_TABLE_NAME: tablename,
			IN_COLUMN_NAMES: fieldnamelist,
			IN_WHERE_CLAUSE: where(where_expr),
			IN_ORDER_BY: order_by,
			IN_ORDER_DESC: order_desc,
			IN_OFFSET: offset,
			IN_ROW_COUNT: count,
			IN_GET_TOTAL_ROWS: get_total,
		}, get_result, progress=progress)

	def get_record(self, tablename, code=None, id=None, field_names=None, row_extra_field_names=None, code_azienda=None, num_esercizio=None, mode=None, mask_binary=None, flags=GET_FLAG_DEFAULT, progress=None):
		if (id is None) and (code is None):
			raise ValueError('Either code or id must be specified')
		def get_result(output):
			data = output[OUT_DICT_DATA]
			data['@checksum'] = output[OUT_CHECKSUM]
			return data
		return self._execute(CMD_GET, {
			IN_TABLE_NAME: tablename,
			IN_ROW_ID: id,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_FLAGS: flags,
			IN_COLUMN_NAMES: field_names,
			IN_ROW_EXTRA_FIELDS: row_extra_field_names,
		}, get_result, progress=progress)

	def insert_record(self, tablename, data, code_azienda=None, num_esercizio=None, log=None, progress=None):
		return self._execute(CMD_INSERT_FROM_DICT, {
			IN_TABLE_NAME: tablename,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_DICT_DATA: data
		}, ( OUT_ID, OUT_CODE ), progress=progress, log=log)
	
	def update_record(self, tablename, data, code=None, id=None, code_azienda=None, num_esercizio=None, log=None, progress=None):
		return self._execute(CMD_UPDATE_FROM_DICT, {
			IN_TABLE_NAME: tablename,
			IN_ROW_ID: id,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_DICT_DATA: data
		}, progress=progress, log=log)
	
	def delete_record(self, tablename, code=None, id=None, code_azienda=None, num_esercizio=None, log=None, progress=None):
		return self._execute(CMD_DELETE_FROM_CODE, {
			IN_TABLE_NAME: tablename,
			IN_ROW_ID: id,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
		}, progress=progress, log=log)
	
	def code_exists(self, tablename, code, code_azienda, num_esercizio, extra_where=None):
		output = self._execute(CMD_CODE_EXISTS, {
			IN_TABLE_NAME: tablename,
			IN_CODE: code,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_EXTRA_WHERE: where(extra_where),
		}, OUT_EXISTS)
	
	def get_next_available_code(self, tablename, code_azienda, num_esercizio, dry_run=False):
		return self._execute(CMD_GET_NEXT_CODE, {
			IN_TABLE_NAME: tablename,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_DRY_RUN: dry_run,
		}, OUT_CODE)

	def get_last_npfe(self, code_azienda, num_esercizio):
		return self._execute(CMD_GET_LAST_NPFE, {
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
		}, OUT_NPFE)
	
	def start_elab(self, command, params, code_azienda, num_esercizio, log=None, progress=None, tx=True):
		return self._execute(CMD_START_ELAB, {
			IN_COMMAND: command,
			IN_PARAMS: params,
			IN_CODE_AZIENDA: code_azienda,
			IN_NUM_ESERCIZIO: num_esercizio,
			IN_TX: tx,
		}, OUT_DATA)

	def list_binaries(self, field_or_tablename, id, type=None, progress=None):
		def get_result(output):
			return [ tuple(row) for row in output[OUT_LIST] if ((type is None) or (row[0] == type)) ]
		return self._execute(CMD_LIST_BINARIES, {
			IN_FIELD_NAME: field_or_tablename,
			IN_ROW_ID: id,
		}, get_result, progress=progress)

	def fetch_image(self, fieldname, id, type, progress=None):
		return self._execute(CMD_FETCH_BINARY, {
			IN_FIELD_NAME: fieldname,
			IN_ROW_ID: id,
			IN_TYPE: type,
		}, OUT_DATA, progress=progress)

	def fetch_binary(self, field_or_tablename, id, type, filename=None, check_only=False, progress=None):
		if (type == 0) and (not filename):
			raise ValueError('filename must be specified for document type resources')
		return self._execute(CMD_FETCH_BINARY, {
			IN_FIELD_NAME: field_or_tablename,
			IN_ROW_ID: id,
			IN_TYPE: type,
			IN_FILENAME: filename,
			IN_CHECK: check_only,
		}, ( OUT_DATA, OUT_FILENAME, OUT_ORIGINAL_FILENAME ), progress=progress)

	def store_binary(self, field_or_tablename, id, type, filename=None, original_filename=None, data=None, desc=None, force_delete=False, code_azienda=None, progress=None):
		return self._execute(CMD_STORE_BINARY, {
			IN_FIELD_NAME: field_or_tablename,
			IN_ROW_ID: id,
			IN_TYPE: type,
			IN_FILENAME: filename,
			IN_ORIGINAL_FILENAME: original_filename,
			IN_CODE_AZIENDA: code_azienda,
			IN_DATA: data,
			IN_DESC: desc,
			IN_FORCE_DELETE: force_delete,
		}, OUT_FILENAME, progress=progress)

	def translate(self, field, value, language):
		return self._execute(CMD_TRANSLATE, {
			IN_FIELD: field,
			IN_VALUE: value,
			IN_LANGUAGE: language
		}, OUT_TEXT)

	def set_database_language(self, language, progress=None):
		return self._execute(CMD_SET_DATABASE_LANGUAGE, {
			IN_LANGUAGE: language,
		}, progress=progress)



if __name__ == '__main__':
	import progress.bar
	import progress.spinner
	
	async def main():
		client = AsyncClient()
		await client.connect('127.0.0.1')
		await client.open_database('sqlite', 'demo')
		await client.authenticate('admin', '')

		# bar = progress.bar.IncrementalBar()
		bar = progress.spinner.Spinner()
		def prog(completeness, state, userdata):
			# bar.goto(completeness)
			bar.next()
			return False

		with bar:
			# async with client:
			try:
				df = await client.select_data('EB_DocumentiFiscali', ['NumeroInterno'], progress=prog)
			except Exception as e:
				df = None
				print(e)

		# print("DONE")
		drivers = client.list_drivers()
		dbs = client.list_databases()
		print(await asyncio.gather(drivers, dbs))
		print(df)


	asyncio.run(main(), debug=True)