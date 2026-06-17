import sys
import os
import os.path
import shutil
import subprocess

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext


root = os.path.abspath(os.path.dirname(__file__))
konga_sdk = os.environ.get('KONGASDK', None)


class BuildExt(build_ext):
	"""Custom build_ext that copies constants.json from the Konga SDK before building."""

	def run(self):
		self._copy_constants()
		build_ext.run(self)

	def _copy_constants(self):
		if konga_sdk is None:
			return
		if sys.platform == 'win32':
			src = os.path.join(konga_sdk, 'constants.json')
		else:
			src = os.path.join(konga_sdk, 'share', 'kongalib', 'constants.json')
		if os.path.exists(src):
			dst = os.path.join(root, 'src', 'kongalib', 'constants.json')
			shutil.copy(src, dst)


def get_ext_args():
	defines = [
		('NOUNCRYPT', None),
		('UNICODE', None),
	]
	include_dirs = [os.path.join('src', '_kongalib')]
	cflags = []
	ldflags = []
	libraries = []
	# CI release builds set KONGALIB_STRIP=1 to omit debug info so the wheels shipped to
	# PyPI/KSS stay slim; kit/dev builds leave it unset and keep full debug info.
	strip = bool(os.environ.get('KONGALIB_STRIP'))

	if sys.platform == 'darwin':
		sdk = _find_macos_sdk()
		sdk_root = konga_sdk or '/usr/local'
		macosx_version_min = os.environ.get('MACOSX_DEPLOYMENT_TARGET', '10.13')
		cflags = [
			'-Wno-deprecated-register', '-Wno-sometimes-uninitialized', '-Wno-write-strings',
			'-fvisibility=hidden',
			'-mmacosx-version-min=%s' % macosx_version_min,
			'-isysroot', sdk,
			'-I%s/include' % sdk_root,
			'-stdlib=libc++', '-std=c++17',
			'-DPY_SSIZE_T_CLEAN',
		]
		ldflags = [
			'-Wl,-syslibroot,%s' % sdk,
			'-L%s/lib' % sdk_root,
			'-framework', 'Cocoa',
			'-lkonga_client_s', '-lebpr_s', '-liconv',
			'-mmacosx-version-min=%s' % macosx_version_min,
			'-headerpad_max_install_names',
			'-stdlib=libc++',
		]

	elif sys.platform == 'win32':
		defines.append(('WIN32', None))
		cflags = [
			'/std:c++17', '/EHsc',
			'/D_CRT_SECURE_NO_WARNINGS', '/DPSAPI_VERSION=1', '/DPY_SSIZE_T_CLEAN',
			'/wd4244', '/wd4005', '/wd4267', '/d2FH4-',
		]
		ldflags = [
			'/NODEFAULTLIB:LIBCMT', '/NODEFAULTLIB:LIBCMTD',
			'/ignore:4197', '/ignore:4099',
		]
		libraries = [
			'ebpr_s', 'konga_client_s',
			'shell32', 'user32', 'netapi32', 'iphlpapi', 'shlwapi',
			'advapi32', 'secur32', 'ws2_32', 'psapi', 'dbghelp', 'bcrypt',
		]
		if konga_sdk is not None:
			cflags.append('/I%s\\Include' % konga_sdk)
			ldflags.append('/LIBPATH:%s\\Lib' % konga_sdk)

	else:
		sdk_root = konga_sdk or '/usr/local'
		cflags = [
			'-Wno-maybe-uninitialized', '-Wno-write-strings', '-Wno-multichar',
			'-fvisibility=hidden',
			'-I%s/include' % sdk_root,
			'-std=c++17',
			'-D__STDC_LIMIT_MACROS', '-D__STDC_FORMAT_MACROS', '-DPY_SSIZE_T_CLEAN',
		]
		ldflags = [
			'-L%s/lib' % sdk_root,
			'-lkonga_client_s', '-lebpr_s', '-lz', '-lpcre2-8', '-ldbus-1',
		]

	if not strip:
		# Dev/kit builds keep full debug info.
		if sys.platform == 'darwin':
			cflags += ['-g', '-ggdb']
		elif sys.platform == 'win32':
			cflags += ['/Zi']
			ldflags += ['/DEBUG']
		else:
			cflags += ['-g']
	elif sys.platform == 'darwin':
		# macOS wheels have no post-build strip step (delocate lacks --strip), so strip
		# debug (-S) and local (-x) symbols at link time. DWARF never lands in the linked
		# .so on macOS, so this only sheds the symbol tables dragged in from the static libs.
		ldflags += ['-Wl,-S', '-Wl,-x']

	# Allow env var overrides (used by CMake build)
	if os.environ.get('CFLAGS'):
		cflags += os.environ['CFLAGS'].split()
	if os.environ.get('LDFLAGS'):
		ldflags += os.environ['LDFLAGS'].split()

	return dict(
		define_macros=defines,
		include_dirs=include_dirs,
		extra_compile_args=cflags,
		extra_link_args=ldflags,
		libraries=libraries,
	)


def _find_macos_sdk():
	sdk_base = os.path.dirname(
		subprocess.check_output('xcrun --show-sdk-path', shell=True, text=True).strip()
	)
	sdk = os.environ.get('SDK')
	if sdk is not None:
		# SDK env var may be a version number (e.g. "26.4") or a full path
		if not os.path.isabs(sdk):
			sdk = os.path.join(sdk_base, 'MacOSX%s.sdk' % sdk)
		if not os.path.exists(sdk):
			raise RuntimeError('macOS SDK not found: %s' % sdk)
		return sdk
	candidates = sorted(
		f for f in os.listdir(sdk_base)
		if f.startswith('MacOSX') and f.endswith('.sdk')
	)
	if not candidates:
		raise RuntimeError('No macOS SDK found in %s' % sdk_base)
	return os.path.join(sdk_base, candidates[-1])


setup(
	ext_modules=[
		Extension(
			'_kongalib',
			sources=[os.path.join('src', '_kongalib', 'amalgamation', 'kongalib.cpp')],
			**get_ext_args(),
		),
	],
	cmdclass={'build_ext': BuildExt},
)
