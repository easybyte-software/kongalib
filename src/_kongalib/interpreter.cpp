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

#ifdef __CL_WIN32__
#include <io.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#endif

#define DEBUG		0



static int
interpreter_timeout_handler(MGA::InterpreterObject *interpreter, PyObject *frame, int what, PyObject *arg)
{
	int result = 0;
	if (interpreter->fTimeOut > 0) {
		if ((CL_GetTime() - interpreter->fStartTime) > interpreter->fTimeOut) {
			result = -1;
			PyEval_SetTrace(NULL, NULL);
			PyObject *module = PyImport_ImportModule("kongalib.scripting");
			if (module) {
				PyObject *dict = NULL;
				PyObject *func = NULL;
		
				dict = PyModule_GetDict(module);
				func = PyDict_GetItemString(dict, "timeout_handler");
				if (func) {
					PyObject *res = NULL;
					Py_INCREF(func);
					res = PyObject_CallFunctionObjArgs(func, NULL);
					Py_DECREF(func);
					
					if (res) {
						Py_DECREF(res);
						result = 0;
					}
				}
				Py_DECREF(module);
			}
			if (result == 0)
				interpreter->fTimeOut = 0;
			interpreter->fStartTime = CL_GetTime();
			PyEval_SetTrace((Py_tracefunc)interpreter_timeout_handler, (PyObject *)interpreter);
		}
	}
	return result;
}


class InterpreterJob : public CL_Job
{
public:
	InterpreterJob(MGA::InterpreterObject *interpreter)
		: CL_Job(), fInterpreter(interpreter)
	{
	}

	void ForwardException()
	{
		PyObject *err = PyErr_Occurred();
		if (err) {
			PyObject *exc_type, *exc_value, *exc_tb;
			PyErr_Fetch(&exc_type, &exc_value, &exc_tb);
			PyErr_NormalizeException(&exc_type, &exc_value, &exc_tb);

			if (!exc_value) {
				exc_value = Py_None;
				Py_INCREF(exc_value);
			}
			if (!exc_tb) {
				exc_tb = Py_None;
				Py_INCREF(exc_tb);
			}
			PyObject *exc_info = PyTuple_Pack(3, exc_type, exc_value, exc_tb);
			PyThreadState *prev_state = PyThreadState_Swap(fOwnerState);
			PyDict_SetItemString(PyThreadState_GetDict(), "kongalib_interpreter_exception", exc_info);
#if DEBUG
			fprintf(stderr, "InterpreterJob::ForwardException() setting interpreter exception\n");
#endif
			PyThreadState_Swap(prev_state);
			Py_DECREF(exc_info);

			Py_XDECREF(exc_type);
			Py_XDECREF(exc_value);
			Py_XDECREF(exc_tb);
		}
	}
	
