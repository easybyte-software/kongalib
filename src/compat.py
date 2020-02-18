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

import sys
import io

from xml.etree import ElementTree as ET



PY3 = (sys.version_info[0] > 2)

if PY3:
	text_base_types = (str,)
	text_type = str
	data_base_types = (bytes,)
	data_type = bytes
	int_base_types = (int,)
	int_type = int
	file_type = io.IOBase
	def reraise(tp, value, tb=None):
		if value is None:
			value = tp()
		if value.__traceback__ is not tb:
			raise value.with_traceback(tb)
		raise value
	unichr = chr
	buffer = bytes
else:
	text_base_types = (basestring,)
	text_type = unicode
	data_base_types = (basestring, buffer)
	data_type = bytes
	int_base_types = (int, long)
	int_type = long
	file_type = file
	exec("def reraise(tp, value, tb=None):\n  raise tp, value, tb\n")



def ensure_text(text, error='replace'):
	if not isinstance(text, text_base_types):
		try:
			text = unicode(text)
		except:
			if isinstance(text, data_base_types):
				text = str(text, 'utf-8', 'replace')
			else:
				text = str(text)
	if isinstance(text, data_type):
		text = text_type(text, 'utf-8', error)
	return text



def _patch_etree():
	OriginalElementTree = ET.ElementTree
	Original_serialize_xml = ET._serialize_xml

	if PY3:
		import warnings
		import collections
		import collections.abc

		Original_iterparse = ET.iterparse
		Original_parse = ET.parse

		def OriginalSubElement(parent, tag, attrib={}, **extra):
			"""Subelement factory which creates an element instance, and appends it
			to an existing parent.

			The element tag, attribute names, and attribute values can be either
			bytes or Unicode strings.

			*parent* is the parent element, *tag* is the subelements name, *attrib* is
			an optional directory containing element attributes, *extra* are
			additional attributes given as keyword arguments.

			"""
			attrib = attrib.copy()
			attrib.update(extra)
			element = parent.makeelement(tag, attrib)
			parent.append(element)
			return element

		class OriginalTreeBuilder:
			"""Generic element structure builder.

			This builder converts a sequence of start, data, and end method
			calls to a well-formed element structure.

			You can use this class to build an element structure using a custom XML
			parser, or a parser for some other XML-like format.

			*element_factory* is an optional element factory which is called
			to create new Element instances, as necessary.

			"""
			def __init__(self, element_factory=None):
				self._data = [] # data collector
				self._elem = [] # element stack
				self._last = None # last element
				self._tail = None # true if we're after an end tag
				if element_factory is None:
					element_factory = ET._Element_Py
				self._factory = element_factory

			def close(self):
				"""Flush builder buffers and return toplevel document Element."""
				assert len(self._elem) == 0, "missing end tags"
				assert self._last is not None, "missing toplevel element"
				return self._last

			def _flush(self):
				if self._data:
					if self._last is not None:
						text = "".join(self._data)
						if self._tail:
							assert self._last.tail is None, "internal error (tail)"
							self._last.tail = text
						else:
							assert self._last.text is None, "internal error (text)"
							self._last.text = text
					self._data = []

			def data(self, data):
				"""Add text to current element."""
				self._data.append(data)

			def start(self, tag, attrs):
				"""Open new element and return it.

				*tag* is the element name, *attrs* is a dict containing element
				attributes.

				"""
				self._flush()
				self._last = elem = self._factory(tag, attrs)
				if self._elem:
					self._elem[-1].append(elem)
				self._elem.append(elem)
				self._tail = 0
				return elem

			def end(self, tag):
				"""Close and return current Element.

				*tag* is the element name.

				"""
				self._flush()
				self._last = self._elem.pop()
				assert self._last.tag == tag,\
					   "end tag mismatch (expected %s, got %s)" % (
						   self._last.tag, tag)
				self._tail = 1
				return self._last

		class OriginalXMLTreeBuilder(object):
			def __init__(self, html=0, target=None, encoding=None):
				try:
					from xml.parsers import expat
				except ImportError:
					try:
						import pyexpat as expat
					except ImportError:
						raise ImportError(
							"No module named expat; use SimpleXMLTreeBuilder instead"
							)
				parser = expat.ParserCreate(encoding, "}")
				if target is None:
					target = OriginalTreeBuilder(ET._Element_Py)

				self.parser = self._parser = parser
				self.target = self._target = target
				self._error = expat.error
				self._names = {}
				parser.DefaultHandlerExpand = self._default
				if hasattr(target, 'start'):
					parser.StartElementHandler = self._start
				if hasattr(target, 'end'):
					parser.EndElementHandler = self._end
				if hasattr(target, 'data'):
					parser.CharacterDataHandler = target.data
				if hasattr(target, 'comment'):
					parser.CommentHandler = target.comment
				if hasattr(target, 'pi'):
					parser.ProcessingInstructionHandler = target.pi
				parser.buffer_text = 1
				parser.ordered_attributes = 1
				parser.specified_attributes = 1
				self._doctype = None
				self.entity = {}
				try:
					self.version = "Expat %d.%d.%d" % expat.version_info
				except AttributeError:
					pass

			def _setevents(self, events_queue, events_to_report):
				parser = self._parser
				append = events_queue.append
				for event_name in events_to_report:
					if event_name == "start":
						parser.ordered_attributes = 1
						parser.specified_attributes = 1
						def handler(tag, attrib_in, event=event_name, append=append, start=self._start):
							append((event, start(tag, attrib_in)))
						parser.StartElementHandler = handler
					elif event_name == "end":
						def handler(tag, event=event_name, append=append, end=self._end):
							append((event, end(tag)))
						parser.EndElementHandler = handler
					elif event_name == "start-ns":
						def handler(prefix, uri, event=event_name, append=append):
							append((event, (prefix or "", uri or "")))
						parser.StartNamespaceDeclHandler = handler
					elif event_name == "end-ns":
						def handler(prefix, event=event_name, append=append):
							append((event, None))
						parser.EndNamespaceDeclHandler = handler
					else:
						raise ValueError("unknown event %r" % event_name)

			def _raiseerror(self, value):
				err = ET.ParseError(value)
				err.code = value.code
				err.position = value.lineno, value.offset
				raise err

			def _fixname(self, key):
				try:
					name = self._names[key]
				except KeyError:
					name = key
					if "}" in name:
						name = "{" + name
					self._names[key] = name
				return name

			def _fixtext(self, text):
				return text

			def _start(self, tag, attr_list):
				fixname = self._fixname
				tag = fixname(tag)
				attrib = {}
				if attr_list:
					for i in range(0, len(attr_list), 2):
						attrib[fixname(attr_list[i])] = attr_list[i+1]
				e = self.target.start(tag, attrib)
				return e

			def _end(self, tag):
				return self.target.end(self._fixname(tag))

			def _default(self, text):
				prefix = text[:1]
				if prefix == "&":
					try:
						data_handler = self.target.data
					except AttributeError:
						return
					try:
						data_handler(self.entity[text[1:-1]])
					except KeyError:
						from xml.parsers import expat
						err = expat.error(
							"undefined entity %s: line %d, column %d" %
							(text, self.parser.ErrorLineNumber,
							self.parser.ErrorColumnNumber)
							)
						err.code = 11 # XML_ERROR_UNDEFINED_ENTITY
						err.lineno = self.parser.ErrorLineNumber
						err.offset = self.parser.ErrorColumnNumber
						raise err
				elif prefix == "<" and text[:9] == "<!DOCTYPE":
					self._doctype = []
				elif self._doctype is not None:
					if prefix == ">":
						self._doctype = None
						return
					text = text.strip()
					if not text:
						return
					self._doctype.append(text)
					n = len(self._doctype)
					if n > 2:
						type = self._doctype[1]
						if type == "PUBLIC" and n == 4:
							name, type, pubid, system = self._doctype
							if pubid:
								pubid = pubid[1:-1]
						elif type == "SYSTEM" and n == 3:
							name, type, system = self._doctype
							pubid = None
						else:
							return
						if hasattr(self.target, "doctype"):
							self.target.doctype(name, pubid, system[1:-1])
						elif self.doctype != self._XMLParser__doctype:
							# warn about deprecated call
							# self._XMLParser__doctype(name, pubid, system[1:-1])
							self.doctype(name, pubid, system[1:-1])
						self._doctype = None

			def doctype(self, name, pubid, system):
				warnings.warn("This method of XMLParser is deprecated.  Define doctype() method on the TreeBuilder target.", DeprecationWarning)

			__doctype = doctype
			_XMLParser__doctype = doctype

			def feed(self, data):
				try:
					self.parser.Parse(data, 0)
				except self._error as v:
					self._raiseerror(v)

			def close(self):
				try:
					self.parser.Parse("", 1) # end of data
				except self._error as v:
					self._raiseerror(v)
				try:
					close_handler = self.target.close
				except AttributeError:
					pass
				else:
					return close_handler()
				finally:
					del self.parser, self._parser
					del self.target, self._target

		def XML(text, parser=None):
			"""Parse XML document from string constant.

			This function can be used to embed "XML Literals" in Python code.

			*text* is a string containing XML data, *parser* is an
			optional parser instance, defaulting to the standard XMLParser.

			Returns an Element instance.

			"""
			if not parser:
				parser = PatchedXMLTreeBuilder(OriginalTreeBuilder(ET._Element_Py))
			parser.feed(text)
			return parser.close()

		def iterparse(source, events=None, parser=None):
			if parser is None:
				parser = PatchedXMLTreeBuilder(OriginalTreeBuilder(ET._Element_Py))
			return Original_iterparse(source, events, parser)

		def parse(source, parser=None):
			if parser is None:
				parser = PatchedXMLTreeBuilder(OriginalTreeBuilder(ET._Element_Py))
			return Original_parse(source, parser)

		def serialize_xml(write, elem, qnames, namespaces, short_empty_elements, **kwargs):
			if getattr(elem, '_is_cdata', False):
				if elem.text:
					write("<![CDATA[%s]]>" % elem.text)
				if elem.tail:
					write(elem.tail)
			else:
				Original_serialize_xml(write, elem, qnames, namespaces, short_empty_elements, **kwargs)

		ET.Element = ET._Element_Py
		ET.SubElement = OriginalSubElement
		ET.XML = ET.fromstring = XML
		ET.iterparse = iterparse
		ET.parse = parse
		ET._serialize_xml = serialize_xml

	else:
		def serialize_xml(write, elem, encoding, qnames, namespaces, **kwargs):
			if getattr(elem, '_is_cdata', False):
				if elem.text:
					text = elem.text.encode(encoding)
					write("<![CDATA[%s]]>" % text)
				if elem.tail:
					write(elem.tail)
			else:
				Original_serialize_xml(write, elem, encoding, qnames, namespaces, **kwargs)

		OriginalXMLTreeBuilder = ET.XMLTreeBuilder
		ET._serialize_xml = serialize_xml
		ET._Element_Py = ET.Element
		
	class PatchedXMLTreeBuilder(OriginalXMLTreeBuilder):
		def __init__(self, html=0, target=None, remove_comments=True, parse_comments=False, strip_cdata=True):
			OriginalXMLTreeBuilder.__init__(self, html, target)
			self._parser.StartCdataSectionHandler = self._start_cdata
			self._parser.EndCdataSectionHandler = self._end_cdata
			self._parser.CharacterDataHandler = self._data
			if (not parse_comments) or remove_comments:
				self._parser.CommentHandler = None
			else:
				self._parser.CommentHandler = self._handle_comment
			self._parser.ProcessingInstructionHandler = self._handle_pi
			self._cdataSection = False
			self._cdataBuffer = None
			self._strip_cdata = strip_cdata
		
		def _start(self, tag, attrib_in):
			elem = OriginalXMLTreeBuilder._start(self, tag, attrib_in)
			if isinstance(elem, ET._Element_Py):
				elem.sourceline = elem.lineno = self._parser.CurrentLineNumber
				elem.offset = elem.column = self._parser.CurrentColumnNumber
			return elem
		
		def _start_list(self, tag, attrib_in):
			elem = OriginalXMLTreeBuilder._start_list(self, tag, attrib_in)
			if isinstance(elem, ET._Element_Py):
				elem.sourceline = elem.lineno = self._parser.CurrentLineNumber
				elem.offset = elem.column = self._parser.CurrentColumnNumber
			return elem
			
		def _start_cdata(self):
			"""
			A CDATA section beginning has been recognized - start collecting
			character data.
			"""
			self._cdataSection = True
			self._cdataBuffer = []
			
		def _end_cdata(self):
			"""
			The CDATA section has ended - join the character data we collected
			and add a CDATA element to the target tree.
			"""
			self._cdataSection = False
			if not self._strip_cdata:
				text = "".join(self._cdataBuffer)
				if not PY3:
					text = self._fixtext(text)
				elem = self._target.start(None, {})
				elem._is_cdata = True
				self._target.data(text)
				self._target.end(None)
				elem.text = text
			self._cdataBuffer = []
	# 		print("created cdata with content:\n---\n%s\n---" % text)
			
		def _handle_comment(self, data):
			return ET.Comment(self._fixtext(data))
		
		def _handle_pi(self, target, data):
			return ET.PI(self._fixtext(target), self._fixtext(data))
		
		def _data(self, text):
			"""
			If we are in the middle of a CDATA section, collect the data into a
			special buffer, otherwise treat it as before.
			"""
			if self._cdataSection:
				self._cdataBuffer.append(text)
			else:
				self._target.data(text)
	
	def CDATA(text=None):
		element = ET.Element(None)
		element.text = text
		element._is_cdata = True
		return element
	
	ET.XMLTreeBuilder = ET.XMLParser = PatchedXMLTreeBuilder
	ET._serialize['xml'] = ET._serialize_xml
	ET.CDATA = CDATA



