/*
 *		 _                           _ _ _
 *		| |                         | (_) |
 *		| | _____  _ __   __ _  __ _| |_| |__
 *		| |/ / _ \| '_ \ / _` |/ _` | | | '_ \
 *		|   < (_) | | | | (_| | (_| | | | |_) |
 *		|_|\_\___/|_| |_|\__, |\__,_|_|_|_.__/
 *		                  __/ |
 *		                 |___/
 *
 *
 *		Konga client library, by EasyByte Software
 *
 *		https://github.com/easybyte-software/kongalib
 */


#include "module.h"


static MGA_Status
_IdleCB(MGA::DeferredObject *request)
{
	if (!Py_IsInitialized())
		return MGA_ERROR;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return MGA_OK;
	}
	
	if ((request->fIdle) && (request->fIdle != Py_None)) {
		PyObject *result = PyObject_CallFunctionObjArgs(request->fIdle, NULL);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	
	PyGILState_Release(gstate);
	return MGA_OK;
}


static MGA_Status
_SyncIdleCB(void *unused)
{
	if (!Py_IsInitialized())
		return MGA_ERROR;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return MGA_OK;
	}
	
	if ((state->fIdleCB) && (state->fIdleCB != Py_None)) {
		PyObject *result = PyObject_CallFunctionObjArgs(state->fIdleCB, NULL);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	
	PyGILState_Release(gstate);
	return MGA_OK;
}


static void
_DiscoverCB(MGA_ServerSpec *spec, uint32 numServers, MGA::DeferredObject *request)
{
	if (!Py_IsInitialized())
		return;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return;
	}

	request->fPending = false;
	
	if ((request->fSuccess) && (request->fSuccess != Py_None)) {
		PyObject *list = PyTuple_New(numServers);
		for (uint32 i = 0; i < numServers; i++) {
			PyObject *server = PyDict_New();
			const char *uuid = spec[i].fUUID;
			PyDict_SetItemString(server, "host", PyUnicode_DecodeUTF8(spec[i].fHost.c_str(), spec[i].fHost.size(), NULL));
			PyDict_SetItemString(server, "port", PyInt_FromLong((long)spec[i].fPort));
			PyDict_SetItemString(server, "name", PyUnicode_DecodeUTF8(spec[i].fName.c_str(), spec[i].fName.size(), NULL));
			PyDict_SetItemString(server, "description", PyUnicode_DecodeUTF8(spec[i].fDescription.c_str(), spec[i].fDescription.size(), NULL));
			PyDict_SetItemString(server, "data_version", PyInt_FromLong((long)spec[i].fDataVersion));
			PyDict_SetItemString(server, "uuid", PyUnicode_DecodeUTF8(uuid, strlen(uuid), NULL));
			PyDict_SetItemString(server, "multitenant_enabled", spec[i].fMultiTenant ? Py_True : Py_False);
			if (spec[i].fMultiTenant)
				Py_INCREF(Py_True);
			else
				Py_INCREF(Py_False);
			PyTuple_SET_ITEM(list, i, server);
		}
		
		PyObject *result = PyObject_CallFunctionObjArgs(request->fSuccess, list, request->fUserData, NULL);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	if (!request->fAborted)
		request->fExecuted = true;
	Py_DECREF(request);
	
	PyGILState_Release(gstate);
}


static void
_SuccessCB(MGA::DeferredObject *request)
{
	if (!Py_IsInitialized())
		return;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return;
	}
	
	request->fPending = false;

	if ((request->fSuccess) && (request->fSuccess != Py_None)) {
		PyObject *result = PyObject_CallFunctionObjArgs(request->fSuccess, request->fUserData, NULL);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	if (!request->fAborted)
		request->fExecuted = true;
	Py_DECREF(request);
	
	PyGILState_Release(gstate);
}


static void
_SuccessWithTableCB(CLU_Table *output, MGA::DeferredObject *request)
{
	if (!Py_IsInitialized())
		return;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return;
	}
	
	request->fPending = false;

	if ((request->fSuccess) && (request->fSuccess != Py_None)) {
		PyObject *table = MGA::Table_FromCLU(output);
		PyObject *result = PyObject_CallFunctionObjArgs(request->fSuccess, table, request->fUserData, NULL);
		Py_DECREF(table);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	if (!request->fAborted)
		request->fExecuted = true;
	Py_DECREF(request);
	
	PyGILState_Release(gstate);
}


static void
_SuccessWithListCB(CLU_List *output, MGA::DeferredObject *request)
{
	if (!Py_IsInitialized())
		return;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return;
	}
	
	request->fPending = false;

	if ((request->fSuccess) && (request->fSuccess != Py_None)) {
		PyObject *list = MGA::List_FromCLU(output);
		PyObject *result = PyObject_CallFunctionObjArgs(request->fSuccess, list, request->fUserData, NULL);
		Py_DECREF(list);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	if (!request->fAborted)
		request->fExecuted = true;
	Py_DECREF(request);
	
	PyGILState_Release(gstate);
}


static void
_SuccessWithUpgradeResultCB(CLU_Table *output, MGA::DeferredObject *request)
{
	if (!Py_IsInitialized())
		return;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return;
	}
	
	request->fPending = false;

	if ((request->fSuccess) && (request->fSuccess != Py_None)) {
		PyObject *log = MGA::List_FromCLU(output->GetList("log"));
		PyObject *old_version = PyInt_FromLong(output->GetInt32("old_version"));
		PyObject *new_version = PyInt_FromLong(output->GetInt32("new_version"));
		PyObject *result = PyObject_CallFunctionObjArgs(request->fSuccess, log, old_version, new_version, request->fUserData, NULL);
		Py_DECREF(log);
		Py_DECREF(old_version);
		Py_DECREF(new_version);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	if (!request->fAborted)
		request->fExecuted = true;
	Py_DECREF(request);
	
	PyGILState_Release(gstate);
}


