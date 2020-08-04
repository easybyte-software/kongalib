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


#include "Python.h"

#define __DEFINE_DICTIONARY__
#include <konga_client/messages.h>
#undef __DEFINE_DICTIONARY__

#define __DEFINE_COMMANDS__
#include <konga_client/commands.h>
#undef __DEFINE_COMMANDS__

#include "module.h"

#include <list>
#include <algorithm>


#if PY3K
PyModuleDef					*MGA::gModuleDefPtr = NULL;
#else
MGA::MODULE_STATE			MGA::gState;
#endif

std::list<MGA::InterpreterObject *> sInterpreterList;
unsigned long						sMainThreadID = -1;



static void
onCreateWorker(CL_ThreadID tid)
{
	if (Py_IsInitialized()) {
		PyGILState_STATE gstate = PyGILState_Ensure();
		PyGILState_Release(gstate);
	}
}


static void
onDestroyWorker(CL_ThreadID tid)
{
	if (Py_IsInitialized()) {
		PyGILState_STATE gstate = PyGILState_Ensure();
		PyObject *module = PyImport_AddModule("kongalib");
		PyObject *onDestroyThread = PyDict_GetItemString(PyModule_GetDict(module), "_on_destroy_thread");
		if (onDestroyThread) {
			PyObject *result = PyObject_CallFunctionObjArgs(onDestroyThread, NULL);
			Py_XDECREF(result);
		}
		if (PyErr_Occurred())
			PyErr_Clear();

		PyGILState_Release(gstate);
	}
}


string
MGA::translate(MGA_Status error)
{
	MGA::MODULE_STATE *state = GET_STATE();
	if (!state)
		return "";
	return state->fTranslator->Get(error);
}


PyObject *
MGA::setException(MGA_Status error_code, const string& error_msg)
{
	MGA::MODULE_STATE *state = GET_STATE();
	std::string string = error_msg;
	if (string.empty() && state)
		string = state->fTranslator->Get(error_code);
	PyObject *args = Py_BuildValue("is", error_code, (const char *)string.c_str());
	if (state)
		PyErr_SetObject(state->fException, args);
	else
		PyErr_SetObject(PyExc_RuntimeError, args);
	Py_DECREF(args);
	return NULL;
}


/**
 *	Gets an error message from the server \a output and sets a Python exception accordingly.
 *	\param	error_code			Error code as returned by MGA_Client::Execute().
 *	\param	output				The server output #CLU_Table as returned by MGA_Client::Execute().
 *	\return						Always returns NULL.
 */
PyObject *
MGA::setException(MGA_Status error_code, CLU_Table *output)
{
	MGA::MODULE_STATE *state = GET_STATE();
	MGA_Status result = error_code;
	string error;
	
	if ((result == MGA_OK) && (output->Exists(MGA_OUT_ERRNO)))
		result = output->Get(MGA_OUT_ERRNO).Int32();
	if (result == MGA_OK) {
		result = error_code;
		if (state)
			error = state->fTranslator->Get(result);
	}
	else {
		if (output->Exists(MGA_OUT_ERROR))
			error = output->Get(MGA_OUT_ERROR).String();
		else if (state)
			error = state->fTranslator->Get(result);
	}
	return MGA::setException(result, error);
}


/**
 *	Gets an error message from the server \a output and sets a Python exception accordingly.
 *	\param	output				The server output #CLU_Table as returned by MGA_Client::Execute().
 *	\return						Always returns NULL.
 */
PyObject *
MGA::setException(MGA::ClientObject *client, MGA_Status result)
{
	MGA::MODULE_STATE *state = GET_STATE();
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "No module state!");
		return NULL;
	}

	return MGA::setException(result, state->fTranslator->Get(result));
}


bool
MGA::trackClient(MGA::ClientObject *client)
{
	MGA::MODULE_STATE *state = GET_STATE();
	if (!state)
		return false;
	CL_AutoLocker locker(&state->fThreadsLock);
	if (state->fInitialized) {
		if (state->fFreeClientsList.empty()) {
			client->fClient = CL_New(MGA_Client(state->fDispatcher));
			state->fClientList.push_back(client->fClient);
		}
		else {
			client->fClient = state->fFreeClientsList.back();
			state->fFreeClientsList.pop_back();
		}

		return true;
	}
	return false;
}


void
MGA::untrackClient(MGA::ClientObject *client)
{
	MGA::MODULE_STATE *state = GET_STATE();
	if (state) {
		CL_AutoLocker locker(&state->fThreadsLock);
		if (state->fInitialized) {
			client->fClient->Disconnect();

			state->fFreeClientsList.push_front(client->fClient);
		}
	}
}


void
MGA::trackInterpreter(MGA::InterpreterObject *interpreter, MGA::MODULE_STATE *state)
{
	sInterpreterList.push_back(interpreter);
}


