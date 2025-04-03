from __future__ import print_function
import sys
import glob
import shutil
import os
import os.path
import subprocess

from setuptools import setup, Extension


konga_sdk = os.environ.get('KONGASDK', None)
root = os.path.abspath(os.path.dirname(__file__))


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
	sdk_base_path = os.path.dirname(subprocess.check_output('xcrun --show-sdk-path', shell=True, universal_newlines=True).split('\n')[0])
	
	if sdk is None:
		try:
			sdk = os.path.basename(sorted(glob.glob('%s/MacOSX*.sdk' % sdk_base_path))[-1])[6:-4]
		except:
			pass
	if sdk is not None:
		path = '%s/MacOSX%s.sdk' % (sdk_base_path, sdk)
		if not os.path.exists(path):
			print('Error: unknown SDK:', sdk)
			sys.exit(1)
		sdk = path
	else:
		print('Error: no valid SDK found!')
		sys.exit(1)
	macosx_version_min = os.environ.get('MACOSX_DEPLOYMENT_TARGET') or '10.13'
	if konga_sdk is None:
		konga_sdk = '/usr/local'
	constants = '%s/share/kongalib/constants.json' % konga_sdk
	if os.path.exists(constants):
		shutil.copy(constants, '%s/src/kongalib/constants.json' % root)
	cflags = '-g -ggdb -Wno-deprecated-register -Wno-sometimes-uninitialized -Wno-write-strings -fvisibility=hidden -mmacosx-version-min=%s -isysroot %s -I%s/include' % (macosx_version_min, sdk, konga_sdk)
	ldflags = '-Wl,-syslibroot,%s -L%s/lib -framework Cocoa -lkonga_client_s -lebpr_s -liconv -mmacosx-version-min=%s -headerpad_max_install_names' % (sdk, konga_sdk, macosx_version_min)
	cflags += ' -stdlib=libc++ -std=c++17 -DPY_SSIZE_T_CLEAN'
	ldflags += ' -stdlib=libc++'
	cflags = cflags.split(' ')
	ldflags = ldflags.split(' ')
	extra_libs = []

elif sys.platform == 'win32':
	cflags = '/std:c++17 /EHsc /D_CRT_SECURE_NO_WARNINGS /DPSAPI_VERSION=1 /DPY_SSIZE_T_CLEAN /Zi /wd4244 /wd4005 /wd4267 /d2FH4-'.split(' ')
	ldflags = '/DEBUG /NODEFAULTLIB:LIBCMT /NODEFAULTLIB:LIBCMTD /ignore:4197 /ignore:4099'.split(' ')
	extra_libs = 'ebpr_s konga_client_s shell32 user32 netapi32 iphlpapi shlwapi advapi32 secur32 ws2_32 psapi bcrypt'.split(' ')
	if konga_sdk is not None:
		cflags.append('/I%s\\Include' % konga_sdk)
		ldflags.append('/LIBPATH:%s\\Lib' % konga_sdk)
		constants = '%s\\constants.json' % konga_sdk
		if os.path.exists(constants):
			shutil.copy(constants, '%s\\src\\kongalib\\constants.json' % root)
else:
	if konga_sdk is None:
		konga_sdk = '/usr/local'
	constants = '%s/share/kongalib/constants.json' % konga_sdk
	if os.path.exists(constants):
		shutil.copy(constants, '%s/src/kongalib/constants.json' % root)
	cflags = '-g -Wno-maybe-uninitialized -Wno-write-strings -Wno-multichar -fvisibility=hidden -I%s/include -std=c++17 -D__STDC_LIMIT_MACROS -D__STDC_FORMAT_MACROS -DPY_SSIZE_T_CLEAN' % konga_sdk
	ldflags = '-L%s/lib -lkonga_client_s -lebpr_s -lz -lpcre -ldbus-1' % konga_sdk
	cflags = cflags.split(' ')
	ldflags = ldflags.split(' ')
	extra_libs = []

if os.environ.get('CFLAGS'):
	cflags += os.environ['CFLAGS'].split(' ')
if os.environ.get('LDFLAGS'):
	ldflags += os.environ['LDFLAGS'].split(' ')

defines = [
	('NOUNCRYPT', None),
	('UNICODE', None),
]
if sys.platform == 'win32':
	defines.append(('WIN32', None))
cflags.append('-I%s' % os.path.join(root, 'src', '_kongalib'))

	
setup(
    ext_modules = [ Extension('_kongalib',
    	sources = [ os.path.join('src', '_kongalib', 'amalgamation', 'kongalib.cpp') ],
    	include_dirs = [ os.path.join('src', '_kongalib') ],
    	define_macros = defines,
    	extra_compile_args = cflags,
    	extra_link_args = ldflags,
    	libraries = extra_libs,
    ) ],
)

