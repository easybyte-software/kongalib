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
 *	trasporto TCP di MGA_Client non esiste): codifica dei dati CLU, cifrari e la sessione Noise del
 *	canale sicuro, presi dal nucleo di ebpr così come li usa CL_TCPClient. Presenti in entrambe le
 *	build del modulo.
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


static void
noise_dealloc(MGA::NoiseObject *self)
{
	PyTypeObject *type = Py_TYPE(self);
	self->~NoiseObject();
	type->tp_free((PyObject*)self);
	Py_DECREF(type);
}


/**
 *	_NoiseSession(static_key=None): la sessione Noise del canale sicuro di una connessione
 *	(Noise_NX_25519_ChaChaPoly_BLAKE2b, vedi CL_NoiseSession). Senza \e static_key è il lato del
 *	client (initiator); con la chiave privata statica di un server (32 byte) quello del server, per
 *	le prove.
 */
static MGA::NoiseObject *
noise_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	char *kwlist[] = { "static_key", NULL };
	Py_buffer view = { 0 };

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|z*", kwlist, &view))
		return NULL;
	if ((view.buf) && (view.len != CL_NOISE_KEY_SIZE)) {
		PyBuffer_Release(&view);
		PyErr_SetString(PyExc_ValueError, "static_key must be 32 bytes");
		return NULL;
	}

	MGA::NoiseObject *self = new (type->tp_alloc(type, 0)) MGA::NoiseObject();
	self->fSession = new CL_NoiseSession(view.buf ? CL_NoiseSession::RESPONDER : CL_NoiseSession::INITIATOR);
	if (view.buf) {
		self->fSession->SetStaticKey((const uint8 *)view.buf);
		PyBuffer_Release(&view);
	}
	return self;
}


static PyObject *
noise_error(CL_Status status)
{
	PyErr_Format(PyExc_ValueError, "Noise session failed (%d)", (int)status);
	return NULL;
}


static PyObject *
noise_start(MGA::NoiseObject *self, PyObject *args)
{
	Py_buffer view;
	if (!PyArg_ParseTuple(args, "y*", &view))
		return NULL;
	CL_Status status = self->fSession->Start(view.buf, (uint32)view.len);
	PyBuffer_Release(&view);
	if (status != CL_OK)
		return noise_error(status);
	Py_RETURN_NONE;
}


static PyObject *
noise_write_handshake(MGA::NoiseObject *self, PyObject *args)
{
	Py_buffer view = { 0 };
	if (!PyArg_ParseTuple(args, "|y*", &view))
		return NULL;
	CL_Blob message;
	CL_Status status = self->fSession->WriteHandshake(message, view.buf, (uint32)view.len);
	if (view.buf)
		PyBuffer_Release(&view);
	if (status != CL_OK)
		return noise_error(status);
	return PyBytes_FromStringAndSize((const char *)message.GetDataForRead(), message.GetSize());
}


static PyObject *
noise_read_handshake(MGA::NoiseObject *self, PyObject *args)
{
	Py_buffer view;
	if (!PyArg_ParseTuple(args, "y*", &view))
		return NULL;
	CL_Blob payload;
	CL_Status status = self->fSession->ReadHandshake(view.buf, (uint32)view.len, &payload);
	PyBuffer_Release(&view);
	if (status != CL_OK)
		return noise_error(status);
	return PyBytes_FromStringAndSize((const char *)payload.GetDataForRead(), payload.GetSize());
}


static PyObject *
noise_write_record(MGA::NoiseObject *self, PyObject *args)
{
	Py_buffer view;
	if (!PyArg_ParseTuple(args, "y*", &view))
		return NULL;
	CL_Blob record;
	CL_Status status = self->fSession->WriteRecord(view.buf, (uint32)view.len, record);
	PyBuffer_Release(&view);
	if (status != CL_OK)
		return noise_error(status);
	return PyBytes_FromStringAndSize((const char *)record.GetDataForRead(), record.GetSize());
}