void
MGA::untrackInterpreter(MGA::InterpreterObject *interpreter, MGA::MODULE_STATE *state)
{
	std::list<MGA::InterpreterObject *>::iterator it = find(sInterpreterList.begin(), sInterpreterList.end(), interpreter);
	if (it != sInterpreterList.end())
		sInterpreterList.erase(it);
}


MGA::DeferredObject::DeferredObject(ClientObject *client, PyObject *userData, PyObject *success, PyObject *error, PyObject *progress, PyObject *idle)
	: fClient(client), fSuccess(success), fError(error), fProgress(progress), fIdle(idle), fUserData(userData), fAborted(false), fExecuted(false), fPending(true)
{
	Py_XINCREF(client);
	Py_INCREF(userData);
	Py_XINCREF(success);
	Py_XINCREF(error);
	Py_XINCREF(progress);
	Py_XINCREF(idle);
}


MGA::DeferredObject::~DeferredObject()
{
	Py_XDECREF(fClient);
	Py_XDECREF(fSuccess);
	Py_XDECREF(fError);
	Py_XDECREF(fProgress);
	Py_XDECREF(fIdle);
	Py_DECREF(fUserData);
}


MGA::DeferredObject *
MGA::DeferredObject::Allocate(MGA::ClientObject *client, PyObject *userData, PyObject *success, PyObject *error, PyObject *progress, PyObject *idle)
{
	return new (DeferredType.tp_alloc(&DeferredType, 0)) DeferredObject(client, userData, success, error, progress, idle);
}


static void
Deferred_dealloc(MGA::DeferredObject *self)
{
	self->~DeferredObject();
	Py_TYPE(self)->tp_free((PyObject*)self);
}


static PyObject *
Deferred_cancel(MGA::DeferredObject *self, PyObject *args)
{
	MGA::MODULE_STATE *state = GET_STATE();
	if (!self->fAborted) {
		Py_BEGIN_ALLOW_THREADS
		if (state)
			state->fTimerLock.Lock();
		self->fAborted = true;
		self->fCondition.Signal();
		if (state)
			state->fTimerLock.Unlock();
		Py_END_ALLOW_THREADS
	}
	
	Py_RETURN_NONE;
}


static PyMethodDef Deferred_methods[] = {
	{	"cancel",			(PyCFunction)Deferred_cancel,				METH_NOARGS,					"Cancels this Deferred, setting 'aborted' attribute to True." },
	{	NULL,				NULL,										0,								NULL }
};


static PyObject *
Deferred_get_aborted(MGA::DeferredObject *self, void *data)
{
	if (self->fAborted)
		Py_RETURN_TRUE;
	else
		Py_RETURN_FALSE;
}


static PyObject *
Deferred_get_executed(MGA::DeferredObject *self, void *data)
{
	if (self->fExecuted)
		Py_RETURN_TRUE;
	else
		Py_RETURN_FALSE;
}


static PyObject *
Deferred_get_pending(MGA::DeferredObject *self, void *data)
{
	if (self->fPending)
		Py_RETURN_TRUE;
	else
		Py_RETURN_FALSE;
}


static PyGetSetDef Deferred_getset[] = {
	{	"aborted",				(getter)Deferred_get_aborted,			NULL,			"Aborted Deferred status", NULL },
	{	"executed",				(getter)Deferred_get_executed,			NULL,			"Executed Deferred status", NULL },
	{	"pending",				(getter)Deferred_get_pending,			NULL,			"Pending Deferred status", NULL },
	{	NULL,					NULL,									NULL,			NULL, NULL }
};


/** Vtable describing the MGA.Deferred type. */
PyTypeObject MGA::DeferredType = {
	PyVarObject_HEAD_INIT(NULL, 0)
    "_kongalib.Deferred",					/* tp_name */
    sizeof(MGA::DeferredObject),			/* tp_basicsize */
	0,										/* tp_itemsize */
	(destructor)Deferred_dealloc,			/* tp_dealloc */
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
	"Deferred objects",						/* tp_doc */
	0,										/* tp_traverse */
	0,										/* tp_clear */
	0,										/* tp_richcompare */
	0,										/* tp_weaklistoffset */
	0,										/* tp_iter */
	0,										/* tp_iternext */
	Deferred_methods,						/* tp_methods */
	0,										/* tp_members */
	Deferred_getset,						/* tp_getset */
};


class TimerJob : public CL_Job
{
public:
	TimerJob(uint32 timeout, MGA::DeferredObject *deferred)
		: CL_Job(), fTimeOut(timeout), fDeferred(deferred)
	{
		MGA::MODULE_STATE *state = GET_STATE();
		if (state) {
			PyList_Append(state->fTimerList, (PyObject *)fDeferred);
		}
	}
	
	~TimerJob() {
	}
	
