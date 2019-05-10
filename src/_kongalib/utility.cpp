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


static void
UnicodeToUTF8(PyObject *unicode, CL_Blob& blob)
{
#if PY3K
	Py_ssize_t size;
	const char *s = PyUnicode_AsUTF8AndSize(unicode, &size);
	blob.Set((void *)s, (uint32)size);
#else
	Py_ssize_t i, size = PyUnicode_GET_SIZE(unicode);
	const Py_UNICODE *s = PyUnicode_AS_UNICODE(unicode);
	
	for (i = 0; i < size;) {
		Py_UCS4 ch = s[i++];
		
		if (ch < 0x80) {
			blob << (uint8)ch;
		}
		else if (ch < 0x0800) {
			blob << (uint8)(0xC0 | (ch >> 6));
			blob << (uint8)(0x80 | (ch & 0x3F));
		}
		else {
			if (ch < 0x10000) {
				if ((ch >= 0xD800) && (ch <= 0xDBFF) && (i != size)) {
					Py_UCS4 ch2 = s[i];
					if ((ch2 >= 0xDC00) && (ch <= 0xDFFF)) {
						ch = (((ch - 0xD800) << 10) | (ch2 - 0xDC00)) + 0x10000;
						i++;
						goto encodeUCS4;
					}
				}
				blob << (uint8)(0xE0 | (ch >> 12));
				blob << (uint8)(0x80 | ((ch >> 6) & 0x3F));
				blob << (uint8)(0x80 | (ch & 0x3F));
				continue;
			}
		encodeUCS4:
			blob << (uint8)(0xF0 | (ch >> 18));
			blob << (uint8)(0x80 | ((ch >> 12) & 0x3F));
			blob << (uint8)(0x80 | ((ch >> 6) & 0x3F));
			blob << (uint8)(0x80 | (ch & 0x3F));
		}
	}
#endif
}


int
MGA::ConvertString(PyObject *object, string *string)
{
	if (PyBytes_Check(object)) {
		*string = PyBytes_AS_STRING(object);
		return 1;
	}
	else if (PyUnicode_Check(object)) {
		CL_Blob buffer;
		UnicodeToUTF8(object, buffer);
		*string = std::string((const char *)buffer.GetData(), (size_t)buffer.GetSize());
		return 1;
	}
	PyErr_SetString(PyExc_ValueError, "Expected 'str' or 'unicode' object");
	return 0;
}


/**
 *	Converts an #CLU_Entry entry to a Python object. The resulting Python object class depends on the type of the data held within the entry:
 *	- #CLU_NULL => None.
 *	- #CLU_BOOL => bool
 *	- #CLU_INTEGER => long.
 *	- #CLU_DECIMAL => MGA.Decimal.
 *	- #CLU_FLOAT => float.
 *	- #CLU_TIMESTAMP => datetime.datetime.
 *	- #CLU_TEXT => unicode.
 *	- #CLU_BLOB => buffer.
 *	- #CLU_LIST => list containing sub entries converted to other Python objects.
 *	- #CLU_TABLE => dict containing sub entries converted to other Python objects.
 *	\param	entry				The #CLU_Entry to be converted.
 *	\return						A Python object representing the converted entry.
 */
static PyObject *
Entry_FromCLU(CLU_Entry *entry)
{
	PyObject *object;
	CL_Blob blob;
	CL_Time time;
	CL_Date date;
	CL_TimeStamp timeStamp;
	MGA::DecimalObject *decimal;
	CLU_Table table;
	CLU_List list;
	string text;
	
	switch (entry->fType) {
	case CLU_BOOL:
		if (entry->fBool)
			object = Py_True;
		else
			object = Py_False;
		Py_INCREF(object);
		break;
	
	case CLU_INTEGER:
		object = PyLong_FromLongLong(entry->fInteger);
		break;
	
	case CLU_DECIMAL:
		decimal = MGA::DecimalObject::Allocate();
		decimal->fValue = entry->fDecimal;
		object = (PyObject *)decimal;
		break;
	
	case CLU_FLOAT:
		object = PyFloat_FromDouble(entry->fFloat);
		break;
	
	case CLU_DATE:
		date = entry->fTimeStamp;
		if ((date.IsValid()) && (date.GetYear() >= 1900) && (date.GetYear() <= 9999)) {
			object = PyDate_FromDate(date.GetYear(), date.GetMonth(), date.GetDay());
		}
		else {
			object = Py_None;
			Py_INCREF(object);
		}
		break;

	case CLU_TIME:
		time = entry->fTimeStamp;
		if (time.IsValid()) {
			object = PyTime_FromTime(time.GetHour(), time.GetMin(), time.GetSec(), 0);
		}
		else {
			object = Py_None;
			Py_INCREF(object);
		}
		break;
	
	case CLU_TIMESTAMP:
		timeStamp = entry->fTimeStamp;
		if ((timeStamp.IsValid()) && (timeStamp.GetYear() >= 1900) && (timeStamp.GetYear() <= 9999)) {
			timeStamp = timeStamp.ToLocal();
			object = PyDateTime_FromDateAndTime(timeStamp.GetYear(), timeStamp.GetMonth(), timeStamp.GetDay(), timeStamp.GetHour(), timeStamp.GetMin(), timeStamp.GetSec(), 0);
		}
		else {
			object = Py_None;
			Py_INCREF(object);
		}
		break;
	
	case CLU_TEXT:
		text = entry->String();
		object = PyUnicode_DecodeUTF8(text.data(), text.size(), "replace");
		break;
	
	case CLU_BLOB:
		object = PyBytes_FromStringAndSize((const char *)entry->fBlob->GetData(), (Py_ssize_t)entry->fBlob->GetSize());
		break;
	
	case CLU_LIST:
		object = MGA::List_FromCLU(entry->fList);
		break;
	
	case CLU_TABLE:
		object = MGA::Table_FromCLU(entry->fTable);
		break;
	
	case CLU_NULL:
	default:
		object = Py_None;
		Py_INCREF(object);
		break;
	}

	return object;
}


