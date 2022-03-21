from __future__ import division
import collections
import traceback
import sys
import ast
import re
from io import StringIO
import sympy

OTHER_SYMPY_FUNCTIONS = ('sqrt',)

Arguments = collections.namedtuple('Arguments', 'function args kwargs')


class Eval(object):
    def __init__(self, namespace={}):
        self._namespace = namespace

    def get(self, name):
        return self._namespace.get(name)

    def set(self, name, value):
        self._namespace[name] = value

    def eval_node(self, node):
        tree = ast.fix_missing_locations(ast.Expression(node))
        return eval(compile(tree, '<string>', 'eval'), self._namespace)

    def eval(self, x, use_none_for_exceptions=False, repr_expression=True):
        globals = self._namespace
        try:
            x = x.strip()
            x = x.replace("\r", "")
            y = x.split('\n')
            if len(y) == 0:
                return ''
            s = '\n'.join(y[:-1]) + '\n'
            t = y[-1]
            try:
                z = compile(t + '\n', '', 'eval')
            except SyntaxError:
                s += '\n' + t
                z = None

            try:
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                eval(compile(s, '', 'exec', division.compiler_flag), globals, globals)

                if not z is None:
                    r = eval(z, globals)

                    if repr_expression:
                        r = repr(r)
                else:
                    r = ''

                if repr_expression:
                    sys.stdout.seek(0)
                    r = sys.stdout.read() + r
            finally:
                sys.stdout = old_stdout
            return r
        except:
            if use_none_for_exceptions:
                return
            etype, value, tb = sys.exc_info()
            # If you decide in the future to remove the first frame from the
            # traceback (since it links to our code, so it could be confusing
            # to the user), it's easy to do:
            #tb = tb.tb_next
            s = "".join(traceback.format_exception(etype, value, tb))
            return s


class LatexVisitor(ast.NodeVisitor):
    EXCEPTIONS = {'integrate': sympy.Integral, 'diff': sympy.Derivative}
    formatters = {}

    @staticmethod
    def formats_function(name):
        def _formats_function(f):
            LatexVisitor.formatters[name] = f
            return f
        return _formats_function

    def format(self, name, node):
        formatter = LatexVisitor.formatters.get(name)

        if not formatter:
            return None

        return formatter(node, self)

    def visit_Call(self, node):
        buffer = []
        fname = node.func.id

        # Only apply to lowercase names (i.e. functions, not classes)
        if fname in self.__class__.EXCEPTIONS:
            node.func.id = self.__class__.EXCEPTIONS[fname].__name__
            self.latex = sympy.latex(self.evaluator.eval_node(node))
        else:
            result = self.format(fname, node)
            if result:
                self.latex = result
            elif fname[0].islower() and fname not in OTHER_SYMPY_FUNCTIONS:
                buffer.append("\\mathrm{%s}" % fname.replace('_', '\\_'))
                buffer.append('(')

                latexes = []
                for arg in node.args:
                    if isinstance(arg, ast.Call) and getattr(arg.func, 'id', None) and arg.func.id[0].lower() == arg.func.id[0]:
                        latexes.append(self.visit_Call(arg))
                    else:
                        latexes.append(sympy.latex(
                            self.evaluator.eval_node(arg)))

                buffer.append(', '.join(latexes))
                buffer.append(')')

                self.latex = ''.join(buffer)
            else:
                self.latex = sympy.latex(self.evaluator.eval_node(node))
        return self.latex


@LatexVisitor.formats_function('rsolve')
def format_rsolve(node, visitor):
    recurrence = sympy.latex(
        sympy.Eq(visitor.evaluator.eval_node(node.args[0]), 0))
    if len(node.args) == 3:
        conds = visitor.evaluator.eval_node(node.args[2])
        initconds = '\\\\\n'.join(
            '&' + sympy.latex(sympy.Eq(eqn, val)) for eqn, val in conds.items())
        text = r'&\mathrm{Solve~the~recurrence~}' + recurrence + r'\\'
        condstext = r'&\mathrm{with~initial~conditions}\\'
        return r'\begin{align}' + text + condstext + initconds + r'\end{align}'
    else:
        return r'\mathrm{Solve~the~recurrence~}' + recurrence


@LatexVisitor.formats_function('summation')
@LatexVisitor.formats_function('product')
def format_diophantine(node, visitor):
    if node.func.id == 'summation':
        klass = sympy.Sum
    else:
        klass = sympy.Product
    return sympy.latex(klass(*map(visitor.evaluator.eval_node, node.args)))


@LatexVisitor.formats_function('help')
def format_help(node, visitor):
    if node.args:
        function = visitor.evaluator.eval_node(node.args[0])
        return r'\mathrm{Show~documentation~for~}' + function.__name__
    return r'\mathrm{Show~documentation~(requires~1~argument)}'


class TopCallVisitor(ast.NodeVisitor):
    def __init__(self):
        super(TopCallVisitor, self).__init__()
        self.call = None

    def visit_Call(self, node):
        self.call = node

    def visit_Name(self, node):
        if not self.call:
            self.call = node

# From https://stackoverflow.com/a/739301/262727


def ordinal(n):
    if 10 <= n % 100 < 20:
        return 'th'
    else:
        return {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, "th")

# TODO: modularize all of this


def latexify(string, evaluator):
    a = LatexVisitor()
    a.evaluator = evaluator
    a.visit(ast.parse(string))
    return a.latex


def topcall(string):
    a = TopCallVisitor()
    a.visit(ast.parse(string))
    if hasattr(a, 'call'):
        return getattr(a.call.func, 'id', None)
    return None


def arguments(string_or_node, evaluator):
    node = None
    if not isinstance(string_or_node, ast.Call):
        a = TopCallVisitor()
        a.visit(ast.parse(string_or_node))

        if hasattr(a, 'call'):
            node = a.call
    else:
        node = string_or_node

    if node:
        if isinstance(node, ast.Call):
            name = getattr(node.func, 'id', None)  # when is it undefined?
            args, kwargs = None, None
            if node.args:
                args = list(map(evaluator.eval_node, node.args))

            kwargs = node.keywords
            if kwargs:
                kwargs = {kwarg.arg: evaluator.eval_node(
                    kwarg.value) for kwarg in kwargs}

            return Arguments(name, args, kwargs)
        elif isinstance(node, ast.Name):
            return Arguments(node.id, [], {})
    return None


re_calls = re.compile(
    r'(Integer|Symbol|Float|Rational)\s*\([\'\"]?([a-zA-Z0-9\.]+)[\'\"]?\s*\)')


def re_calls_sub(match):
    return match.groups()[1]


def removeSymPy(string):
    try:
        return re_calls.sub(re_calls_sub, string)
    except IndexError:
        return string