	virtual CL_Status Run() {
		if (Py_IsInitialized()) {
			PyGILState_STATE gstate;
			gstate = PyGILState_Ensure();
			MGA::MODULE_STATE *state = GET_STATE();
			CL_Status status;

			if (!state)
				return CL_OK;

			Py_INCREF(fDeferred);

			Py_BEGIN_ALLOW_THREADS

			state->fTimerLock.Lock();
			if (fDeferred->fAborted) {
				status = CL_ERROR;
			}
			else {
				status = fDeferred->fCondition.Wait(&state->fTimerLock, fTimeOut);
			}
			state->fTimerLock.Unlock();

			Py_END_ALLOW_THREADS

			for (int i = 0; i < PyList_GET_SIZE(state->fTimerList); i++) {
				MGA::DeferredObject *deferred = (MGA::DeferredObject *)PyList_GET_ITEM(state->fTimerList, i);
				if (deferred == fDeferred) {
					PyList_SetSlice(state->fTimerList, i, i + 1, NULL);
					break;
				}
			}

			if (status == CL_TIMED_OUT) {
				if ((!fDeferred->fAborted) && (fDeferred->fSuccess)) {
					PyObject *result = PyObject_CallFunctionObjArgs(fDeferred->fSuccess, fDeferred->fUserData, NULL);
					Py_XDECREF(result);
					if (PyErr_Occurred()) {
						PyErr_Print();
						PyErr_Clear();
					}
					fDeferred->fExecuted = true;
				}
			}
			Py_DECREF(fDeferred);

			PyGILState_Release(gstate);
		}
		else {
			fDeferred->fPending = false;
			fDeferred->fAborted = true;
		}
		
		return CL_OK;
	}
	
private:
	uint32					fTimeOut;
	MGA::DeferredObject		*fDeferred;
};


static PyObject *
start_timer(PyObject *self, PyObject *args, PyObject *kwds)
{
	MGA::MODULE_STATE *state = GET_STATE();
	char *kwlist[] = { "milliseconds", "callback", "userdata", NULL };
	int32 ms;
	PyObject *callback, *userdata = Py_None;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "iO|O", kwlist, &ms, &callback, &userdata))
		return NULL;
	
	MGA::DeferredObject *deferred = MGA::DeferredObject::Allocate(NULL, userdata, callback, NULL, NULL);
	if (state && state->fInitialized)
		state->fDispatcher->AddJob(CL_New(TimerJob(CL_MAX(0, ms), deferred)), true);
	return (PyObject *)deferred;
}


/**
 *	Converts a dict object to an XML document and saves it inside an unicode string. The XML format is the same
 *	as the one returned via CLU_Table::SaveXML().
 *	\param	self				Unused.
 *	\param	args				Arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e dict: the Python dict object to be converted to XML.
 *	\return						An unicode string holding the XML document derived from \e dict.
 */
static PyObject *
save_xml(PyObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "dict", NULL };
	CLU_Table *table = NULL;
	PyObject *dict, *result;
	CL_XML_Document doc;
	CL_Blob stream;
	string xml;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O!", kwlist, &PyDict_Type, &dict))
		return NULL;
	
	table = MGA::Table_FromPy(dict);
	if (PyErr_Occurred()) {
		CL_Delete(table);
		return NULL;
	}
	Py_BEGIN_ALLOW_THREADS
	doc.SetRoot(table->SaveXML(&doc));
	CL_Delete(table);
	doc.Save(stream);
	stream.Rewind();
	xml << stream;
	Py_END_ALLOW_THREADS
	result = PyUnicode_DecodeUTF8(xml.c_str(), xml.size(), NULL);
	
	return result;
}


/**
 *	Loads the contents of an XML document held in a string into a Python dict object. The XML format understood
 *	must be in the same form as accepted by CLU_Table::LoadXML(). If an error occurs while loading the XML data,
 *	a ValueError exception is raised.
 *	\param	self				Unused.
 *	\param	args				Arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e xml: an unicode string holding the XML document representing the dict.
 *	\return						A dict object representing the data held in the XML document in \e xml.
 */
static PyObject *
load_xml(PyObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "xml", NULL };
	CLU_Table table;
	string xml;
	CL_XML_Document doc;
	CL_XML_Node root;
	bool load;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&", kwlist, MGA::ConvertString, &xml))
		return NULL;
	
	Py_BEGIN_ALLOW_THREADS
	CL_Blob stream;
	stream << xml;
	stream.Rewind();
	load = doc.Load(stream);
	Py_END_ALLOW_THREADS
	if (!load) {
		PyErr_SetString(PyExc_ValueError, doc.GetError().c_str());
		return NULL;
	}
	
	root = doc.GetRoot();
	if ((!root) || (!table.LoadXML(&doc, root))) {
		PyErr_SetString(PyExc_ValueError, "malformed XML dictionary definition");
		return NULL;
	}
	
	return MGA::Table_FromCLU(&table);
}