	virtual CL_Status Run() {
#if DEBUG
		fprintf(stderr, "InterpreterJob::Run() enter\n");
#endif
		if (Py_IsInitialized()) {
			PyObject *object, *item, *module, *dict, *func, *code, *scriptingModule = NULL;
			uint32 i;
			bool write_pyc = false, load_module = true;
			long PyImport_GetMagicNumber(void);
			long magic;
			CL_TimeStamp mtime;
			PyThreadState *state;
			
			state = PyThreadState_New(fInterpreter->fState->interp);
			PyEval_AcquireThread(state);

			module = PyImport_AddModule("__main__");
			dict = PyModule_GetDict(module);

			item = PyCodec_Encoder("ascii");
			Py_XDECREF(item);

			fInterpreter->fThreadAlive = true;
			fInterpreter->fStateThreadID = state->thread_id;
			
			for (;;) {
#if DEBUG
				fprintf(stderr, "InterpreterJob::Run() starting loop\n");
#endif
				while ((fInterpreter->fRunning) && (!fInterpreter->fExecute)) {
					Py_BEGIN_ALLOW_THREADS
					fInterpreter->fLock.Lock();
					fInterpreter->fReady.Signal();
					fInterpreter->fCond.Wait(&fInterpreter->fLock, 10);
					fInterpreter->fLock.Unlock();
					Py_END_ALLOW_THREADS
				}
				if (!fInterpreter->fRunning) {
#if DEBUG
					fprintf(stderr, "InterpreterJob::Run() exiting loop\n");
#endif
					break;
				}
#if DEBUG
				fprintf(stderr, "InterpreterJob::Run() got execute request\n");
#endif
#if PY3K
				item = PyUnicode_DecodeUTF8(fInterpreter->fFileName.c_str(), fInterpreter->fFileName.size(), "replace");
#else
				item = PyString_FromStringAndSize(fInterpreter->fFileName.c_str(), fInterpreter->fFileName.size());
#endif
				PyDict_SetItemString(dict, "__file__", item);
				Py_DECREF(item);

				object = PyList_New(fInterpreter->fArgv.Count());
				for (i = 0; i < fInterpreter->fArgv.Count(); i++) {
					item = PyUnicode_DecodeUTF8(fInterpreter->fArgv[i].c_str(), fInterpreter->fArgv[i].size(), "replace");
					PyList_SET_ITEM(object, i, item);
				}
				PySys_SetObject("argv", object);
				Py_DECREF(object);
				
				object = PyList_New(fInterpreter->fPath.Count());
				for (i = 0; i < fInterpreter->fPath.Count(); i++) {
					item = PyUnicode_DecodeUTF8(fInterpreter->fPath[i].c_str(), fInterpreter->fPath[i].size(), "replace");
					PyList_SET_ITEM(object, i, item);
				}
				PySys_SetObject("path", object);
				Py_DECREF(object);
				
				do {
					if (load_module) {
#if DEBUG
						fprintf(stderr, "InterpreterJob::Run() loading kongalib.scripting\n");
#endif
						scriptingModule = PyImport_ImportModule("kongalib.scripting");
						load_module = false;
						if (!scriptingModule) {
#if DEBUG
							fprintf(stderr, "InterpreterJob::Run() kongalib.scripting exception!\n");
#endif
							// PyErr_Print();
							ForwardException();
							fInterpreter->fExecute = false;
							fInterpreter->fReady.Signal();
							break;
						}
					}
					if (scriptingModule) {
						func = PyDict_GetItemString(PyModule_GetDict(scriptingModule), "init_interpreter");
						if (func) {
#if DEBUG
							fprintf(stderr, "InterpreterJob::Run() running init_interpreter\n");
#endif
							Py_INCREF(func);
							object = PyObject_CallFunctionObjArgs(func, NULL);
							Py_XDECREF(object);
							Py_DECREF(func);
							if (!object) {
#if DEBUG
								fprintf(stderr, "InterpreterJob::Run() init_interpreter exception!\n");
#endif
								// PyErr_Print();
								ForwardException();
								fInterpreter->fExecute = false;
								fInterpreter->fReady.Signal();
								break;
							}
						}
						else {
#if DEBUG
							fprintf(stderr, "InterpreterJob::Run() init_interpreter not found!\n");
#endif
						}
					}
					
					fInterpreter->fStartTime = CL_GetTime();
				
					if (!fInterpreter->fHasCode) {
						code = NULL;
						uint32 info = CL_StatFile(fInterpreter->fFileName, NULL, NULL, &mtime);
						string pyc_fileName = fInterpreter->fFileName + "c";
						FILE *f = fopen(pyc_fileName.c_str(), "rb");
						if (f) {
							magic = PyMarshal_ReadLongFromFile(f);
							if (magic != PyImport_GetMagicNumber()) {
								fclose(f);
								f = NULL;
							}
							else {
								CL_TimeStamp pyc_mtime = CL_TimeStamp((int)PyMarshal_ReadLongFromFile(f));
								if ((info) && (mtime > pyc_mtime)) {
									fclose(f);
									f = NULL;
								}
								else {
									code = PyMarshal_ReadLastObjectFromFile(f);
									if ((!code) || (!PyCode_Check(code))) {
										Py_XDECREF(code);
										PyErr_SetString(PyExc_RuntimeError, "Bad code object in .pyc file");
									}
								}
							}
							if (f)
								fclose(f);
						}
						
						if (!f) {
							CL_Blob data;
							CL_Status status = CL_ReadFile(fInterpreter->fFileName, &data);
							if (status != CL_OK) {
								PyErr_Format(PyExc_IOError, "Cannot open input file '%s'", fInterpreter->fFileName.c_str());
							}
							else {
								const char *script;
								script << data;
								code = Py_CompileString(script, fInterpreter->fFileName.c_str(), Py_file_input);
								write_pyc = true;
							}
						}
					}
					else {
						code = Py_CompileString(fInterpreter->fScript.c_str(), fInterpreter->fFileName.c_str(), Py_file_input);
					}
					if (code) {
						if (write_pyc) {
#if DEBUG
							fprintf(stderr, "InterpreterJob::Run() writing .pyc\n");
#endif
							string pyc_fileName = fInterpreter->fFileName + "c";
							CL_DeleteFile(pyc_fileName);
#ifdef WIN32
							int fd = _open(pyc_fileName.c_str(), _O_EXCL|_O_CREAT|_O_WRONLY|_O_TRUNC|_O_BINARY, _S_IREAD|_S_IWRITE);
#else
							int fd = open(pyc_fileName.c_str(), O_EXCL|O_CREAT|O_WRONLY|O_TRUNC
#ifdef O_BINARY
								|O_BINARY
#endif
								, S_IROTH|S_IRGRP|S_IRUSR|S_IWUSR);
#endif
							if (fd >= 0) {
								FILE *f = fdopen(fd, "wb");
								if (f) {
									PyMarshal_WriteLongToFile(PyImport_GetMagicNumber(), f, Py_MARSHAL_VERSION);
									PyMarshal_WriteLongToFile((int)mtime, f, Py_MARSHAL_VERSION);
									PyMarshal_WriteObjectToFile(code, f, Py_MARSHAL_VERSION);
									if (fflush(f) || ferror(f)) {
										fclose(f);
										CL_DeleteFile(pyc_fileName);
									}
									else {
										fclose(f);
									}
								}
							}
						}
#if DEBUG
						fprintf(stderr, "InterpreterJob::Run() executing code\n");
#endif
						PyEval_SetTrace((Py_tracefunc)interpreter_timeout_handler, (PyObject *)fInterpreter);
#if PY3K
						object = PyEval_EvalCode(code, dict, dict);
#else
						object = PyEval_EvalCode((PyCodeObject *)code, dict, dict);
#endif
						PyEval_SetTrace(NULL, NULL);
						Py_DECREF(code);
					}
					else {
#if DEBUG
						fprintf(stderr, "InterpreterJob::Run() no code to execute!\n");
#endif
						object = NULL;
					}
					
					if (!object) {
						if (!PyErr_ExceptionMatches(PyExc_SystemExit)) {
							ForwardException();
							// PyErr_Print();
						}
						PyErr_Clear();
					}
					else
						Py_DECREF(object);
					
					if (scriptingModule) {
#if DEBUG
						fprintf(stderr, "InterpreterJob::Run() running exit_interpreter\n");
#endif
						func = PyDict_GetItemString(PyModule_GetDict(scriptingModule), "exit_interpreter");
						if (func) {
							Py_INCREF(func);
							object = PyObject_CallFunctionObjArgs(func, NULL);
							if (object)
								Py_DECREF(object);
							else
								PyErr_Clear();
							Py_DECREF(func);
						}
					}
				} while (0);
				fInterpreter->fExecute = false;
			}
			Py_XDECREF(scriptingModule);
			
			module = PyImport_ImportModule("threading");
			
			if (!module)
				PyErr_Clear();
			
			if (module) {
				dict = PyModule_GetDict(module);
#if PY3K
				func = PyDict_GetItemString(dict, "current_thread");
#else
				func = PyDict_GetItemString(dict, "currentThread");
#endif
				if (func) {
					PyObject *res = NULL;
					Py_INCREF(func);
					res = PyEval_CallObject(func, (PyObject *)NULL);
					if (!res) {
						PyErr_Clear();
					}
					Py_XDECREF(res);
					Py_DECREF(func);
				}
				
				func = PyDict_GetItemString(dict, "_shutdown");
				if (func) {
					PyObject *res = NULL;
					Py_INCREF(func);
					res = PyEval_CallObject(func, (PyObject *)NULL);
					if (!res) {
						PyErr_Clear();
					}
					Py_XDECREF(res);
					Py_DECREF(func);
				}
				
				Py_DECREF(module);
			}
			
#if PY3K
			func = NULL;
			module = PyImport_ImportModule("atexit");
			if (module) {
				dict = PyModule_GetDict(module);
				func = PyDict_GetItemString(dict, "_run_exitfuncs");
			}
			else
				PyErr_Clear();
#else
			module = NULL;
			func = PySys_GetObject("exitfunc");
#endif
			if (func) {
				PyObject *res = NULL;
				Py_INCREF(func);
#if PY3K
				res = PyEval_CallObject(func, (PyObject *)NULL);
				if (res) {
					Py_DECREF(res);
					func = PyDict_GetItemString(dict, "_clear");
					Py_INCREF(func);
					res = PyEval_CallObject(func, (PyObject *)NULL);
				}
#else
				PySys_SetObject("exitfunc", (PyObject *)NULL);
				res = PyEval_CallObject(func, (PyObject *)NULL);
#endif
				if (res) {
					Py_DECREF(res);
				}
				else {
					if (!PyErr_ExceptionMatches(PyExc_SystemExit))
						PyErr_Print();
	                PyErr_Clear();
	        	}
				Py_DECREF(func);
			}
			Py_XDECREF(module);
			
			fInterpreter->fStateThreadID = 0;

			PyThreadState_Clear(state);
			PyThreadState_Swap(NULL);
			PyThreadState_Delete(state);
			PyThreadState_Swap(state);
			PyEval_ReleaseThread(state);
		}
#if DEBUG
		fprintf(stderr, "InterpreterJob::Run() exit\n");
#endif
		fInterpreter->fThreadAlive = false;
		return CL_OK;
	}

