# -*- coding: utf-8 -*-

from __future__ import print_function

import kongalib

from kongalib.scripting import proxy as _proxy
from kongalib.scripting import ScriptContext


PRINT_TARGET_PREVIEW			= 0
PRINT_TARGET_PAPER				= 1
PRINT_TARGET_PDF				= 2
PRINT_TARGET_CSV				= 3
PRINT_TARGET_XLS				= 4



class KongaRequiredError(RuntimeError):
	def __str__(self):
		return "Function requires script to be executed from within Konga"



def connect(host=None, port=None, driver=None, database=None, username=None, password=None, tenant_key=None):
	if _proxy.is_valid():
		info = _proxy.util.get_connection_info()
		if info is not None:
			host, port, driver, database, username, password, tenant_key = info
			client = kongalib.Client()
			client.connect(host=host, port=port, options={ 'tenant_key': tenant_key })
			client.open_database(driver, database)
			client.authenticate(username, password)
			return client
	else:
		client = kongalib.Client()
		if host is None:
			servers_list = client.list_servers(timeout=500)
			if servers_list:
				host = servers_list[0]['host']
				port = servers_list[0]['port']
		if host is not None:
			client.connect(host=host, port=port, options={ 'tenant_key': tenant_key })
			if driver is None:
				drivers_list = client.list_drivers(timeout=500)
				if drivers_list:
					driver = drivers_list[0]['name']
			if (driver is not None) and (database is None):
				db_list = client.list_databases(driver, timeout=500)
				if db_list:
					database = db_list[driver][0]['name']
			if (driver is not None) and (database is not None):
				client.open_database(driver, database)
				client.authenticate(username or 'admin', password or '')
				return client
	raise kongalib.Error(kongalib.DATABASE_NOT_CONNECTED, "No database connected")



def get_window_vars():
	if _proxy.is_valid():
		return _proxy.util.get_window_vars()
	else:
		return {}



def print_layout(command_or_layout, builtins=None, code_azienda=None, code_esercizio=None, target=PRINT_TARGET_PREVIEW, filename=None):
	if _proxy.is_valid():
		return _proxy.util.print_layout(command_or_layout, builtins or {}, code_azienda, code_esercizio, target, filename)
	else:
		raise KongaRequiredError




def print_log(log, title, target=PRINT_TARGET_PREVIEW, filename=None):
	if not _proxy.is_valid():
		print(log.dumps())
		return

	template = """<?xml version='1.0' encoding='utf-8'?>
		<layout version="2" name="%(title)s" title="%(title)s" orientation="vertical" margin_top="75" margin_right="75" margin_bottom="75" margin_left="75">
			<init>
				<![CDATA[set_datasource(Datasource(['id', 'type', 'message'], DATA, 'Master'))
]]></init>
			<header width="100%%" height="175" only_first="true">
				<label width="100%%" height="100" align="center" font_size="14" bgcolor="#EEE" border_edges="left|right|top|bottom">%(title)s</label>
			</header>
			
			<module width="100%%" alt_bgcolor="#EEE" condition="iterate('id')">
				<field top="0" width="10%%" align="top" type="data">type</field>
				<field left="10%%" top="0" width="90%%" align="top" wrapping="wrap" type="data">message</field>
			</module>
			<module width="100%%">
				<init>
					<![CDATA[this.visible = (len(DATA) == 0)
]]></init>
				<label width="100%%" align="center">
					<text>
						<it>Operazione completata con successo</it>
					</text>
				</label>
			</module>
			
			<footer width="100%%" font_size="7" height="175">
				<rect top="75" width="100%%" height="100" />
				<field padding_left="50" top="75" left="0" width="30%%" height="50" align="bottom" type="expr">DATABASE_NAME</field>
				<field padding_left="50" top="125" left="0" width="30%%" height="50" align="top" type="expr">COMPANY_NAME</field>
				<field top="75" left="30%%" width="40%%" height="50" align="hcenter|bottom" type="expr">TITLE</field>
				<datetime top="125" left="30%%" width="40%%" height="50" align="hcenter|top" format="PdmyHM">
					<text>
						<it>Stampato da $USER_NAME il %%d alle %%t</it>
						<nl>Afgedrukt door $USER_NAME op %%d om %%t uur</nl>
					</text>
				</datetime>
				<page padding_right="50" top="75" left="80%%" width="20%%" height="100" align="vcenter|right">
					<text>
						<it>Pagina %%p di %%t</it>
						<nl>Pagina %%p van %%t</nl>
					</text>
				</page>
			</footer>
		</layout>
	""" % {
		'title':	title,
	}
	data = []
	for index, message in enumerate(log.get_messages()):
		msg = log.strip_html(message[1])
		if isinstance(msg, bytes):
			msg = msg.decode('utf-8', 'replace')
		data.append((index, ('INFO', 'WARNING', 'ERROR')[message[0]], msg))
	
	print_layout(template, { 'DATA': data }, target=target, filename=filename)



def suspend_timeout():
	if _proxy.is_valid():
		return _proxy.builtin.set_timeout()



def resume_timeout(timeout):
	if _proxy.is_valid():
		_proxy.builtin.set_timeout(timeout)



def set_timeout(timeout):
	if _proxy.is_valid():
		_proxy.builtin.set_timeout(timeout * 1000)



def get_external_images_path(table_name, code_azienda):
	if _proxy.is_valid():
		return _proxy.util.get_external_path(True, table_name, code_azienda)
	else:
		raise KongaRequiredError



def get_external_attachments_path(table_name, code_azienda):
	if _proxy.is_valid():
		return _proxy.util.get_external_path(False, table_name, code_azienda)
	else:
		raise KongaRequiredError



def get_site_packages():
	if _proxy.is_valid():
		return _proxy.util.get_site_packages()
	else:
		import site
		return site.getsitepackages()[0]



def notify_data_changes(table_name, row_id=None):
	if _proxy.is_valid():
		_proxy.util.notify_data_changes(table_name, row_id)



def get_context():
	if _proxy.is_valid():
		return _proxy.util.get_context()
	else:
		raise KongaRequiredError



