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

#include "datetime.h"

#include <locale.h>


#ifdef __CL_WIN32__

class CLocaleEnforcer
{
public:
	CLocaleEnforcer()
		: fPrevThreadLocale(-1)
	{
		char *prevLocale = setlocale(LC_ALL, NULL);
		if (strcmp(prevLocale, "C")) {
			fPrevLocale = prevLocale;
			fPrevThreadLocale = _configthreadlocale(_ENABLE_PER_THREAD_LOCALE);
			setlocale(LC_ALL, "C");
		}
	}

	~CLocaleEnforcer()
	{
		if (fPrevThreadLocale != -1) {
			setlocale(LC_ALL, fPrevLocale.c_str());
			_configthreadlocale(fPrevThreadLocale);
		}
	}

private:
	string		fPrevLocale;
	int			fPrevThreadLocale;
};

#else

class CLocaleEnforcer
{
public:
	CLocaleEnforcer()
		: fPrevLocale(NULL)
	{
		char *prevLocale = setlocale(LC_ALL, NULL);
		if (strcmp(prevLocale, "C")) {
			fPrevLocale = uselocale(c_locale());
		}
	}

	~CLocaleEnforcer()
	{
		if (fPrevLocale) {
			uselocale(fPrevLocale);
		}
	}

	static locale_t c_locale()
	{
		static locale_t locale = NULL;
		if (!locale) {
			locale = newlocale(LC_ALL_MASK, "C", NULL);
		}
		return locale;
	}

private:
	locale_t	fPrevLocale;
};

#endif



static PyObject *
setException(const string& msg)
{
	MGA::MODULE_STATE *state = GET_STATE();
	PyObject *args = Py_BuildValue("s", (const char *)msg.c_str());
	if (state)
		PyErr_SetObject(state->fJSONException, args);
	else
		PyErr_SetObject(PyExc_RuntimeError, args);
	Py_DECREF(args);
	return NULL;
}


static bool
checkGen(yajl_gen_status status)
{
	char *msg;
	
	switch (status) {
	case yajl_gen_status_ok:
		return true;
	case yajl_gen_keys_must_be_strings:
		msg = "Expected string object as mapping key";
		break;
	case yajl_max_depth_exceeded:
		msg = "Maximum generation depth exceeded";
		break;
	case yajl_gen_in_error_state:
		msg = "Cannot write while in error state";
		break;
	case yajl_gen_generation_complete:
		msg = "A complete JSON document has been generated";
		break;
	default:
		msg = "Internal error";
		break;
	}
	setException(msg);
	return false;
}


static bool
encode_object(MGA::JSONEncoderObject *self, PyObject *object)
{
	MGA::MODULE_STATE *state = GET_STATE();
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		return false;
	}
	
	if (object == Py_None) {
		if (!checkGen(yajl_gen_null(self->fHandle)))
			return false;
	}
	else if (PyBool_Check(object)) {
		if (!checkGen(yajl_gen_bool(self->fHandle, PyObject_IsTrue(object) ? 1 : 0)))
			return false;
	}
#if !(PY3K)
	else if (PyInt_Check(object)) {
		if (!checkGen(yajl_gen_integer(self->fHandle, (long long)PyInt_AS_LONG(object))))
			return false;
	}