	void ResetOwner()
	{
		fOwnerState = PyThreadState_Get();
		PyDict_SetItemString(PyThreadState_GetDict(), "kongalib_interpreter_exception", Py_None);
	}
	
private:
	MGA::InterpreterObject		*fInterpreter;
	PyThreadState				*fOwnerState;
};


static int32
_interpreter_runner(CL_Job *job)
{
	job->Run();
	return 0;
}


static MGA::InterpreterObject *
interpreter_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	return new (type->tp_alloc(type, 0)) MGA::InterpreterObject();
}


static void
interpreter_dealloc(MGA::InterpreterObject *self)
{
	self->~InterpreterObject();
	Py_TYPE(self)->tp_free((PyObject*)self);
}


static PyObject *
interpreter_execute(MGA::InterpreterObject *self, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "script", "filename", "argv", "path", "timeout", NULL };
	PyObject *script = NULL, *argv = NULL, *path = NULL;
	
	if (!self->fRunning) {
		PyErr_SetString(PyExc_RuntimeError, "Cannot execute on a stopped interpreter");
		return NULL;
	}

	self->fScript = "";
	self->fHasCode = false;
	self->fFileName = "<script>";
	self->fTimeOut = 0;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OO&OOi", kwlist, &script, MGA::ConvertString, &self->fFileName, &argv, &path, &self->fTimeOut)) {
		return NULL;
	}
	if ((script) && (script != Py_None)) {
		if (!MGA::ConvertString(script, &self->fScript))
			return NULL;
		self->fHasCode = true;
	}
	
	self->fArgv.Clear();
	if (argv) {
		PyObject *seq = PySequence_Fast(argv, "Expected sequence object");
		if (!seq) {
			return NULL;
		}
		for (Py_ssize_t i = 0; i < PySequence_Fast_GET_SIZE(seq); i++) {
			string v;
			if (!MGA::ConvertString(PySequence_Fast_GET_ITEM(seq, i), &v)) {
				Py_DECREF(seq);
				return NULL;
			}
			self->fArgv.Append(v);
		}
		Py_DECREF(seq);
	}
	if (self->fArgv.Count() == 0)
		self->fArgv.Append(self->fFileName);
	
	self->fPath.Clear();
	if (path) {
		PyObject *seq = PySequence_Fast(path, "Expected sequence object");
		if (!seq)
			return NULL;
		for (Py_ssize_t i = 0; i < PySequence_Fast_GET_SIZE(seq); i++) {
			string v;
			if (!MGA::ConvertString(PySequence_Fast_GET_ITEM(seq, i), &v)) {
				Py_DECREF(seq);
				return NULL;
			}
			self->fPath.Append(v);
		}
		Py_DECREF(seq);
	}
	
