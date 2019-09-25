# -*- coding: utf-8 -*-
#	 _                           _ _ _
#	| |                         | (_) |
#	| | _____  _ __   __ _  __ _| |_| |__
#	| |/ / _ \| '_ \ / _` |/ _` | | | '_ \
#	|   < (_) | | | | (_| | (_| | | | |_) |
#	|_|\_\___/|_| |_|\__, |\__,_|_|_|_.__/
#	                  __/ |
#	                 |___/
#
#	Konga client library, by EasyByte Software
#
#	https://github.com/easybyte-software/kongalib


from __future__ import print_function

from kongalib import JSONEncoder, JSONDecoder, Decimal
from .compat import *



class Encoder(JSONEncoder):
	def encode(self, obj):
		self.reset()
		self.write(obj)
		return bytes(self.generate())


class Decoder(JSONDecoder):
	def save_object(self, obj):
		top, key = self.stack[-1]
		if isinstance(top, list):
			top.append(obj)
		elif isinstance(top, dict):
			top[key] = obj
		else:
			return True

	def start_map(self):
		obj = {}
		self.save_object(obj)
		self.stack.append([obj, None])

	def end_map(self):
		self.top = self.stack.pop()

	def read_key(self, key):
		self.stack[-1][1] = key

	def start_array(self):
		obj = []
		self.save_object(obj)
		self.stack.append([obj, None])

	def end_array(self):
		self.top = self.stack.pop()

	def read(self, obj):
		if self.save_object(obj):
			self.stack.append([obj, None])

	def decode(self, text):
		self.stack = [ [None, None] ]
		self.top = None

		if isinstance(text, text_base_types) or isinstance(text, data_base_types):
			self.parse(text)
		else:
			while True:
				data = text.read(65536)
				if not data:
					break
				self.parse(data)
		self.complete_parse()

		if len(self.stack) <= 1:
			obj = self.top[0]
		else:
			obj = self.stack[1][0]
		del self.stack
		return obj


def dumps(obj, encoding='utf-8', pretty=True):
	return Encoder(encoding, pretty).encode(obj)


def dump(obj, fp, encoding='utf-8'):
	fp.write(dumps(obj, encoding))


def loads(text, encoding='utf-8'):
	return Decoder(encoding).decode(text)


load = loads



if __name__ == '__main__':
	from pprint import pprint
	data = { 'a': 1, 'b': [ 1,2,3, { 'c': { 'd': [4,5,6]}} ], 'e': {'f': None}, 'g': Decimal("12.345678"), 'h': [ { 'h1': 1, 'h2': [ 1,2] }, { 'h3': 3, 'h4': [3,4,5] } ] }

	saved = dumps(data)
	print("SAVED:")
	print(saved)

	loaded = loads(saved)
	print("LOADED:")
	pprint(loaded)