#endif
	else if (PyLong_Check(object)) {
		if (!checkGen(yajl_gen_integer(self->fHandle, PyLong_AsLongLong(object))))
			return false;
	}
	else if (PyFloat_Check(object)) {
		CLocaleEnforcer _;
		if (!checkGen(yajl_gen_double(self->fHandle, PyFloat_AS_DOUBLE(object))))
			return false;
	}
	else if (PyObject_TypeCheck(object, &MGA::DecimalType)) {
		string number = ((MGA::DecimalObject *)object)->fValue.ToString();
		if (!checkGen(yajl_gen_number(self->fHandle, number.c_str(), number.size())))
			return false;
	}
	else if (PyDateTime_Check(object)) {
		string datetime = CL_TimeStamp(PyDateTime_GET_DAY(object), PyDateTime_GET_MONTH(object), PyDateTime_GET_YEAR(object),
									   PyDateTime_DATE_GET_HOUR(object), PyDateTime_DATE_GET_MINUTE(object), PyDateTime_DATE_GET_SECOND(object)).ToString();
		if (!checkGen(yajl_gen_string(self->fHandle, (const unsigned char *)datetime.c_str(), datetime.size())))
			return false;
	}
	else if (PyDate_Check(object)) {
		string date = CL_Date(PyDateTime_GET_DAY(object), PyDateTime_GET_MONTH(object), PyDateTime_GET_YEAR(object)).ToString();
		if (!checkGen(yajl_gen_string(self->fHandle, (const unsigned char *)date.c_str(), date.size())))
			return false;
	}
	else if (PyTime_Check(object)) {
		string time = CL_Time(PyDateTime_TIME_GET_HOUR(object), PyDateTime_TIME_GET_MINUTE(object), PyDateTime_TIME_GET_SECOND(object)).ToString();
		if (!checkGen(yajl_gen_string(self->fHandle, (const unsigned char *)time.c_str(), time.size())))
			return false;
	}
	else if (PyBytes_Check(object)) {
		object = PyCodec_Decode(object, "utf-8", NULL);
		if (!object)
			return false;
		PyObject *text = PyCodec_Encode(object, self->fEncoding.c_str(), NULL);
		Py_DECREF(object);
		if (!text)
			return false;
		bool result = checkGen(yajl_gen_string(self->fHandle, (const unsigned char *)PyBytes_AS_STRING(text), PyBytes_GET_SIZE(text)));
		Py_DECREF(text);
		if (!result)
			return false;
	}
	else if (PyUnicode_Check(object)) {
		PyObject *text = PyCodec_Encode(object, self->fEncoding.c_str(), NULL);
		if (!text)
			return false;
		bool result = checkGen(yajl_gen_string(self->fHandle, (const unsigned char *)PyBytes_AS_STRING(text), PyBytes_GET_SIZE(text)));
		Py_DECREF(text);
		if (!result)
			return false;
	}
	else if (PyDict_Check(object)) {
		PyObject *key, *value;
		Py_ssize_t pos = 0;
		
		if (!checkGen(yajl_gen_map_open(self->fHandle)))
			return false;
		while (PyDict_Next(object, &pos, &key, &value)) {
			if ((!encode_object(self, key)) || (!PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodWrite, value, NULL)))
				return false;
		}
		if (!checkGen(yajl_gen_map_close(self->fHandle)))
			return false;
	}
	else if (PySequence_Check(object)) {
		PyObject *seq = PySequence_Fast(object, "Expecting tuple or list");
		if (!seq)
			return false;
		if (!checkGen(yajl_gen_array_open(self->fHandle))) {
			Py_DECREF(seq);
			return false;
		}
		Py_ssize_t i, size = PySequence_Fast_GET_SIZE(seq);
		for (i = 0; i < size; i++) {
			if (!PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodWrite, PySequence_Fast_GET_ITEM(seq, i), NULL)) {
				Py_DECREF(seq);
				return false;
			}
		}
		if (!checkGen(yajl_gen_array_close(self->fHandle))) {
			Py_DECREF(seq);
			return false;
		}
		Py_DECREF(seq);
	}
	else {
		PyErr_Format(PyExc_ValueError, "Unexpected type %s, expecting bool, int, long, float, Decimal, date, datetime or str/unicode object", Py_TYPE(object)->tp_name);
		return false;
	}
	return true;
}


static PyObject *
enc_write(MGA::JSONEncoderObject *self, PyObject *args, PyObject *kwds)
{
	PyObject *object;
	
	if (!PyArg_ParseTuple(args, "O:write", &object))
		return NULL;
	
	if (!encode_object(self, object))
		return NULL;
	Py_RETURN_NONE;
}


static PyObject *
enc_start_map(MGA::JSONEncoderObject *self, PyObject *args, PyObject *kwds)
{
	if (!checkGen(yajl_gen_map_open(self->fHandle)))
		return NULL;
	Py_RETURN_NONE;
}


