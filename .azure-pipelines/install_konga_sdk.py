import sys
import urllib.request
import subprocess


def main(tag, operating_system):
	if tag in ('latest', 'current'):
		tag = 'current'
	else:
		if tag.endswith('-beta'):
			tag = 'stable/%s' % tag
		else:
			tag = 'archive/%s' % tag
	url = 'https://public.easybyte.it/downloads/%s/sdk?os=%s' % (tag, operating_system)
	path = urllib.request.urlretrieve(url)[0]
	print('Downloaded SDK into %s' % path)
	if operating_system == 'mac':
		cmd = 'sudo installer -pkg %s -target /' % path
	elif operating_system == 'win':
		cmd = '%s /install /quiet' % path
	else:
		cmd = 'sudo dpkg -i %s' % path
	subprocess.run(cmd, shell=True)


main(sys.argv[1], sys.argv[2])

