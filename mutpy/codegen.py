# -*- coding: utf-8 -*-
"""
    codegen
    ~~~~~~~

    Extension to ast that allow ast -> python code generation.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: BSD.
"""
import ast
from mutpy import utils

BOOLOP_SYMBOLS = {
    ast.And:        'and',
    ast.Or:         'or'
}

BINOP_SYMBOLS = {
    ast.Add:        '+',
    ast.Sub:        '-',
    ast.Mult:       '*',
    ast.Div:        '/',
    ast.FloorDiv:   '//',
    ast.Mod:        '%',
    ast.LShift:     '<<',
    ast.RShift:     '>>',
    ast.BitOr:      '|',
    ast.BitAnd:     '&',
    ast.BitXor:     '^',
    ast.Pow:        '**'
}

CMPOP_SYMBOLS = {
    ast.Eq:         '==',
    ast.Gt:         '>',
    ast.GtE:        '>=',
    ast.In:         'in',
    ast.Is:         'is',
    ast.IsNot:      'is not',
    ast.Lt:         '<',
    ast.LtE:        '<=',
    ast.NotEq:      '!=',
    ast.NotIn:      'not in'
}

UNARYOP_SYMBOLS = {
    ast.Invert:     '~',
    ast.Not:        'not',
    ast.UAdd:       '+',
    ast.USub:       '-'
}

ALL_SYMBOLS = {}
ALL_SYMBOLS.update(BOOLOP_SYMBOLS)
ALL_SYMBOLS.update(BINOP_SYMBOLS)
ALL_SYMBOLS.update(CMPOP_SYMBOLS)
ALL_SYMBOLS.update(UNARYOP_SYMBOLS)

def to_source(node, indent_with=' ' * 4):
    """This function can convert a node tree back into python sourcecode.
    This is useful for debugging purposes, especially if you're dealing with
    custom asts not generated by python itself.

    It could be that the sourcecode is evaluable when the AST itself is not
    compilable / evaluable.  The reason for this is that the AST contains some
    more data than regular sourcecode does, which is dropped during
    conversion.

    Each level of indentation is replaced with `indent_with`.  Per default this
    parameter is equal to four spaces as suggested by PEP 8, but it might be
    adjusted to match the application's styleguide.
    """
    generator = SourceGenerator(indent_with)
    generator.visit(node)

    return  ''.join(generator.result)

def add_line_numbers(source):
    lines = source.split('\n')
    n = 0
    digits_number = len(str(len(lines)))

    while n < len(lines):
        lines[n] = '{:>{}}: {}'.format(n + 1, digits_number + 1, lines[n])
        n += 1

    return '\n'.join(lines)

def remove_extra_lines(source):
        parts = source.split('\n')
        result = [part for part in parts if part.strip()]
        return '\n'.join(result)