static PyObject *
enc_end_map(MGA::JSONEncoderObject *self, PyObject *args, PyObject *kwds)
{
	if (!checkGen(yajl_gen_map_close(self->fHandle)))
		return NULL;
	Py_RETURN_NONE;
}


static PyObject *
enc_start_array(MGA::JSONEncoderObject *self, PyObject *args, PyObject *kwds)
{
	if (!checkGen(yajl_gen_array_open(self->fHandle)))
		return NULL;
	Py_RETURN_NONE;
}


static PyObject *
enc_end_array(MGA::JSONEncoderObject *self, PyObject *args, PyObject *kwds)
{
	if (!checkGen(yajl_gen_array_close(self->fHandle)))
		return NULL;
	Py_RETURN_NONE;
}


static PyObject *
enc_generate(MGA::JSONEncoderObject *self, PyObject *args, PyObject *kwds)
{
	const unsigned char *source;
	size_t source_size;
	
	if (!checkGen(yajl_gen_get_buf(self->fHandle, &source, &source_size)))
		return NULL;
	
	PyObject *buffer = PyBytes_FromStringAndSize((const char *)source, (Py_ssize_t)source_size);
	if (buffer)
		yajl_gen_clear(self->fHandle);
	return buffer;
}


static PyObject *
enc_reset(MGA::JSONEncoderObject *self, PyObject *args, PyObject *kwds)
{
	yajl_gen_free(self->fHandle);
	self->fHandle = yajl_gen_alloc(NULL);
	if (self->fPretty) {
		yajl_gen_config(self->fHandle, yajl_gen_beautify, 1);
		yajl_gen_config(self->fHandle, yajl_gen_indent_string, "\t");
	}
	else {
		yajl_gen_config(self->fHandle, yajl_gen_beautify, 0);
		yajl_gen_config(self->fHandle, yajl_gen_indent_string, "");
	}
	Py_RETURN_NONE;
}


static MGA::JSONEncoderObject *
enc_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	return new (type->tp_alloc(type, 0)) MGA::JSONEncoderObject();
}


static void
enc_dealloc(MGA::JSONEncoderObject *self)
{
	yajl_gen_free(self->fHandle);
	
	self->~JSONEncoderObject();
	Py_TYPE(self)->tp_free((PyObject*)self);
}


static int
enc_init(MGA::JSONEncoderObject *self, PyObject *args, PyObject *kwds)
{
	string encoding;
	PyObject *pretty = Py_True;
	
	if (!PyArg_ParseTuple(args, "|O&O", MGA::ConvertString, &encoding, &pretty))
		return -1;
	
	if (!encoding.empty())
		self->fEncoding = encoding;

	self->fPretty = PyObject_IsTrue(pretty) ? true : false;
	if (self->fPretty) {
		yajl_gen_config(self->fHandle, yajl_gen_beautify, 1);
		yajl_gen_config(self->fHandle, yajl_gen_indent_string, "\t");
	}
	else {
		yajl_gen_config(self->fHandle, yajl_gen_beautify, 0);
		yajl_gen_config(self->fHandle, yajl_gen_indent_string, "");
	}
	return 0;
}