/**
 *	Converts a Python object to an #CLU_Entry entry. Applies one of these conversions depending on the class of the Python object:
 *	- None => #CLU_NULL.
 *	- bool => #CLU_BOOL.
 *	- int or long => #CLU_INTEGER.
 *	- MGA.Decimal => #CLU_DECIMAL.
 *	- float => #CLU_FLOAT.
 *	- datetime.datetime => #CLU_TIMESTAMP.
 *	- string or unicode => #CLU_TEXT.
 *	- tuple or list => #CLU_LIST.
 *	- dict => #CLU_TABLE.
 *	- buffer => #CLU_BLOB.
 *	\param	object				The Python object to be converted to #CLU_Entry.
 *	\return						The converted #CLU_Entry representing the Python object.
 */
static CLU_Entry *
Entry_FromPy(PyObject *object)
{
	CLU_Entry *entry = CLU_Entry::Allocate();
	char *text;
	Py_buffer buffer;
	Py_ssize_t size;
	
	if (object == Py_None) {
		entry->fType = CLU_NULL;
	}
	else if (PyBool_Check(object)) {
		entry->fType = CLU_BOOL;
		entry->fBool = PyObject_IsTrue(object) ? true : false;
	}
	else if (PyLong_Check(object)) {
		entry->fType = CLU_INTEGER;
		entry->fInteger = PyLong_AsLongLong(object);
	}
#if !PY3K
	else if (PyInt_Check(object)) {
		entry->fType = CLU_INTEGER;
		entry->fInteger = (int64)PyInt_AS_LONG(object);
	}
#endif
	else if (PyObject_TypeCheck(object, &MGA::DecimalType)) {
		entry->fType = CLU_DECIMAL;
		entry->fDecimal = ((MGA::DecimalObject *)object)->fValue;
	}
	else if (PyFloat_Check(object)) {
		entry->fType = CLU_FLOAT;
		entry->fFloat = PyFloat_AS_DOUBLE(object);
	}
	else if (PyDateTime_Check(object)) {
		entry->fType = CLU_TIMESTAMP;
		entry->fTimeStamp = CL_TimeStamp(PyDateTime_GET_DAY(object), PyDateTime_GET_MONTH(object), PyDateTime_GET_YEAR(object),
										 PyDateTime_DATE_GET_HOUR(object), PyDateTime_DATE_GET_MINUTE(object), PyDateTime_DATE_GET_SECOND(object)).ToUTC();
	}
	else if (PyDate_Check(object)) {
		entry->fType = CLU_DATE;
		entry->fTimeStamp = CL_Date(PyDateTime_GET_DAY(object), PyDateTime_GET_MONTH(object), PyDateTime_GET_YEAR(object));
	}
	else if (PyTime_Check(object)) {
		entry->fType = CLU_TIME;
		entry->fTimeStamp = CL_Time(PyDateTime_TIME_GET_HOUR(object), PyDateTime_TIME_GET_MINUTE(object), PyDateTime_TIME_GET_SECOND(object));
	}
	else if ((PyBytes_Check(object)) && (!PyBytes_AsStringAndSize(object, &text, &size))) {
		entry->fType = CLU_TEXT;
		entry->fBlob = CL_New(CL_Blob((const void *)text, (uint32)size));
	}
	else if (PyUnicode_Check(object)) {
		entry->fType = CLU_TEXT;
		entry->fBlob = CL_New(CL_Blob);
		UnicodeToUTF8(object, *entry->fBlob);
	}
	else if ((PyList_Check(object)) || (PyTuple_Check(object))) {
		entry->fType = CLU_LIST;
		entry->fList = MGA::List_FromPy(object);
	}
	else if (PyDict_Check(object)) {
		entry->fType = CLU_TABLE;
		entry->fTable = MGA::Table_FromPy(object);
	}
	else if ((PyObject_CheckBuffer(object)) && (!PyObject_GetBuffer(object, &buffer, PyBUF_SIMPLE))) {
		entry->fType = CLU_BLOB;
		entry->fBlob = CL_New(CL_Blob((const void *)buffer.buf, (uint32)buffer.len));
		PyBuffer_Release(&buffer);
	}
	else {
		PyErr_Clear();
		PyObject *temp = PyObject_Str(object);
		if (!temp) {
			PyErr_Clear();
			temp = PyObject_Repr(object);
		}
		if (temp) {
#if PY3K
			text = (char *)PyUnicode_AsUTF8(temp);
#else
			text = PyString_AS_STRING(temp);
#endif
			entry->fType = CLU_TEXT;
			entry->fBlob = CL_New(CL_Blob);
			*entry->fBlob << text;
			Py_DECREF(temp);
		}
		else
			PyErr_Clear();
	}
	
	return entry;
}