class AbstractSourceGenerator(ast.NodeVisitor):
    """This visitor is able to transform a well formed syntax tree into python
    sourcecode.  For more details have a look at the docstring of the
    `node_to_source` function.
    """

    def __init__(self, indent_with):
        self.result = []
        self.indent_with = indent_with
        self.indentation = 0
        self.new_line = False

    def write(self, x, node=None):
        self.correct_line_number(node)
        self.result.append(x)

    def correct_line_number(self, node):
        if self.new_line:
            if self.result:
                self.result.append('\n')
            self.result.append(self.indent_with * self.indentation)
            self.new_line = False

        if node and hasattr(node, 'lineno'):
            lines = len("".join(self.result).split('\n')) if self.result else 0
            line_diff = node.lineno - lines

            if line_diff:
                self.result.append(('\n' + (self.indent_with * self.indentation)) * line_diff)

    def newline(self, node=None):
        self.new_line = True
        self.correct_line_number(node)

    def body(self, statements):
        self.new_line = True
        self.indentation += 1
        for stmt in statements:
            self.visit(stmt)
        self.indentation -= 1

    def body_or_else(self, node):
        self.body(node.body)
        if node.orelse:
            self.newline()
            self.write('else:')
            self.body(node.orelse)

    def signature(self, node):
        want_comma = []
        def write_comma():
            if want_comma:
                self.write(', ')
            else:
                want_comma.append(True)

        padding = [None] * (len(node.args) - len(node.defaults))
        for arg, default in zip(node.args, padding + node.defaults):
            write_comma()
            self.visit(arg)
            if default is not None:
                self.write('=')
                self.visit(default)
        if node.vararg is not None:
            write_comma()
            self.write('*' + node.vararg.arg)
        if node.kwarg is not None:
            write_comma()
            self.write('**' + node.kwarg.arg)

    def decorators(self, node):
        for decorator in node.decorator_list:
            self.newline(decorator)
            self.write('@')
            self.visit(decorator)

    # Statements
    def visit_Assign(self, node):
        self.newline(node)
        for idx, target in enumerate(node.targets):
            if idx:
                self.write(', ')
            self.visit(target)
        self.write(' = ')
        self.visit(node.value)

    def visit_AugAssign(self, node):
        self.newline(node)
        self.visit(node.target)
        self.write(' ' + BINOP_SYMBOLS[type(node.op)] + '= ')
        self.visit(node.value)

    def visit_NameConstant(self, node):
        self.write(str(node.value), node)

    def visit_ImportFrom(self, node):
        self.newline(node)

        imports = []
        for alias in node.names:
            name = alias.name
            if alias.asname:
                name += ' as ' + alias.asname
            imports.append(name)
        self.write('from {}{} import {}'.format('.' * node.level, node.module or '', ', '.join(imports)))

    def visit_Import(self, node):
        self.newline(node)
        for item in node.names:
            self.write('import ')
            self.visit(item)

    def visit_Expr(self, node):
        self.newline(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.decorators(node)
        self.newline(node)
        self.write('def %s(' % node.name, node)
        self.signature(node.args)
        self.write('):')
        self.body(node.body)

    def visit_ClassDef(self, node):
        have_args = []
        def paren_or_comma():
            if have_args:
                self.write(', ')
            else:
                have_args.append(True)
                self.write('(')

        self.decorators(node)
        self.newline(node)
        self.write('class %s' % node.name, node)
        for base in node.bases:
            paren_or_comma()
            self.visit(base)
        # XXX: the if here is used to keep this module compatible
        #      with python 2.6.
        if hasattr(node, 'keywords'):
            for keyword in node.keywords:
                paren_or_comma()
                self.write(keyword.arg + '=')
                self.visit(keyword.value)
            if hasattr(node, 'starargs') and node.starargs is not None:
                paren_or_comma()
                self.write('*')
                self.visit(node.starargs)
            if hasattr(node, 'kwargs') and node.kwargs is not None:
                paren_or_comma()
                self.write('**')
                self.visit(node.kwargs)
        self.write(have_args and '):' or ':')
        self.body(node.body)

    def visit_If(self, node):
        self.newline(node)
        self.write('if ')
        self.visit(node.test)
        self.write(':')
        self.body(node.body)
        while node.orelse:
            else_ = node.orelse
            if len(else_) == 1 and isinstance(else_[0], ast.If):
                node = else_[0]
                self.newline()
                self.write('elif ')
                self.visit(node.test)
                self.write(':')
                self.body(node.body)
            else:
                self.newline()
                self.write('else:')
                self.body(else_)
                break

    def visit_For(self, node):
        self.newline(node)
        self.write('for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        self.write(':')
        self.body_or_else(node)

    def visit_While(self, node):
        self.newline(node)
        self.write('while ')
        self.visit(node.test)
        self.write(':')
        self.body_or_else(node)

    def visit_Pass(self, node):
        self.newline(node)
        self.write('pass', node)

    def visit_Print(self, node):
        # XXX: python 2.6 only
        self.newline(node)
        self.write('print ')
        want_comma = False
        if node.dest is not None:
            self.write(' >> ')
            self.visit(node.dest)
            want_comma = True
        for value in node.values:
            if want_comma:
                self.write(', ')
            self.visit(value)
            want_comma = True
        if not node.nl:
            self.write(',')

    def visit_Delete(self, node):
        self.newline(node)
        self.write('del ')

        for target in node.targets:
            self.visit(target)
            if target is not node.targets[-1]:
                self.write(', ')

    def visit_Global(self, node):
        self.newline(node)
        self.write('global ' + ', '.join(node.names))

    def visit_Nonlocal(self, node):
        self.newline(node)
        self.write('nonlocal ' + ', '.join(node.names))

    def visit_Return(self, node):
        self.newline(node)
        self.write('return')
        if node.value:
            self.write(' ')
            self.visit(node.value)


    def visit_Break(self, node):
        self.newline(node)
        self.write('break')

    def visit_Continue(self, node):
        self.newline(node)
        self.write('continue')

    def visit_Raise(self, node):
        # XXX: Python 2.6 / 3.0 compatibility
        self.newline(node)
        self.write('raise')
        if hasattr(node, 'exc') and node.exc is not None:
            self.write(' ')
            self.visit(node.exc)
            if node.cause is not None:
                self.write(' from ')
                self.visit(node.cause)
        elif hasattr(node, 'type') and node.type is not None:
            self.visit(node.type)
            if node.inst is not None:
                self.write(', ')
                self.visit(node.inst)
            if node.tback is not None:
                self.write(', ')
                self.visit(node.tback)

    # Expressions

    def visit_Attribute(self, node):
        self.visit(node.value)
        self.write('.' + node.attr)

    def visit_Call(self, node):
        want_comma = []
        def write_comma():
            if want_comma:
                self.write(', ')
            else:
                want_comma.append(True)

        self.visit(node.func)
        self.write('(')
        for arg in node.args:
            write_comma()
            self.visit(arg)
        for keyword in node.keywords:
            write_comma()
            self.write(keyword.arg + '=')
            self.visit(keyword.value)
        if getattr(node, 'starargs', None) is not None:
            write_comma()
            self.write('*')
            self.visit(node.starargs)
        if getattr(node, 'kwargs', None) is not None:
            write_comma()
            self.write('**')
            self.visit(node.kwargs)
        self.write(')')

    def visit_arg(self, node):
        self.write(node.arg)

    def visit_Name(self, node):
        if isinstance(node.id, str):
            self.write(node.id, node)
        else:
            self.visit(node.id)

    def visit_Str(self, node):
        self.write(repr(node.s))

    def visit_Bytes(self, node):
        self.write(repr(node.s))

    def visit_Num(self, node):
        self.write(repr(node.n))

    def visit_Tuple(self, node):
        self.write('(')
        idx = -1
        for idx, item in enumerate(node.elts):
            if idx:
                self.write(', ')
            self.visit(item)
        self.write(idx and ')' or ',)')


    def sequence_visit(left, right): #@NoSelf
        def visit(self, node):
            self.write(left)
            for idx, item in enumerate(node.elts):
                if idx:
                    self.write(', ')
                self.visit(item)
            self.write(right)
        return visit

    visit_List = sequence_visit('[', ']')
    visit_Set = sequence_visit('{', '}')
    del sequence_visit

    def visit_Dict(self, node):
        self.write('{')
        for idx, (key, value) in enumerate(zip(node.keys, node.values)):
            if idx:
                self.write(', ')
            self.visit(key)
            self.write(': ')
            self.visit(value)
        self.write('}')

    def visit_BinOp(self, node):
        self.visit(node.left)
        self.write(' %s ' % BINOP_SYMBOLS[type(node.op)])
        self.visit(node.right)

    def visit_BoolOp(self, node):
        self.write('(')
        for idx, value in enumerate(node.values):
            if idx:
                self.write(' %s ' % BOOLOP_SYMBOLS[type(node.op)])
            self.visit(value)
        self.write(')')

    def visit_Compare(self, node):
        #self.write('(')
        self.visit(node.left)
        for op, right in zip(node.ops, node.comparators):
            self.write(' %s ' % CMPOP_SYMBOLS[type(op)])
            self.visit(right)
        #self.write(')')

    def visit_UnaryOp(self, node):
        self.write('(')
        op = UNARYOP_SYMBOLS[type(node.op)]
        self.write(op)
        if op == 'not':
            self.write(' ')
        self.visit(node.operand)
        self.write(')')

    def visit_Subscript(self, node):
        self.visit(node.value)
        self.write('[')
        self.visit(node.slice)
        self.write(']')

    def visit_Slice(self, node):
        if node.lower is not None:
            self.visit(node.lower)
        self.write(':')
        if node.upper is not None:
            self.visit(node.upper)
        if node.step is not None:
            self.write(':')
            if not (isinstance(node.step, ast.Name) and node.step.id == 'None'):
                self.visit(node.step)

    def visit_ExtSlice(self, node):
        for idx, item in node.dims:
            if idx:
                self.write(', ')
            self.visit(item)

    def visit_Yield(self, node):
        self.write('yield')
        if node.value:
            self.write(' ')
            self.visit(node.value)

    def visit_Lambda(self, node):
        self.write('lambda ')
        self.signature(node.args)
        self.write(': ')
        self.visit(node.body)

    def visit_Ellipsis(self, node):
        self.write('Ellipsis')

    def generator_visit(left, right): #@NoSelf
        def visit(self, node):
            self.write(left)
            self.visit(node.elt)
            for comprehension in node.generators:
                self.visit(comprehension)
            self.write(right)
        return visit

    visit_ListComp = generator_visit('[', ']')
    visit_GeneratorExp = generator_visit('(', ')')
    visit_SetComp = generator_visit('{', '}')
    del generator_visit

    def visit_DictComp(self, node):
        self.write('{')
        self.visit(node.key)
        self.write(': ')
        self.visit(node.value)
        for comprehension in node.generators:
            self.visit(comprehension)
        self.write('}')

    def visit_IfExp(self, node):
        self.visit(node.body)
        self.write(' if ')
        self.visit(node.test)
        self.write(' else ')
        self.visit(node.orelse)

    def visit_Starred(self, node):
        self.write('*')
        self.visit(node.value)

    def visit_Repr(self, node):
        # XXX: python 2.6 only
        self.write('`')
        self.visit(node.value)
        self.write('`')

    # Helper Nodes

    def visit_alias(self, node):
        self.write(node.name)
        if node.asname is not None:
            self.write(' as ' + node.asname)

    def visit_comprehension(self, node):
        self.write(' for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        if node.ifs:
            for if_ in node.ifs:
                self.write(' if ')
                self.visit(if_)

    def visit_ExceptHandler(self, node):
        self.newline(node)
        self.write('except')
        if node.type is not None:
            self.write(' ')
            self.visit(node.type)
            if node.name is not None:
                self.write(' as ' + node.name)
        self.write(':')
        self.body(node.body)

    def visit_arg(self, node):
        self.write(node.arg)

    def visit_Assert(self, node):
        self.newline(node)
        self.write('assert ')
        self.visit(node.test)
        if node.msg:
            self.write(', ')
            self.visit(node.msg)


class SourceGeneratorPython32(AbstractSourceGenerator):

    __python_version__ = (3, 2)

    def visit_TryExcept(self, node):
        self.newline(node)
        self.write('try:')
        self.body(node.body)
        for handler in node.handlers:
            self.visit(handler)

    def visit_TryFinally(self, node):
        self.newline(node)
        self.write('try:')
        self.body(node.body)
        self.newline(node)
        self.write('finally:')
        self.body(node.finalbody)

    def visit_With(self, node):
        self.newline(node)
        self.write('with ')
        self.visit(node.context_expr)
        if node.optional_vars is not None:
            self.write(' as ')
            self.visit(node.optional_vars)
        self.write(':')
        self.body(node.body)


class SourceGeneratorPython33(AbstractSourceGenerator):

    __python_version__ = (3, 3)

    def visit_Try(self, node):
        self.newline(node)
        self.write('try:')
        self.body(node.body)
        for handler in node.handlers:
            self.visit(handler)
        if node.finalbody:
            self.newline(node)
            self.write('finally:')
            self.body(node.finalbody)


    def visit_With(self, node):
        self.newline(node)
        self.write('with ')
        for with_item in node.items:
            self.visit(with_item.context_expr)
            if with_item.optional_vars is not None:
                self.write(' as ')
                self.visit(with_item.optional_vars)
            if with_item != node.items[-1]:
                self.write(', ')
        self.write(':')
        self.body(node.body)


SourceGenerator = utils.get_by_python_version([
    SourceGeneratorPython32,
    SourceGeneratorPython33
])

