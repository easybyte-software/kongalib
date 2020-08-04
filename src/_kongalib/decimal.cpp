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
#include <wchar.h>


/**
 *	Addition operator for the MGA.Decimal type.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_add(PyObject *_self, PyObject *_other)
{
	MGA::DecimalObject *result;
	MGA::DecimalObject *self;
	MGA::DecimalObject *other;

	if (!MGA::ConvertDecimal(_self, &self))
		return NULL;

	if (!MGA::ConvertDecimal(_other, &other)) {
		Py_DECREF(self);
		return NULL;
	}

	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue + other->fValue;

	Py_DECREF(self);
	Py_DECREF(other);
	
	return result;
}


/**
 *	Subtraction operator for the MGA.Decimal type.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_sub(PyObject *_self, PyObject *_other)
{
	MGA::DecimalObject *result;
	MGA::DecimalObject *self;
	MGA::DecimalObject *other;

	if (!MGA::ConvertDecimal(_self, &self))
		return NULL;

	if (!MGA::ConvertDecimal(_other, &other)) {
		Py_DECREF(self);
		return NULL;
	}
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue - other->fValue;

	Py_DECREF(self);
	Py_DECREF(other);
	
	return result;
}


/**
 *	Multiplication operator for the MGA.Decimal type.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_mul(PyObject *_self, PyObject *_other)
{
	MGA::DecimalObject *result;
	MGA::DecimalObject *self;
	MGA::DecimalObject *other;

	if (!MGA::ConvertDecimal(_self, &self))
		return NULL;

	if (!MGA::ConvertDecimal(_other, &other)) {
		Py_DECREF(self);
		return NULL;
	}
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue * other->fValue;

	Py_DECREF(self);
	Py_DECREF(other);
	
	return result;
}


#if !PY3K

/**
 *	Deprecated (old) division operator for the MGA.Decimal type.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_classic_div(MGA::DecimalObject *self, MGA::DecimalObject *other)
{
	MGA::DecimalObject *result;
	
	if ((Py_DivisionWarningFlag >= 2) && (PyErr_Warn(PyExc_DeprecationWarning, "decimal classic division") < 0))
		return NULL;
	
	if (other->fValue == 0) {
		PyErr_SetString(PyExc_ZeroDivisionError, "decimal division");
		return NULL;
	}
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue / other->fValue;
	
	return result;
}

#endif


/**
 *	Remainder operator for the MGA.Decimal type.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_rem(PyObject *_self, PyObject *_other)
{
	MGA::DecimalObject *result;
	MGA::DecimalObject *self;
	MGA::DecimalObject *other;

	if (!MGA::ConvertDecimal(_self, &self))
		return NULL;

	if (!MGA::ConvertDecimal(_other, &other)) {
		Py_DECREF(self);
		return NULL;
	}
	
	if (other->fValue == 0) {
		Py_DECREF(self);
		Py_DECREF(other);
		PyErr_SetString(PyExc_ZeroDivisionError, "decimal division");
		return NULL;
	}
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue % other->fValue;

	Py_DECREF(self);
	Py_DECREF(other);
	
	return result;
}


/**
 *	divmod operator for the MGA.Decimal type. Returns a tuple with the quotient and remainder of the division between \a self and \a other.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static PyObject *
MGA_Decimal_divmod(PyObject *_self, PyObject *_other)
{
	MGA::DecimalObject *quotient, *remainder;
	MGA::DecimalObject *self, *other;

	if (!MGA::ConvertDecimal(_self, &self))
		return NULL;
	
	if (!MGA::ConvertDecimal(_other, &other)) {
		Py_DECREF(self);
		return NULL;
	}
	
	if (other->fValue == 0) {
		Py_DECREF(self);
		Py_DECREF(other);
		PyErr_SetString(PyExc_ZeroDivisionError, "decimal division");
		return NULL;
	}
	quotient = MGA::DecimalObject::Allocate();
	quotient->fValue = (self->fValue / other->fValue).Floor();
	
	remainder = MGA::DecimalObject::Allocate();
	remainder->fValue = self->fValue % other->fValue;

	Py_DECREF(self);
	Py_DECREF(other);
	
	return Py_BuildValue("(OO)", quotient, remainder);
}


/**
 *	Exponentiation operator for the MGA.Decimal type.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\param	unused				Unused.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_pow(PyObject *_self, PyObject *_other, PyObject *unused)
{
	MGA::DecimalObject *result;
	MGA::DecimalObject *self;
	MGA::DecimalObject *other;

	if (unused != Py_None) {
		PyErr_SetString(PyExc_TypeError, "pow() 3rd argument not allowed unless all arguments are integers");
		return NULL;
	}

	if (!MGA::ConvertDecimal(_self, &self))
		return NULL;

	if (!MGA::ConvertDecimal(_other, &other)) {
		Py_DECREF(self);
		return NULL;
	}
	if (other->fValue == 0) {
		result = MGA::DecimalObject::Allocate();
		result->fValue = 1;

		Py_DECREF(self);
		Py_DECREF(other);
		
		return result;
	}
	if (self->fValue == 0) {
		if (other->fValue < 0) {
			Py_DECREF(self);
			Py_DECREF(other);
			PyErr_SetString(PyExc_ZeroDivisionError, "0.0 cannot be raised to a negative power");
			return NULL;
		}
		Py_DECREF(self);
		Py_DECREF(other);
		
		result = MGA::DecimalObject::Allocate();
		result->fValue = 0;
		
		return result;
	}
	if ((self->fValue < 0) && (other->fValue != other->fValue.Floor())) {
		Py_DECREF(self);
		Py_DECREF(other);
		PyErr_SetString(PyExc_ValueError, "negative number cannot be raised to a fractional power");
		return NULL;
	}
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue.Pow(other->fValue);

	Py_DECREF(self);
	Py_DECREF(other);
	
	return result;
}


/**
 *	Returns the negated version of input MGA.Decimal object.
 *	\param	self				MGA.Decimal to be negated.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_neg(MGA::DecimalObject *self)
{
	MGA::DecimalObject *result;
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = -self->fValue;
	
	return result;
}


/**
 *	Returns the positive version of input MGA.Decimal object. Actually just returns a new reference to \a self.
 *	\param	self				Input MGA.Decimal.
 *	\return						A new reference to \a self.
 */
