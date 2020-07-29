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
from __future__ import absolute_import

import re
import io
import tempfile
import collections

from .compat import *



class LRUCache(object):
	def __init__(self, capacity):
		self.capacity = capacity
		self.cache = collections.OrderedDict()

	def clear(self):
		self.cache.clear()

	def get(self, key, default=None):
		try:
			value = self.cache.pop(key)
			self.cache[key] = value
			return value
		except KeyError:
			return default

	def __getitem__(self, key):
		value = self.cache.pop(key)
		self.cache[key] = value
		return value

	def __setitem__(self, key, value):
		try:
			self.cache.pop(key)
		except KeyError:
			if len(self.cache) >= self.capacity:
				self.cache.popitem(last=False)
		self.cache[key] = value

	def __delitem__(self, key):
		self.cache.pop(key)

	def __contains__(self, key):
		return key in self.cache

	def __len__(self):
		return len(self.cache)



_sParseCache = LRUCache(64)



def parse(sql):
	if not sql:
		return None
	expr = _sParseCache.get(sql, None)
	if expr is not None:
		return expr

	from . import lex, yacc
	
	tokens = (
		'LPAREN',
		'RPAREN',
		'OPERAND',
		'ID',
		'VALUE',
		'AND',
		'OR',
		'NOT',
		'IS',
		'LIKE',
		'IN',
		'NULL',
		'COMMA',
	)
	reserved = set(('AND','OR','NOT','IS','LIKE','IN','NULL'))
	
	t_COMMA = r'\,'
	t_LPAREN = r'\('
	t_RPAREN = r'\)'
	t_OPERAND = r'\=|\<\=|\>\=|\<|\>|\!\=|\+|\-|\*|\/|\&|\||\^'
	def t_ID(t):
		r'[A-Za-z_][A-Za-z0-9_\.]*'
		if t.value.upper() in reserved:
			t.type = t.value.upper()
		return t
	def t_VALUE(t):
		r'\"([^\"]*)\"|\'(\'\'|[^\'])*\'|(\-)?\d+'
		c = t.value[0]
		if (c == '"') or (c == "'"):
			t.value = t.value[1:-1].replace("''", "'")
		return t
	
	def t_error(t):
		print("Illegal character '%s'" % t.value[0])
		t.lexer.skip(1)
    
	t_ignore = ' \t'
	lex.lex()
	
	precedence = (
		( 'left', 'OR' ),
		( 'left', 'AND' ),
		( 'right', 'NOT' ),
	)
	
	def p_expression_and(p):
		'expression : expression AND expression'
		p[0] = AND(p[1], p[3])
	
	def p_expression_and_value(p):
		'expression : expression AND value'
		try:
			if eval(p[3]):
				node = OperandEQ('1', '1')
			else:
				node = OperandNE('1', '1')
		except:
			node = OperandNE('1', '1')
		p[0] = AND(p[1], node)
	
	def p_expression_or(p):
		'expression : expression OR expression'
		p[0] = OR(p[1], p[3])
	
	def p_expression_or_value(p):
		'expression : expression OR value'
		try:
			if eval(p[3]):
				node = OperandEQ('1', '1')
			else:
				node = OperandNE('1', '1')
		except:
			node = OperandNE('1', '1')
		p[0] = OR(p[1], node)
	
	def p_expression_fieldop(p):
		'expression : ID OPERAND ID'
		p[0] = Operand(p[1], p[2], p[3], _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE | _HasLogic.FLAG_VALUE_IS_FIELD)
	
	def p_expression_binop(p):
		'expression : ID OPERAND VALUE'
		p[0] = Operand(p[1], p[2], p[3])

	def p_expression_func_fieldop(p):
		'expression : function OPERAND ID'
		p[0] = Operand(p[1], p[2], p[3], _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE | _HasLogic.FLAG_VALUE_IS_FIELD)

	def p_expression_func_binop(p):
		'expression : function OPERAND VALUE'
		p[0] = Operand(p[1], p[2], p[3])
	
	def p_expression_not(p):
		'expression : NOT expression'
		p[0] = NOT(p[2])
	
	def p_expression_paren(p):
		'expression : LPAREN expression RPAREN'
		p[0] = p[2]
	
	def p_expression_is_null(p):
		'expression : ID IS NULL'
		p[0] = OperandIsNull(p[1])
	
	def p_expression_is_not_null(p):
		'expression : ID IS NOT NULL'
		p[0] = OperandIsNotNull(p[1])
	
	def p_expression_like(p):
		'expression : ID LIKE VALUE'
		p[0] = OperandLIKE(p[1], p[3])
	
	def p_expression_not_like(p):
		'expression : ID NOT LIKE VALUE'
		p[0] = OperandNotLIKE(p[1], p[4])
	
	def p_expression_in(p):
		'expression : ID IN LPAREN valueslist RPAREN'
		values = []
		node = p[4]
		while node is not None:
			values.append(node[0])
			node = node[1]
		p[0] = OperandIN(p[1], values)
	
	def p_function(p):
		'function : ID LPAREN ID RPAREN'
		p[0] = '%s(%s)' % (p[1], p[3])

	def p_function_recursive(p):
		'function : ID LPAREN function RPAREN'
		p[0] = '%s(%s)' % (p[1], p[3])

	def p_value_paren(p):
		'value : LPAREN value RPAREN'
		p[0] = p[2]

	def p_value(p):
		'value : VALUE'
		p[0] = p[1]
	
	def p_valueslist_single(p):
		'valueslist : VALUE'
		p[0] = (p[1], None)
	
	def p_valueslist_multi(p):
		'valueslist : VALUE COMMA valueslist'
		p[0] = (p[1], p[3])
	
	def p_error(p):
		if p:
			raise SyntaxError("Parse error near '%s'" % p.value[0])
		else:
			raise SyntaxError("Parse error")
	
