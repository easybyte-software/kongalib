from __future__ import print_function
import sys
import glob
import os
import os.path
import ssl

try:
	from setuptools import setup, Extension
except:
	from distutils.core import setup
	from distutils.extension import Extension

import distutils.ccompiler


debug = '--debug' in sys.argv
if debug:
	sys.argv.remove('--debug')

new_compiler = distutils.ccompiler.new_compiler
def _new_compiler(*args, **kwargs):
	compiler = new_compiler(*args, **kwargs)
	
	def wrapper(func):
		def _wrapper(*args, **kwargs):
			kwargs['debug'] = debug
			return func(*args, **kwargs)
		return _wrapper
	
	compiler.compile = wrapper(compiler.compile)
	compiler.link_shared_object = wrapper(compiler.link_shared_object)
	compiler.create_static_lib = wrapper(compiler.create_static_lib)
	compiler.find_library_file = wrapper(compiler.find_library_file)
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
	extra_libs = ''
elif sys.platform == 'win32':
	suffix = '_d' if debug else ''
	cflags = '/EHsc /D_CRT_SECURE_NO_WARNINGS /DPSAPI_VERSION=1 /DPY_SSIZE_T_CLEAN /Zi /wd4244 /wd4005 /wd4267'
	ldflags = '/DEBUG /NODEFAULTLIB:LIBCMT /NODEFAULTLIB:LIBCMTD /ignore:4197 /ignore:4099'
	extra_libs = 'ebpr_s%s konga_client_s%s shell32 user32 netapi32 iphlpapi shlwapi advapi32 secur32 ws2_32 psapi bcrypt' % (suffix, suffix)
	if konga_sdk is not None:
		if ' ' in konga_sdk:
			cflags += ' /I"%s\\Include"' % konga_sdk
			ldflags += ' /LIBPATH:"%s\\Lib"' % konga_sdk
		else:
			cflags += ' /I%s\\Include' % konga_sdk
			ldflags += ' /LIBPATH:%s\\Lib' % konga_sdk
	cflags += ' %s' % (os.environ.get('CFLAGS') or '')
	ldflags += ' %s' % (os.environ.get('LDFLAGS') or '')
else:
	if konga_sdk is None:
		konga_sdk = '/usr/local'
	cflags = '-g -Wno-maybe-uninitialized -Wno-write-strings -Wno-multichar -fvisibility=hidden -I%s/include -std=c++11 -D__STDC_LIMIT_MACROS -D__STDC_FORMAT_MACROS -DPY_SSIZE_T_CLEAN' % konga_sdk
	ldflags = '-L%s/lib -lkonga_client_s -lebpr_s -lz -lpcre -ldbus-1' % konga_sdk
	extra_libs = ''

defines = [
	('NOUNCRYPT', None),
	('UNICODE', None),
	('YAJL_BUILD', None),
]
if sys.platform == 'win32':
	defines.append(('WIN32', None))


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst'), encoding='utf-8').read()
VERSION = open(os.path.join(here, 'VERSION'), encoding='utf-8').read()

setup(
    name = 'kongalib',
    version = VERSION,
    
    packages = [ 'kongalib' ],
    package_dir = { 'kongalib': 'src' },
    py_modules = [ 'kongautil', 'kongaui' ],

    ext_modules = [ Extension('kongalib._kongalib',
    	glob.glob(os.path.join('src', '_kongalib', '*.cpp')) + glob.glob(os.path.join('src', '_kongalib', 'yajl-2.0.1', 'src', '*.c')),
    	include_dirs = [
    		os.path.join('src', '_kongalib'),
    		os.path.join('src', '_kongalib', 'yajl-2.0.1', 'src'),
    		os.path.join('src', '_kongalib', 'yajl-2.0.1', 'include'),
    	],
    	define_macros = defines,
    	extra_compile_args = cflags.split(),
    	extra_link_args = ldflags.split(),
    	libraries = extra_libs.split(),
    ) ],
    
    install_requires=[
        'colorama',
    ],
    
	zip_safe = True,

    # metadata for upload to PyPI
    author = "EasyByte Software",
    author_email = "konga@easybyte.it",
    description = "Konga client library",
    license = "LGPL",
    keywords = [ "konga", "client", "erp" ],
    url = "https://github.com/easybyte-software/kongalib",
	classifiers = [
		"Natural Language :: Italian",
		"Programming Language :: Python",
		"Programming Language :: Python :: 3",
		"Programming Language :: Python :: 3 :: Only",
		"Programming Language :: Python :: 3.7",
		"Programming Language :: Python :: 3.8",
		"Programming Language :: Python :: 3.9",
		"Programming Language :: Python :: 3.10",
		"Programming Language :: Python :: 3.11",
		"Programming Language :: C++",
		"Development Status :: 5 - Production/Stable",
		"Environment :: Console",
		"Intended Audience :: Developers",
		"Intended Audience :: Information Technology",
		"Intended Audience :: Financial and Insurance Industry",
		"License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
		"Operating System :: MacOS :: MacOS X",
		"Operating System :: Microsoft :: Windows",
		"Operating System :: POSIX :: Linux",
		"Topic :: Office/Business",
		"Topic :: Office/Business :: Financial",
		"Topic :: Software Development :: Libraries",
	],
	long_description = README,
)

