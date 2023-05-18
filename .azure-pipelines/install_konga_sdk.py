import sys
import re
import subprocess
import requests


def get_filename_from_cd(cd):
	if not cd:
		return None
	fname = re.findall('filename=(.+)', cd)
	if len(fname) == 0:
		return None
	return fname[0]


def main(tag, operating_system):
	if tag in ('latest', 'current'):
		tag = 'current'
	else:
		if tag.endswith('-beta'):
			tag = 'stable/%s' % tag
		else:
			tag = 'archive/%s' % tag
	url = 'https://public.easybyte.it/downloads/%s/sdk?os=%s' % (tag, operating_system)

	r = requests.get(url, allow_redirects=True)
	path = get_filename_from_cd(r.headers.get('content-disposition'))
	with open(path, 'wb') as f:
		f.write(r.content)
	print('Downloaded SDK into %s' % path)
	if operating_system == 'mac':
		cmd = 'sudo installer -pkg %s -target /' % path
	elif operating_system == 'win':
		cmd = '%s /install /quiet' % path
	else:
		cmd = 'sudo apt install %s && sudo apt install -f' % path
	subprocess.run(cmd, shell=True)


main(sys.argv[1], sys.argv[2])

