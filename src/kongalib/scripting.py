# -*- coding: utf-8 -*-
#  _                           _ _ _
# | |                         | (_) |
# | | _____  _ __   __ _  __ _| |_| |__
# | |/ / _ \| '_ \ / _` |/ _` | | | '_ \
# |   < (_) | | | | (_| | (_| | | | |_) |
# |_|\_\___/|_| |_|\__, |\__,_|_|_|_.__/
#                   __/ |
#                  |___/
#
# Konga client library, by EasyByte Software
#
# https://github.com/easybyte-software/kongalib


from __future__ import print_function
from __future__ import absolute_import

from kongalib import Error
from _kongalib import get_application_log_path, set_interpreter_timeout, get_interpreter_timeout, get_interpreter_time_left, _set_process_foreground

import sys
import os
import atexit
import io
import threading
import multiprocessing
import multiprocessing.connection
import asyncio
import signal
import logging
import logging.handlers
import time


DEBUG = False

gConnFamily = None
gConnFamilyOverride = False

_DLL_PATHS = []


class BadConnection(Exception):
	def __init__(self):
		self._bad_connection = True


class InterpreterTimeout(Exception):
	pass



class InterpreterError(Exception):
	def __init__(self, exc_info):
		self._exc_info = exc_info
	def get_exc_info(self):
		return self._exc_info



def debug_log(text):
	try:
		_logger.debug(text)
	except:
		try:
			sys.__stderr__.write('%s\n' % text)
		except:
			pass
	# sys.__stderr__.write(text + '\n')



class _TimeoutBlocker(object):
	def __init__(self):
		self.timeout = 0
		self.lock = threading.RLock()
	def __enter__(self):
		try:
			self.timeout = get_interpreter_time_left() or 0
			set_interpreter_timeout(0)
		except:
			self.timeout = 0
		self.lock.acquire()
	def __exit__(self, exc_type, exc_value, exc_traceback):
		self.lock.release()
		if _State.restore_timeout:
			try:
				set_interpreter_timeout(self.timeout)
			except:
				pass
		else:
			_State.restore_timeout = True


class Proxy(object):
	def __init__(self):
		self._conn = None
		self._lock = _TimeoutBlocker()

	def _initialize(self):
		conn_type = str(sys.argv.pop(1))
		address = str(sys.argv.pop(1))
		if conn_type == 'AF_INET':
			colon = address.rfind(':')
			address = (address[:colon], int(address[colon+1:]))
		debug_log("[Proxy] init: %s" % repr(address))
		try:
			self._conn = multiprocessing.connection.Client(address, conn_type)
		except:
			import traceback
			_logger.error("[Proxy] init error: %s" % traceback.format_exc())
			raise
		debug_log("[Proxy] connection established")

	def is_valid(self):
		return self._conn is not None
	
	def close(self):
		if self._conn is not None:
			sys.stdout.flush()
			sys.stderr.flush()
			self._conn.close()
			self._conn = None
		debug_log("[Proxy] connection closed")
	
	def __getattr__(self, name):
		return _MethodHandler(self._conn, self._lock, name)


class _State(object):
	handler = None
	controller = None
	io = []
	restore_timeout = True


proxy = Proxy()
_logger = logging.getLogger("script")


def timeout_handler():
	if proxy.builtin.handle_timeout():
		raise InterpreterTimeout
	else:
		timeout = _State.controller.timeout
		set_interpreter_timeout(timeout)



def init_interpreter():
	_State.io.append((sys.stdout, sys.stderr, sys.stdin))
	try:
		proxy._initialize()
		sys.stdout = _ProxyStdOut()
		sys.stderr = _ProxyStdErr()
	#   sys.stdout = io.TextIOWrapper(_ProxyStdOut(), 'utf-8', line_buffering=True)
	#   sys.stderr = io.TextIOWrapper(_ProxyStdErr(), 'utf-8', line_buffering=True)
		sys.stdin = _ProxyStdIn()
		sys.prefix, sys.exec_prefix = proxy.builtin.get_prefixes()
		sys.is_kongalib_interpreter = True
	except:
		raise BadConnection()

	import getpass
	getpass.getpass = proxy.builtin.getpass

	def excepthook(type, value, tb):
		import traceback
		# debug_log('EXCEPTHOOK:\n%s' % '\n'.join(traceback.format_exception(type, value, tb)))
		tb = traceback.extract_tb(tb)
		def do_filter(entry):
			filename = entry[0].replace('\\', '/')
			if filename.endswith('kongalib/scripting.py'):
				return False
			return True
		tb = list(filter(do_filter, tb))
		try:
			proxy.builtin.print_exception(type, value, tb)
		except:
			debug_log('proxy.builtin.print_exception exception:\n%s' % traceback.format_exc())
	sys.excepthook = excepthook

	def close_proxy():
		try:
			proxy.close()
		except:
			pass
	atexit.register(close_proxy)