/**
 *	Converts an #CLU_List and all the entries it contains to a Python list object containing converted sub-objects.
 *	\param	list				The #CLU_List to be converted.
 *	\return						A Python object representing the converted list.
 */
PyObject *
MGA::List_FromCLU(CLU_List *_list)
{
	PyObject *object = PyList_New(_list->Count());
	PyObject *item;
	CLU_Entry *entry;
	CL_Iterator iterator;
	Py_ssize_t pos;
	
	for (pos = 0, entry = _list->Open(iterator); entry; entry = _list->Next(iterator), pos++) {
		item = Entry_FromCLU(entry);
		if (!item) {
			for (; pos < (signed)_list->Count(); pos++) {
				Py_INCREF(Py_None);
				PyList_SET_ITEM(object, pos, Py_None);
			}
			Py_DECREF(object);
			return NULL;
		}
		PyList_SET_ITEM(object, pos, item);
	}
	
	return object;
}


/**
 *	Converts a Python list object and all the objects it contains to an #CLU_List containing converted entries.
 *	\param	object				The Python list object to be converted.
 *	\return						A #CLU_List representing the converted list.
 */
CLU_List *
MGA::List_FromPy(PyObject *object)
{
	CLU_List *list = CL_New(CLU_List);
	CLU_Entry *entry;
	PyObject *item;
	int32 size;
	Py_ssize_t pos;
	
	if (PyTuple_Check(object)) {
		size = PyTuple_GET_SIZE(object);
		for (pos = 0; (pos < size) && (!PyErr_Occurred()); pos++) {
			item = PyTuple_GET_ITEM(object, pos);
			entry = Entry_FromPy(item);
			list->Append(entry);
		}
	}
	else if (PyList_Check(object)) {
		size = PyList_GET_SIZE(object);
		for (pos = 0; (pos < size) && (!PyErr_Occurred()); pos++) {
			item = PyList_GET_ITEM(object, pos);
			entry = Entry_FromPy(item);
			list->Append(entry);
		}
	}
	return list;
}


/**
 *	Converts an #CLU_Table and all the entries it contains to a Python dict object containing converted sub-objects. Original #CLU_Table
 *	keys are reused in the converted dict object to map sub-objects.
 *	\param	table				The #CLU_Table to be converted.
 *	\return						A Python object representing the converted table.
 */
PyObject *
MGA::Table_FromCLU(CLU_Table *table)
{
	PyObject *object = PyDict_New();
	PyObject *value;
	CLU_Entry *entry;
	CL_Iterator iterator;
	string key;
	
	for (entry = table->Open(iterator, &key); entry; entry = table->Next(iterator, &key)) {
		value = Entry_FromCLU(entry);
		if (!value) {
			Py_DECREF(object);
			return NULL;
		}
		PyObject *okey = PyUnicode_DecodeUTF8(key.c_str(), key.size(), "replace");
		PyDict_SetItem(object, okey, value);
		Py_DECREF(okey);
		Py_DECREF(value);
	}
	
	return object;
}


/**
 *	Converts a Python dict object and all the objects it contains to an #CLU_Table containing converted entries. Original dict keys are
 *	reused in the converted #CLU_Table to map sub-entries.
 *	\param	object				The Python table object to be converted.
 *	\return						A #CLU_Table representing the converted table.
 */
CLU_Table *
MGA::Table_FromPy(PyObject *object)
{
	CLU_Table *table = CL_New(CLU_Table);
	CLU_Entry *entry;
	PyObject *key, *value, *okey;
	Py_ssize_t pos = 0;
	string skey;
	
	if (PyDict_Check(object)) {
		while ((!PyErr_Occurred()) && (PyDict_Next(object, &pos, &key, &value))) {
			if (!MGA::ConvertString(key, &skey)) {
				okey = PyObject_Str(key);
				if (!okey) {
					PyErr_Clear();
					okey = PyObject_Repr(key);
				}
#if PY3K
				skey = PyUnicode_AsUTF8(okey);
#else
				skey = PyString_AS_STRING(okey);
#endif
				Py_DECREF(okey);
			}
			entry = Entry_FromPy(value);
			table->Set(skey, entry);
		}
	}
	return table;
}


void
MGA::InitUtilities()
{
	PyDateTime_IMPORT;
	PyImport_ImportModule("datetime");
}


/*@}*/
