import sympy
import collections
from contextlib import contextmanager

from sympy import latex


def functionnames(numterms):
    if numterms == 2:
        return ["f", "g"]
    elif numterms == 3:
        return ["f", "g", "h"]
    else:
        return ["f_{}".format(i) for i in range(numterms)]

def replace_u_var(rule, old_u, new_u):
    d = rule._asdict()
    for field, val in d.items():
        if isinstance(val, sympy.Basic):
            d[field] = val.subs(old_u, new_u)
        elif isinstance(val, tuple):
            d[field] = replace_u_var(val, old_u, new_u)
        elif isinstance(val, list):
            result = []
            for item in val:
                if isinstance(item, tuple):
                    result.append(replace_u_var(item, old_u, new_u))
                else:
                    result.append(item)
            d[field] = result
    return rule.__class__(**d)

class Printer(object):
    def __init__(self):
        self.lines = []
        self.level = 0

    def append(self, text):
        self.lines.append(self.level * "\t" + text)

    def finalize(self):
        return "\n".join(self.lines)

    def format_math(self, math):
        return str(math)

    def format_math_display(self, math):
        return self.format_math(math)

    @contextmanager
    def new_level(self):
        self.level += 1
        yield self.level
        self.level -= 1

    @contextmanager
    def new_step(self):
        yield self.level
        self.lines.append('\n')

class LaTeXPrinter(Printer):
    def format_math(self, math):
        return latex(math)

class HTMLPrinter(LaTeXPrinter):
    def __init__(self):
        super(HTMLPrinter, self).__init__()
        self.lines = ['<ol id="changedisplaytonone">']

    def format_math(self, math):
        return '<script type="math/tex; mode=inline">{}</script>'.format(
            latex(math))

    def format_math_display(self, math):
        if not isinstance(math, str):
            math = latex(math)
        return '<script type="math/tex; mode=display">{}</script>'.format(
            math)

    @contextmanager
    def new_level(self):
        self.level += 1
        self.lines.append(' ' * 4 * self.level + '<div class="collapsible"><h2>open</h2><ol class="content">')
        yield
        self.lines.append(' ' * 4 * self.level + '</ol></div>')
        self.level -= 1

    @contextmanager
    def new_step(self):
        self.lines.append(' ' * 4 * self.level + '<li>')
        yield self.level
        self.lines.append(' ' * 4 * self.level + '</li>')

    @contextmanager
    def new_collapsible(self):
        self.lines.append(' ' * 4 * self.level + '<div target="_blank" id="change_to_invisible">')
        yield self.level
        self.lines.append(' ' * 4 * self.level + '</div>')

    @contextmanager
    def new_u_vars(self):
        self.u, self.du = sympy.Symbol('u'), sympy.Symbol('du')
        yield self.u, self.du

    def append(self, text):
        self.lines.append(' ' * 4 * (self.level + 1) + '<p>{}</p>'.format(text))

    def append_header(self, text):
        self.lines.append(' ' * 4 * (self.level + 1) + '<h2>{}</h2>'.format(text))