/**
 *	Performs a forward or reverse DNS lookup, given an \e address on input. If \e address is an host name, a forward DNS
 *	lookup is performed and the function returns the associated IP in dotted numbers format. If \e address is in dotted
 *	numbers format, a reverse DNS lookup is performed and the function returns the associated host name. If lookup fails,
 *	the same input string is returned.
 *	\param	self				Unused.
 *	\param	args				Arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e address: an unicode string holding the IP or host name to be looked up.
 *	\return						An unicode string object holding the looked up address, or unmodified \e address on error.
 */
static PyObject *
host_lookup(PyObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "address", NULL };
	string address;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&", kwlist, MGA::ConvertString, &address))
		return NULL;
	
	Py_BEGIN_ALLOW_THREADS
	address = CL_NetAddress::Lookup(address);
	Py_END_ALLOW_THREADS
	
	return PyUnicode_DecodeUTF8(address.c_str(), address.size(), NULL);
}


static PyObject *
get_network_interfaces(PyObject *self, PyObject *args, PyObject *kwds)
{
	PyObject *result;
	CL_NetInterface IFs[32];
	uint32 i, numIFs;
	
	Py_BEGIN_ALLOW_THREADS
	numIFs = CL_NetInterface::Enumerate(IFs, 32);
	Py_END_ALLOW_THREADS
	result = PyTuple_New(numIFs);
	
	for (i = 0; i < numIFs; i++) {
		PyObject *entry = PyDict_New();
		PyObject *temp;
		CL_NetInterface *IF = &IFs[i];
		CL_NetAddress address;
		uint8 mac[6];
		
		temp = PyUnicode_FromStringAndSize(IF->GetName(), strlen(IF->GetName()));
		PyDict_SetItemString(entry, "name", temp);
		Py_DECREF(temp);
		
		IF->GetMAC(mac);
		temp = PyBytes_FromStringAndSize((const char *)mac, 6);
		PyDict_SetItemString(entry, "mac", temp);
		Py_DECREF(temp);
		
		address = IF->GetAddress();
		temp = PyUnicode_FromStringAndSize(address.GetIP().c_str(), address.GetIP().size());
		PyDict_SetItemString(entry, "address", temp);
		Py_DECREF(temp);
		
		address = IF->GetNetmask();
		temp = PyUnicode_FromStringAndSize(address.GetIP().c_str(), address.GetIP().size());
		PyDict_SetItemString(entry, "netmask", temp);
		Py_DECREF(temp);
		
		address = IF->GetBroadcast();
		temp = PyUnicode_FromStringAndSize(address.GetIP().c_str(), address.GetIP().size());
		PyDict_SetItemString(entry, "broadcast", temp);
		Py_DECREF(temp);
		
		temp = PyInt_FromLong(IF->GetFeatures());
		PyDict_SetItemString(entry, "features", temp);
		Py_DECREF(temp);
		
		PyTuple_SetItem(result, (Py_ssize_t)i, entry);
	}
	return result;
}


static PyObject *
get_machine_uuid(PyObject *self, PyObject *args, PyObject *kwds)
{
	string uuid = (const char *)MGA::GetComputerUUID();
	return PyUnicode_DecodeUTF8(uuid.c_str(), uuid.size(), NULL);
}


static PyObject *
get_system_info(PyObject *self, PyObject *args, PyObject *kwds)
{
	CL_ComputerInfo info;
	CL_GetComputerInfo(&info);
	return PyUnicode_DecodeUTF8(info.fOSSpec.c_str(), info.fOSSpec.size(), NULL);
}


/**
 *	Obtains the hashed version of given plain password.
 *	\param	self				Unused.
 *	\param	args				Arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e password: an unicode string holding the unencrypted plain password.
 *	\return						An unicode string object holding the hashed password.
 */
static PyObject *
hash_password(PyObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "password", NULL };
	string password;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&", kwlist, MGA::ConvertString, &password))
		return NULL;
	
	password = MGA::GetPassword(password);
	return PyUnicode_DecodeUTF8(password.c_str(), password.size(), NULL);
}


static PyObject *
set_interpreter_timeout(PyObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "timeout", NULL };
	PyObject *object = NULL;
	uint32 timeout, oldTimeout;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &object))
		return NULL;
	
	if ((!object) || (object == Py_None)) {
		timeout = 0;
	}
	else {
		timeout = PyInt_AsLong(object);
		if (PyErr_Occurred())
			return NULL;
	}
	MGA::MODULE_STATE *state = GET_STATE();
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		return NULL;
	}
	PyThreadState *current_tstate = PyThreadState_Get();
	for (std::list<MGA::InterpreterObject *>::iterator it = sInterpreterList.begin(); it != sInterpreterList.end(); it++) {
		MGA::InterpreterObject *interpreter = *it;
		if (interpreter->fState) {
			PyThreadState *tstate = PyInterpreterState_ThreadHead(interpreter->fState->interp);
			while (tstate) {
				if (tstate == current_tstate) {
					oldTimeout = interpreter->fTimeOut;
					interpreter->fTimeOut = timeout;
					interpreter->fStartTime = CL_GetTime();
					return PyInt_FromLong(oldTimeout);
				}
				tstate = PyThreadState_Next(tstate);
			}
		}
	}
	PyErr_SetString(PyExc_RuntimeError, "No parent Interpreter object for current context!");
	return NULL;
}