static int
parse_null(void *ctx)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	PyObject *result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodRead, Py_None, NULL);
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static int
parse_boolean(void *ctx, int boolean)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	PyObject *result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodRead, boolean ? Py_True : Py_False, NULL);
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static int
parse_number(void *ctx, const char *number, size_t size)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	PyObject *result, *object;
	CL_Decimal decimal(string(number, size));
	
	if ((decimal == decimal.Floor()) && (decimal >= -2147483647L - 1) && (decimal <= 2147483647L)) {
		object = PyLong_FromLong((long)decimal);
	}
	else {
		object = (PyObject *)MGA::DecimalObject::Allocate();
		((MGA::DecimalObject *)object)->fValue = decimal;
	}
	result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodRead, object, NULL);
	Py_DECREF(object);
	
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static int
parse_string(void *ctx, const unsigned char *text, size_t size)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	CL_TimeStamp datetime;
	CL_Date date;
	CL_Time time;
	string s((const char *)text, size);
	PyObject *object = NULL, *result = NULL;
	
	if (datetime.FromString(s).IsValid()) {
		object = PyDateTime_FromDateAndTime(datetime.GetYear(), datetime.GetMonth(), datetime.GetDay(), datetime.GetHour(), datetime.GetMin(), datetime.GetSec(), 0);
	}
	else if (date.FromString(s).IsValid()) {
		object = PyDate_FromDate(date.GetYear(), date.GetMonth(), date.GetDay());
	}
	else if (time.FromString(s).IsValid()) {
		object = PyTime_FromTime(time.GetHour(), time.GetMin(), time.GetSec(), 0);
	}
	else {
		PyObject *temp = PyBytes_FromStringAndSize((const char *)text, (Py_ssize_t)size);
		if (temp) {
			object = PyCodec_Decode(temp, self->fEncoding.c_str(), NULL);
			Py_DECREF(temp);
		}
	}
	if (object) {
		result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodRead, object, NULL);
		Py_DECREF(object);
	}
	
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static int
parse_map_key(void *ctx, const unsigned char *key, size_t size)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	PyObject *result = NULL;
	PyObject *object = PyUnicode_DecodeUTF8((const char *)key, (Py_ssize_t)size, NULL);
	if (object) {
		result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodReadKey, object, NULL);
		Py_DECREF(object);
	}
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static int
parse_start_map(void *ctx)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	PyObject *result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodStartMap, NULL);
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static int
parse_end_map(void *ctx)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	PyObject *result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodEndMap, NULL);
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static int
parse_start_array(void *ctx)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	PyObject *result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodStartArray, NULL);
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static int
parse_end_array(void *ctx)
{
	PyGILState_STATE gstate;
	gstate = PyGILState_Ensure();
	MGA::MODULE_STATE *state = GET_STATE();
	
	if (!state) {
		PyErr_SetString(PyExc_RuntimeError, "no module state!");
		PyGILState_Release(gstate);
		return 0;
	}
	MGA::JSONDecoderObject *self = (MGA::JSONDecoderObject *)ctx;
	PyObject *result = PyObject_CallMethodObjArgs((PyObject *)self, state->fMethodEndArray, NULL);
	Py_XDECREF(result);
	PyGILState_Release(gstate);
	
	return result ? 1 : 0;
}


static PyObject *
dec_read(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	Py_RETURN_NONE;
}


static PyObject *
dec_read_key(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	Py_RETURN_NONE;
}


static PyObject *
dec_start_map(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	Py_RETURN_NONE;
}


static PyObject *
dec_end_map(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	Py_RETURN_NONE;
}


static PyObject *
dec_start_array(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	Py_RETURN_NONE;
}


static PyObject *
dec_end_array(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	Py_RETURN_NONE;
}


static MGA::JSONDecoderObject *
dec_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	return new (type->tp_alloc(type, 0)) MGA::JSONDecoderObject();
}


static void
dec_dealloc(MGA::JSONDecoderObject *self)
{
	yajl_free(self->fHandle);
	
	self->~JSONDecoderObject();
	Py_TYPE(self)->tp_free((PyObject*)self);
}


static PyObject *
dec_parse(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	string text;
	yajl_status status;
	
	if (!PyArg_ParseTuple(args, "O&", MGA::ConvertString, &text))
		return NULL;
	Py_BEGIN_ALLOW_THREADS
	status = yajl_parse(self->fHandle, (const unsigned char *)text.c_str(), text.size());
	Py_END_ALLOW_THREADS
	if (status != yajl_status_ok) {
		if (!PyErr_Occurred()) {
			unsigned char *error = yajl_get_error(self->fHandle, 0, (const unsigned char *)text.c_str(), text.size());
			size_t line, column;
			yajl_get_error_position(self->fHandle, &line, &column);
			if (self->fFileName.empty())
				text = CL_StringFormat("<string>, line %d, column %d: %s", (int)line, (int)column, (const char *)error);
			else
				text = CL_StringFormat("%s, line %d, column %d: %s", self->fFileName.c_str(), (int)line, (int)column, (const char *)error);
			setException(text);
			yajl_free_error(self->fHandle, error);
		}
		return NULL;
	}
	Py_RETURN_NONE;
}


