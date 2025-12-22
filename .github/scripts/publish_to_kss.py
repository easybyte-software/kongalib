import sys
import os
import argparse
import binascii
import re
import io
import glob
import tarfile
import zipfile

import requests
import rsa


SUPPORT_SERVER_PUBLISH_UPLOAD	= 'https://kss-secure.easybyte.it/service/publish_upload'


def main():
	parser = argparse.ArgumentParser(description='Publish installers to KSS.')
	parser.add_argument('--private-key', type=str, required=True, help='Private key for signing uploads.')
	parser.add_argument('--sdk-version', type=str, required=True, help='Version tag for the upload.')
	parser.add_argument('--public', action='store_true', help='Make the upload public.')
	parser.add_argument('path', nargs='+', help='Paths to installer files to upload.')
	options = parser.parse_args()

	private_key = rsa.PrivateKey.load_pkcs1(binascii.a2b_base64(options.private_key))

	for path in options.path:
		for archive in glob.glob(path):
			print("Uploading %s" % archive)
			spec = archive.split('-')[-1]
			if re.match(r'^macos_\d+_\d+_universal2.whl$', spec):
				platform = 'u'
			elif re.match(r'^manylinux_\d+_\d+_aarch64.whl$', spec):
				platform = 'a'
			elif re.match(r'^manylinux_\d+_\d+_x86_64.whl$', spec):
				platform = 'l'
			elif re.match(r'^win_amd64.whl$', spec):
				platform = 'w'
			else:
				platform = ''

			if (not platform) and (spec.endswith('.tar.gz')):
				buffer = io.BytesIO()
				with tarfile.open(archive, 'r|gz') as tf:
					with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
						for m in tf:
							f = tf.extractfile(m)
							fl = f.read()
							fn = f.name
							zf.writestr(fn, fl)
				content = buffer.getvalue()
				archive = archive.replace('.tar.gz', '.zip')
			else:
				with open(archive, 'rb') as file:
					content = file.read()
			signature = rsa.sign(content, private_key, 'SHA-1')

			if options.sdk_version == 'nightly':
				tag = version = ''
				channel = 'nightly'
			else:
				channel, version = options.sdk_version.split('/')
				tag = version

			response = requests.post(SUPPORT_SERVER_PUBLISH_UPLOAD, data={
				'signature': binascii.hexlify(signature),
				'public': 'true' if (channel == 'archive') else 'false',
				'dist': 'true' if (channel == 'archive') and options.public else 'false',
				'tag': tag,
				'version': version,
				'activation_version': 0,
				'target': 'kongalib',
				'platform': platform,
			}, files={
				'installer_file': ( os.path.basename(archive), io.BytesIO(content) ),
			})
			response.raise_for_status()


if __name__ == '__main__':
	main()
