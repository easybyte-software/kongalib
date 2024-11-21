import os
from setuptools import build_meta as build_meta

_VERSION = '2.0.1'


def __getattr__(name):
	if name == '__version__':
		version_build = os.environ.get('KONGALIB_BUILD', None)
		if version_build:
			return '%s-%s' % (_VERSION, version_build)
		else:
			return _VERSION
		
