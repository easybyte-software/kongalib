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

#include <yajl/yajl_parse.h>
#include <yajl/yajl_gen.h>

#include <ebpr/types.h>
#include <ebpr/system.h>
#include <ebpr/decimal.h>
#include <ebpr/timestamp.h>
#include <ebpr/socket.h>
#include <ebpr/dispatcher.h>
#include <ebpr/cipher.h>
#include <ebpr/regex.h>
#include <ebpr/thread.h>

#include <konga_client/client.h>
#include <konga_client/common.h>

#include <ebpr/errors.h>
#include <konga_client/errors.h>


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
	size_t			fPosition;
} JSONDecoderObject;


typedef struct NamedSemaphoreObject
{
	PyObject_HEAD

	NamedSemaphoreObject(const string& name)
		: fSem(name)
	{}

	CL_NamedSemaphore		fSem;
} NamedSemaphoreObject;


typedef struct MODULE_STATE
{
	PyObject						*fParentModule;
	CL_RecursiveMutex				fThreadsLock;
	CL_Dispatcher					*fDispatcher;
	PyObject						*fIdleCB;
	PyObject						*fSuspendCB;
	PyObject						*fResumeCB;
	volatile bool					fInitialized;
	PyObject						*fException;
	CL_Mutex						fTimerLock;
	PyObject						*fTimerList;
	std::list<MGA_Client *>			fClientList;
	std::list<MGA_Client *>			fFreeClientsList;
	string							fLanguage;
	uint32							fTimeOut;
	uint32							fStartTime;
	PyObject						*fJSONException;
	PyObject						*fMethodRead;
	PyObject						*fMethodReadKey;
	PyObject						*fMethodStartMap;
	PyObject						*fMethodEndMap;
	PyObject						*fMethodStartArray;
	PyObject						*fMethodEndArray;
	PyObject						*fMethodWrite;
} MODULE_STATE;


extern PyModuleDef					*gModuleDefPtr;

extern PyTypeObject ClientType;
extern PyTypeObject DeferredType;
extern PyTypeObject DecimalType;
extern PyTypeObject JSONEncoderType;
extern PyTypeObject JSONDecoderType;
extern PyTypeObject NamedSemaphoreType;


extern string translate(MGA_Status error);

extern PyObject *setException(MGA_Status error_code, const string& error_msg = "");
extern PyObject *setException(MGA_Status error_code, CLU_Table *output);
extern PyObject *setException(MGA::ClientObject *client, MGA_Status result);

extern bool trackClient(MGA::ClientObject *client);
extern void untrackClient(MGA::ClientObject *client);

extern int ConvertString(PyObject *object, string *string);
extern int ConvertDecimal(PyObject *object, DecimalObject **decimal);
extern PyObject *List_FromCLU(CLU_List *list);
extern void List_FromPy(PyObject *object, CLU_List *list);
extern PyObject *Table_FromCLU(CLU_Table *table);
extern void Table_FromPy(PyObject *object, CLU_Table *table);

extern void InitUtilities();
extern void InitJSON();

};


#define GET_STATE_EX(m)				((MGA::MODULE_STATE *)PyModule_GetState(m))
#define GET_STATE()					(PyState_FindModule(MGA::gModuleDefPtr) ? GET_STATE_EX(PyState_FindModule(MGA::gModuleDefPtr)) : NULL)
#define PyInt_FromLong				PyLong_FromLong
#define PyInt_AsLong				PyLong_AsLong
#define PyInt_AS_LONG				PyLong_AsLong


#endif