static void
_SuccessWithResultSetCB(uint32 affectedRows, CLU_List *columnNames, CLU_List *resultSet, MGA::DeferredObject *request)
{
	if (!Py_IsInitialized())
		return;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return;
	}
	
	request->fPending = false;

	if ((request->fSuccess) && (request->fSuccess != Py_None)) {
		PyObject *_affectedRows, *_columnNames, *_resultSet;
		
		_affectedRows = PyInt_FromLong(affectedRows);
		_columnNames = MGA::List_FromCLU(columnNames);
		_resultSet = MGA::List_FromCLU(resultSet);
		
		PyObject *result = PyObject_CallFunctionObjArgs(request->fSuccess, _affectedRows, _columnNames, _resultSet, request->fUserData, NULL);
		
		Py_DECREF(_affectedRows);
		Py_DECREF(_columnNames);
		Py_DECREF(_resultSet);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	if (!request->fAborted)
		request->fExecuted = true;
	Py_DECREF(request);
	
	PyGILState_Release(gstate);
}


static void
_ErrorCB(MGA_Status error_no, const string& error, MGA::DeferredObject *request)
{
	if (!Py_IsInitialized())
		return;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *state = GET_STATE();
	if ((!state) || (!state->fInitialized)) {
		PyGILState_Release(gstate);
		return;
	}
	
	request->fPending = false;
	
	if ((request->fError) && (request->fError != Py_None)) {
		string error_str = error;
		if (error_str.empty())
			error_str = MGA::translate(error_no);
		PyObject *error_obj = PyUnicode_DecodeUTF8(error_str.c_str(), error_str.size(), NULL);
		if (!error_obj) {
			PyErr_Clear();
			error_str = CL_StringFormat("<Error %d>", error_no);
			error_obj = PyUnicode_FromString(error_str.c_str());
		}
		PyObject *result = PyObject_CallFunction(request->fError, "iOO", error_no, error_obj, request->fUserData, NULL);
		Py_DECREF(error_obj);
		if (!result) {
			PyErr_Print();
			PyErr_Clear();
		}
		else
			Py_DECREF(result);
	}
	request->fExecuted = true;
	
	Py_DECREF(request);
	
	PyGILState_Release(gstate);
}


static MGA_Status
_ProgressCB(MGA_ProgressType type, double completeness, const string& message, CLU_Table *output, MGA::DeferredObject *request)
{
	MGA_Status result = MGA_ERROR;
	if (!Py_IsInitialized())
		return result;

	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	
	MGA::MODULE_STATE *s = GET_STATE();
	if ((!s) || (!s->fInitialized)) {
		PyGILState_Release(gstate);
		return result;
	}
	
// 	printf("_ProgressCB: %d (%g) - %d %d %d\n", type, completeness, (!request->fAborted) ? 1 : 0, (!request->fExecuted) ? 1 : 0, (request->fProgress) ? 1 : 0);
	if ((!request->fAborted) && (!request->fExecuted) && (request->fProgress) && (request->fProgress != Py_None)) {
		PyObject *state = PyUnicode_DecodeUTF8(message.c_str(), message.size(), NULL);
		if (!state) {
			PyErr_Clear();
			state = PyUnicode_FromString("");
		}
		PyObject *dict = MGA::Table_FromCLU(output);
		if (!dict) {
			PyErr_Clear();
			dict = PyDict_New();
		}
		Py_INCREF(request->fProgress);
		Py_XINCREF(request->fUserData);
		PyObject *obj = PyObject_CallFunction(request->fProgress, "idOOO", type, completeness, state, dict, request->fUserData);
		Py_DECREF(dict);
		Py_DECREF(state);
		Py_DECREF(request->fProgress);
		Py_XDECREF(request->fUserData);
		
		if (!obj) {
			PyErr_Print();
			PyErr_Clear();
		}
		
		if ((!obj) || ((obj != Py_None) && (PyObject_Not(obj))))
			request->fAborted = true;
		
		Py_XDECREF(obj);
	}
	if (!request->fAborted)
		result = MGA_OK;
	
	PyGILState_Release(gstate);
	
	return result;
}


/**
 *	Starts an automatic servers discovery operation, allowing to retrieve the list of MGA servers currently available in the local
 *	area network. Until \e timeout expires, the currently installed progress callback gets invoked with a MGA.PROGRESS_DISCOVER type;
 *	the callback return value is ignored though, so it is not possible to abort this operation. When \e timeout expires, the callback
 *	will be invoked one last time with a MGA.PROGRESS_COMPLETE type and the function will return a Python tuple object, where each
 *	element is a dict representing a found server, and holding the following keys:
 *	- \e host: unicode string holding the IP address of the server in dotted numbers notation.
 *	- \e port: int holding the TCP network port number this server responds to.
 *	- \e name: unicode string with the public name of the server.
 *	- \e description: unicode string with a brief description of the server.
 *
 *	Servers discovery works by sending discovery broadcast packets via UDP on a series of network ports. You can alter the default port
 *	where to start this process via the \e port parameter.
 *	\param	self				Unused.
 *	\param	args				Arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e timeout: timeout in milliseconds of the server discovery operation. MGA.DEFAULT_DISCOVER_TIMEOUT if
 *									not specified.
 *								- \e port: UDP network port number where to start automatic server discovery. MGA.DEFAULT_SERVER_RESPONDER_PORT
 *									if not specified.
 *	\return						A tuple of dict objects representing the found servers on the local area network. See above.
 */
