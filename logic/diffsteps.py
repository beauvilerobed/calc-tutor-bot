"""Step-by-step differentiation with HTML output."""
import sympy
import functools
from collections import namedtuple

from logic import stepprinter
from logic.stepprinter import functionnames, replace_u_var

from sympy.core.function import AppliedUndef
from sympy.functions.elementary.trigonometric import TrigonometricFunction, InverseTrigonometricFunction
from sympy.functions.elementary.hyperbolic import HyperbolicFunction
from sympy.strategies.core import switch


# Rule types for differentiation steps
def Rule(name, props=""):
    return namedtuple(name, props + " context symbol")

ConstantRule = Rule("ConstantRule", "number")
ConstantTimesRule = Rule("ConstantTimesRule", "constant other substep")
PowerRule = Rule("PowerRule", "base exp")
AddRule = Rule("AddRule", "substeps")
MulRule = Rule("MulRule", "terms substeps")
DivRule = Rule("DivRule", "numerator denominator numerstep denomstep")
ChainRule = Rule("ChainRule", "substep inner u_var innerstep")
TrigRule = Rule("TrigRule", "f")
InverseTrigRule = Rule("InverseTrigRule", "f")  # For asin, acos, atan, etc.
HyperbolicRule = Rule("HyperbolicRule", "f")  # For sinh, cosh, tanh, etc.
ExpRule = Rule("ExpRule", "f base")
LogRule = Rule("LogRule", "arg base")
LogDiffRule = Rule("LogDiffRule", "base exp base_step exp_step")  # For f(x)^g(x)
FunctionRule = Rule("FunctionRule")
AlternativeRule = Rule("AlternativeRule", "alternatives")
DontKnowRule = Rule("DontKnowRule")
RewriteRule = Rule("RewriteRule", "rewritten substep")

DerivativeInfo = namedtuple('DerivativeInfo', 'expr symbol')

# Evaluators for computing derivatives from rules
_evaluators = {}

def evaluates(rule):
    """Decorator to register an evaluator for a rule type."""
    def decorator(func):
        _evaluators[rule] = func
        return func
    return decorator


def diff(rule):
    """Evaluate a differentiation rule to get the result."""
    evaluator = _evaluators.get(rule.__class__)
    if not evaluator:
        raise ValueError("Cannot evaluate derivative")
    return evaluator(*rule)


# Rule evaluators
@evaluates(ConstantRule)
def eval_constant(*args):
    return 0

@evaluates(ConstantTimesRule)
def eval_constanttimes(constant, other, substep, expr, symbol):
    return constant * diff(substep)

@evaluates(AddRule)
def eval_add(substeps, expr, symbol):
    return sum(diff(step) for step in substeps)

@evaluates(DivRule)
def eval_div(numer, denom, numerstep, denomstep, expr, symbol):
    d_numer, d_denom = diff(numerstep), diff(denomstep)
    return (denom * d_numer - numer * d_denom) / (denom ** 2)

@evaluates(ChainRule)
def eval_chain(substep, inner, u_var, innerstep, expr, symbol):
    return diff(substep).subs(u_var, inner) * diff(innerstep)

@evaluates(MulRule)
def eval_mul(terms, substeps, expr, symbol):
    diffs = [diff(s) for s in substeps]
    return sum(diffs[i] * functools.reduce(lambda a, b: a * b, 
               [t for j, t in enumerate(terms) if j != i], 1) 
               for i in range(len(terms)))

@evaluates(TrigRule)
def eval_trig(*args):
    return sympy.trigsimp(eval_default(*args))

@evaluates(RewriteRule)
def eval_rewrite(rewritten, substep, expr, symbol):
    return diff(substep)

@evaluates(AlternativeRule)
def eval_alternative(alternatives, expr, symbol):
    return diff(alternatives[1])

@evaluates(PowerRule)
@evaluates(ExpRule)
@evaluates(LogRule)
@evaluates(DontKnowRule)
@evaluates(FunctionRule)
@evaluates(InverseTrigRule)
@evaluates(HyperbolicRule)
def eval_default(*args):
    func, symbol = args[-2], args[-1]
    if isinstance(func, sympy.Symbol):
        func = sympy.Pow(func, 1, evaluate=False)
    
    substitutions, mapping = [], {}
    constant_symbol = sympy.Dummy()
    for arg in func.args:
        if symbol in arg.free_symbols:
            mapping[symbol] = arg
            substitutions.append(symbol)
        else:
            mapping[constant_symbol] = arg
            substitutions.append(constant_symbol)
    
    rule = func.func(*substitutions).diff(symbol)
    return rule.subs(mapping)