# 	yacc.yacc()
	yacc.yacc(debug=False, outputdir=tempfile.gettempdir(), write_tables=False, errorlog=yacc.NullLogger())
	expr = yacc.parse(sql, lexer=lex.lexer)
	_sParseCache[sql] = expr
	return expr



class _HasLogic(object):
	LOGIC_NONE				= 0
	LOGIC_AND				= 1
	LOGIC_OR				= 2
	LOGIC_OP_MASK			= ~0x3
	LOGIC_NOT				= 0x4
	
	FLAG_NO_ESCAPE			= 0x1
	FLAG_VALUE_IS_FIELD		= 0x2
	FLAG_ESCAPE_LIKE		= 0x4
	
	def is_and(self):
		return self.logic_op & _HasLogic.LOGIC_AND
	
	def is_or(self):
		return self.logic_op & _HasLogic.LOGIC_OR
	
	def is_and_not(self):
		if not (self.logic_op & _HasLogic.LOGIC_AND):
			return False
		children = self.parent.children
		index = children.index(self)
		if index + 1 >= len(children):
			return False
		return children[index + 1].logic_op & _HasLogic.LOGIC_NOT
	
	def is_or_not(self):
		if not (self.logic_op & _HasLogic.LOGIC_OR):
			return False
		children = self.parent.children
		index = children.index(self)
		if index + 1 >= len(children):
			return False
		return children[index + 1].logic_op & _HasLogic.LOGIC_NOT