static PyObject *
MGA_Client_list_servers(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "timeout", "port", "success", "error", "progress", "userdata", NULL };
	uint32 timeout = MGA_DEFAULT_DISCOVER_TIMEOUT, port = 0;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|iiOOOO", kwlist, &timeout, &port, &success, &error, &progress, &userdata))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->GetServerList((MGA_DiscoverCB)_DiscoverCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout, port);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		MGA_ServerSpec spec[100];
		uint32 numServers;
		Py_BEGIN_ALLOW_THREADS
		numServers = self->fClient->GetServerList(spec, 100, timeout, (uint16)port);
		Py_END_ALLOW_THREADS
		PyObject *list = PyTuple_New(numServers);
		for (uint32 i = 0; i < numServers; i++) {
			PyObject *server = PyDict_New();
			const char *uuid = spec[i].fUUID;
			PyDict_SetItemString(server, "host", PyUnicode_DecodeUTF8(spec[i].fHost.c_str(), spec[i].fHost.size(), NULL));
			PyDict_SetItemString(server, "port", PyInt_FromLong((long)spec[i].fPort));
			PyDict_SetItemString(server, "name", PyUnicode_DecodeUTF8(spec[i].fName.c_str(), spec[i].fName.size(), NULL));
			PyDict_SetItemString(server, "description", PyUnicode_DecodeUTF8(spec[i].fDescription.c_str(), spec[i].fDescription.size(), NULL));
			PyDict_SetItemString(server, "data_version", PyInt_FromLong((long)spec[i].fDataVersion));
			PyDict_SetItemString(server, "uuid", PyUnicode_DecodeUTF8(uuid, strlen(uuid), NULL));
			PyDict_SetItemString(server, "multitenant_enabled", spec[i].fMultiTenant ? Py_True : Py_False);
			if (spec[i].fMultiTenant)
				Py_INCREF(Py_True);
			else
				Py_INCREF(Py_False);
			PyTuple_SET_ITEM(list, i, server);
		}
		return list;
	}
}


/**
 *	Attempts a connection to a remote MGA server. The progress callback will be repeatedly invoked with a MGA.PROGRESS_CONNECT type;
 *	the callback return value is ignored though, so it is not possible to abort this operation. When \e timeout expires or a connection
 *	is successfully established, or an error occurs, the callback will be invoked one last time with a MGA.PROGRESS_COMPLETE type and
 *	the function will exit.
 *	\param	self				Unused.
 *	\param	args				Arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e server: dict object with server specifications in the same form as returned by MGA.GetServerList.
 *									Most notably, only \e host and \e port need to be set for MGA.Connect() to work.
 *								- \e host: server IP address string, for when \e server is not specified.
 *								- \e port: server TCP network port number, for when \e server is not specified.
 *								- \e compress: boolean value, specifying if to apply data compression when communicating with the server.
 *								- \e crypting: integer crypting level, ranging 0-3. MGA.CRYPT_NORMAL if not specified.
 *								- \e timeout: operation timeout in milliseconds. MGA.DEFAULT_CONNECT_TIMEOUT if not specified.
 *	\return						Always None.
 */
static PyObject *
MGA_Client_connect(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "server", "host", "port", "options", "timeout", "success", "error", "progress", "userdata", NULL };
	PyObject *server = Py_None, *object, *optionsObj = NULL;
	MGA_ServerSpec spec;
	CLU_Table *options = NULL;
	char *host = NULL;
	string portStr, tenant_key;
	int32 port = 0, timeout = MGA_DEFAULT_CONNECT_TIMEOUT;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	MGA_Status result;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OsiOiOOOO", kwlist, &server, &host, &port, &optionsObj, &timeout, &success, &error, &progress, &userdata))
		return NULL;
	
	if ((server == Py_None) && (!host)) {
		PyErr_SetString(PyExc_ValueError, "either 'host' or 'server' parameter must be specified");
		return NULL;
	}
	if (server != Py_None) {
		if (!PyDict_Check(server)) {
			PyErr_SetString(PyExc_TypeError, "'server' must be a dictionary object");
			return NULL;
		}
		object = PyDict_GetItemString(server, "host");
		if (!object) {
			PyErr_SetString(PyExc_KeyError, "missing 'host' entry in server dictionary");
			return NULL;
		}
		if (!MGA::ConvertString(object, &spec.fHost)) {
			return NULL;
		}
		object = PyDict_GetItemString(server, "port");
		if (!object) {
			PyErr_SetString(PyExc_KeyError, "missing 'port' entry in server dictionary");
			return NULL;
		}
#if PY3K
		if (!PyLong_Check(object)) {
			if (MGA::ConvertString(object, &portStr)) {
				spec.fPort = CL_ATOI(portStr) & 0xFFFF;
			}
			else {
				PyErr_Clear();
				PyErr_SetString(PyExc_TypeError, "'port' entry in 'server' dictionary must be an integer object");
				return NULL;
			}
		}
#else
		if (!PyInt_Check(object)) {
			if (PyLong_Check(object)) {
				spec.fPort = (uint16)PyLong_AsLong(object);
			}
			else if (MGA::ConvertString(object, &portStr)) {
				spec.fPort = CL_ATOI(portStr) & 0xFFFF;
			}
			else {
				PyErr_Clear();
				PyErr_SetString(PyExc_TypeError, "'port' entry in 'server' dictionary must be an integer object");
				return NULL;
			}
		}
#endif
		else {
			spec.fPort = (uint16)PyInt_AS_LONG(object);
		}
	}
	else {
		spec.fHost = host;
		spec.fPort = port;
	}
	
	if ((optionsObj) && (optionsObj != Py_None) && (PyDict_Check(optionsObj))) {
		options = MGA::Table_FromPy(optionsObj);
	}
	if (options) {
		if (PyErr_Occurred()) {
			CL_Delete(options);
			return NULL;
		}
		if (options->IsValid("sid"))
			spec.fSID = options->GetString("sid");
		if (options->IsValid("remote_address"))
			spec.fRemoteAddress = options->GetString("remote_address");
	}
	else {
		options = CL_New(CLU_Table());
	}

	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->Connect(&spec, *options, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		CL_Delete(options);
		
		return (PyObject *)request;
	}
	else {
		CLU_Table output;
		
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->Connect(&spec, &output, *options, timeout);
		Py_END_ALLOW_THREADS
		CL_Delete(options);
		if (result != MGA_OK)
			return MGA::setException(result);
		
		return MGA::Table_FromCLU(&output);
	}
}


/**
 *	Disconnects from the currently connected remote MGA server, if any.
 *	\param	self				Unused.
 *	\param	args				Unused.
 *	\return						Always None.
 */
static PyObject *
MGA_Client_disconnect(MGA::ClientObject *self, PyObject *args)
{
	self->fClient->Disconnect();
	
	Py_RETURN_NONE;
}


/**
 *	Gets the ID of this client on the server.
 *	\param	self				Unused.
 *	\param	args				Unused.
 *	\return						The client ID.
 */