static PyObject *
dec_complete_parse(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	yajl_status status;
	
	Py_BEGIN_ALLOW_THREADS
	status = yajl_complete_parse(self->fHandle);
	Py_END_ALLOW_THREADS
	if (status != yajl_status_ok) {
		string text = yajl_status_to_string(status);
		size_t line, column;
		yajl_get_error_position(self->fHandle, &line, &column);
		if (self->fFileName.empty())
			text = CL_StringFormat("<string>, line %d, column %d: %s", (int)line, (int)column, text.c_str());
		else
			text = CL_StringFormat("%s, line %d, column %d: %s", self->fFileName.c_str(), (int)line, (int)column, text.c_str());
		setException(text);
		return NULL;
	}
	Py_RETURN_NONE;
}


static PyObject *
dec_set_filename(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	string fileName;
	
	if (!PyArg_ParseTuple(args, "O&", MGA::ConvertString, &fileName))
		return NULL;
	self->fFileName = fileName;
	
	Py_RETURN_NONE;
}


static PyObject *
dec_get_parse_position(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	size_t line, column;
	yajl_get_error_position(self->fHandle, &line, &column);
	return Py_BuildValue("ii", (int)line, (int)column);
}


static int
dec_init(MGA::JSONDecoderObject *self, PyObject *args, PyObject *kwds)
{
	string encoding, fileName;
	
	if (!PyArg_ParseTuple(args, "|O&O&", MGA::ConvertString, &encoding, MGA::ConvertString, &fileName))
		return -1;
	
	if (!encoding.empty())
		self->fEncoding = encoding;
	self->fFileName = fileName;
	
	return 0;
}


static yajl_callbacks sCallbacks = {
    parse_null,
    parse_boolean,
    NULL,
    NULL,
    parse_number,
    parse_string,
    parse_start_map,
    parse_map_key,
    parse_end_map,
    parse_start_array,
    parse_end_array
};


static PyMethodDef enc_methods[] = {
	{	"write",					(PyCFunction)enc_write,				METH_VARARGS | METH_KEYWORDS,	"write(object)\n\nWrites a bool/int/long/float/Decimal/string/date/datetime to the stream" },
	{	"start_map",				(PyCFunction)enc_start_map,			METH_VARARGS | METH_KEYWORDS,	"start_map()\n\nStarts a new mapping in the stream" },
	{	"end_map",					(PyCFunction)enc_end_map,			METH_VARARGS | METH_KEYWORDS,	"end_map()\n\nEnds current mapping in the stream" },
	{	"start_array",				(PyCFunction)enc_start_array,		METH_VARARGS | METH_KEYWORDS,	"start_array()\n\nStarts a new array in the stream" },
	{	"end_array",				(PyCFunction)enc_end_array,			METH_VARARGS | METH_KEYWORDS,	"end_array()\n\nEnds current array in the stream" },
	{	"generate",					(PyCFunction)enc_generate,			METH_VARARGS | METH_KEYWORDS,	"generate()\n\nReturns currently generated output and clear internal buffer" },
	{	"reset",					(PyCFunction)enc_reset,				METH_VARARGS | METH_KEYWORDS,	"reset()\n\nResets encoder so a new file can be generated" },
	{	NULL }
};


