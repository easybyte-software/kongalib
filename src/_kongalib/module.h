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


#ifndef __MGA_MODULE_H__
#define __MGA_MODULE_H__

#include "Python.h"
#include "marshal.h"

#if PY_MAJOR_VERSION >= 3
#define PY3K		1
#else
#define PY3K		0
#endif

#include "yajl/yajl_parse.h"
#include "yajl/yajl_gen.h"

#if (defined(_WIN32) && (_MSC_VER < 1900))
#define CL_USE_TINYXML
#define TIXML_USE_STL
#endif

#include <ebpr/types.h>
#include <ebpr/system.h>
#include <ebpr/decimal.h>
#include <ebpr/timestamp.h>
#include <ebpr/socket.h>
#include <ebpr/dispatcher.h>
#include <ebpr/cipher.h>

#include <konga_client/client.h>
#include <konga_client/common.h>

#include <ebpr/messages.h>
#include <konga_client/messages.h>


#if (defined(__GNUC__) || defined(__clang__))
	#define EXPORT		__attribute__((__visibility__("default")))
#else
	#define EXPORT
#endif

#define STRING_EXPAND(x)					#x
#define TO_STRING(x)						STRING_EXPAND(x)


namespace MGA
{

struct MODULE_STATE;


/**
 *	\brief Small type managing an MGA client instance
 *
 *	Wraps #MGA_Client and its functionalities to allow accessing a remote MGA server via Python.
 */
typedef struct ClientObject
{
	PyObject_HEAD
	
	ClientObject();
	
	MGA_Client		*fClient;				/**< The #MGA_Client object doing the real work behind the scene. */
} ClientObject;


/**
 *
 */
typedef struct DeferredObject
{
	PyObject_HEAD
	
	DeferredObject(ClientObject *client, PyObject *userData, PyObject *success, PyObject *error, PyObject *progress, PyObject *idle);
	~DeferredObject();
	
	static DeferredObject *Allocate(ClientObject *client, PyObject *userData, PyObject *success = NULL, PyObject *error = NULL, PyObject *progress = NULL, PyObject *idle = NULL);
	
	ClientObject	*fClient;
	PyObject		*fSuccess;
	PyObject		*fError;
	PyObject		*fProgress;
	PyObject		*fIdle;
	PyObject		*fUserData;
	volatile bool	fAborted;
	volatile bool	fExecuted;
	volatile bool	fPending;
	CL_Condition	fCondition;
} DeferredObject;


/**
 *	\brief Type describing the Python MGA.Decimal object
 *
 *	Wraps around the functionalities of a #CL_Decimal object to represent a decimal value in Python.
 */
typedef struct DecimalObject
{
	PyObject_HEAD

	DecimalObject() {}

	static DecimalObject *Allocate();
	
	CL_Decimal		fValue;					/**< The #CL_Decimal object associated to this Python MGA.Decimal object. */
} DecimalObject;


/**
 *
 */
typedef struct JSONEncoderObject
{
	PyObject_HEAD
	
	JSONEncoderObject();
	
	yajl_gen		fHandle;
	string			fEncoding;
	bool			fPretty;
} JSONEncoderObject;


/**
 *
 */
typedef struct JSONDecoderObject
{
	PyObject_HEAD
	
	JSONDecoderObject();
	
	yajl_handle		fHandle;
	string			fEncoding;
	string			fFileName;
} JSONDecoderObject;



/**
 *
 */
typedef struct InterpreterObject
{
	PyObject_HEAD
	
	InterpreterObject();
	~InterpreterObject();

	void Start(MODULE_STATE *state = NULL);
	void Stop(MODULE_STATE *state = NULL);
	void Destroy();
	
	CL_Job				*fJob;
	volatile bool		fRunning;
	volatile bool		fExecute;
	bool				fHasCode;
	string				fFileName;
	string				fScript;
	CL_Mutex			fLock;
	CL_Condition		fCond;
	CL_Condition		fReady;
	volatile uint32		fStartTime;
	uint32				fTimeOut;
	PyThreadState		*fState;
	unsigned long		fStateThreadID;
	CL_Array<string>	fArgv;
	CL_Array<string>	fPath;
	volatile bool		fThreadAlive;
	CL_ThreadID			fThreadID;
} InterpreterObject;



typedef struct MODULE_STATE
{
	PyObject						*fParentModule;
	CL_RecursiveMutex				fThreadsLock;
	CL_Dispatcher					*fDispatcher;
	PyObject						*fIdleCB;
	volatile bool					fInitialized;
	PyObject						*fException;
	CL_Translator					*fTranslator;
	CL_Mutex						fTimerLock;
	PyObject						*fTimerList;
	std::list<MGA_Client *>			fClientList;
	std::list<MGA_Client *>			fFreeClientsList;
	CL_AESCipher					fCipher;
	string							fLanguage;
	PyObject						*fJSONException;
	PyObject						*fMethodRead;
	PyObject						*fMethodReadKey;
	PyObject						*fMethodStartMap;
	PyObject						*fMethodEndMap;
	PyObject						*fMethodStartArray;
	PyObject						*fMethodEndArray;
	PyObject						*fMethodWrite;
} MODULE_STATE;


#if PY3K
extern PyModuleDef					*gModuleDefPtr;
#else
extern MODULE_STATE					gState;
#endif

extern PyTypeObject ClientType;
extern PyTypeObject DeferredType;
extern PyTypeObject DecimalType;
extern PyTypeObject JSONEncoderType;
extern PyTypeObject JSONDecoderType;
extern PyTypeObject InterpreterType;


extern string translate(MGA_Status error);

extern PyObject *setException(MGA_Status error_code, const string& error_msg = "");
extern PyObject *setException(MGA_Status error_code, CLU_Table *output);
extern PyObject *setException(MGA::ClientObject *client, MGA_Status result);

extern bool trackClient(MGA::ClientObject *client);
extern void untrackClient(MGA::ClientObject *client);
extern void trackInterpreter(MGA::InterpreterObject *interpreter, MGA::MODULE_STATE *state);
extern void untrackInterpreter(MGA::InterpreterObject *interpreter, MGA::MODULE_STATE *state);

extern int ConvertString(PyObject *object, string *string);
extern int ConvertDecimal(PyObject *object, DecimalObject **decimal);
extern PyObject *List_FromCLU(CLU_List *list);
extern CLU_List *List_FromPy(PyObject *object);
extern PyObject *Table_FromCLU(CLU_Table *table);
extern CLU_Table *Table_FromPy(PyObject *object);

extern void InitUtilities();
extern void InitJSON();
extern void InitInterpreter();

};


#if PY3K
#define GET_STATE_EX(m)				((MGA::MODULE_STATE *)PyModule_GetState(m))
#define GET_STATE()					(PyState_FindModule(MGA::gModuleDefPtr) ? GET_STATE_EX(PyState_FindModule(MGA::gModuleDefPtr)) : NULL)
#define PyInt_FromLong				PyLong_FromLong
#define PyInt_AsLong				PyLong_AsLong
#define PyInt_AS_LONG				PyLong_AsLong
#else
#define GET_STATE_EX(m)				(&MGA::gState)
#define GET_STATE()					(&MGA::gState)
#define Py_RETURN_NOTIMPLEMENTED	return Py_INCREF(Py_NotImplemented), Py_NotImplemented
#endif


#endif