@evaluates(LogDiffRule)
def eval_logdiff(base, exp, base_step, exp_step, expr, symbol):
    """Evaluate f(x)^g(x) using logarithmic differentiation.
    
    d/dx[f^g] = f^g * (g' * ln(f) + g * f'/f)
    """
    f, g = base, exp
    df, dg = diff(base_step), diff(exp_step)
    return expr * (dg * sympy.log(f) + g * df / f)
    func, symbol = args[-2], args[-1]
    if isinstance(func, sympy.Symbol):
        func = sympy.Pow(func, 1, evaluate=False)
    
    substitutions, mapping = [], {}
    constant_symbol = sympy.Dummy()
    for arg in func.args:
        if symbol in arg.free_symbols:
            mapping[symbol] = arg
            substitutions.append(symbol)
        else:
            mapping[constant_symbol] = arg
            substitutions.append(constant_symbol)
    
    rule = func.func(*substitutions).diff(symbol)
    return rule.subs(mapping)


# Rule generators
def diff_steps(expr, symbol):
    """Generate differentiation steps for an expression."""
    # Convert Python numbers to SymPy objects
    if isinstance(expr, (int, float)):
        expr = sympy.sympify(expr)
    
    deriv = DerivativeInfo(expr, symbol)

    def key(d):
        e = d.expr
        if isinstance(e, TrigonometricFunction):
            return TrigonometricFunction
        if isinstance(e, InverseTrigonometricFunction):
            return InverseTrigonometricFunction
        if isinstance(e, HyperbolicFunction):
            return HyperbolicFunction
        if isinstance(e, AppliedUndef):
            return AppliedUndef
        if not e.has(symbol):
            return 'constant'
        return e.func

    return switch(key, {
        sympy.Pow: power_rule,
        sympy.Symbol: power_rule,
        sympy.Dummy: power_rule,
        sympy.Add: add_rule,
        sympy.Mul: mul_rule,
        TrigonometricFunction: trig_rule,
        InverseTrigonometricFunction: inverse_trig_rule,
        HyperbolicFunction: hyperbolic_rule,
        sympy.exp: exp_rule,
        sympy.log: log_rule,
        AppliedUndef: function_rule,
        'constant': constant_rule
    })(deriv)


def power_rule(derivative):
    expr, symbol = derivative.expr, derivative.symbol
    base, exp = expr.as_base_exp()

    if not base.has(symbol):
        if isinstance(exp, sympy.Symbol):
            return ExpRule(expr, base, expr, symbol)
        u = sympy.Dummy()
        f = base ** u
        return ChainRule(ExpRule(f, base, f, u), exp, u, diff_steps(exp, symbol), expr, symbol)
    elif not exp.has(symbol):
        if isinstance(base, sympy.Symbol):
            return PowerRule(base, exp, expr, symbol)
        u = sympy.Dummy()
        f = u ** exp
        return ChainRule(PowerRule(u, exp, f, u), base, u, diff_steps(base, symbol), expr, symbol)
    else:
        # Both base and exponent contain the variable: use logarithmic differentiation
        # d/dx[f^g] = f^g * (g' * ln(f) + g * f'/f)
        return LogDiffRule(base, exp, diff_steps(base, symbol), diff_steps(exp, symbol), expr, symbol)


def add_rule(derivative):
    expr, symbol = derivative.expr, derivative.symbol
    return AddRule([diff_steps(arg, symbol) for arg in expr.args], expr, symbol)


def constant_rule(derivative):
    return ConstantRule(derivative.expr, derivative.expr, derivative.symbol)


def mul_rule(derivative):
    expr, symbol = derivative.expr, derivative.symbol
    coeff, f = expr.as_independent(symbol)
    
    if coeff != 1:
        return ConstantTimesRule(coeff, f, diff_steps(f, symbol), expr, symbol)
    
    numer, denom = expr.as_numer_denom()
    if denom != 1:
        return DivRule(numer, denom, diff_steps(numer, symbol), diff_steps(denom, symbol), expr, symbol)
    
    return MulRule(expr.args, [diff_steps(g, symbol) for g in expr.args], expr, symbol)