class Operand(_HasLogic):
	def __init__(self, column, operator, value, logic_op=_HasLogic.LOGIC_NONE, flags=0):
		self.column = ensure_text(column)
		self.operator = ensure_text(operator)
		if value is not None:
			self.value = ensure_text(value)
		else:
			self.value = None
		self.logic_op = int(logic_op)
		self.parent = None
		self.flags = flags
	
	def copy(self):
		return Operand(self.column, self.operator, self.value, self.logic_op, self.flags)
	
	def walk(self, repl):
		repl(self)
	
	def replace_markup(self, repl):
		if self.value is not None:
			if isinstance(repl, dict):
				for key, value in repl.items():
					self.value = self.value.replace(u'$%s' % key, ensure_text(value))
			else:
				self.value = repl(self.value)
	
	def as_list(self):
		return [ self.column, self.operator, self.value, self.flags ]
	
	def __eq__(self, other):
		return isinstance(other, Operand) and (self.column == other.column) and (self.operator == other.operator) and (self.value == other.value) and (self.logic_op == other.logic_op)

	def __ne__(self, other):
		return not self.__eq__(other)
	
	def __hash__(self):
		return hash(str(self))
	
	def __unicode__(self):
		if self.value is None:
			value = 'NULL'
		elif re.match(r'^(\-)?[0-9]+$', self.value):
			value = self.value
		else:
			if self.operator == 'IN':
				value = self.value
			else:
				if self.flags & _HasLogic.FLAG_VALUE_IS_FIELD:
					value = self.value
				else:
					value = "'%s'" % self.value.replace("'", "''")
		return (u'%s %s %s' % (ensure_text(self.column), ensure_text(self.operator), ensure_text(value)))

	def __str__(self):
		if PY3:
			return self.__unicode__()
		else:
			return self.__unicode__().encode('utf-8')
	
	def __repr__(self):
		return str(self)

	def apply(self, func):
		func(self)

	def serialize(self):
		return {
			'__type__':		'operand',
			'column':		self.column,
			'op':			self.operator,
			'logic_op':		self.logic_op,
			'flags':		self.flags,
			'value':		ensure_text(self.value) if self.value is not None else None,
		}
	
	@classmethod
	def unserialize(cls, obj):
		if isinstance(obj, dict):
			return Operand(obj['column'], obj['op'], obj['value'], obj['logic_op'], obj['flags'])
		return obj

	def serialize_xml(self, node):
		"""
		Salva il descrittore sul nodo XML I{node}.
		
		@param	node:			Nodo XML in cui salvare il descrittore.
		@type	node:			ET.Element
		"""
		node.attrib['column'] = self.column
		node.attrib['operator'] = self.operator
		if self.logic_op != _HasLogic.LOGIC_NONE:
			node.attrib['logic_op'] = str(self.logic_op)
		node.attrib['flags'] = str(self.flags)
		if self.value is not None:
			node.text = ensure_text(self.value)
	
	@classmethod
	def unserialize_xml(cls, node):
		"""
		Carica ed instanzia un descrittore dal nodo XML I{node}.
		
		@param	node:			Nodo XML da cui caricare la nuova istanza.
		@type	node:			ET.Element
		
		@return:				Nuova istanza caricata dal nodo.
		@rtype:					L{ColumnDescriptor}
		"""
		return Operand(node.get('column'), node.get('operator'), node.text, int(node.get('logic_op', _HasLogic.LOGIC_NONE)), int(node.get('flags', '0')))
	


class OperandEQ(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, 'IS' if value is None else '=', value)



class OperandNE(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, 'IS NOT' if value is None else '!=', value)



class OperandLT(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, '<', value)



class OperandGT(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, '>', value)



class OperandLE(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, '<=', value)



class OperandGE(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, '>=', value)



class OperandAND(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, '&', value)



class OperandOR(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, '|', value)



class OperandXOR(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, '^', value)



class OperandLIKE(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, 'LIKE', value)



class OperandNotLIKE(Operand):
	def __init__(self, column, value):
		Operand.__init__(self, column, 'NOT LIKE', value)



class OperandIsNull(Operand):
	def __init__(self, column):
		Operand.__init__(self, column, 'IS', None)



class OperandIsNotNull(Operand):
	def __init__(self, column):
		Operand.__init__(self, column, 'IS NOT', None)



class OperandIN(OperandNE):
	def __init__(self, column, value):
		if not isinstance(value, text_base_types):
			value = u"('%s')" % (u"', '".join([ ensure_text(x).replace("'", "''") for x in value]))
		Operand.__init__(self, column, 'IN', value, _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE)



class OperandNotIN(OperandNE):
	def __init__(self, column, value):
		if not isinstance(value, text_base_types):
			value = u"('%s')" % (u"', '".join([ ensure_text(x).replace("'", "''") for x in value]))
		Operand.__init__(self, column, 'NOT IN', value, _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE)



class OperandFieldEQ(OperandEQ):
	def __init__(self, column, value):
		Operand.__init__(self, column, '=', value, _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE | _HasLogic.FLAG_VALUE_IS_FIELD)



class OperandFieldNE(OperandNE):
	def __init__(self, column, value):
		Operand.__init__(self, column, '!=', value, _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE | _HasLogic.FLAG_VALUE_IS_FIELD)



class OperandFieldLT(OperandLT):
	def __init__(self, column, value):
		Operand.__init__(self, column, '<', value, _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE | _HasLogic.FLAG_VALUE_IS_FIELD)