static PyObject *
lock(PyObject *self, PyObject *args)
{
	MGA::MODULE_STATE *state = GET_STATE();

	if (state) {
		Py_BEGIN_ALLOW_THREADS
		state->fThreadsLock.Lock();
		Py_END_ALLOW_THREADS
	}

	Py_RETURN_NONE;
}


static PyObject *
unlock(PyObject *self, PyObject *args)
{
	MGA::MODULE_STATE *state = GET_STATE();

	if (state) {
		Py_BEGIN_ALLOW_THREADS
		state->fThreadsLock.Unlock();
		Py_END_ALLOW_THREADS
	}

	Py_RETURN_NONE;
}


static PyObject *
_cleanup(PyObject *self, PyObject *args)
{
	MGA::MODULE_STATE *state = GET_STATE();

	if ((Py_IsInitialized()) && (state) && (state->fInitialized)) {
		PyThreadState *tstate = PyThreadState_Get();
		if (((unsigned long)tstate->thread_id == sMainThreadID) && (state->fDispatcher)) {
			{
				CL_AutoLocker locker(&state->fThreadsLock);
				state->fInitialized = false;
			}
			
			for (int i = 0; i < PyList_GET_SIZE(state->fTimerList); i++) {
				MGA::DeferredObject *deferred = (MGA::DeferredObject *)PyList_GET_ITEM(state->fTimerList, i);
				deferred->fAborted = true;
				deferred->fCondition.Signal();
			}

			for (std::list<MGA::InterpreterObject *>::iterator it = sInterpreterList.begin(); it != sInterpreterList.end(); it++) {
				MGA::InterpreterObject *interpreter = *it;
				if (tstate != interpreter->fState) {
					interpreter->Stop(state);
					interpreter->Destroy();
				}
			}

			Py_BEGIN_ALLOW_THREADS

			for (std::list<MGA_Client *>::iterator it = state->fClientList.begin(); it != state->fClientList.end(); it++) {
				MGA_Client *client = *it;
				client->Disconnect();
			}

			while (!state->fDispatcher->WaitForJobs(50)) {
				PyGILState_STATE gstate;
				gstate = PyGILState_Ensure();
				
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
			}
			Py_END_ALLOW_THREADS
		}
	}
	
	Py_RETURN_NONE;
}


static CL_Status
_power_callback(int state, void *param)
{
#ifdef WIN32
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();

	MGA::MODULE_STATE *s = GET_STATE();
	if ((state == CL_POWER_SLEEP) && (s)) {
		CL_AutoLocker locker(&s->fThreadsLock);
		for (std::list<MGA_Client *>::iterator it = s->fClientList.begin(); it != s->fClientList.end(); it++) {
			MGA_Client *client = *it;
			client->Disconnect();
		}
	}

	PyGILState_Release(gstate);
#endif
	return CL_OK;
}


static PyObject *
set_default_idle_callback(PyObject *self, PyObject *args, PyObject *kwds)
{
	MGA::MODULE_STATE *state = GET_STATE();
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		return NULL;
	}
	char *kwlist[] = { "callback", NULL };
	PyObject *object;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &object))
		return NULL;
	
	Py_INCREF(object);
	Py_XDECREF(state->fIdleCB);
	state->fIdleCB = object;
	
	Py_RETURN_NONE;
}


static PyObject *
checksum(PyObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "callback", NULL };
	PyObject *object;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &object))
		return NULL;
	
	CL_Blob data;
#if PY3K
	{
#else
	if PyBuffer_Check(object) {
		const void *source;
		Py_ssize_t size;
		if (PyObject_AsReadBuffer(object, &source, &size))
			return 0;
		data.Set(source, (uint32)size);
	}
	else {
#endif
		Py_buffer view;
		if (PyObject_GetBuffer(object, &view, PyBUF_CONTIG_RO))
			return 0;
		data.Set((const char *)view.buf, (uint32)view.len);
		PyBuffer_Release(&view);
	}
	return PyInt_FromLong(data.CheckSum());
}


static PyObject *
get_application_log_path(PyObject *self, PyObject *args, PyObject *kwds)
{
	string name = CL_GetPath(CL_APPLICATION_PATH);
	string path = CL_GetPath(CL_USER_LOG_PATH);
	if (name.size() > 0)
		name = name.substr(0, name.size() - 1);
#ifdef __CL_WIN32__
	name = name.substr(name.rfind('\\') + 1) + "\\Log\\";
#else
	name = name.substr(name.rfind('/') + 1);
#ifdef __CL_DARWIN__
	name = name.substr(0, name.rfind('.'));
#endif
#endif
	path += name;

	return PyUnicode_DecodeUTF8(path.c_str(), path.size(), NULL);
}