static MGA::DecimalObject *
MGA_Decimal_pos(MGA::DecimalObject *self)
{
	Py_INCREF(self);
	return self;
}


/**
 *	Returns the absolute value of input MGA.Decimal object.
 *	\param	self				MGA.Decimal whose absolute value is to be returned.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_abs(MGA::DecimalObject *self)
{
	MGA::DecimalObject *result;
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue.Abs();
	
	return result;
}


/**
 *	Checks if a specified MGA.Decimal object is not zero.
 *	\param	self				MGA.Decimal to be checked.
 *	\return						0 if \a self is zero, -1 otherwise.
 */
static int
MGA_Decimal_nonzero(MGA::DecimalObject *self)
{
	return self->fValue != 0;
}


#if !PY3K

/**
 *	Coerces operand in \a pw to MGA.Decimal operand in \a pv.
 *	\param	pv					First operand (MGA.Decimal).
 *	\param	pw					Second operand (can be int, long or float), to be converted to MGA.Decimal.
 *	\retval	0					Coersion successful; \a pw converted to MGA.Decimal.
 *	\retval	1					Coersion failed.
 */
static int
MGA_Decimal_coerce(PyObject **pv, PyObject **pw)
{
	MGA::DecimalObject *object;
	
	if (PyFloat_Check(*pw)) {
		double value = PyFloat_AS_DOUBLE(*pw);
		object = MGA::DecimalObject::Allocate();
		object->fValue = value;
		*pw = (PyObject *)object;
		Py_XINCREF(*pv);
		return 0;
	}
	else if (PyObject_TypeCheck(*pw, &MGA::DecimalType)) {
		Py_XINCREF(*pv);
		Py_INCREF(*pw);
		return 0;
	}
	else {
		bool invalid, overflow;
		PyObject *o = PyObject_Str(*pw);
		if (!o) {
			PyErr_Clear();
			return 1;
		}
		object = MGA::DecimalObject::Allocate();
		object->fValue = CL_Decimal::FromString(PyString_AS_STRING(o), &invalid, &overflow);
		Py_DECREF(o);
		if ((invalid) || (overflow)) {
			Py_DECREF(object);
			return 1;
		}
		*pw = (PyObject *)object;
		Py_XINCREF(*pv);
		return 0;
	}

	return 1;
}

#endif


/**
 *	Casts the MGA.Decimal object in \a self to an int.
 *	\param	self				MGA.Decimal object to be casted to int.
 *	\return						An int object representing \a self.
 */
static PyObject *
MGA_Decimal_int(MGA::DecimalObject *self)
{
	int64 value = self->fValue.ToInt64();
	if ((value >= -2147483647L - 1) && (value <= 2147483647L))
		return PyInt_FromLong((long)value);
	else
		return PyLong_FromLongLong(value);
}


#if !PY3K

/**
 *	Casts the MGA.Decimal object in \a self to a long.
 *	\param	self				MGA.Decimal object to be casted to long.
 *	\return						A long object representing \a self.
 */