if PY3:
	def ensure_source_compatibility(source):
		import re
		lines = source.splitlines()
		for line in lines:
			if (not line) or (not line.strip()) or (line.strip()[0] == '\n'):
				continue
			m = re.match(r'# \-\*\- py3k-safe \-\*\-', line)
			if (m is None) and (line.strip()[0] == '#'):
				continue
			break
		else:
			m = None
		if m is not None:
			return source
		try:
			import application, slew
			import os, os.path

			from lib2to3.pgen2 import driver

			if application.EXECUTABLE and (not getattr(driver, '_patched', False)):
				def load_packaged_grammar(package, grammar_source):
					data = slew.load_resource('data/' + driver._generate_pickle_name(os.path.basename(grammar_source)))
					g = driver.grammar.Grammar()
					g.loads(data)
					return g
				driver._patched = True
				driver.load_packaged_grammar = load_packaged_grammar
		except:
			pass

		from lib2to3.refactor import RefactoringTool
		from io import BytesIO

		class SilentRefactoringTool(RefactoringTool):
			def __init__(self):
				fixers = [ 'lib2to3.fixes.fix_%s' % name for name in [
					'apply', 'asserts', 'basestring', 'buffer', 'dict', 'except', 'exec', 'execfile', 'exitfunc', 'filter', 'funcattrs', 'future', 'getcwdu', 'has_key',
					'idioms', 'import', 'imports', 'imports2', 'input', 'intern', 'isinstance', 'itertools', 'itertools_imports', 'long', 'map', 'metaclass', 'methodattrs',
					'ne', 'nonzero', 'numliterals', 'operator', 'paren', 'print', 'raise', 'raw_input', 'reduce', 'reload', 'renames', 'repr', 'set_literal',
					'standarderror', 'sys_exc', 'throw', 'tuple_params', 'types', 'unicode', 'urllib', 'ws_comma', 'xrange', 'xreadlines', 'zip', 
				] ]
				RefactoringTool.__init__(self, fixers)
			def refactor_source(self, source):
				tree = self.refactor_string(source, 'dummy')
				if tree is None:
					return None
				return str(tree)
			def log_error(self, *args, **kwargs):
				pass
			def log_message(self, *args, **kwargs):
				pass
			def log_debug(self, *args, **kwargs):
				pass

		saved_stdin = sys.stdin
		saved_stdout = sys.stdout
		saved_stderr = sys.stderr
		sys.stdin = BytesIO()
		sys.stdout = BytesIO()
		sys.stderr = BytesIO()
		try:
			tool = getattr(ensure_source_compatibility, 'tool', None)
			if tool is None:
				tool = SilentRefactoringTool()
				ensure_source_compatibility.tool = tool
			try:
				output = tool.refactor_source(source + '\n')[:-1]
			except:
				output = None
			if output is None:
				return source
			return output
		finally:
			sys.stdin = saved_stdin
			sys.stdout = saved_stdout
			sys.stderr = saved_stderr
else:
	def ensure_source_compatibility(source):
		return source



try:
	from xml.etree.ElementTree import CDATA
except:
	_patch_etree()



if __name__ == '__main__':
	print(ensure_source_compatibility('print("Hello world!")'))