#if DEBUG
	fprintf(stderr, "execute() enter\n");
#endif
	((InterpreterJob *)self->fJob)->ResetOwner();
	self->fExecute = true;
	Py_BEGIN_ALLOW_THREADS
	self->fLock.Lock();
	self->fCond.Signal();
#if DEBUG
	fprintf(stderr, "execute() signaled job, now waiting\n");
#endif
	while (self->fExecute) {
		self->fReady.Wait(&self->fLock, 50);
	}
	self->fLock.Unlock();
	Py_END_ALLOW_THREADS

#if DEBUG
	fprintf(stderr, "execute() exit (error: %p)\n", PyErr_Occurred());
#endif

	PyObject *exc = PyDict_GetItemString(PyThreadState_GetDict(), "kongalib_interpreter_exception");
	if (exc != Py_None) {
		PyObject *exc_value = PyTuple_GetItem(exc, 1);
		if (exc_value != Py_None) {
			PyErr_SetObject((PyObject *)Py_TYPE(exc_value), exc_value);
		}
		else {
			exc_value = PyTuple_GetItem(exc, 0);
			if (exc_value != Py_None)
				PyErr_SetObject(exc_value, Py_None);
			else
				PyErr_BadInternalCall();
		}

		return NULL;
	}
	
	Py_RETURN_NONE;
}