static PyObject *
MGA_Decimal_long(MGA::DecimalObject *self)
{
	string s = self->fValue.Floor().ToString();
	return PyLong_FromString((char *)s.c_str(), NULL, 10);
}

#endif


/**
 *	Casts the MGA.Decimal object in \a self to a float.
 *	\param	self				MGA.Decimal object to be casted to float.
 *	\return						A float object representing \a self.
 */
static PyObject *
MGA_Decimal_float(MGA::DecimalObject *self)
{
	return PyFloat_FromDouble(self->fValue);
}


/**
 *	Integer division operator for the MGA.Decimal type.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\return						A new reference to a MGA.Decimal object with the integer part of the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_floor_div(PyObject *self, PyObject *other)
{
	PyObject *tuple;
	MGA::DecimalObject *result;
	
	tuple = MGA_Decimal_divmod(self, other);
	if ((!tuple) || (tuple == Py_NotImplemented))
		return (MGA::DecimalObject *)tuple;
	result = (MGA::DecimalObject *)PyTuple_GET_ITEM(tuple, 0);
	Py_INCREF(result);
	Py_DECREF(tuple);
	
	return result;
}


/**
 *	Division operator for the MGA.Decimal type.
 *	\param	self				First MGA.Decimal operand.
 *	\param	other				Second MGA.Decimal operand.
 *	\return						A new reference to a MGA.Decimal object with the result of the operation.
 */
static MGA::DecimalObject *
MGA_Decimal_div(PyObject *_self, PyObject *_other)
{
	MGA::DecimalObject *result;
	MGA::DecimalObject *self;
	MGA::DecimalObject *other;

	if (!MGA::ConvertDecimal(_self, &self))
		return NULL;

	if (!MGA::ConvertDecimal(_other, &other)) {
		Py_DECREF(self);
		return NULL;
	}
	
	if (other->fValue == 0) {
		Py_DECREF(self);
		Py_DECREF(other);
		PyErr_SetString(PyExc_ZeroDivisionError, "decimal division");
		return NULL;
	}
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue / other->fValue;

	Py_DECREF(self);
	Py_DECREF(other);
	
	return result;
}



/**
 *	Returns an hash value generated from the \a self MGA.Decimal object, to be used to index mapped objects.
 *	\param	self				The MGA.Decimal object used as index.
 *	\return						The generated hash value.
 */
static long
MGA_Decimal_hash(MGA::DecimalObject *self)
{
	return _Py_HashDouble(self->fValue);
}


/**
 *	Converts an MGA.Decimal object to a string representation.
 *	\param	self				The MGA.Decimal object to be represented as a string.
 *	\return						A string object holding the string representation of \a self, in the form <tt>integer_part.fractional_part</tt>.
 */
static PyObject *
MGA_Decimal_str(MGA::DecimalObject *self)
{
	string s = self->fValue.ToString();
#if PY3K
	return PyUnicode_FromString(s.c_str());
#else
	return PyString_FromString(s.c_str());
#endif
}


/**
 *	Compares an MGA.Decimal object with another Python object and returns the result of this comparision. Currently only supports
 *	comparing with MGA.Decimal, int, long and float objects; comparing with another object type will return Py_NotImplemented.
 *	\param	self				First operand (always MGA.Decimal type).
 *	\param	other				Second operand.
 *	\param	op					Python comparision operator.
 *	\return						A bool object holding the comparision result, or Py_NotImplemented if \a other is not MGA.Decimal, int, long or float.
 */