static PyObject *
_aes_set_key(PyObject *self, PyObject *args, PyObject *kwds)
{
	MGA::MODULE_STATE *state = GET_STATE();
	char *kwlist[] = { "key", NULL };
	char *keyBuffer;
	Py_ssize_t keyLen;

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s#", kwlist, &keyBuffer, &keyLen))
		return NULL;

	CL_Blob key(keyBuffer, (int32)keyLen);
	key.Rewind();
	if (state)
		state->fCipher.SetKey(key);

	Py_RETURN_NONE;
}


static PyObject *
_aes_encrypt(PyObject *self, PyObject *args, PyObject *kwds)
{
	MGA::MODULE_STATE *state = GET_STATE();
	char *kwlist[] = { "data", NULL };
	char *dataBuffer;
	Py_ssize_t dataLen;

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s#", kwlist, &dataBuffer, &dataLen))
		return NULL;

	CL_Blob data(dataBuffer, dataLen);
	data.Rewind();
	if (state)
		state->fCipher.Encrypt(data, dataLen);

	return PyBytes_FromStringAndSize((const char *)data.GetData(), dataLen);
}


static PyObject *
_aes_decrypt(PyObject *self, PyObject *args, PyObject *kwds)
{
	MGA::MODULE_STATE *state = GET_STATE();
	char *kwlist[] = { "data", NULL };
	char *dataBuffer;
	Py_ssize_t dataLen;

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s#", kwlist, &dataBuffer, &dataLen))
		return NULL;

	CL_Blob data(dataBuffer, dataLen);
	data.Rewind();
	if (state)
		state->fCipher.Decrypt(data, dataLen);

	return PyBytes_FromStringAndSize((const char *)data.GetData(), dataLen);
}


static PyObject *
_apply_stylesheet(PyObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "xml", "xslt", NULL };
	string xml, xslt;
	CL_Blob xmlBlob, xsltBlob, output;

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&O&", kwlist, MGA::ConvertString, &xml, MGA::ConvertString, &xslt))
		return NULL;

	xmlBlob.Set(xml.data(), xml.size());
	xsltBlob.Set(xslt.data(), xslt.size());
	CL_XML_Document xmlDoc(xmlBlob);
	CL_XML_Document xsltDoc(xsltBlob, CL_XML_PARSE_REPLACE_ENTITIES);

	if ((!xmlDoc.IsValid()) || (!xsltDoc.IsValid()) || (!xmlDoc.Transform(xsltDoc, &output)) || (output.GetSize() == 0)) {
		string error = xmlDoc.GetError();
		if (error.empty())
			error = xsltDoc.GetError();
		if (error.empty())
			error = "transformation error";
		PyErr_SetString(PyExc_ValueError, CL_StringFormat("Error applying stylesheet: %s", error.c_str()).c_str());
		return NULL;
	}
	return PyUnicode_FromStringAndSize((const char *)output.GetDataForRead(), (Py_ssize_t)output.GetSize());
}