def exit_interpreter():
	sys.stdout, sys.stderr, sys.stdin = _State.io.pop()
	# proxy.close()


class _Controller(threading.Thread):
	QUIT_REQUEST =  (None, None, None, None, None)

	def __init__(self, conn, sem):
		self.conn = conn
		self.sem = sem
		self.lock = threading.RLock()
		self.request_cond = threading.Condition(self.lock)
		self.request = None
		self.exc_info = None
		self.timeout = None
		def terminate(signo=None, stack_frame=None):
			self.execute(*_Controller.QUIT_REQUEST)
		signal.signal(signal.SIGTERM, terminate)
		super(_Controller, self).__init__()

	def get_execute_request(self):
		with self.lock:
			while not self.request_cond.wait(0.5):
				if self.request is not None:
					break
			request = self.request
			self.request = None
			return request

	def run(self):
		name = None
		while name != 'exit':
			try:
				ready = multiprocessing.connection.wait([ self.conn ], 0.5)
				if not ready:
					if self.request == _Controller.QUIT_REQUEST:
						break
					continue
				data = self.conn.recv()
				handler, name, args, kwargs = data
				msg = repr(args)
				if len(msg) > 80:
					msg = msg[:80] + '[...]'
			except IOError:
				return
			except EOFError:
				return
			except KeyboardInterrupt:
				return
			result = getattr(self, name)(*args, **kwargs)
			try:
				self.conn.send((None, result))
			except IOError:
				return
			except EOFError:
				return
			except KeyboardInterrupt:
				return
			except:
				import traceback
				_logger.debug(traceback.format_exc())
		sys.exit(0)

	def set_timeout(self, timeout, restore=True):
		_State.restore_timeout = restore
		self.timeout = timeout
		return set_interpreter_timeout(timeout)

	def get_time_left(self):
		return get_interpreter_time_left() or 0

	def execute(self, args, path, timeout, script, cwd):
		with self.lock:
			self.request = (args, path, timeout, script, cwd)
			self.request_cond.notify()

	def set_exc_info(self, exc_info):
		with self.lock:
			self.exc_info = exc_info

	def get_exc_info(self):
		with self.lock:
			return self.exc_info

	def exit(self):
		self.sem.release()



def _trampoline(conn, sem, foreground, env, dll_paths, queue, level):
	logging.getLogger().setLevel(level)
	logger = logging.getLogger('script._trampoline')
	handler = logging.handlers.QueueHandler(queue)
	handler.setLevel(level)
	logger.addHandler(handler)
	logger.debug('entering interpreter process')
	try:
		_set_process_foreground(foreground)
		for path in dll_paths:
			try:
				os.add_dll_directory(path)
				logger.debug('added DLL directory: %s' % path)
			except:
				if sys.platform == 'win32':
					logger.error('error adding DLL directory: %s' % path)
		for key, value in (env or {}).items():
			key = str(key)
			value = str(value)
			os.environ[key] = value
			logger.debug('added env variable %s=%s' % (key, value))

		_State.controller = _Controller(conn, sem)
		_State.controller.start()

		while True:
			request = _State.controller.get_execute_request()
			if request == _Controller.QUIT_REQUEST:
				break
			args, path, timeout, script, cwd = request
			sys.argv = args
			sys.path = path
			filename = args[0]
			if cwd:
				os.chdir(cwd)
			init_interpreter()
			try:
				script = compile(script, filename, 'exec', dont_inherit=1)
				exc = None
				_State.controller.set_timeout(timeout)
				exec(script, { '__file__': filename, '__name__': '__main__' })
			except Exception as e:
				import traceback
				exc_type, exc_value, exc_tb = sys.exc_info()
				exc_tb = [ tuple(tb) for tb in traceback.extract_tb(exc_tb) ]
				exc_info = ( exc_type, exc_value, exc_tb )
			else:
				exc_info = None
			_State.controller.set_timeout(0)
			_State.controller.set_exc_info(exc_info)
			exit_interpreter()
			sem.release()
		try:
			conn.close()
			conn = None
		except:
			pass
		_State.controller.join()
	except KeyboardInterrupt:
		logger.debug('user issued a keyboard interrupt')
	except Exception as e:
		import traceback
		logger.critical('unhandled error in interpreter process: %s' % traceback.format_exc())
	finally:
		if conn is not None:
			try:
				conn.close()
			except:
				pass
		logger.debug('exiting interpreter process')
	