static PyObject *
noise_decrypt(MGA::NoiseObject *self, PyObject *args)
{
	Py_buffer view;
	if (!PyArg_ParseTuple(args, "y*", &view))
		return NULL;
	if (view.len < CL_NOISE_TAG_SIZE) {
		PyBuffer_Release(&view);
		return noise_error(CL_BAD_STREAM);
	}
	PyObject *plain = PyBytes_FromStringAndSize(NULL, view.len - CL_NOISE_TAG_SIZE);
	CL_Status status = plain ? self->fSession->Decrypt(view.buf, (uint32)view.len, PyBytes_AS_STRING(plain)) : CL_OUT_OF_MEMORY;
	PyBuffer_Release(&view);
	if (status != CL_OK) {
		Py_XDECREF(plain);
		return plain ? noise_error(status) : NULL;
	}
	return plain;
}


static PyObject *
noise_get_remote_static_key(MGA::NoiseObject *self, PyObject *args)
{
	const uint8 *key = self->fSession->GetRemoteStaticKey();
	if (!key)
		Py_RETURN_NONE;
	return PyBytes_FromStringAndSize((const char *)key, CL_NOISE_KEY_SIZE);
}


static PyObject *
noise_get_handshake_hash(MGA::NoiseObject *self, PyObject *args)
{
	const uint8 *hash = self->fSession->GetHandshakeHash();
	if (!hash)
		Py_RETURN_NONE;
	return PyBytes_FromStringAndSize((const char *)hash, CL_NOISE_HASH_SIZE);
}


static PyObject *
noise_generate_key_pair(PyObject *cls, PyObject *args)
{
	uint8 privateKey[CL_NOISE_KEY_SIZE], publicKey[CL_NOISE_KEY_SIZE];
	if (CL_NoiseSession::GenerateKeyPair(privateKey, publicKey) != CL_OK)
		return noise_error(CL_ERROR);
	PyObject *result = Py_BuildValue("(y#y#)", (const char *)privateKey, (Py_ssize_t)CL_NOISE_KEY_SIZE, (const char *)publicKey, (Py_ssize_t)CL_NOISE_KEY_SIZE);
	CL_MEMSET(privateKey, 0, sizeof(privateKey));
	return result;
}


static PyMethodDef noise_methods[] = {
	{	"start",					(PyCFunction)noise_start,					METH_VARARGS,				"start(prologue)\n\nStarts the handshake; both sides must pass the same prologue." },
	{	"write_handshake",			(PyCFunction)noise_write_handshake,			METH_VARARGS,				"write_handshake(payload=b'') -> bytes\n\nThe next handshake message of this side." },
	{	"read_handshake",			(PyCFunction)noise_read_handshake,			METH_VARARGS,				"read_handshake(message) -> bytes\n\nReads the other side's handshake message, returning its payload; ValueError if forged or malformed." },
	{	"write_record",				(PyCFunction)noise_write_record,			METH_VARARGS,				"write_record(packet) -> bytes\n\nThe transport record of a packet: its big endian 16 bits size, then the packet encrypted." },
	{	"decrypt",					(PyCFunction)noise_decrypt,					METH_VARARGS,				"decrypt(message) -> bytes\n\nDecrypts the message of a transport record (without its size); ValueError if forged, replayed or out of order." },
	{	"get_remote_static_key",	(PyCFunction)noise_get_remote_static_key,	METH_NOARGS,				"get_remote_static_key() -> bytes or None\n\nThe server's public key, once the handshake has read it." },
	{	"get_handshake_hash",		(PyCFunction)noise_get_handshake_hash,		METH_NOARGS,				"get_handshake_hash() -> bytes or None\n\nThe handshake hash, once the handshake is done." },
	{	"generate_key_pair",		(PyCFunction)noise_generate_key_pair,		METH_NOARGS | METH_STATIC,	"generate_key_pair() -> (private, public)\n\nA new X25519 key pair." },
	{	NULL }
};


static PyType_Slot Noise_slots[] = {
	{ Py_tp_dealloc, (void *)noise_dealloc },
	{ Py_tp_doc, (void *)"Noise session of an IPC connection's secure channel" },
	{ Py_tp_methods, (void *)noise_methods },
	{ Py_tp_new, (void *)noise_new },
	{ 0, NULL }
};

PyType_Spec Noise_spec = {
	"_kongalib._NoiseSession",
	sizeof(MGA::NoiseObject),
	0,
	Py_TPFLAGS_DEFAULT,
	Noise_slots,
};