static PyObject *
MGA_Decimal_richcompare(MGA::DecimalObject *self, PyObject *other, int op)
{
	int result = 0;
	
	if (PyObject_TypeCheck(other, &MGA::DecimalType)) {
		MGA::DecimalObject *value = (MGA::DecimalObject *)other;
		switch (op) {
		case Py_EQ: result = self->fValue == value->fValue; break;
		case Py_NE: result = self->fValue != value->fValue; break;
		case Py_LE: result = self->fValue <= value->fValue; break;
		case Py_GE: result = self->fValue >= value->fValue; break;
		case Py_LT: result = self->fValue < value->fValue; break;
		case Py_GT: result = self->fValue > value->fValue; break;
		}
	}
#if !PY3K
	else if (PyInt_Check(other)) {
		long value = PyInt_AS_LONG(other);
		switch (op) {
		case Py_EQ: result = self->fValue == value; break;
		case Py_NE: result = self->fValue != value; break;
		case Py_LE: result = self->fValue <= value; break;
		case Py_GE: result = self->fValue >= value; break;
		case Py_LT: result = self->fValue < value; break;
		case Py_GT: result = self->fValue > value; break;
		}
	}
#endif
	else if (PyLong_Check(other)) {
		PyObject *o = PyObject_Str(other);
#if PY3K
		CL_Decimal value(string(PyUnicode_AsUTF8(o)));
#else
		CL_Decimal value(string(PyString_AS_STRING(o)));
#endif
		Py_DECREF(o);
		switch (op) {
		case Py_EQ: result = self->fValue == value; break;
		case Py_NE: result = self->fValue != value; break;
		case Py_LE: result = self->fValue <= value; break;
		case Py_GE: result = self->fValue >= value; break;
		case Py_LT: result = self->fValue < value; break;
		case Py_GT: result = self->fValue > value; break;
		}
	}
	else if (PyFloat_Check(other)) {
		double value = PyFloat_AS_DOUBLE(other);
		switch (op) {
		case Py_EQ: result = self->fValue == value; break;
		case Py_NE: result = self->fValue != value; break;
		case Py_LE: result = self->fValue <= value; break;
		case Py_GE: result = self->fValue >= value; break;
		case Py_LT: result = self->fValue < value; break;
		case Py_GT: result = self->fValue > value; break;
		}
	}
	else {
		Py_INCREF(Py_NotImplemented);
		return Py_NotImplemented;
	}
	
	return PyBool_FromLong(result);
}


/**
 *	Internal function to parse a decimal number from a Python string or unicode object.
 *	\param	result				#CL_Decimal object that will contain the parsed decimal on exit.
 *	\param	string				Python string or unicode object to be parsed.
 *	\param	overflow			On exit, this will return true if the parsed number generates an overflow.
 *	\return						True if parsing successful, False otherwise or if overflow.
 */
static bool
MGA_Decimal_from_string(CL_Decimal& result, PyObject *string, bool *overflow)
{
	std::string value;
	bool invalid = false;

	*overflow = false;
	
	MGA::ConvertString(string, &value);
	
	if (value.empty())
		return false;
	result = CL_Decimal::FromString(value, &invalid, overflow);
	
	return !invalid;
}


/**
 *	Initialization method for the MGA.Decimal class. Accepts the "value" parameter with which to initialize the decimal number.
 *	\param	self				MGA.Decimal object being initialized.
 *	\param	args				Initialization arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e value: int, long, float or string object from which to fetch initial decimal value to be set.
 *	\retval	0					Initialization successful.
 *	\retval	-1					An error occured, and an exception was raised.
 */
static int
MGA_Decimal_init(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	static char *kwlist[] = { "value", NULL };
	PyObject *value = NULL, *number;
	bool overflow = false, bad = false;
	
	self->fValue = 0LL;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &value))
		return -1;
	
	if (value) {
		if (PyObject_TypeCheck(value, &MGA::DecimalType)) {
			self->fValue = ((MGA::DecimalObject *)value)->fValue;
		}
#if !PY3K
		else if (PyInt_Check(value)) {
			self->fValue = (int32)PyInt_AS_LONG(value);
		}
#endif
		else if (PyLong_Check(value)) {
			PyObject *o = PyObject_Str(value);
#if PY3K
			self->fValue = CL_Decimal::FromString(string(PyUnicode_AsUTF8(o)), &bad, &overflow);
#else
			self->fValue = CL_Decimal::FromString(string(PyString_AS_STRING(o)), &bad, &overflow);
#endif
			Py_DECREF(o);
		}
		else if (PyFloat_Check(value)) {
			self->fValue = PyFloat_AS_DOUBLE(value);
		}
		else if (PyNumber_Check(value)) {
			number = PyNumber_Float(value);
			if (number) {
				self->fValue = PyFloat_AS_DOUBLE(number);
				Py_DECREF(number);
			}
			else
				return -1;
		}
		else if ((PyBytes_Check(value)) || (PyUnicode_Check(value)))
			bad = !MGA_Decimal_from_string(self->fValue, value, &overflow);
		else
			bad = true;
		
		if (bad) {
			if (overflow)
				PyErr_SetString(PyExc_OverflowError, "Arithmetic overflow");
			else
				PyErr_SetString(PyExc_ValueError, "Bad Decimal initializer");
			return -1;
		}
	}
	
	return 0;
}


/**
 *	Formats this decimal object into a string to be displayed.
 *	\param	self				The decimal object for which a formatted string is requested.
 *	\param	args				Arguments tuple.
 *	\param	kwds				Supported argument keywords. Accepted keywords are:
 *								- \e precision: Number of fractional digits of this decimal to be printed.
 *								- \e width: Total number of characters of the returned formatted string.
 *								- \e sep: If True, put a '<tt>,</tt>' separator between thousands.
 *								- \e padzero: If True, pad with '<tt>0</tt>' ahead of the decimal.
 *	\return						A string object containing the formatted decimal string, or NULL on exception.
 */