static PyObject *
interpreter_stop(MGA::InterpreterObject *self, PyObject *args, PyObject *kwds)
{
	if (self->fState) {
		PyThreadState *state = PyThreadState_Swap(self->fState);
		if (self->fStateThreadID)
			PyThreadState_SetAsyncExc(self->fStateThreadID, PyExc_SystemExit);
		PyThreadState_Swap(state);
	}
	MGA::MODULE_STATE *state = GET_STATE();
	if (state) {
		self->Stop(state);
	}
	
	Py_RETURN_NONE;
}


static PyObject *
interpreter_is_running(MGA::InterpreterObject *self, PyObject *args, PyObject *kwds)
{
	PyObject *result = (self->fStateThreadID ? Py_True : Py_False);
	Py_INCREF(result);
	return result;
}


static PyObject *
interpreter_set_timeout(MGA::InterpreterObject *self, PyObject *args, PyObject *kwds, uint32 action)
{
	char *kwlist[] = { "timeout", NULL };
	PyObject *timeout = NULL;
	
	uint32 oldTimeout = self->fTimeOut;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &timeout)) {
		return NULL;
	}
	if ((!timeout) || (timeout == Py_None)) {
		self->fTimeOut = 0;
	}
	else {
		long t = PyInt_AsLong(timeout);
		if (PyErr_Occurred()) {
			return NULL;
		}
		self->fTimeOut = t;
	}
	self->fStartTime = CL_GetTime();
	if (oldTimeout == 0)
		Py_RETURN_NONE;
	else
		return PyInt_FromLong(oldTimeout);
}


static PyObject *
interpreter_get_time_left(MGA::InterpreterObject *self, PyObject *args, PyObject *kwds)
{
	uint32 time = CL_GetTime();
	uint32 result;
	
	if ((time - self->fStartTime) > self->fTimeOut)
		result = 0;
	else
		result = self->fTimeOut - (time - self->fStartTime);
	return PyInt_FromLong(result);
}


static PyObject *
interpreter_get_exc_info(MGA::InterpreterObject *self, PyObject *args, PyObject *kwds)
{
	PyObject *exc = PyDict_GetItemString(PyThreadState_GetDict(), "kongalib_interpreter_exception");
	Py_INCREF(exc);
	return exc;
}