class _ControllerProxy(Proxy):
	class NullLocker(object):
		def __enter__(self):
			pass
		def __exit__(self, exc_type, exc_value, exc_traceback):
			pass
	def __init__(self, conn):
		self._conn = conn
		self._lock = _ControllerProxy.NullLocker()


class Interpreter(object):
	def __init__(self, foreground=True, env=None):
		self.proc = None
		self.exc_info = None
		self.conn = None
		self.lock = threading.RLock()
		self.sem = multiprocessing.Semaphore(0)
		self.queue = multiprocessing.Queue()
		self.proxy = None
		self.foreground = foreground
		self.env = env
		self.logger_listener = logging.handlers.QueueListener(self.queue, *logging.getLogger().handlers, respect_handler_level=True)

	def __del__(self):
		with self.lock:
			if self.proc is not None:
				if self.proc.is_alive():
					try:
						self.proxy.exit()
					except:
						pass
				try:
					self.logger_listener.stop()
				except:
					pass

	def ensure_proc(self):
		with self.lock:
			if self.proc is None:
				self.conn, self.client_conn = multiprocessing.Pipe()
				self.proxy = _ControllerProxy(self.conn).controller
				self.logger_listener.start()
				self.proc = multiprocessing.Process(target=_trampoline, args=(self.client_conn, self.sem, self.foreground, self.env, _DLL_PATHS, self.queue, logging.getLogger().level), daemon=True)
				self.proc.start()
				exitcode = self.proc.exitcode
				if exitcode is not None:
					raise RuntimeError('Unable to start interpreter process: exit code %d' % exitcode)

	def execute(self, script=None, filename=None, argv=None, path=None, timeout=None):
		with self.lock:
			self.ensure_proc()
			self.exc_info = None
			args = argv
			if not args:
				args = [ filename or '<script>' ]
			if (script is None) and filename:
				with open(filename, 'r') as f:
					script = f.read()
			try:
				cwd = os.path.dirname(os.path.abspath(filename))
			except:
				cwd = None
			self.proxy.execute(args, path, timeout, script or '', cwd )
			self.lock.release()
			while not self.sem.acquire(False):
				with self.lock:
					if (self.proc is None) or (not self.proc.is_alive()):
						break
				time.sleep(0.05)
			self.lock.acquire()
			if (self.proc is not None) and self.proc.is_alive():
				self.exc_info = self.proxy.get_exc_info()
			if self.exc_info is not None:
				raise InterpreterError(self.exc_info)

	def stop(self):
		with self.lock:
			proc = self.proc
			if proc is not None:
				self.proc = None
				self.lock.release()
				try:
					try:
						proc.terminate()
					except:
						pass
					proc.join(3)
					if proc.is_alive():
						try:
							proc.kill()
						except Exception as e:
							debug_log('Interpreter.stop() failed with error: %s' % str(e))
				finally:
					self.lock.acquire()

	def is_running(self):
		conn = self.conn
		proc = self.proc
		return (conn is None) or ((proc is not None) and proc.is_alive())

	def set_timeout(self, timeout=None, restore=False):
		with self.lock:
			if self.proxy is not None:
				func = self.proxy.set_timeout
			else:
				func = None
		if func is not None:
			return func(timeout, restore)

	def get_time_left(self):
		with self.lock:
			return self.proxy.get_time_left()

	def get_exc_info(self):
		with self.lock:
			return self.exc_info


class _ProxyStdIn(io.StringIO):
	def readline(self, size=-1):
		return proxy.builtin.read_line()