static PyObject *
MGA_Decimal_format(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	MGA::MODULE_STATE *state = GET_STATE();
	static char *kwlist[] = { "precision", "width", "sep", "padzero", "monetary", NULL };
	int precision = -1, width = 0, padzero = 0, sep = 0, monetary=0;
	CL_LocaleInfo info;

	CL_GetLocaleInfo(&info, state ? state->fLanguage : "");
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|iiiii", kwlist, &precision, &width, &sep, &padzero, &monetary))
		return NULL;
	
	if (precision < 0)
		precision = 5;
	
	if (padzero)
		sep = 0;
	
	if (sep)
		monetary = 1;

	// fprintf(stderr, "Format %s (mon: %s), locale: { name: %s, isoname: %s, decsep: %s, tsep: %s, mondecsep: %s, montsep: %s }\n", self->fValue.ToString().c_str(), monetary?"Y":"N", info.fName.c_str(), info.fISOName.c_str(), info.fDecimalSep.c_str(), info.fThousandSep.c_str(), info.fMonDecimalSep.c_str(), info.fMonThousandSep.c_str());

	wchar_t dsep, tsep;
	wchar_t buffer[64], *p = buffer;
	int64 iPart = self->fValue;
	int64 fPart = iPart % CL_DECIMAL_UNIT;
	int32 len = 0;
	
	bool neg = (iPart < 0);
	iPart /= CL_DECIMAL_UNIT;
	iPart = CL_ABS64(iPart);

	if (monetary) {
		dsep = CL_FromUTF8(info.fMonDecimalSep)[0];
		tsep = CL_FromUTF8(info.fMonThousandSep)[0];
	}
	else {
		if (sep) {
			dsep = CL_FromUTF8(info.fDecimalSep)[0];
			tsep = CL_FromUTF8(info.fThousandSep)[0];
		}
		else {
			dsep = '.';
			tsep = ',';
		}
	}
	
	if (sep) {
		int32 i, digits = iPart ? ((int32)log10((double)iPart) + 1) : 1;
		int32 iPos = digits + ((digits - 1) / 3);
		for (i = 0; i < iPos; i++) {
			if ((i % 4) == 3) {
				buffer[iPos - i - 1] = tsep;
			}
			else {
				buffer[iPos - i - 1] = (iPart % 10) + '0';
				iPart /= 10LL;
			}
		}
		p += iPos;
		*p = '\0';
		len = iPos;
	}
	else {
#ifdef __CL_WIN32__
		len = swprintf(buffer, 63, L"%I64d", iPart);
#else
		len = swprintf(buffer, 63, L"%lld", iPart);
#endif
		p += len;
	}
	
	if (precision) {
		int64 mask = fPart >> 63LL;
		fPart = (fPart ^ mask) - mask;

		*p++ = dsep;
		int32 fPos = 0;
		mask = CL_DECIMAL_UNIT / 10;
		do {
			*p++ = '0' + ((fPart / mask) % 10);
			if (((fPart % mask) == 0) || (++fPos >= precision))
				break;
			mask /= 10;
		} while (fPos < 6);
		while (fPos < precision) {
			*p++ = '0';
			fPos++;
		}
		len += fPos + 1;
		*p = '\0';
	}
	if ((width) && (width > len)) {
		memmove(buffer + (width - len), buffer, (len + 1) * sizeof(wchar_t));
		for (int32 i = 0; i < width - len; i++) {
			buffer[i] = padzero ? '0' : ' ';
		}
		len = width;
	}
	if (((int64)self->fValue != 0) && (neg)) {
		memmove(buffer + 1, buffer, (len + 1) * sizeof(wchar_t));
		p = buffer;
		while (*(p + 1) == ' ')
			p++;
		*p = '-';
		len++;
	}
	
	return PyUnicode_FromWideChar(buffer, len);
}


static MGA::DecimalObject *
MGA_Decimal_ceil(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	static char *kwlist[] = { "value", NULL };
	MGA::DecimalObject *value = NULL;
	MGA::DecimalObject *result = NULL;
	bool dealloc = false;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O&", kwlist, MGA::ConvertDecimal, &value))
		return NULL;
	
	if (!value) {
		value = MGA::DecimalObject::Allocate();
		value->fValue = 1;
		dealloc = true;
	}
	if (value->fValue == 0) {
		if (dealloc)
			Py_DECREF(value);
		PyErr_SetString(PyExc_ZeroDivisionError, "ceil operand cannot be zero");
		return NULL;
	}
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue.Ceil(value->fValue);
	
	if (dealloc)
		Py_DECREF(value);
	
	return result;
}