def trig_rule(derivative):
    expr, symbol = derivative.expr, derivative.symbol
    arg = expr.args[0]
    
    default = TrigRule(expr, expr, symbol)
    if not isinstance(arg, sympy.Symbol):
        u = sympy.Dummy()
        default = ChainRule(TrigRule(expr.func(u), expr.func(u), u), arg, u, diff_steps(arg, symbol), expr, symbol)

    if isinstance(expr, (sympy.sin, sympy.cos)):
        return default
    
    # Rewrite rules for other trig functions
    rewrites = {
        sympy.tan: [sympy.sin(arg) / sympy.cos(arg)],
        sympy.csc: [1 / sympy.sin(arg)],
        sympy.sec: [1 / sympy.cos(arg)],
        sympy.cot: [1 / sympy.tan(arg), sympy.cos(arg) / sympy.sin(arg)],
    }
    
    if expr.func in rewrites:
        alts = [default] + [RewriteRule(r, diff_steps(r, symbol), expr, symbol) for r in rewrites[expr.func]]
        return AlternativeRule(alts, expr, symbol)
    
    return DontKnowRule(expr, symbol)


def inverse_trig_rule(derivative):
    """Handle inverse trig functions: asin, acos, atan, acot, asec, acsc."""
    expr, symbol = derivative.expr, derivative.symbol
    arg = expr.args[0]
    
    default = InverseTrigRule(expr, expr, symbol)
    if not isinstance(arg, sympy.Symbol):
        u = sympy.Dummy()
        default = ChainRule(InverseTrigRule(expr.func(u), expr.func(u), u), arg, u, diff_steps(arg, symbol), expr, symbol)
    
    return default


def hyperbolic_rule(derivative):
    """Handle hyperbolic functions: sinh, cosh, tanh, coth, sech, csch."""
    expr, symbol = derivative.expr, derivative.symbol
    arg = expr.args[0]
    
    default = HyperbolicRule(expr, expr, symbol)
    if not isinstance(arg, sympy.Symbol):
        u = sympy.Dummy()
        default = ChainRule(HyperbolicRule(expr.func(u), expr.func(u), u), arg, u, diff_steps(arg, symbol), expr, symbol)
    
    return default


def exp_rule(derivative):
    expr, symbol = derivative.expr, derivative.symbol
    exp_arg = expr.args[0]
    
    if isinstance(exp_arg, sympy.Symbol):
        return ExpRule(expr, sympy.E, expr, symbol)
    
    u = sympy.Dummy()
    f = sympy.exp(u)
    return ChainRule(ExpRule(f, sympy.E, f, u), exp_arg, u, diff_steps(exp_arg, symbol), expr, symbol)


def log_rule(derivative):
    expr, symbol = derivative.expr, derivative.symbol
    arg = expr.args[0]
    base = expr.args[1] if len(expr.args) == 2 else sympy.E
    
    if isinstance(arg, sympy.Symbol):
        return LogRule(arg, base, expr, symbol)
    
    u = sympy.Dummy()
    return ChainRule(LogRule(u, base, sympy.log(u, base), u), arg, u, diff_steps(arg, symbol), expr, symbol)


def function_rule(derivative):
    return FunctionRule(derivative.expr, derivative.symbol)


