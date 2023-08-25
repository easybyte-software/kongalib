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
UnicodeToUTF8(PyObject *unicode, string *dest)
{
	Py_ssize_t size;
	const char *s = PyUnicode_AsUTF8AndSize(unicode, &size);
	*dest = string(s, size);
}


int
MGA::ConvertString(PyObject *object, string *string)
{
	if (PyBytes_Check(object)) {
		*string = PyBytes_AS_STRING(object);
		return 1;
	}
	else if (PyUnicode_Check(object)) {
		UnicodeToUTF8(object, string);
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
	MGA::DecimalObject *decimal;
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
		if ((entry->fDate.IsValid()) && (entry->fDate.GetYear() >= 1900) && (entry->fDate.GetYear() <= 9999)) {
			object = PyDate_FromDate(entry->fDate.GetYear(), entry->fDate.GetMonth(), entry->fDate.GetDay());
		}
		else {
			object = Py_None;
			Py_INCREF(object);
		}
		break;

	case CLU_TIME:
		if (entry->fTime.IsValid()) {
			object = PyTime_FromTime(entry->fTime.GetHour(), entry->fTime.GetMin(), entry->fTime.GetSec(), 0);
		}
		else {
			object = Py_None;
			Py_INCREF(object);
		}
		break;
	
	case CLU_TIMESTAMP:
		if ((entry->fTimeStamp.IsValid()) && (entry->fTimeStamp.GetYear() >= 1900) && (entry->fTimeStamp.GetYear() <= 9999)) {
			CL_TimeStamp timeStamp = entry->fTimeStamp.ToLocal();
			object = PyDateTime_FromDateAndTime(timeStamp.GetYear(), timeStamp.GetMonth(), timeStamp.GetDay(), timeStamp.GetHour(), timeStamp.GetMin(), timeStamp.GetSec(), 0);
		}
		else {
			object = Py_None;
			Py_INCREF(object);
		}
		break;
	
	case CLU_TEXT:
		object = PyUnicode_DecodeUTF8(entry->fString.data(), entry->fString.size(), "replace");
		break;
	
	case CLU_BLOB:
		object = PyBytes_FromStringAndSize((const char *)entry->fBlob.GetData(), (Py_ssize_t)entry->fBlob.GetSize());
		break;
	
	case CLU_LIST:
		object = MGA::List_FromCLU(&entry->fList);
		break;
	
	case CLU_TABLE:
		object = MGA::Table_FromCLU(&entry->fTable);
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
static void
Entry_FromPy(PyObject *object, CLU_Entry *entry)
{
	char *text;
	Py_buffer buffer;
	Py_ssize_t size;
	
	if (object == Py_None) {
		entry->Set(CLU_Null);
	}
	else if (PyBool_Check(object)) {
		entry->Set(PyObject_IsTrue(object) ? true : false);
	}
	else if (PyLong_Check(object)) {
		entry->Set((int64)PyLong_AsLongLong(object));
	}
	else if (PyObject_TypeCheck(object, &MGA::DecimalType)) {
		entry->Set(((MGA::DecimalObject *)object)->fValue);
	}
	else if (PyFloat_Check(object)) {
		entry->Set(PyFloat_AS_DOUBLE(object));
	}
	else if (PyDateTime_Check(object)) {
		entry->Set(CL_TimeStamp(PyDateTime_GET_DAY(object), PyDateTime_GET_MONTH(object), PyDateTime_GET_YEAR(object),
								PyDateTime_DATE_GET_HOUR(object), PyDateTime_DATE_GET_MINUTE(object), PyDateTime_DATE_GET_SECOND(object)).ToUTC());
	}
	else if (PyDate_Check(object)) {
		entry->Set(CL_Date(PyDateTime_GET_DAY(object), PyDateTime_GET_MONTH(object), PyDateTime_GET_YEAR(object)));
	}
	else if (PyTime_Check(object)) {
		entry->Set(CL_Time(PyDateTime_TIME_GET_HOUR(object), PyDateTime_TIME_GET_MINUTE(object), PyDateTime_TIME_GET_SECOND(object)));
	}
	else if ((PyBytes_Check(object)) && (!PyBytes_AsStringAndSize(object, &text, &size))) {
		entry->Set(string(text, size));
	}
	else if (PyUnicode_Check(object)) {
		string temp;
		UnicodeToUTF8(object, &temp);
		entry->Set(temp);
	}
	else if ((PyList_Check(object)) || (PyTuple_Check(object))) {
		CLU_List temp;
		MGA::List_FromPy(object, &temp);
		entry->Set(temp);
	}
	else if (PyDict_Check(object)) {
		CLU_Table temp;
		MGA::Table_FromPy(object, &temp);
		entry->Set(temp);
	}
	else if ((PyObject_CheckBuffer(object)) && (!PyObject_GetBuffer(object, &buffer, PyBUF_SIMPLE))) {
		entry->Set(CL_Blob((const void *)buffer.buf, (uint32)buffer.len));
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
			string temps;
			UnicodeToUTF8(temp, &temps);
			entry->Set(temps);
			Py_DECREF(temp);
		}
		else {
			PyErr_Clear();
			entry->Set(CLU_Null);
		}
	}
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
	CLU_List::iterator it;
	Py_ssize_t pos;
	
	for (pos = 0, it = _list->begin(); it != _list->end(); it++, pos++) {
		item = Entry_FromCLU(it.ptr());
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
void
MGA::List_FromPy(PyObject *object, CLU_List *list)
{
	CLU_Entry entry;
	PyObject *item;
	int32 size;
	Py_ssize_t pos;

	list->Clear();
	if (PyTuple_Check(object)) {
		size = PyTuple_GET_SIZE(object);
		for (pos = 0; (pos < size) && (!PyErr_Occurred()); pos++) {
			item = PyTuple_GET_ITEM(object, pos);
			Entry_FromPy(item, &entry);
			list->Append(entry);
		}
	}
	else if (PyList_Check(object)) {
		size = PyList_GET_SIZE(object);
		for (pos = 0; (pos < size) && (!PyErr_Occurred()); pos++) {
			item = PyList_GET_ITEM(object, pos);
			Entry_FromPy(item, &entry);
			list->Append(entry);
		}
	}
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
	CLU_Table::iterator it;
	
	for (it = table->begin(); it != table->end(); it++) {
		value = Entry_FromCLU(it.ptr());
		if (!value) {
			Py_DECREF(object);
			return NULL;
		}
		PyObject *okey = PyUnicode_DecodeUTF8(it.key().c_str(), it.key().size(), "replace");
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
void
MGA::Table_FromPy(PyObject *object, CLU_Table *table)
{
	CLU_Entry entry;
	PyObject *key, *value, *okey;
	Py_ssize_t pos = 0;
	string skey;
	
	table->Clear();
	if (PyDict_Check(object)) {
		while ((!PyErr_Occurred()) && (PyDict_Next(object, &pos, &key, &value))) {
			if (!MGA::ConvertString(key, &skey)) {
				okey = PyObject_Str(key);
				if (!okey) {
					PyErr_Clear();
					okey = PyObject_Repr(key);
				}
				skey = PyUnicode_AsUTF8(okey);
				Py_DECREF(okey);
			}
			Entry_FromPy(value, &entry);
			table->Set(skey, entry);
		}
	}
}


void
MGA::InitUtilities()
{
	PyDateTime_IMPORT;
	PyImport_ImportModule("datetime");
}


/*@}*/