static MGA::DecimalObject *
MGA_Decimal_floor(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	static char *kwlist[] = { "value", NULL };
	MGA::DecimalObject *value = NULL;
	MGA::DecimalObject *result = NULL;
	bool dealloc = false;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O&", kwlist, MGA::ConvertDecimal, &value))
		return NULL;
	
	if (!value) {
		value = MGA::DecimalObject::Allocate();
		value->fValue = 1;
		dealloc = true;
	}
	if (value->fValue == 0) {
		if (dealloc)
			Py_DECREF(value);
		PyErr_SetString(PyExc_ZeroDivisionError, "floor operand cannot be zero");
		return NULL;
	}
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue.Floor(value->fValue);
	
	if (dealloc)
		Py_DECREF(value);
	
	return result;
}


static MGA::DecimalObject *
MGA_Decimal_round(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	static char *kwlist[] = { "value", NULL };
	MGA::DecimalObject *value = NULL;
	MGA::DecimalObject *result = NULL;
	bool dealloc = false;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O&", kwlist, MGA::ConvertDecimal, &value))
		return NULL;
	
	if (!value) {
		value = MGA::DecimalObject::Allocate();
		value->fValue = 1;
		dealloc = true;
	}
	if (value->fValue == 0) {
		if (dealloc)
			Py_DECREF(value);
		PyErr_SetString(PyExc_ZeroDivisionError, "round operand cannot be zero");
		return NULL;
	}
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue.Round(value->fValue);
	
	if (dealloc)
		Py_DECREF(value);
	
	return result;
}


static MGA::DecimalObject *
MGA_Decimal___round__(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	static char *kwlist[] = { "digits", NULL };
	int digits = 0;
	MGA::DecimalObject *result = NULL;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|i", kwlist, &digits))
		return NULL;
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue.Round(digits);
	
	return result;
}


static MGA::DecimalObject *
MGA_Decimal_multiply(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	static char *kwlist[] = { "other", "value", "mode", NULL };
	MGA::DecimalObject *other, *result;
	MGA::DecimalObject *value = NULL;
	int mode = CL_Decimal::ROUND;
	bool dealloc = false;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&|O&i", kwlist, MGA::ConvertDecimal, &other, MGA::ConvertDecimal, &value, &mode))
		return NULL;
	
	if (!value) {
		value = MGA::DecimalObject::Allocate();
		value->fValue = 1;
		dealloc = true;
	}
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue.Multiply(other->fValue, value->fValue, (CL_Decimal::RoundType)mode);
	
	if (dealloc)
		Py_DECREF(value);
	Py_DECREF(other);
	
	return result;
}


static MGA::DecimalObject *
MGA_Decimal_divide(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	static char *kwlist[] = { "other", "value", "mode", NULL };
	MGA::DecimalObject *other, *result;
	MGA::DecimalObject *value = NULL;
	int mode = CL_Decimal::ROUND;
	bool dealloc = false;

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O&|O&i", kwlist, MGA::ConvertDecimal, &other, MGA::ConvertDecimal, &value, &mode))
		return NULL;
	
	if (!value) {
		value = MGA::DecimalObject::Allocate();
		value->fValue = 1;
		dealloc = true;
	}
	if (value->fValue == 0) {
		if (dealloc)
			Py_DECREF(value);
		PyErr_SetString(PyExc_ZeroDivisionError, "decimal division");
		return NULL;
	}
	
	result = MGA::DecimalObject::Allocate();
	result->fValue = self->fValue.Divide(other->fValue, value->fValue, (CL_Decimal::RoundType)mode);
	
	if (dealloc)
		Py_DECREF(value);
	Py_DECREF(other);
	
	return result;
}


static MGA::DecimalObject *
MGA_Decimal_copy(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	MGA::DecimalObject *value;
	
	value = MGA::DecimalObject::Allocate();
	value->fValue = self->fValue;
	
	return value;
}


static PyObject *
MGA_Decimal_reduce(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	PyObject *tuple = PyTuple_New(2);
	PyObject *arguments = PyTuple_New(1);
	PyTuple_SET_ITEM(arguments, 0, MGA_Decimal_str(self));
	Py_INCREF(&MGA::DecimalType);
	PyTuple_SET_ITEM(tuple, 0, (PyObject *)&MGA::DecimalType);
	PyTuple_SET_ITEM(tuple, 1, arguments);
	return tuple;
}