# Printer class for HTML output
class DiffPrinter(stepprinter.HTMLPrinter):
    """Generates HTML step-by-step differentiation output."""
    
    def __init__(self, rule):
        super().__init__()
        self.rule = rule
        self.alternative_functions_printed = set()
        self.print_rule(rule)

    def print_rule(self, rule):
        """Dispatch to appropriate print method."""
        method = getattr(self, f'print_{rule.__class__.__name__}', None)
        if method:
            method(rule)
        else:
            self.append(repr(rule))

    def print_ConstantRule(self, rule):
        with self.new_step():
            self.append(f"Derivative of {self.format_math(rule.number)} is 0.")

    def print_PowerRule(self, rule):
        with self.new_step():
            self.append(f"Power rule: {self.format_math(rule.context)} → {self.format_math(diff(rule))}")

    def print_ConstantTimesRule(self, rule):
        with self.new_step():
            self.append("Pull the constant out:")
            with self.new_level():
                self.print_rule(rule.substep)
            self.append(f"Result: {self.format_math(diff(rule))}")

    def print_AddRule(self, rule):
        with self.new_step():
            self.append("Differentiate each term:")
            with self.new_level():
                for substep in rule.substeps:
                    self.print_rule(substep)
            self.append(f"Result: {self.format_math(diff(rule))}")

    def print_MulRule(self, rule):
        with self.new_step():
            self.append("Product rule:")
            fnames = [sympy.Function(n)(rule.symbol) for n in functionnames(len(rule.terms))]
            derivatives = [sympy.Derivative(f, rule.symbol) for f in fnames]

            ruleform = []
            for i in range(len(rule.terms)):
                parts = [derivatives[i] if j == i else fnames[j] for j in range(len(rule.terms))]
                ruleform.append(functools.reduce(lambda a, b: a * b, parts))

            self.append(self.format_math_display(sympy.Eq(
                sympy.Derivative(functools.reduce(lambda a, b: a * b, fnames), rule.symbol),
                sum(ruleform))))

            for fname, deriv, term, substep in zip(fnames, derivatives, rule.terms, rule.substeps):
                self.append(f"{self.format_math(sympy.Eq(fname, term))}. Find {self.format_math(deriv)}:")
                with self.new_level():
                    self.print_rule(substep)

            self.append(f"Result: {self.format_math(diff(rule))}")

    def print_DivRule(self, rule):
        with self.new_step():
            x = rule.symbol
            ff, gg = sympy.Function("f")(x), sympy.Function("g")(x)
            qrule = sympy.Eq(sympy.Derivative(ff / gg, x), sympy.ratsimp(sympy.diff(ff / gg)))

            self.append("Quotient rule:")
            self.append(self.format_math_display(qrule))
            self.append(f"{self.format_math(sympy.Eq(ff, rule.numerator))}, {self.format_math(sympy.Eq(gg, rule.denominator))}.")
            self.append(f"Find {self.format_math(ff.diff(x))}:")
            with self.new_level():
                self.print_rule(rule.numerstep)
            self.append(f"Find {self.format_math(gg.diff(x))}:")
            with self.new_level():
                self.print_rule(rule.denomstep)
            self.append(f"Plug in: {self.format_math(diff(rule))}")

    def print_ChainRule(self, rule):
        with self.new_step(), self.new_u_vars() as (u, _):
            self.append(f"Let {self.format_math(sympy.Eq(u, rule.inner))}.")
            self.print_rule(replace_u_var(rule.substep, rule.u_var, u))
        with self.new_step():
            if isinstance(rule.innerstep, FunctionRule):
                self.append(f"Find {self.format_math(sympy.Derivative(rule.inner, rule.symbol))}:")
                self.append(self.format_math_display(diff(rule)))
            else:
                self.append(f"Find {self.format_math(sympy.Derivative(rule.inner, rule.symbol))}:")
                with self.new_level():
                    self.print_rule(rule.innerstep)
                self.append(f"Chain rule result: {self.format_math(diff(rule))}")

    def print_TrigRule(self, rule):
        with self.new_step():
            messages = {
                sympy.sin: "Derivative of sin is cos:",
                sympy.cos: "Derivative of cos is -sin:",
                sympy.sec: "Derivative of sec is sec·tan:",
                sympy.csc: "Derivative of csc is -csc·cot:",
            }
            self.append(messages.get(type(rule.f), "Trig derivative:"))
            self.append(self.format_math_display(sympy.Eq(sympy.Derivative(rule.f, rule.symbol), diff(rule))))

    def print_InverseTrigRule(self, rule):
        with self.new_step():
            messages = {
                sympy.asin: "Derivative of arcsin:",
                sympy.acos: "Derivative of arccos:",
                sympy.atan: "Derivative of arctan:",
                sympy.acot: "Derivative of arccot:",
                sympy.asec: "Derivative of arcsec:",
                sympy.acsc: "Derivative of arccsc:",
            }
            self.append(messages.get(type(rule.f), "Inverse trig derivative:"))
            self.append(self.format_math_display(sympy.Eq(sympy.Derivative(rule.f, rule.symbol), diff(rule))))

    def print_HyperbolicRule(self, rule):
        with self.new_step():
            messages = {
                sympy.sinh: "Derivative of sinh is cosh:",
                sympy.cosh: "Derivative of cosh is sinh:",
                sympy.tanh: "Derivative of tanh is sech²:",
                sympy.coth: "Derivative of coth is -csch²:",
                sympy.sech: "Derivative of sech is -sech·tanh:",
                sympy.csch: "Derivative of csch is -csch·coth:",
            }
            self.append(messages.get(type(rule.f), "Hyperbolic derivative:"))
            self.append(self.format_math_display(sympy.Eq(sympy.Derivative(rule.f, rule.symbol), diff(rule))))

    def print_ExpRule(self, rule):
        with self.new_step():
            if rule.base == sympy.E:
                self.append(f"Derivative of {self.format_math(sympy.exp(rule.symbol))} is itself.")
            else:
                self.append(self.format_math(sympy.Eq(sympy.Derivative(rule.f, rule.symbol), diff(rule))))

    def print_LogRule(self, rule):
        with self.new_step():
            self.append(f"Derivative of {self.format_math(rule.context)} is {self.format_math(diff(rule))}.")

    def print_AlternativeRule(self, rule):
        if rule.context.func in self.alternative_functions_printed:
            self.print_rule(rule.alternatives[0])
        elif len(rule.alternatives) == 2:
            self.alternative_functions_printed.add(rule.context.func)
            self.print_rule(rule.alternatives[1])
        else:
            self.alternative_functions_printed.add(rule.context.func)
            with self.new_step():
                self.append("Multiple ways to solve this:")
                for i, r in enumerate(rule.alternatives[1:]):
                    with self.new_collapsible():
                        self.append_header(f"Method {i + 1}")
                        with self.new_level():
                            self.print_rule(r)

    def print_RewriteRule(self, rule):
        with self.new_step():
            self.append("Rewrite:")
            self.append(self.format_math_display(sympy.Eq(rule.context, rule.rewritten)))
            self.print_rule(rule.substep)

    def print_FunctionRule(self, rule):
        with self.new_step():
            self.append("Trivial:")
            self.append(self.format_math_display(sympy.Eq(sympy.Derivative(rule.context, rule.symbol), diff(rule))))

    def print_LogDiffRule(self, rule):
        """Print steps for logarithmic differentiation of f(x)^g(x)."""
        f, g = rule.base, rule.exp
        x = rule.symbol

        with self.new_step():
            self.append(f"Use <strong>logarithmic differentiation</strong> (both base and exponent depend on {self.format_math(x)}):")

        with self.new_step():
            self.append(f"Let {self.format_math(sympy.Symbol('y'))} = {self.format_math(f**g)}. Take ln of both sides:")
            self.append(self.format_math_display(sympy.Eq(sympy.log(sympy.Symbol('y')), g * sympy.log(f))))

        with self.new_step():
            self.append("Differentiate both sides:")
            self.append(self.format_math_display(sympy.Symbol(r'\frac{1}{y} \cdot \frac{dy}{dx} = \frac{d}{dx}\left[' + sympy.latex(g) + r' \cdot \ln(' + sympy.latex(f) + r')\right]')))

        with self.new_step():
            self.append("Product rule on the right:")
            df = diff(rule.base_step)
            dg = diff(rule.exp_step)
            rhs = dg * sympy.log(f) + g * df / f
            self.append(self.format_math_display(sympy.Symbol(r'\frac{1}{y} \cdot \frac{dy}{dx} = ' + sympy.latex(rhs))))

        with self.new_step():
            self.append(f"Multiply by {self.format_math(sympy.Symbol('y'))} = {self.format_math(f**g)}:")
            result = diff(rule)
            self.append(self.format_math_display(sympy.Eq(sympy.Derivative(rule.context, x), result)))

    def print_DontKnowRule(self, rule):
        with self.new_step():
            self.append("No step-by-step available. Answer:")
            self.append(self.format_math_display(diff(rule)))

    def finalize(self):
        answer = diff(self.rule)
        if answer:
            simp = sympy.simplify(answer)
            if simp != answer:
                with self.new_step():
                    self.append('Simplify:')
                    self.append_raw(self.format_math_display(simp))
        self.lines.append('</ol>')
        return '\n'.join(self.lines)


def print_html_steps(function, symbol):
    """Generate HTML steps for differentiating a function."""
    return DiffPrinter(diff_steps(function, symbol)).finalize()