class _ProxyStdOut(io.StringIO):
	def write(self, text):
		proxy.builtin.write_stdout(str(text))
		return len(text)

	def flush(self):
		try:
			proxy.builtin.flush_stdout()
		except:
			pass


class _ProxyStdErr(io.StringIO):
	def write(self, text):
		sys.__stderr__.write(str(text))
		try:
			proxy.builtin.write_stderr(str(text))
		except:
			pass
		return len(text)

	def flush(self):
		try:
			proxy.builtin.flush_stderr()
		except:
			pass



class _MethodHandler(object):
	def __init__(self, conn, lock, name):
		self._conn = conn
		self._lock = lock
		self._name = name
	
	def __getattr__(self, name):
		return _Method(self, name)



class _Method(object):
	def __init__(self, handler, name):
		self.handler = handler
		self.name = name
	
	def __call__(self, *args, **kwargs):
		with self.handler._lock:
			if DEBUG:
				s = time.time()
				debug_log('[Proxy] call: %s' % str((self.handler._name, self.name, args, kwargs)))
			self.handler._conn.send((self.handler._name, self.name, args, kwargs))
			if DEBUG:
				debug_log('[Proxy] call sent in %f secs. Waiting reply: %s' % (time.time() - s, str((self.handler._name, self.name))))
			
			multiprocessing.connection.wait([ self.handler._conn ])
			e, result = self.handler._conn.recv()
			if DEBUG:
				s = time.time()
				debug_log('[Proxy] got reply in %f secs: %s' % (time.time() - s, str((self.handler._name, self.name, result))))
			if e is None:
				return result
			errmsg, errno = e
			if errno is None:
				raise RuntimeError(errmsg)
			else:
				raise Error(errno, errmsg)


class _ServerProxy(threading.Thread):
	def __init__(self, handlers=None):
		self.handlers = handlers or {}
		self.listener = None
		self.conn = None
		super(_ServerProxy, self).__init__()
	
	def start(self):
		if gConnFamilyOverride:
			family = None
		else:
			family = gConnFamily
		try:
			self.listener = multiprocessing.connection.Listener(family=family)
		except:
			raise BadConnection()
		super(_ServerProxy, self).start()

	def stop(self):
		if self.listener is not None:
			self.listener.close()
			self.listener = None
		if self.conn is not None:
			self.conn.close()
		self.handlers = {}
		if self.is_alive():
			self.join()

	def run(self):
		debug_log("[ServerProxy] run")
		try:
			self.conn = self.listener.accept()
			debug_log("[ServerProxy] got proxy")
			while True:
				ready = multiprocessing.connection.wait([ self.conn ], 0.5)
				if ready:
					data = self.conn.recv()
					handler, name, args, kwargs = data
					if handler in self.handlers:
						# debug_log("[kongaprint:%s] %s(%s)" % (handler, name, ', '.join([ repr(arg) for arg in args ] + [ '%s=%s' % (key, repr(value)) for key, value in kwargs.iteritems() ])))
						func = getattr(self.handlers[handler], name, None)
					else:
						func = None
					try:
						if func is None:
							raise RuntimeError('Method "%s" unavailable in this context' % name)
						result = func(*args, **kwargs)
						if asyncio.iscoroutine(result):
							try:
								loop = asyncio.get_running_loop()
							except:
								loop = asyncio.get_event_loop_policy().get_event_loop()
							result = asyncio.run_coroutine_threadsafe(result, loop).result()
						result = (None, result)
					except Exception as e:
						import traceback
						_logger.error("[ServerProxy] method error: %s" % traceback.format_exc())
						# sys.__stderr__.write('SCRIPTING EXCEPTION:\n%s\n' % traceback.format_exc())
						if isinstance(e, Error):
							errno = e.errno
						else:
							errno = None
						result = ((str(e), errno), None)
					finally:
						self.conn.send(result)
		except IOError:
			if self.listener is not None:
				import traceback
				debug_log("[ServerProxy] IOError: %s" % traceback.format_exc())
		except EOFError:
			pass
		finally:
			debug_log("[ServerProxy] exiting")


