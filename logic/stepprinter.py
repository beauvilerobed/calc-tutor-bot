"""Step-by-step printing utilities for calculus operations."""
import sympy
from contextlib import contextmanager
from sympy import latex


def functionnames(numterms):
    """Generate function names (f, g, h, ...) for multi-term expressions."""
    if numterms <= 3:
        return ["f", "g", "h"][:numterms]
    return [f"f_{i}" for i in range(numterms)]


def replace_u_var(rule, old_u, new_u):
    """Replace a variable in a rule with a new variable."""
    # Handle both namedtuples (old SymPy) and dataclasses (SymPy 1.14+)
    if hasattr(rule, '_asdict'):
        # Old namedtuple style
        d = rule._asdict()
    elif hasattr(rule, '__dataclass_fields__'):
        # New dataclass style (SymPy 1.14+)
        from dataclasses import fields
        d = {f.name: getattr(rule, f.name) for f in fields(rule)}
    else:
        return rule
    
    for field, val in d.items():
        if isinstance(val, sympy.Basic):
            d[field] = val.subs(old_u, new_u)
        elif hasattr(val, '__dataclass_fields__') or (isinstance(val, tuple) and hasattr(val, '_asdict')):
            d[field] = replace_u_var(val, old_u, new_u)
        elif isinstance(val, list):
            d[field] = [replace_u_var(item, old_u, new_u) 
                        if hasattr(item, '__dataclass_fields__') or (isinstance(item, tuple) and hasattr(item, '_asdict'))
                        else item for item in val]
    return rule.__class__(**d)


class Printer:
    """Base class for step-by-step output printers."""
    
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
    """Printer that formats math as LaTeX."""
    
    def format_math(self, math):
        return latex(math)


class HTMLPrinter(LaTeXPrinter):
    """Printer that outputs HTML with embedded LaTeX for MathJax 3."""
    
    def __init__(self):
        super().__init__()
        self.lines = ['<ol class="steps">']
        self.u = self.du = None
        self.step_counter = 0

    def format_math(self, math):
        return f'<span class="step__math">\\({latex(math)}\\)</span>'

    def format_math_display(self, math):
        math_latex = math if isinstance(math, str) else latex(math)
        return f'<div class="step__math">\\[{math_latex}\\]</div>'

    @contextmanager
    def new_level(self):
        indent = ' ' * 4 * self.level
        self.level += 1
        self.lines.append(f'{indent}<ol class="steps steps--nested">')
        yield
        self.lines.append(f'{indent}</ol>')
        self.level -= 1

    @contextmanager
    def new_step(self):
        indent = ' ' * 4 * self.level
        self.step_counter += 1
        self.lines.append(f'{indent}<li class="step collapsible" data-step="{self.step_counter}">')
        self.lines.append(f'{indent}    <span class="step__hint" aria-hidden="true">Click to show step</span>')
        yield self.level
        self.lines.append(f'{indent}</li>')

    @contextmanager
    def new_collapsible(self):
        indent = ' ' * 4 * self.level
        self.lines.append(f'{indent}<div class="step__details">')
        yield self.level
        self.lines.append(f'{indent}</div>')

    @contextmanager
    def new_u_vars(self):
        self.u, self.du = sympy.Symbol('u'), sympy.Symbol('du')
        yield self.u, self.du

    def append(self, text):
        indent = ' ' * 4 * (self.level + 1)
        self.lines.append(f'{indent}<p class="step__text">{text}</p>')

    def append_raw(self, html):
        """Append raw HTML without wrapping in <p> tags."""
        indent = ' ' * 4 * (self.level + 1)
        self.lines.append(f'{indent}<div class="step__content">{html}</div>')

    def append_header(self, text):
        indent = ' ' * 4 * (self.level + 1)
        self.lines.append(f'{indent}<h2>{text}</h2>')