static PyObject *
MGA_Client_get_id(MGA::ClientObject *self, PyObject *args)
{
	return PyInt_FromLong(self->fClient->GetID());
}


/**
 *	Gets informations on the current connected server
 *	\param	self				Unused.
 *	\param	args				Unused.
 *	\return						Server info dict or None.
 */
static PyObject *
MGA_Client_get_connection_info(MGA::ClientObject *self, PyObject *args)
{
	CLU_Table info;
	self->fClient->GetConnectionInfo(&info);
	CLU_UUID uuid(0);
	
	if (info.Exists("uuid"))
		uuid = CLU_UUID(info.GetString("uuid"));
	if (uuid == CLU_UUID(0))
		Py_RETURN_NONE;
	
	CLU_Table& database = self->fClient->GetDatabase();
	if (database.Empty())
		info.Set("database", CLU_Null);
	else
		info.Set("database", database);
	CLU_Table& user = self->fClient->GetUser();
	if (user.Empty())
		info.Set("user", CLU_Null);
	else
		info.Set("user", user);
	
	return MGA::Table_FromCLU(&info);
}


/**
 *	Executes a command request on the remote MGA server. During execution, the progress callback is repeatedly called with a
 *	MGA.PROGRESS_PROCESS, MGA.PROGRESS_SEND, MGA.PROGRESS_RECEIVE or MGA.PROGRESS_EXECUTE type (see MGA_Client::Execute()).
 *	If the callback returns an expression that evaluates to True, the callback will be invoked one last time with the
 *	MGA.PROGRESS_ABORT type, and this function will throw an MGA.Error exception. If on the other hand, the operation successfully
 *	completes, the callback will be invoked one last time with the MGA.PROGRESS_COMPLETE type, and the function will return a
 *	dict object holding the operation output data as replied by the server.
 *	\param	self				Unused.
 *	\param	args				Arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e command: integer identifier of the command to be executed on the server.
 *								- \e data: dict object holding request input data. None if not specified.
 *								- \e feed: boolean value specifying if the progress callback is going to get partially received
 *									output data from the server. False if not specified.
 *								- \e timeout: integer timeout of the execute operation in milliseconds. MGA.DEFAULT_EXECUTE_TIMEOUT
 *									if not specified.
 *	\return						A dict object holding the operation results returned by the server.
 */
static PyObject *
MGA_Client_execute(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "command", "data", "timeout", "success", "error", "progress", "idle", "userdata", NULL };
	PyObject *py_input = NULL;
	CLU_Table *input = NULL, output;
	MGA_Command command;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *idle = NULL, *userdata = Py_None;
	MGA_Status result;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "i|O!iOOOOO:execute", kwlist, &command, &PyDict_Type, &py_input, &timeout, &success, &error, &progress, &idle, &userdata))
		return NULL;
	
	if (py_input) {
		input = MGA::Table_FromPy(py_input);
		if (PyErr_Occurred()) {
			CL_Delete(input);
			return NULL;
		}
	}
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress, idle);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->Execute(command, input, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, (MGA_IdleCB)_IdleCB, request, timeout);
		Py_END_ALLOW_THREADS
		CL_Delete(input);
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
// 		uint32 time = CL_Timer::GetTime();
		result = self->fClient->Execute(command, input, &output, _SyncIdleCB, timeout);
// 		fprintf(stderr, "EXECUTE TIME: %d\n", CL_Timer::GetTime() - time);
		Py_END_ALLOW_THREADS
		CL_Delete(input);
		if (result != MGA_OK)
			return MGA::setException(result, &output);
		
		return MGA::Table_FromCLU(&output);
	}
}


static PyObject *
MGA_Client_interrupt(MGA::ClientObject *self, PyObject *args)
{
	self->fClient->Interrupt();

	Py_RETURN_NONE;
}


/**
 *	Obtains the data dictionary from the currently connected server. The data dictionary is returned as a raw dict object
 *	containing the data as held in server memory.
 *	\return						The data dictionary dict object.
 */
static PyObject *
MGA_Client_get_data_dictionary(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "success", "error", "progress", "userdata", "timeout", NULL };
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	MGA_Status result;
	CLU_Table *dict;
	PyObject *output;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OOOOi:get_data_dictionary", kwlist, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->GetDataDictionary((MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->GetDataDictionary(&dict);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		output = MGA::Table_FromCLU(dict);
		CL_Delete(dict);
		
		return output;
	}
}


static PyObject *
MGA_Client_list_drivers(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "configured", "success", "error", "progress", "userdata", "timeout", NULL };
	PyObject *configured = Py_True, *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	MGA_Status result;
	CLU_List *drivers;
	PyObject *output;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OOOOOi:list_drivers", kwlist, &configured, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->ListDrivers(PyObject_IsTrue(configured) ? true : false, (MGA_SuccessWithListCB)_SuccessWithListCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->ListDrivers(PyObject_IsTrue(configured) ? true : false, &drivers);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		output = MGA::List_FromCLU(drivers);
		CL_Delete(drivers);
		
		return output;
	}
}


static PyObject *
MGA_Client_list_databases(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "driver", "quick", "success", "error", "progress", "userdata", "timeout", NULL };
	string driver;
	PyObject *driverObj = NULL, *quickObj = Py_False, *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	MGA_Status result;
	CLU_Table *databases;
	PyObject *output;
	bool quick;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OOOOOOi:list_databases", kwlist, &driverObj, &quickObj, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((driverObj != Py_None) && (driverObj) && (!MGA::ConvertString(driverObj, &driver)))
		return NULL;
	
	quick = PyObject_IsTrue(quickObj) ? true : false;
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->ListDatabases(driver, quick, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->ListDatabases(driver, quick, &databases);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		output = MGA::Table_FromCLU(databases);
		CL_Delete(databases);
		
		return output;
	}
}


static PyObject *
MGA_Client_create_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "driver", "name", "desc", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, driver, name, desc;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&O&O&|O&OOOOi:create_database", kwlist, MGA::ConvertString, &password, MGA::ConvertString, &driver, MGA::ConvertString, &name, MGA::ConvertString, &desc, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->CreateDatabase(password, driver, name, desc, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		CLU_UUID uuid;
		
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->CreateDatabase(password, driver, name, desc, &uuid);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		string uuids = (const char *)uuid;
		return PyUnicode_FromString(uuids.c_str());
	}
}