class OperandFieldGT(OperandGT):
	def __init__(self, column, value):
		Operand.__init__(self, column, '>', value, _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE | _HasLogic.FLAG_VALUE_IS_FIELD)



class OperandFieldLE(OperandLE):
	def __init__(self, column, value):
		Operand.__init__(self, column, '<=', value, _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE | _HasLogic.FLAG_VALUE_IS_FIELD)



class OperandFieldGE(OperandGE):
	def __init__(self, column, value):
		Operand.__init__(self, column, '>=', value, _HasLogic.LOGIC_NONE, _HasLogic.FLAG_NO_ESCAPE | _HasLogic.FLAG_VALUE_IS_FIELD)



class Expression(_HasLogic):
	def __init__(self, *args):
		if len(args) == 0:
			self.children = []
		else:
			for child in args:
				if not isinstance(child, (Expression, Operand)):
					raise ValueError('Expected Expression or Operand object')
			self.children = args
		self.name = None
		self.logic_op = _HasLogic.LOGIC_NONE
		self.parent = None
	
	def set_name(self, name):
		self.name = name
	
	def get_name(self):
		return self.name
	
	def copy(self):
		e = Expression()
		e.name = self.name
		e.logic_op = self.logic_op
		for child in self.children:
			e.children.append(child.copy())
		return e
	
	def append(self, operand, logic_op):
		operand.logic_op = (operand.logic_op & _HasLogic.LOGIC_OP_MASK) | logic_op
		self.children.append(operand)
		operand.parent = self
	
	def walk(self, repl):
		for child in self.children:
			child.walk(repl)

	def replace_markup(self, repl):
		for child in self.children:
			child.replace_markup(repl)
	
	def as_list(self):
		l = []
		for index, child in enumerate(self.children):
			if (index == 0) and (child.logic_op & _HasLogic.LOGIC_NOT):
				l.append(True)
			l.append(child.as_list())
			if child is not self.children[-1]:
				if child.logic_op & _HasLogic.LOGIC_AND:
					op = 'AND'
				elif child.logic_op & _HasLogic.LOGIC_OR:
					op = 'OR'
				if self.children[index + 1].logic_op & _HasLogic.LOGIC_NOT:
					op += ' NOT'
			else:
				if (len(self.children) == 1) and (self.children[-1].logic_op & _HasLogic.LOGIC_NOT):
					l[-1].append(True)
				op = None
			l.append(op)
		return l
	
	def __eq__(self, other):
		if not isinstance(other, Expression):
			return False
		if len(self.children) != len(other.children):
			return False
		for child, other_child in zip(self.children, other.children):
			if child != other_child:
				return False
		return True

	def __ne__(self, other):
		return not self.__eq__(other)
	
	def __hash__(self):
		return hash(str(self))

	def __unicode__(self):
		s = u''
		for child in self.children:
			if child.logic_op & _HasLogic.LOGIC_NOT:
				s += 'NOT '
			s += u'(%s)' % ensure_text(child)
			if child is not self.children[-1]:
				if child.logic_op & _HasLogic.LOGIC_AND:
					s += ' AND '
				elif child.logic_op & _HasLogic.LOGIC_OR:
					s += ' OR '
		return ensure_text(s)

	def __str__(self):
		if PY3:
			return self.__unicode__()
		else:
			return self.__unicode__().encode('utf-8')
	
	def __repr__(self):
		return str(self)
	
	def __len__(self):
		return len(self.children)
	
	def __getitem__(self, index):
		return self.children[index]
	
	def apply(self, func):
		for child in self.children:
			child.apply(func)
	
	def serialize(self):
		obj = {
			'__type__':		'expression',
			'name':			self.name,
			'logic_op':		self.logic_op,
			'children':		[]
		}
		for child in self.children:
			obj['children'].append(child.serialize())
		return obj

	@classmethod
	def unserialize(cls, obj):
		if isinstance(obj, dict):
			expr = Expression()
			for child in obj['children']:
				if isinstance(child, dict):
					if child['__type__'] == 'expression':
						elem = Expression.unserialize(child)
					elif child['__type__'] == 'operand':
						elem = Operand.unserialize(child)
					else:
						raise ValueError('Bad Expression JSON definition')
				elif isinstance(child, (Operand, Expression)):
					elem = child
				else:
					raise ValueError('Bad Expression XML definition')
				expr.children.append(elem)
				elem.parent = expr
			expr.logic_op = obj['logic_op']
			expr.name = obj['name']
			return expr
		return obj

	def serialize_xml(self, node):
		"""
		Salva il descrittore sul nodo XML I{node}.
		
		@param	node:			Nodo XML in cui salvare il descrittore.
		@type	node:			ET.Element
		"""
		for child in self.children:
			if isinstance(child, Operand):
				elem = ET.SubElement(node, 'operand')
			else:
				elem = ET.SubElement(node, 'expression')
			child.serialize_xml(elem)
		if self.logic_op != _HasLogic.LOGIC_NONE:
			node.attrib['logic_op'] = str(self.logic_op)
		if self.name is not None:
			node.attrib['name'] = self.name
	
	@classmethod
	def unserialize_xml(cls, node):
		"""
		Carica ed instanzia un descrittore dal nodo XML I{node}.
		
		@param	node:			Nodo XML da cui caricare la nuova istanza.
		@type	node:			ET.Element
		
		@return:				Nuova istanza caricata dal nodo.
		@rtype:					L{ColumnDescriptor}
		"""
		expr = Expression()
		for child in node.getchildren():
			if ET.iselement(child):
				if child.tag == 'expression':
					elem = Expression.unserialize_xml(child)
				elif child.tag == 'operand':
					elem = Operand.unserialize_xml(child)
				else:
					raise ValueError('Bad Expression XML definition')
				expr.children.append(elem)
				elem.parent = expr
		expr.logic_op = int(node.get('logic_op', _HasLogic.LOGIC_NONE))
		expr.name = node.get('name', None)
		return expr