/** Vtable declaring MGA module methods. */
static PyMethodDef sMGA_Methods[] = {
	{	"host_lookup",					(PyCFunction)host_lookup,				METH_VARARGS | METH_KEYWORDS,	"host_lookup(str) -> str\n\nPerforms a forward or reverse DNS lookup given an IP/host name." },
	{	"get_network_interfaces",		(PyCFunction)get_network_interfaces,	METH_VARARGS | METH_KEYWORDS,	"get_network_interfaces() -> tuple\n\nReturns a list of dicts holding informations on all the available network interfaces." },
	{	"get_machine_uuid",				(PyCFunction)get_machine_uuid,			METH_NOARGS,					"get_machine_uuid() -> str\n\nGets machine unique UUID." },
	{	"get_system_info",				(PyCFunction)get_system_info,			METH_NOARGS,					"get_system_info() -> str\n\nGets informations on the operating system." },
	{	"save_xml",						(PyCFunction)save_xml,					METH_VARARGS | METH_KEYWORDS,	"save_xml(dict) -> str\n\nConverts given dictionary object in XML form and returns it as an (unicode) string." },
	{	"load_xml",						(PyCFunction)load_xml,					METH_VARARGS | METH_KEYWORDS,	"load_xml(str) -> dict\n\nLoads XML from given (unicode) string and returns a corresponding dictionary object." },
	{	"start_timer",					(PyCFunction)start_timer,				METH_VARARGS | METH_KEYWORDS,	"start_timer(seconds, callback, userdata) -> Deferred\n\nStarts a timer, so that callback gets called after specified amount of seconds. Returns a cancellable Deferred object." },
	{	"hash_password",				(PyCFunction)hash_password,				METH_VARARGS | METH_KEYWORDS,	"hash_password(password) -> str\n\nReturns the hashed version of given plain password." },
	{	"set_interpreter_timeout",		(PyCFunction)set_interpreter_timeout,	METH_VARARGS | METH_KEYWORDS,	"set_interpreter_timeout(timeout)\n\nSets timeout for current interpreter." },
	{	"lock",							(PyCFunction)lock,						METH_NOARGS,					"lock()\n\nAcquires the global MGA threads lock." },
	{	"unlock",						(PyCFunction)unlock,					METH_NOARGS,					"unlock()\n\nReleases the global MGA threads lock." },
	{	"_cleanup",						(PyCFunction)_cleanup,					METH_NOARGS,					"_cleanup()\n\nCleanup resources." },
	{	"set_default_idle_callback",	(PyCFunction)set_default_idle_callback,	METH_VARARGS | METH_KEYWORDS,	"set_default_idle_callback(callback)\n\nSets the default callback to be issued during client sync operations." },
	{	"checksum",						(PyCFunction)checksum,					METH_VARARGS | METH_KEYWORDS,	"checksum(buffer) -> int\n\nComputes a fast checksum of a buffer." },
	{	"get_application_log_path",		(PyCFunction)get_application_log_path,	METH_NOARGS,					"get_application_log_path() -> str\n\nReturns the user log path concatenated with the application name." },
	{	"_aes_set_key",					(PyCFunction)_aes_set_key,				METH_VARARGS | METH_KEYWORDS,	"_aes_set_key(key)\n\nSets AES cipher key." },
	{	"_aes_encrypt",					(PyCFunction)_aes_encrypt,				METH_VARARGS | METH_KEYWORDS,	"_aes_encrypt(data) -> data\n\nPerforms AES encryption on a block of data" },
	{	"_aes_decrypt",					(PyCFunction)_aes_decrypt,				METH_VARARGS | METH_KEYWORDS,	"_aes_decrypt(data) -> data\n\nPerforms AES decryption on a block of data." },
	{	"_apply_stylesheet",			(PyCFunction)_apply_stylesheet,			METH_VARARGS | METH_KEYWORDS,	"_apply_stylesheet(xml, xslt) -> str\n\nApplies given xslt transform to xml (both specified as strings) and returns transform result." },
	{	NULL,							NULL,									0,								NULL }
};


static int
module_clear(PyObject *m)
{
	MGA::MODULE_STATE *s = GET_STATE_EX(m);
	if (!s)
		return 1;

	Py_CLEAR(s->fIdleCB);
	Py_CLEAR(s->fException);
	Py_CLEAR(s->fTimerList);
	Py_CLEAR(s->fJSONException);
	Py_CLEAR(s->fMethodRead);
	Py_CLEAR(s->fMethodReadKey);
	Py_CLEAR(s->fMethodStartMap);
	Py_CLEAR(s->fMethodEndMap);
	Py_CLEAR(s->fMethodStartArray);
	Py_CLEAR(s->fMethodEndArray);
	Py_CLEAR(s->fMethodWrite);

	return 0;
}


static void
module_free(PyObject *m)
{
	MGA::MODULE_STATE *s = GET_STATE_EX(m);
	if (!s)
		return;
	{
		CL_AutoLocker locker(&s->fThreadsLock);
		s->fInitialized = false;
	}
	CL_Delete(s->fTranslator);
	s->fTranslator = NULL;
	CL_Dispatcher *dispatcher = s->fDispatcher;
	s->fDispatcher = NULL;
	if (Py_IsInitialized()) {
		Py_BEGIN_ALLOW_THREADS
		CL_Delete(dispatcher);
		Py_END_ALLOW_THREADS

		module_clear(m);
	}
	else {
		CL_Delete(dispatcher);
	}

	CL_RemovePowerCallback(_power_callback);
#if PY3K
	s->~MODULE_STATE();
#endif
}


#if PY3K

static int
module_traverse(PyObject *m, visitproc visit, void *arg)
{
	MGA::MODULE_STATE *s = GET_STATE_EX(m);
	if (!s)
		return 1;

	Py_VISIT(s->fIdleCB);
	Py_VISIT(s->fException);
	Py_VISIT(s->fTimerList);
	Py_VISIT(s->fJSONException);
	Py_VISIT(s->fMethodRead);
	Py_VISIT(s->fMethodReadKey);
	Py_VISIT(s->fMethodStartMap);
	Py_VISIT(s->fMethodEndMap);
	Py_VISIT(s->fMethodStartArray);
	Py_VISIT(s->fMethodEndArray);
	Py_VISIT(s->fMethodWrite);
	
	return 0;
}


static struct PyModuleDef sModuleDef = {
	PyModuleDef_HEAD_INIT,
	"_kongalib",
	"kongalib support module",
	sizeof(MGA::MODULE_STATE),
	sMGA_Methods,
	NULL,
	module_traverse,
	module_clear,
	(freefunc)module_free,
};