static PyMethodDef interpreter_methods[] = {
	{	"execute",				(PyCFunction)interpreter_execute,		METH_VARARGS | METH_KEYWORDS,	"execute(script, filename, argv, path, timeout)\n\nExecutes a script in the interpreter" },
	{	"stop",					(PyCFunction)interpreter_stop,			METH_VARARGS | METH_KEYWORDS,	"stop()\n\nStops any execution of this interpreter" },
	{	"is_running",			(PyCFunction)interpreter_is_running,	METH_NOARGS,					"is_running() -> bool\n\nReturns True if interpreter is currently running, False otherwise" },
	{	"set_timeout",			(PyCFunction)interpreter_set_timeout,	METH_VARARGS | METH_KEYWORDS,	"set_timeout(timeout)\n\nSets timeout for this interpreter" },
	{	"get_time_left",		(PyCFunction)interpreter_get_time_left,	METH_NOARGS,					"get_time_left() -> int\n\nReturns remaining time before interpreter timeout" },
	{	"get_exc_info",			(PyCFunction)interpreter_get_exc_info,	METH_NOARGS,					"get_exc_info() -> (value,type,tb)\n\nReturns current exception info" },
	{	NULL }
};



PyTypeObject MGA::InterpreterType = {
	PyVarObject_HEAD_INIT(NULL, 0)
    "_kongalib.Interpreter",				/* tp_name */
    sizeof(MGA::InterpreterObject),			/* tp_basicsize */
	0,										/* tp_itemsize */
	(destructor)interpreter_dealloc,		/* tp_dealloc */
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
	Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,	/* tp_flags */
	"Interpreter objects",					/* tp_doc */
	0,										/* tp_traverse */
	0,										/* tp_clear */
	0,										/* tp_richcompare */
	0,										/* tp_weaklistoffset */
	0,										/* tp_iter */
	0,										/* tp_iternext */
	interpreter_methods,					/* tp_methods */
	0,										/* tp_members */
	0,										/* tp_getset */
	0,										/* tp_base */
	0,										/* tp_dict */
	0,										/* tp_descr_get */
	0,										/* tp_descr_set */
	0,										/* tp_dictoffset */
	0,										/* tp_init */
	0,										/* tp_alloc */
	(newfunc)interpreter_new,				/* tp_new */
};


namespace MGA {
	
	InterpreterObject::InterpreterObject()
		: fRunning(true), fExecute(false), fState(NULL), fStateThreadID(0), fThreadAlive(false)
	{
		MODULE_STATE *state = GET_STATE();

		PyThreadState *old_state = PyThreadState_Get();
		fState = Py_NewInterpreter();
		PyThreadState_Swap(old_state);

		fJob = CL_New(InterpreterJob(this));

		fThreadID = CL_Thread::Spawn("sub_interpreter", CL_THREAD_PRIORITY_NORMAL, (CL_Thread::Proc)&_interpreter_runner, (void *)fJob);
		if (state)
			trackInterpreter(this, state);

		while (!fThreadAlive) {
			Py_BEGIN_ALLOW_THREADS
			CL_Thread::Sleep(50);
			Py_END_ALLOW_THREADS
		}
		// fprintf(stderr, "*** InterpreterObject\n");
	}
	
	InterpreterObject::~InterpreterObject()
	{
		MODULE_STATE *state = GET_STATE();
		if (state) {
			Stop(state);
		}
		CL_Delete(fJob);
		if (state) {
			untrackInterpreter(this, state);
		}
		// fprintf(stderr, "*** ~InterpreterObject\n");
		Destroy();
	}

	void
	InterpreterObject::Destroy()
	{
		PyThreadState *state = fState;
		if (state) {
			fState = NULL;
			PyThreadState *old_state = PyThreadState_Get();
			PyThreadState_Swap(state);
			Py_EndInterpreter(state);
			PyThreadState_Swap(old_state);
		}
	}

	void
	InterpreterObject::Stop(MODULE_STATE *state)
	{
		if (!fState)
			return;
		if (!state)
			state = GET_STATE();
		fRunning = false;
		if (!state)
			return;

		// fprintf(stderr, "*** Stop() %d\n", Py_REFCNT((PyObject *)this));

		while (fThreadAlive) {
			fCond.Signal();
			Py_BEGIN_ALLOW_THREADS

			CL_Thread::Sleep(50);

			Py_END_ALLOW_THREADS

			if ((state->fIdleCB) && (state->fIdleCB != Py_None)) {
				PyObject *result = PyObject_CallFunctionObjArgs(state->fIdleCB, NULL);
				if (!result) {
					PyErr_Print();
					PyErr_Clear();
				}
				else
					Py_DECREF(result);
			}
		}
		CL_Thread::Wait(fThreadID);
	}
	
	void
	InitInterpreter()
	{
	}
};


