from __future__ import print_function
import sys
import glob
import os
import os.path

from setuptools import setup, Extension

import distutils.ccompiler


new_compiler = distutils.ccompiler.new_compiler
def _new_compiler(*args, **kwargs):
	compiler = new_compiler(*args, **kwargs)
	
	if (sys.platform == 'darwin') or (sys.platform.startswith('linux')):
		def _compile_wrapper(func):
			def _wrapper(obj, src, ext, cc_args, extra_postargs, pp_opts):
				if ext == '.c':
					extra_postargs = list(extra_postargs)
					extra_postargs.remove('-std=c++11')
					if '-stdlib=libc++' in extra_postargs:
						extra_postargs.remove('-stdlib=libc++')
				elif (ext == '.cpp') and (sys.platform.startswith('linux')):
					if '-Wstrict-prototypes' in compiler.compiler_so:
						compiler.compiler_so.remove('-Wstrict-prototypes')
				return func(obj, src, ext, cc_args, extra_postargs, pp_opts)
			return _wrapper
		compiler._compile = _compile_wrapper(compiler._compile)
		compiler.language_map['.mm'] = "objc"
		compiler.src_extensions.append(".mm")
	elif sys.platform == 'win32':
		compiler.initialize()
		compiler.compile_options.append('/Zi')
	return compiler

distutils.ccompiler.new_compiler = _new_compiler


konga_sdk = os.environ.get('KONGASDK', None)


if sys.platform == 'darwin':
	sdk = os.environ.get('SDK', None)
	for index, arg in enumerate(sys.argv):
		if arg == '--sdk':
			if index + 1 >= len(sys.argv):
				print('Missing sdk parameter')
				sys.exit(1)
			sdk = sys.argv[index + 1]
			del sys.argv[index:index+2]
			break
		elif arg.startswith('--sdk='):
			sdk = arg[6:].strip()
			del sys.argv[index]
			break

	if sdk is None:
		try:
			sdk = os.path.basename(sorted(glob.glob('/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX*.sdk'))[-1])[6:-4]
		except:
			pass
	if sdk is not None:
		path = '/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX%s.sdk' % sdk
		if not os.path.exists(path):
			print('Error: unknown SDK:', sdk)
			sys.exit(1)
		sdk = path
	else:
		print('Error: no valid SDK found!')
		sys.exit(1)
	macosx_version_min = os.environ.get('MACOSX_DEPLOYMENT_TARGET') or '10.10'
	if konga_sdk is None:
		konga_sdk = '/usr/local'
	cflags = '-g -ggdb -Wno-deprecated-register -Wno-sometimes-uninitialized -Wno-write-strings -fvisibility=hidden -mmacosx-version-min=%s -isysroot %s -I%s/include' % (macosx_version_min, sdk, konga_sdk)
	ldflags = '-Wl,-syslibroot,%s -L%s/lib -framework Cocoa -lkonga_client_s -lebpr_s -liconv -ltidy -mmacosx-version-min=%s -headerpad_max_install_names' % (sdk, konga_sdk, macosx_version_min)
	cflags += ' -stdlib=libc++ -std=c++11 -DPY_SSIZE_T_CLEAN'
	ldflags += ' -stdlib=libc++'
	cflags = cflags.split(' ')
	ldflags = ldflags.split(' ')
	extra_libs = []

elif sys.platform == 'win32':
	cflags = '/EHsc /D_CRT_SECURE_NO_WARNINGS /DPSAPI_VERSION=1 /DPY_SSIZE_T_CLEAN /Zi /wd4244 /wd4005 /wd4267'.split(' ')
	ldflags = '/DEBUG /NODEFAULTLIB:LIBCMT /NODEFAULTLIB:LIBCMTD /ignore:4197 /ignore:4099'.split(' ')
	extra_libs = 'ebpr_s konga_client_s shell32 user32 netapi32 iphlpapi shlwapi advapi32 secur32 ws2_32 psapi bcrypt'.split(' ')
	if konga_sdk is not None:
		cflags.append('/I%s\\Include' % konga_sdk)
		ldflags.append('/LIBPATH:%s\\Lib' % konga_sdk)
	if os.environ.get('CFLAGS'):
		cflags += os.environ['CFLAGS'].split(' ')
	if os.environ.get('LDFLAGS'):
		ldflags += os.environ['LDFLAGS'].split(' ')
else:
	if konga_sdk is None:
		konga_sdk = '/usr/local'
	cflags = '-g -Wno-maybe-uninitialized -Wno-write-strings -Wno-multichar -fvisibility=hidden -I%s/include -std=c++11 -D__STDC_LIMIT_MACROS -D__STDC_FORMAT_MACROS -DPY_SSIZE_T_CLEAN' % konga_sdk
	ldflags = '-L%s/lib -lkonga_client_s -lebpr_s -lz -lpcre -ldbus-1' % konga_sdk
	cflags = cflags.split(' ')
	ldflags = ldflags.split(' ')
	extra_libs = []

defines = [
	('NOUNCRYPT', None),
	('UNICODE', None),
	('YAJL_BUILD', None),
]
if sys.platform == 'win32':
	defines.append(('WIN32', None))



setup(
    ext_modules = [ Extension('_kongalib',
    	glob.glob(os.path.join('src', '_kongalib', '*.cpp')) + glob.glob(os.path.join('src', '_kongalib', 'yajl-2.0.1', 'src', '*.c')),
    	include_dirs = [
    		os.path.join('src', '_kongalib'),
    		os.path.join('src', '_kongalib', 'yajl-2.0.1', 'src'),
    		os.path.join('src', '_kongalib', 'yajl-2.0.1', 'include'),
    	],
    	define_macros = defines,
    	extra_compile_args = cflags,
    	extra_link_args = ldflags,
    	libraries = extra_libs,
    ) ],
)