static PyObject *
MGA_Client_open_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "driver", "name", "success", "error", "progress", "userdata", "timeout", NULL };
	string driver, name;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None, *output;
	CLU_Table *info;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&O&|OOOOi:open_database", kwlist, MGA::ConvertString, &driver, MGA::ConvertString, &name, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->OpenDatabase(driver, name, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->OpenDatabase(driver, name, &info);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		output = MGA::Table_FromCLU(info);
		CL_Delete(info);
		
		return output;
	}
}


static PyObject *
MGA_Client_close_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "backup", "success", "error", "progress", "userdata", "timeout", NULL };
	PyObject *backup = Py_False, *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OOOOOi:close_database", kwlist, &backup, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->CloseDatabase(PyObject_IsTrue(backup) ? true : false, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		MGA_Status result;
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->CloseDatabase(PyObject_IsTrue(backup) ? true : false);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_upgrade_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "driver", "name", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, driver, name;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	uint32 old_version, new_version;
	CLU_List *log;
	PyObject *info;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&O&O&|OOOOi:upgrade_database", kwlist, MGA::ConvertString, &password, MGA::ConvertString, &driver, MGA::ConvertString, &name, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->UpgradeDatabase(password, driver, name, (MGA_SuccessWithTableCB)_SuccessWithUpgradeResultCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->UpgradeDatabase(password, driver, name, &log, &old_version, &new_version);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		info = PyTuple_New(3);
		PyTuple_SET_ITEM(info, 0, MGA::List_FromCLU(log));
		PyTuple_SET_ITEM(info, 1, PyInt_FromLong(old_version));
		PyTuple_SET_ITEM(info, 2, PyInt_FromLong(new_version));
		CL_Delete(log);
		
		return info;
	}
}


static PyObject *
MGA_Client_delete_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "driver", "name", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, driver, name;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&O&O&|OOOOi:delete_database", kwlist, MGA::ConvertString, &password, MGA::ConvertString, &driver, MGA::ConvertString, &name, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->DeleteDatabase(password, driver, name, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->DeleteDatabase(password, driver, name);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_query_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "query", "native", "full_column_names", "collapse_blobs", "success", "error", "progress", "userdata", "timeout", NULL };
	string query;
	PyObject *_native = Py_False, *_full_column_names = Py_False, *_collapse_blobs = Py_False;
	bool native, full_column_names, collapse_blobs;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&|OOOOOOOi:query_database", kwlist, MGA::ConvertString, &query, &_native, &_full_column_names, &_collapse_blobs, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	native = PyObject_IsTrue(_native) ? true : false;
	full_column_names = PyObject_IsTrue(_full_column_names) ? true : false;
	collapse_blobs = PyObject_IsTrue(_collapse_blobs) ? true : false;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->QueryDatabase(query, (MGA_SuccessWithResultSetCB)_SuccessWithResultSetCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, native, full_column_names, collapse_blobs, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		uint32 affectedRows;
		CLU_List *columnNames;
		CLU_List *resultSet;
		string errorMsg;
		PyObject *output, *temp1, *temp2, *temp3;
		
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->QueryDatabase(query, &affectedRows, &columnNames, &resultSet, native, full_column_names, collapse_blobs, &errorMsg);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(result, errorMsg);
		
		temp1 = PyInt_FromLong(affectedRows);
		temp2 = MGA::List_FromCLU(columnNames);
		temp3 = MGA::List_FromCLU(resultSet);
		output = PyTuple_Pack(3, temp1, temp2, temp3);
		Py_DECREF(temp1);
		Py_DECREF(temp2);
		Py_DECREF(temp3);
		
		CL_Delete(columnNames);
		CL_Delete(resultSet);
		
		return output;
	}
}


static PyObject *
MGA_Client_backup_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "backupName", "driver", "name", "auto", "overwrite", "position", "storeindex", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, backupName, driver, name;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None, *automatic = Py_True, *overWrite = Py_False, *storeIndex = Py_False;
	uint32 position = 0, timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&O&|O&O&OOiOOOOOi:backup_database", kwlist, MGA::ConvertString, &password, MGA::ConvertString, &backupName, MGA::ConvertString, &driver, MGA::ConvertString, &name, &automatic, &overWrite, &position, &storeIndex, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->BackupDatabase(password, driver, name, backupName, PyObject_IsTrue(automatic) ? true : false, PyObject_IsTrue(overWrite) ? true : false, position, PyObject_IsTrue(storeIndex) ? true : false, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->BackupDatabase(password, driver, name, backupName, PyObject_IsTrue(automatic) ? true : false, PyObject_IsTrue(overWrite) ? true : false, position, PyObject_IsTrue(storeIndex) ? true : false);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_restore_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "backupName", "driver", "name", "changeUUID", "overWrite", "position", "restoreindex", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, backupName, driver, name;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 changeUUID = 1, overWrite = 0, position=0, restoreIndex=1, timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&O&|O&O&iiiiOOOOi:restore_database", kwlist, MGA::ConvertString, &password, MGA::ConvertString, &backupName, MGA::ConvertString, &driver, MGA::ConvertString, &name, &changeUUID, &overWrite, &position, &restoreIndex, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->RestoreDatabase(password, driver, name, backupName, changeUUID ? true : false, overWrite ? true : false, position, restoreIndex ? true : false, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->RestoreDatabase(password, driver, name, backupName, changeUUID ? true : false, overWrite ? true : false, position, restoreIndex ? true : false);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_list_backups(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "position", "success", "error", "progress", "userdata", "timeout", NULL };
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 position=0, timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	MGA_Status result;
	CLU_List *backups;
	PyObject *output;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|iOOOOi:list_backups", kwlist, &position, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->ListBackups(position, (MGA_SuccessWithListCB)_SuccessWithListCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->ListBackups(position, &backups);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		output = MGA::List_FromCLU(backups);
		CL_Delete(backups);
		
		return output;
	}
}