#define MOD_ERROR		NULL
#define MOD_SUCCESS(v)	v
#ifdef __CL_UNIX__
#define MOD_INIT(name)	extern "C" EXPORT PyObject *PyInit_##name(void)
#else
#define MOD_INIT(name)	PyMODINIT_FUNC EXPORT PyInit_##name(void)
#endif
#else


/**
 *	Cleanup function to be called on module exit. Closes any connection to the MGA server previously enstablished.
 */
static void
MGA_Cleanup()
{
	module_free(NULL);
}


#define MOD_ERROR
#define MOD_SUCCESS(v)
#define MOD_INIT(name)	PyMODINIT_FUNC EXPORT init##name(void)
#endif


/**
 *	Main module initialization function. Automatically called by Python on module import.
 */
MOD_INIT(_kongalib)
{
	PyObject *module;
	MGA::MODULE_STATE *state;
	
	CL_Init();

	PyEval_InitThreads();

#if PY3K
	MGA::gModuleDefPtr = &sModuleDef;
	module = PyModule_Create(&sModuleDef);
#else
	module = Py_InitModule3("_kongalib", sMGA_Methods, "kongalib support module");
	Py_AtExit(&MGA_Cleanup);
#endif

	state = GET_STATE_EX(module);
#if PY3K
	new (state) MGA::MODULE_STATE();
#endif

	state->fTranslator = CL_New(CL_Translator);
	state->fTranslator->Load(CL_LANG_EN, sDefaultDictionary_CL_MESSAGES);
	state->fTranslator->Load(CL_LANG_EN, sDefaultDictionary_MGA_MESSAGES, false);
	
	Py_BEGIN_ALLOW_THREADS
	state->fDispatcher = CL_New(CL_Dispatcher(8, 128, &onCreateWorker, &onDestroyWorker));
	Py_END_ALLOW_THREADS
	
	state->fParentModule = PyImport_AddModule("kongalib");
	state->fException = PyDict_GetItemString(PyModule_GetDict(state->fParentModule), "Error");
	Py_INCREF(state->fException);
	
	if (PyType_Ready(&MGA::DecimalType) < 0)
		return MOD_ERROR;
	Py_INCREF(&MGA::DecimalType);
	if (PyModule_AddObject(module, "Decimal", (PyObject *)&MGA::DecimalType) < 0)
		return MOD_ERROR;
	
	if (PyType_Ready(&MGA::ClientType) < 0)
		return MOD_ERROR;
	Py_INCREF(&MGA::ClientType);
	if (PyModule_AddObject(module, "Client", (PyObject *)&MGA::ClientType) < 0)
		return MOD_ERROR;
	
	if (PyType_Ready(&MGA::DeferredType) < 0)
		return MOD_ERROR;
	Py_INCREF(&MGA::DeferredType);
	if (PyModule_AddObject(module, "Deferred", (PyObject *)&MGA::DeferredType) < 0)
		return MOD_ERROR;
	
	if (PyType_Ready(&MGA::JSONEncoderType) < 0)
		return MOD_ERROR;
	Py_INCREF(&MGA::JSONEncoderType);
	if (PyModule_AddObject(module, "JSONEncoder", (PyObject *)&MGA::JSONEncoderType) < 0)
		return MOD_ERROR;
	
	if (PyType_Ready(&MGA::JSONDecoderType) < 0)
		return MOD_ERROR;
	Py_INCREF(&MGA::JSONDecoderType);
	if (PyModule_AddObject(module, "JSONDecoder", (PyObject *)&MGA::JSONDecoderType) < 0)
		return MOD_ERROR;
	
	if (PyType_Ready(&MGA::InterpreterType) < 0)
		return MOD_ERROR;
	Py_INCREF(&MGA::InterpreterType);
	if (PyModule_AddObject(module, "Interpreter", (PyObject *)&MGA::InterpreterType) < 0)
		return MOD_ERROR;
	
	MGA::InitJSON();
	MGA::InitInterpreter();
	MGA::InitUtilities();
	
	if ((signed)sMainThreadID == -1)
		sMainThreadID = PyThreadState_Get()->thread_id;
	state->fInitialized = true;
	state->fIdleCB = NULL;
	state->fJSONException = PyDict_GetItemString(PyModule_GetDict(state->fParentModule), "JSONError");
	state->fMethodRead = PyUnicode_FromString("read");
	state->fMethodReadKey = PyUnicode_FromString("read_key");
	state->fMethodStartMap = PyUnicode_FromString("start_map");
	state->fMethodEndMap = PyUnicode_FromString("end_map");
	state->fMethodStartArray = PyUnicode_FromString("start_array");
	state->fMethodEndArray = PyUnicode_FromString("end_array");
	state->fMethodWrite = PyUnicode_FromString("write");

	Py_INCREF(state->fJSONException);	

	state->fTimerList = PyList_New(0);
	
	CL_AddPowerCallback(_power_callback);

	return MOD_SUCCESS(module);
}


/*@}*/