static PyObject *
MGA_Decimal_set_locale(MGA::DecimalObject *self, PyObject *args, PyObject *kwds)
{
	MGA::MODULE_STATE *state = GET_STATE();
	static char *kwlist[] = { "lang", NULL };
	const char *lang;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &lang))
		return NULL;
	
	if (state)
		state->fLanguage = lang;

	Py_RETURN_NONE;
}


static MGA::DecimalObject *
MGA_Decimal_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	return MGA::DecimalObject::Allocate();
}


static void
MGA_Decimal_dealloc(MGA::DecimalObject *self)
{
	self->~DecimalObject();
	Py_TYPE(self)->tp_free((PyObject*)self);
}


/** Vtable for MGA.Decimal numeric operations. */
static PyNumberMethods MGA_Decimal_as_number = {
	(binaryfunc)MGA_Decimal_add,			/* nb_add */
	(binaryfunc)MGA_Decimal_sub,			/* nb_subtract */
	(binaryfunc)MGA_Decimal_mul,			/* nb_multiply */
#if !PY3K
	(binaryfunc)MGA_Decimal_classic_div,	/* nb_divide */
#endif
	(binaryfunc)MGA_Decimal_rem,			/* nb_remainder */
	(binaryfunc)MGA_Decimal_divmod,			/* nb_divmod */
	(ternaryfunc)MGA_Decimal_pow,			/* nb_power */
	(unaryfunc)MGA_Decimal_neg,				/* nb_negative */
	(unaryfunc)MGA_Decimal_pos,				/* nb_positive */
	(unaryfunc)MGA_Decimal_abs,				/* nb_absolute */
	(inquiry)MGA_Decimal_nonzero,			/* nb_nonzero */
	0,										/* nb_invert */
	0,										/* nb_lshift */
	0,										/* nb_rshift */
	0,										/* nb_and */
	0,										/* nb_xor */
	0,										/* nb_or */
#if !PY3K
	(coercion)MGA_Decimal_coerce,			/* nb_coerce */
#endif
	(unaryfunc)MGA_Decimal_int,				/* nb_int */
#if PY3K
	0,										/* nb_reserved */
#else
	(unaryfunc)MGA_Decimal_long,			/* nb_long */
#endif
	(unaryfunc)MGA_Decimal_float,			/* nb_float */
#if !PY3K
	0,										/* nb_oct */
	0,										/* nb_hex */
#endif
	0,										/* nb_inplace_add */
	0,										/* nb_inplace_subtract */
	0,										/* nb_inplace_multiply */
#if !PY3K
	0,										/* nb_inplace_divide */
#endif
	0,										/* nb_inplace_remainder */
	0,										/* nb_inplace_power */
	0,										/* nb_inplace_lshift */
	0,										/* nb_inplace_rshift */
	0,										/* nb_inplace_and */
	0,										/* nb_inplace_xor */
	0,										/* nb_inplace_or */
	(binaryfunc)MGA_Decimal_floor_div,		/* nb_floor_divide */
	(binaryfunc)MGA_Decimal_div,			/* nb_true_divide */
	0,										/* nb_inplace_floor_divide */
	0,										/* nb_inplace_true_divide */
};


static PyMethodDef MGA_Decimal_methods[] = {
	{	"format",			(PyCFunction)MGA_Decimal_format,			METH_VARARGS | METH_KEYWORDS,	"format([precision, width, sep, padzero]) -> str\n\nFormats the number into a string with specified precision." },
	{	"ceil",				(PyCFunction)MGA_Decimal_ceil,				METH_VARARGS | METH_KEYWORDS,	"ceil([value]) -> Decimal\n\nReturns number rounded up to given value." },
	{	"floor",			(PyCFunction)MGA_Decimal_floor,				METH_VARARGS | METH_KEYWORDS,	"floor([value]) -> Decimal\n\nReturns number rounded down to given value." },
	{	"round",			(PyCFunction)MGA_Decimal_round,				METH_VARARGS | METH_KEYWORDS,	"round([value]) -> Decimal\n\nReturns number rounded to given value." },
	{	"multiply",			(PyCFunction)MGA_Decimal_multiply,			METH_VARARGS | METH_KEYWORDS,	"multiply(other [, value, mode])\n\nMultiplies and rounds number by a given value using mode for rounding." },
	{	"divide",			(PyCFunction)MGA_Decimal_divide,			METH_VARARGS | METH_KEYWORDS,	"divide(other [, value, mode])\n\nMultiplies and rounds number by a given value using mode for rounding." },
	{	"__copy__",			(PyCFunction)MGA_Decimal_copy,				METH_VARARGS | METH_KEYWORDS,	"__copy__() -> Decimal\n\nReturns a copy of the decimal." },
	{	"__deepcopy__",		(PyCFunction)MGA_Decimal_copy,				METH_VARARGS | METH_KEYWORDS,	"__deepcopy__() -> Decimal\n\nReturns a copy of the decimal." },
	{	"__reduce__",		(PyCFunction)MGA_Decimal_reduce,			METH_VARARGS | METH_KEYWORDS,	"__reduce__() -> tuple\n\nReduce method for pickling support." },
	{	"__round__",		(PyCFunction)MGA_Decimal___round__,			METH_VARARGS | METH_KEYWORDS,	"__round__([digits]) -> Decimal\n\nReturns number rounded to given value." },
	{	"set_locale",		(PyCFunction)MGA_Decimal_set_locale,		METH_VARARGS | METH_KEYWORDS | METH_CLASS,		"set_locale(lang)\n\nSets the current locale for decimal format." },
	{	NULL }
};