static PyMethodDef dec_methods[] = {
	{	"read",						(PyCFunction)dec_read,				METH_VARARGS | METH_KEYWORDS,	"read(object)\n\nMethod called when a bool/int/long/float/Decimal/string/date/datetime is parsed from the stream" },
	{	"read_key",					(PyCFunction)dec_read_key,			METH_VARARGS | METH_KEYWORDS,	"read_key(str)\n\nMethod called when a mapping key is parsed from the stream" },
	{	"start_map",				(PyCFunction)dec_start_map,			METH_VARARGS | METH_KEYWORDS,	"start_map()\n\nMethod called when a mapping start is parsed from the stream" },
	{	"end_map",					(PyCFunction)dec_end_map,			METH_VARARGS | METH_KEYWORDS,	"end_map()\n\nMethod called when a mapping end is parsed from the stream" },
	{	"start_array",				(PyCFunction)dec_start_array,		METH_VARARGS | METH_KEYWORDS,	"start_array()\n\nMethod called when an array start is parsed from the stream" },
	{	"end_array",				(PyCFunction)dec_end_array,			METH_VARARGS | METH_KEYWORDS,	"end_array()\n\nMethod called when an array end is parsed from the stream" },
	{	"parse",					(PyCFunction)dec_parse,				METH_VARARGS | METH_KEYWORDS,	"parse(text)\n\nParses given text" },
	{	"complete_parse",			(PyCFunction)dec_complete_parse,	METH_VARARGS | METH_KEYWORDS,	"complete_parse()\n\nEnds parsing session, parsing any remaining buffered data" },
	{	"set_filename",				(PyCFunction)dec_set_filename,		METH_VARARGS | METH_KEYWORDS,	"set_filename(str)\n\nSets current filename for error reporting" },
	{	"get_parse_position",		(PyCFunction)dec_get_parse_position,METH_VARARGS | METH_KEYWORDS,	"get_parse_position()\n\nGets current parser position" },
	{	NULL }
};


PyTypeObject MGA::JSONEncoderType = {
	PyVarObject_HEAD_INIT(NULL, 0)
    "_kongalib.JSONEncoder",				/* tp_name */
    sizeof(MGA::JSONEncoderObject),			/* tp_basicsize */
	0,										/* tp_itemsize */
	(destructor)enc_dealloc,				/* tp_dealloc */
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
	"JSONEncoder objects",					/* tp_doc */
	0,										/* tp_traverse */
	0,										/* tp_clear */
	0,										/* tp_richcompare */
	0,										/* tp_weaklistoffset */
	0,										/* tp_iter */
	0,										/* tp_iternext */
	enc_methods,							/* tp_methods */
	0,										/* tp_members */
	0,										/* tp_getset */
	0,										/* tp_base */
	0,										/* tp_dict */
	0,										/* tp_descr_get */
	0,										/* tp_descr_set */
	0,										/* tp_dictoffset */
	(initproc)enc_init,						/* tp_init */
	0,										/* tp_alloc */
	(newfunc)enc_new,						/* tp_new */
};


PyTypeObject MGA::JSONDecoderType = {
	PyVarObject_HEAD_INIT(NULL, 0)
    "_kongalib.JSONDecoder",				/* tp_name */
    sizeof(MGA::JSONDecoderType),			/* tp_basicsize */
	0,										/* tp_itemsize */
	(destructor)dec_dealloc,				/* tp_dealloc */
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
	"JSONDecoder objects",					/* tp_doc */
	0,										/* tp_traverse */
	0,										/* tp_clear */
	0,										/* tp_richcompare */
	0,										/* tp_weaklistoffset */
	0,										/* tp_iter */
	0,										/* tp_iternext */
	dec_methods,							/* tp_methods */
	0,										/* tp_members */
	0,										/* tp_getset */
	0,										/* tp_base */
	0,										/* tp_dict */
	0,										/* tp_descr_get */
	0,										/* tp_descr_set */
	0,										/* tp_dictoffset */
	(initproc)dec_init,						/* tp_init */
	0,										/* tp_alloc */
	(newfunc)dec_new,						/* tp_new */
};


namespace MGA {
	
	JSONEncoderObject::JSONEncoderObject()
		: fEncoding("utf-8"), fPretty(true)
	{
		fHandle = yajl_gen_alloc(NULL);
		yajl_gen_config(fHandle, yajl_gen_beautify, 1);
		yajl_gen_config(fHandle, yajl_gen_indent_string, "\t");
	}
	
	JSONDecoderObject::JSONDecoderObject()
		: fEncoding("utf-8")
	{
		fHandle = yajl_alloc(&sCallbacks, NULL, (void *)this);
		yajl_config(fHandle, yajl_allow_comments, 1);
		yajl_config(fHandle, yajl_dont_validate_strings, 1);
	}
	
	
};


void
MGA::InitJSON()
{
	PyDateTime_IMPORT;
	PyImport_ImportModule("datetime");
}