static PyObject *
MGA_Client_delete_backup(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "backupName", "position", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, backupName;
	CLU_List backupNames;
	PyObject *object, *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 position, timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&Oi|OOOOi:delete_backup", kwlist, MGA::ConvertString, &password, &object, &position, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if (!MGA::ConvertString(object, &backupName)) {
		PyErr_Clear();
		object = PySequence_Fast(object, "Expected 'str' or 'list' object");
		if (!object)
			return NULL;
		for (Py_ssize_t i = 0; i < PySequence_Fast_GET_SIZE(object); i++) {
			PyObject *name = PySequence_Fast_GET_ITEM(object, i);
			if (!MGA::ConvertString(name, &backupName)) {
				Py_DECREF(object);
				return NULL;
			}
			backupNames.Append(backupName);
		}
		Py_DECREF(object);
	}
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		if (backupNames.Count() > 0)
			self->fClient->DeleteBackup(position, password, backupNames, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		else
			self->fClient->DeleteBackup(position, password, backupName, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		if (backupNames.Count() > 0)
			result = self->fClient->DeleteBackup(position, password, backupNames);
		else
			result = self->fClient->DeleteBackup(position, password, backupName);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_optimize_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "driver", "name", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, driver, name;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&|O&O&OOOOi:optimize_database", kwlist, MGA::ConvertString, &password, MGA::ConvertString, &driver, MGA::ConvertString, &name, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->OptimizeDatabase(password, driver, name, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->OptimizeDatabase(password, driver, name);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_repair_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "driver", "name", "output", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, driver, name, output;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&|O&O&O&OOOOi:optimize_database", kwlist, MGA::ConvertString, &password, MGA::ConvertString, &driver, MGA::ConvertString, &name, MGA::ConvertString, &output, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->RepairDatabase(password, driver, name, output, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->RepairDatabase(password, driver, name, output);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_index_database(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "password", "driver", "name", "reset", "run", "success", "error", "progress", "userdata", "timeout", NULL };
	string password, driver, name;
	PyObject *reset = Py_False, *run = Py_True, *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&|O&O&OOOOOOi:index_database", kwlist, MGA::ConvertString, &password, MGA::ConvertString, &driver, MGA::ConvertString, &name, &reset, &run, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->IndexDatabase(password, driver, name, PyObject_IsTrue(reset) ? true : false, PyObject_IsTrue(run) ? true : false, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->IndexDatabase(password, driver, name, PyObject_IsTrue(reset) ? true : false, PyObject_IsTrue(run) ? true : false);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_list_clients(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "full", "any", "success", "error", "progress", "userdata", "timeout", NULL };
	PyObject *fullObj = Py_False, *anyObj = Py_False, *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	bool full, any;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OOOOOOi:list_clients", kwlist, &fullObj, &anyObj, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	full = PyObject_IsTrue(fullObj) ? true : false;
	any = PyObject_IsTrue(anyObj) ? true : false;
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->GetClientList(full, any, (MGA_SuccessWithListCB)_SuccessWithListCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		MGA_Status result;
		CLU_List *list;
		PyObject *output;
		
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->GetClientList(full, any, &list);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		output = MGA::List_FromCLU(list);
		CL_Delete(list);
		
		return output;
	}
}


static PyObject *
MGA_Client_get_client_info(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "id", "success", "error", "progress", "userdata", "timeout", NULL };
	uint32 clientId = 0;
	string sid;
	PyObject *client, *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|OOOOi:get_client_info", kwlist, &client, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if (!MGA::ConvertString(client, &sid)) {
		PyErr_Clear();
		clientId = PyInt_AsLong(client);
		if (PyErr_Occurred())
			return NULL;
	}
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		if (sid.empty())
			self->fClient->GetClientInfo(clientId, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		else
			self->fClient->GetClientInfo(sid, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		CLU_Table *info;
		PyObject *output;
		
		Py_BEGIN_ALLOW_THREADS
		if (sid.empty())
			result = self->fClient->GetClientInfo(clientId, &info);
		else
			result = self->fClient->GetClientInfo(sid, &info);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		output = MGA::Table_FromCLU(info);
		CL_Delete(info);
		
		return output;
	}
}


static PyObject *
MGA_Client_kill_client(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "id", "password", "success", "error", "progress", "userdata", "timeout", NULL };
	uint32 clientId = 0;
	string sid, password;
	PyObject *client, *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO&|OOOOi:kill_client", kwlist, &client, MGA::ConvertString, &password, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if (!MGA::ConvertString(client, &sid)) {
		PyErr_Clear();
		clientId = PyInt_AsLong(client);
		if (PyErr_Occurred())
			return NULL;
	}
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		if (sid.empty())
			self->fClient->KillClient(clientId, password, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		else
			self->fClient->KillClient(sid, password, (MGA_SuccessCB)_SuccessCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		if (sid.empty())
			result = self->fClient->KillClient(clientId, password);
		else
			result = self->fClient->KillClient(sid, password);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		Py_RETURN_NONE;
	}
}


static PyObject *
MGA_Client_authenticate(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "username", "password", "success", "error", "progress", "userdata", "timeout", "new_password", NULL };
	string userName, password, newPassword;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None, *newPasswordObj = NULL;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	CLU_Table *userInfo;
	PyObject *output;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&O&|OOOOiO:authenticate", kwlist, MGA::ConvertString, &userName, MGA::ConvertString, &password, &success, &error, &progress, &userdata, &timeout, &newPasswordObj))
		return NULL;

	if (newPasswordObj == Py_None)
		newPasswordObj = NULL;
	if ((newPasswordObj) && (!MGA::ConvertString(newPasswordObj, &newPassword)))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		if (newPasswordObj)
			self->fClient->Authenticate(userName, password, newPassword, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		else
			self->fClient->Authenticate(userName, password, (MGA_SuccessWithTableCB)_SuccessWithTableCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		Py_BEGIN_ALLOW_THREADS
		if (newPasswordObj)
			result = self->fClient->Authenticate(userName, password, newPassword, &userInfo);
		else
			result = self->fClient->Authenticate(userName, password, &userInfo);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK)
			return MGA::setException(self, result);
		
		output = MGA::Table_FromCLU(userInfo);
		CL_Delete(userInfo);
		
		return output;
	}
}