/** Vtable describing the MGA.Decimal type. */
PyTypeObject MGA::DecimalType = {
	PyVarObject_HEAD_INIT(NULL, 0)
    "kongalib.Decimal",						/* tp_name */
    sizeof(MGA::DecimalObject),				/* tp_basicsize */
	0,										/* tp_itemsize */
	(destructor)MGA_Decimal_dealloc,		/* tp_dealloc */
	0,										/* tp_print */
	0,										/* tp_getattr */
	0,										/* tp_setattr */
	0,										/* tp_compare */
	(reprfunc)MGA_Decimal_str,				/* tp_repr */
	&MGA_Decimal_as_number,					/* tp_as_number */
	0,										/* tp_as_sequence */
	0,										/* tp_as_mapping */
	(hashfunc)MGA_Decimal_hash,				/* tp_hash */
	0,										/* tp_call */
	(reprfunc)MGA_Decimal_str,				/* tp_str */
	0,										/* tp_getattro */
	0,										/* tp_setattro */
	0,										/* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,						/* tp_flags */
	"Decimal objects",						/* tp_doc */
	0,										/* tp_traverse */
	0,										/* tp_clear */
	(richcmpfunc)MGA_Decimal_richcompare,	/* tp_richcompare */
	0,										/* tp_weaklistoffset */
	0,										/* tp_iter */
	0,										/* tp_iternext */
	MGA_Decimal_methods,					/* tp_methods */
	0,										/* tp_members */
	0,										/* tp_getset */
	0,										/* tp_base */
	0,										/* tp_dict */
	0,										/* tp_descr_get */
	0,										/* tp_descr_set */
	0,										/* tp_dictoffset */
	(initproc)MGA_Decimal_init,				/* tp_init */
	0,										/* tp_alloc */
	(newfunc)MGA_Decimal_new,				/* tp_new */
};


MGA::DecimalObject *
MGA::DecimalObject::Allocate()
{
	return new (DecimalType.tp_alloc(&DecimalType, 0)) MGA::DecimalObject();
}


int
MGA::ConvertDecimal(PyObject *object, MGA::DecimalObject **decimal)
{
	CL_Decimal value;
	if (PyObject_TypeCheck(object, &MGA::DecimalType)) {
		*decimal = (MGA::DecimalObject *)object;
		Py_INCREF(object);
		return 1;
	}
#if !PY3K
	else if (PyInt_Check(object)) {
		value = (int32)PyInt_AS_LONG(object);
	}
#endif
	else if (PyLong_Check(object)) {
		PyObject *o = PyObject_Str(object);
		bool invalid;
#if PY3K
		value = CL_Decimal::FromString(string(PyUnicode_AsUTF8(o)), &invalid);
#else
		value = CL_Decimal::FromString(string(PyString_AS_STRING(o)), &invalid);
#endif
		Py_DECREF(o);
		if (invalid) {
			PyErr_SetString(PyExc_ValueError, "Invalid Decimal object");
			return 0;
		}
	}
	else if (PyFloat_Check(object)) {
		value = PyFloat_AS_DOUBLE(object);
	}
	else if (PyNumber_Check(object)) {
		PyObject *number = PyNumber_Float(object);
		if (number) {
			value = PyFloat_AS_DOUBLE(number);
			Py_DECREF(number);
		}
		else
			return 0;
	}
	else if ((PyBytes_Check(object)) || (PyUnicode_Check(object))) {
		bool overflow;
		if ((!MGA_Decimal_from_string(value, object, &overflow)) || (overflow)) {
			PyErr_SetString(PyExc_ValueError, "Invalid Decimal object");
			return 0;
		}
	}
	else {
		PyErr_SetString(PyExc_ValueError, "Expected Decimal object");
		return 0;
	}
	*decimal = MGA::DecimalObject::Allocate();
	(*decimal)->fValue = value;
	return 1;
}

