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


/*
 *	Primitive del protocollo IPC per un client scritto in Python (kongalib nel browser, dove il
 *	trasporto TCP di MGA_Client non esiste): codifica dei dati CLU e cifrari, presi dal nucleo
 *	di ebpr così come li usa CL_TCPClient. Presenti in entrambe le build del modulo.
 */

#include "module.h"

#include <ebpr/ipc.h>


/**
 *	_clu_encode(dict) -> bytes: codifica un dizionario come tabella CLU, nel formato con cui
 *	viaggia nei pacchetti DATA del protocollo.
 */
PyObject *
MGA::CLU_Encode(PyObject *self, PyObject *args)
{
	PyObject *object;
	if (!PyArg_ParseTuple(args, "O!", &PyDict_Type, &object))
		return NULL;

	MGA::MODULE_STATE *state = (MGA::MODULE_STATE *)PyModule_GetState(self);
	CLU_Table table;
	MGA::Table_FromPy(state, object, &table);
	if (PyErr_Occurred())
		return NULL;

	CL_Blob data;
	table.Flatten(data);
	return PyBytes_FromStringAndSize((const char *)data.GetDataForRead(), data.GetSize());
}


/**
 *	_clu_decode(bytes) -> dict: decodifica una tabella CLU ricevuta dal server; dati troncati
 *	o non validi sollevano ValueError.
 */
PyObject *
MGA::CLU_Decode(PyObject *self, PyObject *args)
{
	Py_buffer view;
	if (!PyArg_ParseTuple(args, "y*", &view))
		return NULL;

	MGA::MODULE_STATE *state = (MGA::MODULE_STATE *)PyModule_GetState(self);
	CL_Blob data;
	data.Set((const char *)view.buf, (uint32)view.len);
	PyBuffer_Release(&view);
	data.Rewind();

	CLU_Table table;
	if (!table.Unflatten(data)) {
		PyErr_SetString(PyExc_ValueError, "invalid CLU data");
		return NULL;
	}
	return MGA::Table_FromCLU(state, &table);
}


static void
cipher_dealloc(MGA::CipherObject *self)
{
	PyTypeObject *type = Py_TYPE(self);
	self->~CipherObject();
	type->tp_free((PyObject*)self);
	Py_DECREF(type);
}


/**
 *	_Cipher(flags, key): il cifrario di una connessione. \e flags sono i bit dell'header della
 *	risposta AUTH (come in CL_TCPClient vale il primo tra TEA, Blowfish e AES; nessuno vuol dire
 *	nessuna cifratura), \e key i byte della chiave (ID del client e ID del server).
 */
static MGA::CipherObject *
cipher_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "flags", "key", NULL };
	unsigned int flags;
	Py_buffer view;

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "Iy*", kwlist, &flags, &view))
		return NULL;

	MGA::CipherObject *self = new (type->tp_alloc(type, 0)) MGA::CipherObject();
	if (flags & CL_IPC_TEA_CRYPTING)
		self->fCipher = new CL_TEACipher;
	else if (flags & CL_IPC_BLOWFISH_CRYPTING)
		self->fCipher = new CL_BlowfishCipher;
	else if (flags & CL_IPC_AES_CRYPTING)
		self->fCipher = new CL_AESCipher;
	else
		self->fCipher = new CL_Cipher;

	CL_Blob key;
	key.Set((const char *)view.buf, (uint32)view.len);
	PyBuffer_Release(&view);
	key.Rewind();
	self->fCipher->SetKey(key);
	return self;
}


static PyObject *
cipher_apply(MGA::CipherObject *self, PyObject *args, bool encrypt)
{
	Py_buffer view;
	if (!PyArg_ParseTuple(args, "y*", &view))
		return NULL;

	CL_Blob data;
	data.Set((const char *)view.buf, (uint32)view.len);
	PyBuffer_Release(&view);
	data.Rewind();

	Py_BEGIN_ALLOW_THREADS
	if (encrypt)
		self->fCipher->Encrypt(data);
	else
		self->fCipher->Decrypt(data);
	Py_END_ALLOW_THREADS

	return PyBytes_FromStringAndSize((const char *)data.GetDataForRead(), data.GetSize());
}


static PyObject *
cipher_encrypt(MGA::CipherObject *self, PyObject *args)
{
	return cipher_apply(self, args, true);
}


static PyObject *
cipher_decrypt(MGA::CipherObject *self, PyObject *args)
{
	return cipher_apply(self, args, false);
}


static PyMethodDef cipher_methods[] = {
	{	"encrypt",					(PyCFunction)cipher_encrypt,		METH_VARARGS,					"encrypt(data) -> bytes\n\nEncrypts data as sent to the server." },
	{	"decrypt",					(PyCFunction)cipher_decrypt,		METH_VARARGS,					"decrypt(data) -> bytes\n\nDecrypts data as received from the server (a whole payload or one packet of it)." },
	{	NULL }
};


static PyType_Slot Cipher_slots[] = {
	{ Py_tp_dealloc, (void *)cipher_dealloc },
	{ Py_tp_doc, (void *)"Cipher of an IPC connection" },
	{ Py_tp_methods, (void *)cipher_methods },
	{ Py_tp_new, (void *)cipher_new },
	{ 0, NULL }
};

PyType_Spec Cipher_spec = {
	"_kongalib._Cipher",
	sizeof(MGA::CipherObject),
	0,
	Py_TPFLAGS_DEFAULT,
	Cipher_slots,
};