static PyObject *
MGA_Client_full_text_search(MGA::ClientObject *self, PyObject *args, PyObject *kwds)
{
	MGA_Status result;
	static char *kwlist[] = { "text", "limit", "success", "error", "progress", "userdata", "timeout", NULL };
	string text;
	uint32 limit = 0;
	PyObject *success = NULL, *error = NULL, *progress = NULL, *userdata = Py_None;
	uint32 timeout = MGA_DEFAULT_EXECUTE_TIMEOUT;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&|iOOOOi:full_text_search", kwlist, MGA::ConvertString, &text, &limit, &success, &error, &progress, &userdata, &timeout))
		return NULL;
	
	if ((success) && (success != Py_None)) {
		MGA::DeferredObject *request = MGA::DeferredObject::Allocate(self, userdata, success, error, progress);
		
		Py_INCREF(request);
		Py_BEGIN_ALLOW_THREADS
		self->fClient->FullTextSearch(text, limit, (MGA_SuccessWithListCB)_SuccessWithListCB, (MGA_ErrorCB)_ErrorCB, (MGA_ProgressCB)_ProgressCB, request, timeout);
		Py_END_ALLOW_THREADS
		
		return (PyObject *)request;
	}
	else {
		CLU_List results;
		PyObject *resultsObject;
		
		Py_BEGIN_ALLOW_THREADS
		result = self->fClient->FullTextSearch(text, &results, limit);
		Py_END_ALLOW_THREADS
		if (result != MGA_OK) {
			return MGA::setException(self, result);
		}
		
		resultsObject = MGA::List_FromCLU(&results);
		
		return resultsObject;
	}
}


static MGA::ClientObject *
MGA_Client_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	MGA::ClientObject *self = new (type->tp_alloc(type, 0)) MGA::ClientObject();

	if (!MGA::trackClient(self)) {
		CL_Delete(self->fClient);
		self->~ClientObject();
		PyErr_SetString(PyExc_RuntimeError, "cannot instantiate Client object during termination");
		return NULL;
	}
	self->fClient->SetDefaultIdleCB(_SyncIdleCB);
	
	return self;
}


static void
MGA_Client_dealloc(MGA::ClientObject *self)
{
	MGA::untrackClient(self);
	
// 	Py_BEGIN_ALLOW_THREADS
// 	
	self->~ClientObject();
// 	
// 	Py_END_ALLOW_THREADS
	
	Py_TYPE(self)->tp_free((PyObject*)self);
}