class BuiltinHandler(object):
	def __init__(self):
		self.__interpreter = None
		self.__exit_funcs = []
	
	def _set_interpreter(self, interpreter):
		self.__interpreter = interpreter
	
	def _get_interpreter(self):
		return self.__interpreter
	
	def write_stdout(self, text):
		sys.__stdout__.write(text)
	
	def write_stderr(self, text):
		sys.__stderr__.write(text)

	def flush_stdout(self):
		pass

	def flush_stderr(self):
		pass
	
	def read_line(self):
		sys.__stdin__.readline()

	def getpass(self, prompt='Password: ', stream=None):
		import getpass
		return getpass.getpass(prompt, stream)
	
	def get_prefixes(self):
		return os.getcwd(), os.getcwd()
	
	def format_exception(self, type, value, tb):
		import traceback
		if not all([ isinstance(x, str) for x in tb ]):
			tb = traceback.format_list(tb)
		text = [ 'Traceback (most recent call last):\n' ] + tb + traceback.format_exception_only(type, value)
		return ''.join(text)
	
	def print_exception(self, type, value, tb):
		print(self.format_exception(type, value, tb))
	
	def get_time_left(self):
		if self.__interpreter is not None:
			return self.__interpreter.get_time_left()
		return 0
	
	def set_timeout(self, timeout=0, restore=False):
		if self.__interpreter is not None:
			return self.__interpreter.set_timeout(timeout, restore)
	
	def handle_timeout(self):
		raise InterpreterTimeout
	
	def noop(self):
		pass

	def atexit(self, func, *args, **kwargs):
		self.__exit_funcs.append((func, args, kwargs))
	
	def _atexit(self):
		while self.__exit_funcs:
			func, args, kwargs = self.__exit_funcs.pop()
			func(*args, **kwargs)


def set_connection_family(family):
	global gConnFamily
	gConnFamily = family


def add_dll_directory(path):
	if path not in _DLL_PATHS:
		_DLL_PATHS.append(path)


def execute(script=None, filename=None, argv=None, path=None, timeout=0, handlers=None, interpreter=None):
	import traceback
	if (script is None) and (filename is None):
		raise ValueError('Either script or filename must be specified')
	debug_log("[ServerProxy] launching...")
	if filename is None:
		filename = '<script>'
	if argv is None:
		argv = [ filename ]
	if interpreter is None:
		interpreter = Interpreter()
	debug_log("[ServerProxy] instantiating ServerProxy")
	_handlers = { 'builtin': BuiltinHandler() }
	_handlers.update(handlers or {})
	_handlers['builtin']._set_interpreter(interpreter)
	while True:
		p = _ServerProxy(_handlers)
		try:
			p.start()
			debug_log("[ServerProxy] listener address is: %s" % repr(p.listener.address))
			conn_type = multiprocessing.connection.address_type(p.listener.address)
			if conn_type == 'AF_INET':
				address = '%s:%d' % tuple(p.listener.address)
			else:
				address = p.listener.address
			argv.insert(1, conn_type)
			argv.insert(2, address)
			debug_log("[ServerProxy] waiting proxy: %s" % repr(argv))

	#     import time
	#     start = time.time()
			interpreter.execute(script, filename, argv, path or [], timeout)
	#     print("Script execution time:", time.time() - start)
		except Exception as e:
			if getattr(e, '_bad_connection', False) and (gConnFamily is not None):
				debug_log("[ServerProxy] bad connection, trying default connection family")
				global gConnFamilyOverride
				gConnFamilyOverride = True
				set_connection_family(None)
				argv[1:3] = []
				continue
			if isinstance(e, InterpreterError):
				type, value, tb = e.get_exc_info()
			else:
				debug_log("[ServerProxy] unhandled execute exception: %s" % traceback.format_exc())
				type, value, tb = sys.exc_info()
				tb = traceback.format_tb(tb)
			def do_filter(entry):
				filename = entry[0].replace('\\', '/')
				if filename.endswith('kongalib/scripting.py') or filename.endswith('__script_host__.py'):
					return False
				return True
			tb = list(filter(do_filter, tb))
			try:
				_handlers['builtin'].print_exception(type, value, tb)
			except:
				debug_log('proxy.builtin.print_exception exception:\n%s' % traceback.format_exc())
		finally:
			_handlers['builtin']._set_interpreter(None)
			interpreter = None
			_handlers['builtin']._atexit()
			try:
				debug_log("[ServerProxy] done")
			finally:
				p.stop()
		break