def AND(*args):
	args = [x for x in args if x is not None]
	if len(args) == 1:
		return args[0]
	e = Expression()
	for arg in args:
		e.append(arg.copy(), _HasLogic.LOGIC_AND)
	return e



def OR(*args):
	args = [x for x in args if x is not None]
	if len(args) == 1:
		return args[0]
	e = Expression()
	for arg in args:
		e.append(arg.copy(), _HasLogic.LOGIC_OR)
	return e



def NOT(arg):
	e = arg.copy()
	e.logic_op ^= _HasLogic.LOGIC_NOT
	return e



def where(expr):
	if expr is None:
		return []
	elif isinstance(expr, text_base_types):
		return where(parse(expr))
	elif isinstance(expr, Operand):
		return [ expr.as_list(), None ]
	elif isinstance(expr, (tuple, list)):
		return expr
	else:
		return expr.as_list()



def loads(xml):
	if not xml:
		return None
	document = ET.ElementTree()
	if isinstance(xml, text_base_types):
		xml = ensure_text(xml).encode('utf-8')
	if isinstance(xml, data_base_types):
		xml = io.BytesIO(bytes(xml))
	if not ET.iselement(xml):
		xml = document.parse(xml, ET.XMLTreeBuilder(parse_comments=False))
	if xml.tag == 'operand':
		return Operand.unserialize_xml(xml)
	elif xml.tag == 'expression':
		return Expression.unserialize_xml(xml)
	raise ValueError('expected valid expression XML')



def dumps(expr):
	if expr is None:
		return ''
	elif isinstance(expr, Operand):
		node = ET.Element('operand')
		expr.serialize_xml(node)
		return ET.tostring(node)
	elif isinstance(expr, Expression):
		node = ET.Element('expression')
		expr.serialize_xml(node)
		return ET.tostring(node)
	raise ValueError('expected valid expression object')
	
	


# if __name__ == '__main__':
# 	sql = """(EB_Ciccio.a < 1) AND (EB_Pluto.b IN (0, 1, 2))"""
# # 	sql = """((EB_ClientiFornitori.Codice >= 'C00100') AND (EB_ClientiFornitori.Codice <= 'C00101')) AND ((EB_ClientiFornitori.ref_Azienda = 1) OR (EB_ClientiFornitori.ref_Azienda IS NULL)) AND (EB_ClientiFornitori.Tipo = 1)"""
# # 	sql = """(EB_Ciccio.a < 1) and (EB_Pluto.b != 'Antani')"""
# 	expr = parse(sql)
# 	print sql
# 	print expr.as_list()
# 	print type(expr)
# 	print expr