static PyMethodDef MGA_Client_methods[] = {
	{	"list_servers",				(PyCFunction)MGA_Client_list_servers,			METH_VARARGS | METH_KEYWORDS,	"list_servers([timeout [, port, success, progress, userdata]) -> tuple | Deferred\n\nGets a list of available servers found in the local network, using specified UDP port for servers discovery. Returns a tuple of dict objects with informations on each server found." },
	{	"connect",					(PyCFunction)MGA_Client_connect,				METH_VARARGS | METH_KEYWORDS,	"connect([, server]|[, host, port, compress, crypting] [, timeout, success, error, progress, userdata]) [ -> Deferred ]\n\nConnects to a specified server using supplied activation key. Server can be specified as dict (as returned by GetServerList()) or by single parameters." },
	{	"disconnect",				(PyCFunction)MGA_Client_disconnect,				METH_NOARGS,					"disconnect([success, error, progress, userdata]) [ -> Deferred ]\n\nDisconnects from currently connected server." },
	{	"get_id",					(PyCFunction)MGA_Client_get_id,					METH_NOARGS,					"get_id() -> int\n\nReturns the ID identifying this client on the server." },
	{	"get_connection_info",		(PyCFunction)MGA_Client_get_connection_info,	METH_NOARGS,					"get_connection_info() -> dict | None\n\nReturns informations on the currently connected server or None if not connected at all." },
	{	"execute",					(PyCFunction)MGA_Client_execute,				METH_VARARGS | METH_KEYWORDS,	"execute(command [, data, timeout, success, error, progress, userdata]) -> dict | Deferred\n\nExecutes an operation on the server. If feed is True, the progress callback will receive partial results." },
	{	"interrupt",				(PyCFunction)MGA_Client_interrupt,				METH_NOARGS,					"interrupt()\n\nInterrupts all pending operations on this client." },
	{	"get_data_dictionary",		(PyCFunction)MGA_Client_get_data_dictionary,	METH_VARARGS | METH_KEYWORDS,	"get_data_dictionary([success, error, progress, userdata]) -> dict | Deferred\n\nGets the data dictionary from currently connected server." },
	{	"list_drivers",				(PyCFunction)MGA_Client_list_drivers,			METH_VARARGS | METH_KEYWORDS,	"list_drivers([success, error, progress, userdata]) -> list | Deferred\n\nReturns a list where each entry is in the form {'name': ..., 'description': ..., 'icon': ... }, identifying the supported server drivers." },
	{	"list_databases",			(PyCFunction)MGA_Client_list_databases,			METH_VARARGS | METH_KEYWORDS,	"list_databases([success, error, progress, userdata]) -> dict | Deferred\n\nReturns a dictionary with an entry for each supported server driver. The entry value is a list where each entry contains informations on a single database for that driver as found on the server." },
	{	"create_database",			(PyCFunction)MGA_Client_create_database,		METH_VARARGS | METH_KEYWORDS,	"create_database(driver, name [, desc, success, error, progress, userdata]) [ -> Deferred ]\n\nCreates a new named database on the server using specified driver and assigning a description to it." },
	{	"open_database",			(PyCFunction)MGA_Client_open_database,			METH_VARARGS | METH_KEYWORDS,	"open_database(driver, name [, success, error, progress, userdata]) [ -> Deferred ]\n\nAttempts to open a connection to a specified database on the server." },
	{	"close_database",			(PyCFunction)MGA_Client_close_database,			METH_VARARGS | METH_KEYWORDS,	"close_database([success, error, progress, userdata]) [ -> Deferred ]\n\nCloses connection to the current database, if any." },
	{	"upgrade_database",			(PyCFunction)MGA_Client_upgrade_database,		METH_VARARGS | METH_KEYWORDS,	"upgrade_database(driver, name [, success, error, progress, userdata]) -> list | Deferred\n\nUpgrades specified database to the latest data dictionary version, and returns a log of the operations performed to accomplish the task." },
	{	"delete_database",			(PyCFunction)MGA_Client_delete_database,		METH_VARARGS | METH_KEYWORDS,	"delete_database(driver, name [, success, error, progress, userdata]) [ -> Deferred ]\n\nDeletes specified database from server." },
	{	"query_database",			(PyCFunction)MGA_Client_query_database,			METH_VARARGS | METH_KEYWORDS,	"query_database(query [, native, success, error, progress, userdata]) -> tuple | Deferred\n\nExecutes an SQL query on the connected database, using either native driver or generic SQL syntax. Returns a tuple in the form (columnNamesList, resultSetList)." },
	{	"backup_database",			(PyCFunction)MGA_Client_backup_database,		METH_VARARGS | METH_KEYWORDS,	"backup_database(backupName [, driver, name, success, error, progress, userdata]) [ -> Deferred ]\n\nStarts a backup operation on currently connected database, or the database identified by driver, name. The backup is saved using given backup name." },
	{	"restore_database",			(PyCFunction)MGA_Client_restore_database,		METH_VARARGS | METH_KEYWORDS,	"restore_database(backupName, driver, name [, changeUUID, success, error, progress, userdata]) [ -> Deferred ]\n\nRestores a previously saved backup with given backup name into a new database created using driver and name. If changeUUID is True (the default), a new UUID is generated for the restored database, otherwise its UUID is restored from the backup as well." },
	{	"list_backups",				(PyCFunction)MGA_Client_list_backups,			METH_VARARGS | METH_KEYWORDS,	"list_backups([success, error, progress, userdata]) -> tuple | Deferred\n\nLists available backups." },
	{	"delete_backup",			(PyCFunction)MGA_Client_delete_backup,			METH_VARARGS | METH_KEYWORDS,	"delete_backup(backupName [, success, error, progress, userdata]) [ -> Deferred ]\n\nDeletes a backup from the server." },
	{	"optimize_database",		(PyCFunction)MGA_Client_optimize_database,		METH_VARARGS | METH_KEYWORDS,	"optimize_database(password, driver, name [, success, error, progress, userdata]) [ -> Deferred ]\n\nOptimizes a database on the server." },
	{	"repair_database",			(PyCFunction)MGA_Client_repair_database,		METH_VARARGS | METH_KEYWORDS,	"repair_database(password, driver, name [, success, error, progress, userdata]) [ -> Deferred ]\n\nAttempts to repair a database on the server." },
	{	"index_database",			(PyCFunction)MGA_Client_index_database,			METH_VARARGS | METH_KEYWORDS,	"index_database(password, driver, name [, success, error, progress, userdata]) [ -> Deferred ]\n\nPerforms full text search indexing on a database on the server." },
	{	"list_clients",				(PyCFunction)MGA_Client_list_clients,			METH_VARARGS | METH_KEYWORDS,	"list_clients([success, error, progress, userdata]) -> list | Deferred\n\nReturns the list of client IDs currently connected to the server." },
	{	"get_client_info",			(PyCFunction)MGA_Client_get_client_info,		METH_VARARGS | METH_KEYWORDS,	"get_client_info(id [, success, error, progress, userdata]) -> dict | Deferred\n\nReturns informations on specified client ID currently connected to the server." },
	{	"kill_client",				(PyCFunction)MGA_Client_kill_client,			METH_VARARGS | METH_KEYWORDS,	"kill_client(id [, success, error, progress, userdata]) -> dict | Deferred\n\nKills the server connection for client with ID." },
	{	"authenticate",				(PyCFunction)MGA_Client_authenticate,			METH_VARARGS | METH_KEYWORDS,	"authenticate(userName, password [, success, error, progress, userdata]) -> table | Deferred\n\nAttempts to authenticate an user on the currently connected database; on success, returns informations on the authenticated user." },
	{	"full_text_search",			(PyCFunction)MGA_Client_full_text_search,		METH_VARARGS | METH_KEYWORDS,	"full_text_search(text [, limit, success, error, progress, userdata]) -> list | Deferred\n\nPerforms a full text search on the connected database and returns a list of entries in the form (score, tableId, rowId)." },
	{	NULL }
};


/** Vtable describing the MGA.Client type. */
PyTypeObject MGA::ClientType = {
	PyVarObject_HEAD_INIT(NULL, 0)
    "_kongalib.Client",						/* tp_name */
    sizeof(MGA::ClientObject),				/* tp_basicsize */
	0,										/* tp_itemsize */
	(destructor)MGA_Client_dealloc,			/* tp_dealloc */
	0,										/* tp_print */
	0,										/* tp_getattr */
	0,										/* tp_setattr */
	0,										/* tp_compare */
	0,										/* tp_repr */
	0,										/* tp_as_number */
	0,										/* tp_as_sequence */
	0,										/* tp_as_mapping */
	0,										/* tp_hash */
	0,										/* tp_call */
	0,										/* tp_str */
	0,										/* tp_getattro */
	0,										/* tp_setattro */
	0,										/* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,						/* tp_flags */
	"Client objects",						/* tp_doc */
	0,										/* tp_traverse */
	0,										/* tp_clear */
	0,										/* tp_richcompare */
	0,										/* tp_weaklistoffset */
	0,										/* tp_iter */
	0,										/* tp_iternext */
	MGA_Client_methods,						/* tp_methods */
	0,										/* tp_members */
	0,										/* tp_getset */
	0,										/* tp_base */
	0,										/* tp_dict */
	0,										/* tp_descr_get */
	0,										/* tp_descr_set */
	0,										/* tp_dictoffset */
	0,										/* tp_init */
	0,										/* tp_alloc */
	(newfunc)MGA_Client_new,				/* tp_new */
};


namespace MGA {
	
	ClientObject::ClientObject()
		: fClient(NULL)
	{
	}
	
};

