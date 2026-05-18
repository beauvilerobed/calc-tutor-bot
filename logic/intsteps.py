"""Step-by-step integration with HTML output."""
import sympy
from logic import stepprinter
from logic.stepprinter import replace_u_var

from sympy.integrals.manualintegrate import (
    integral_steps, manualintegrate, ConstantRule, ConstantTimesRule, 
    PowerRule, AddRule, URule, PartsRule, CyclicPartsRule, TrigRule, 
    ExpRule, ArctanRule, AlternativeRule, DontKnowRule, RewriteRule
)

# Import additional rules that may exist in newer SymPy versions
try:
    from sympy.integrals.manualintegrate import ReciprocalRule
except ImportError:
    ReciprocalRule = None

try:
    from sympy.integrals.manualintegrate import SinRule, CosRule
except ImportError:
    SinRule = CosRule = None

try:
    from sympy.integrals.manualintegrate import ArcsinRule
except ImportError:
    ArcsinRule = None

# Hyperbolic function rules
try:
    from sympy.integrals.manualintegrate import SinhRule, CoshRule
except ImportError:
    SinhRule = CoshRule = None

try:
    from sympy.integrals.manualintegrate import ArcsinhRule
except ImportError:
    ArcsinhRule = None

try:
    from sympy.integrals.manualintegrate import HyperbolicRule
except ImportError:
    HyperbolicRule = None

try:
    from sympy.integrals.manualintegrate import ReciprocalSqrtQuadraticRule
except ImportError:
    ReciprocalSqrtQuadraticRule = None

# LogRule may not exist in newer SymPy versions
try:
    from sympy.integrals.manualintegrate import LogRule
except ImportError:
    LogRule = None


def _manualintegrate(rule):
    """Compatibility wrapper for evaluating integration rules."""
    return rule.eval() if hasattr(rule, 'eval') else manualintegrate(rule.integrand, rule.variable)


def _get_rule_values(rule):
    """Get field values from a rule (works with namedtuples and dataclasses)."""
    if hasattr(rule, '_asdict'):
        return rule._asdict().values()
    elif hasattr(rule, '__dataclass_fields__'):
        from dataclasses import fields
        return [getattr(rule, f.name) for f in fields(rule)]
    return []


def contains_dont_know(rule):
    """Check if a rule contains any DontKnowRule."""
    if isinstance(rule, DontKnowRule):
        return True
    for val in _get_rule_values(rule):
        if hasattr(val, '__dataclass_fields__') or (isinstance(val, tuple) and hasattr(val, '_asdict')):
            if contains_dont_know(val):
                return True
        if isinstance(val, list) and any(contains_dont_know(i) for i in val if hasattr(i, '__dataclass_fields__') or (isinstance(i, tuple) and hasattr(i, '_asdict'))):
            return True
    return False


def filter_unknown_alternatives(rule):
    """Filter out alternatives that contain DontKnowRule."""
    if isinstance(rule, AlternativeRule):
        known = [r for r in rule.alternatives if not contains_dont_know(r)]
        # AlternativeRule fields changed in SymPy 1.14+
        if hasattr(rule, 'context'):
            return AlternativeRule(known or rule.alternatives, _get_context(rule), _get_symbol(rule))
        else:
            return AlternativeRule(rule.integrand, rule.variable, known or rule.alternatives)
    return rule


def _get_context(rule):
    """Get the context/integrand from a rule (compatible with old and new SymPy)."""
    return getattr(rule, 'context', None) or getattr(rule, 'integrand', None)


def _get_symbol(rule):
    """Get the symbol/variable from a rule (compatible with old and new SymPy)."""
    return getattr(rule, 'symbol', None) or getattr(rule, 'variable', None)


# Rule type to print method mapping
RULE_PRINTERS = {}

def prints_rule(rule_type):
    """Decorator to register a print method for a rule type."""
    def decorator(func):
        RULE_PRINTERS[rule_type] = func
        return func
    return decorator


class IntegralPrinter(stepprinter.HTMLPrinter):
    """Generates HTML step-by-step integration output."""
    
    def __init__(self, rule):
        super().__init__()
        self.rule = rule
        self.alternative_functions_printed = set()
        self.print_rule(rule)

    def print_rule(self, rule):
        """Dispatch to appropriate print method based on rule type."""
        for rule_type, printer in RULE_PRINTERS.items():
            if isinstance(rule, rule_type):
                printer(self, rule)
                return
        # Fallback for unknown rules - display nicely instead of repr()
        self._print_unknown_rule(rule)

    def _print_unknown_rule(self, rule):
        """Handle unknown rule types gracefully."""
        with self.new_step():
            integrand = _get_context(rule)
            var = _get_symbol(rule)
            if integrand and var:
                self.append("Evaluate:")
                self.append(self.format_math_display(
                    sympy.Eq(sympy.Integral(integrand, var), _manualintegrate(rule))))
            else:
                result = _manualintegrate(rule)
                if result:
                    self.append("Answer:")
                    self.append(self.format_math_display(result))

    @prints_rule(ConstantRule)
    def print_Constant(self, rule):
        with self.new_step():
            self.append("Integral of a constant:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))

    @prints_rule(ConstantTimesRule)
    def print_ConstantTimes(self, rule):
        with self.new_step():
            self.append("Pull the constant out:")
            self.append(self.format_math_display(sympy.Eq(
                sympy.Integral(_get_context(rule), _get_symbol(rule)),
                rule.constant * sympy.Integral(rule.other, _get_symbol(rule)))))
            with self.new_level():
                self.print_rule(rule.substep)
            self.append(f"Result: {self.format_math(_manualintegrate(rule))}")

    @prints_rule(PowerRule)
    def print_Power(self, rule):
        with self.new_step():
            self.append("Power rule:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))

    @prints_rule(AddRule)
    def print_Add(self, rule):
        with self.new_step():
            self.append("Integrate each term:")
            for substep in rule.substeps:
                with self.new_level():
                    self.print_rule(substep)
            self.append(f"Result: {self.format_math(_manualintegrate(rule))}")

    @prints_rule(URule)
    def print_U(self, rule):
        with self.new_step(), self.new_u_vars() as (u, du):
            var = _get_symbol(rule)
            dx = sympy.Symbol('d' + var.name, commutative=0)
            self.append(f"Let {self.format_math(sympy.Eq(u, rule.u_func))}.")
            self.append(f"Then {self.format_math(sympy.Eq(du, rule.u_func.diff(var) * dx))}. Substitute:")
            substep_integrand = _get_context(rule.substep)
            if substep_integrand:
                self.append(self.format_math_display(sympy.Integral(substep_integrand.subs(rule.u_var, u), u)))
            with self.new_level():
                self.print_rule(replace_u_var(rule.substep, var.name, u))
            self.append(f"Put {self.format_math(u)} back: {self.format_math_display(_manualintegrate(rule))}")

    @prints_rule(PartsRule)
    def print_Parts(self, rule):
        with self.new_step():
            self.append("Integration by parts:")
            u, v, du, dv = [sympy.Function(f)(_get_symbol(rule)) for f in ['u', 'v', 'du', 'dv']]
            self.append(self.format_math_display(
                r"\int \operatorname{u} \operatorname{dv} = \operatorname{u}\operatorname{v} - \int \operatorname{v} \operatorname{du}"))
            self.append(f"Let {self.format_math(sympy.Eq(u, rule.u))}, {self.format_math(sympy.Eq(dv, rule.dv))}.")
            self.append(f"So {self.format_math(sympy.Eq(du, rule.u.diff(_get_symbol(rule))))}.")
            self.append(f"Find {self.format_math(v)}:")
            with self.new_level():
                self.print_rule(rule.v_step)
            self.append("Evaluate the rest:")
            self.print_rule(rule.second_step)

    @prints_rule(CyclicPartsRule)
    def print_CyclicParts(self, rule):
        with self.new_step():
            self.append("Use integration by parts (the integrand will repeat):")
            u, dv = sympy.Function('u')(_get_symbol(rule)), sympy.Function('dv')(_get_symbol(rule))
            current_integrand = _get_context(rule)
            total_result = sympy.S.Zero
            sign = 1
            with self.new_level():
                for rl in rule.parts_rules:
                    with self.new_step():
                        self.append(f"For {self.format_math(current_integrand)}:")
                        self.append(f"Let {self.format_math(sympy.Eq(u, rl.u))}, {self.format_math(sympy.Eq(dv, rl.dv))}.")
                        v_f = _manualintegrate(rl.v_step)
                        du_f = rl.u.diff(_get_symbol(rule))
                        total_result += sign * rl.u * v_f
                        current_integrand = v_f * du_f
                        self.append(f"So {self.format_math(sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), total_result - sign * sympy.Integral(current_integrand, _get_symbol(rule))))}.")
                        sign *= -1
                with self.new_step():
                    self.append("The integral repeats. Move it to one side:")
                    self.append(self.format_math_display(sympy.Eq(
                        (1 - rule.coefficient) * sympy.Integral(_get_context(rule), _get_symbol(rule)), total_result)))
                    self.append("So:")
                    self.append(self.format_math_display(sympy.Eq(
                        sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))

    @prints_rule(TrigRule)
    def print_Trig(self, rule):
        with self.new_step():
            messages = {
                'sin': "Integral of sin is -cos:",
                'cos': "Integral of cos is sin:",
                'sec*tan': "Integral of sec·tan is sec:",
                'csc*cot': "Integral of csc·cot is -csc:",
            }
            self.append(messages.get(rule.func, "Trig integral:"))
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))

    @prints_rule(ExpRule)
    def print_Exp(self, rule):
        with self.new_step():
            if rule.base == sympy.E:
                self.append(r"\(e^x\) integrates to itself:")
            else:
                self.append("Exponential: divide by ln(base):")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))

    @prints_rule(ArctanRule)
    def print_Arctan(self, rule):
        with self.new_step():
            self.append(f"Arctangent rule: {self.format_math(1 / (1 + _get_symbol(rule) ** 2))} integrates to "
                       f"{self.format_math(_manualintegrate(rule))}.")

    @prints_rule(RewriteRule)
    def print_Rewrite(self, rule):
        with self.new_step():
            self.append("Rewrite:")
            self.append(self.format_math_display(sympy.Eq(_get_context(rule), rule.rewritten)))
            self.print_rule(rule.substep)

    @prints_rule(DontKnowRule)
    def print_DontKnow(self, rule):
        with self.new_step():
            self.append("No step-by-step available. Answer:")
            self.append(self.format_math_display(sympy.integrate(_get_context(rule), _get_symbol(rule))))

    @prints_rule(AlternativeRule)
    def print_Alternative(self, rule):
        rule = filter_unknown_alternatives(rule)
        if len(rule.alternatives) == 1:
            self.print_rule(rule.alternatives[0])
            return
        if _get_context(rule).func in self.alternative_functions_printed:
            self.print_rule(rule.alternatives[0])
        else:
            self.alternative_functions_printed.add(_get_context(rule).func)
            with self.new_step():
                self.append("Multiple ways to solve this:")
                for i, r in enumerate(rule.alternatives):
                    with self.new_collapsible():
                        self.append_header(f"Method {i + 1}")
                        with self.new_level():
                            self.print_rule(r)

    def format_math_constant(self, math):
        return f'<div class="step__math">\\[{sympy.latex(math)}+ \\mathrm{{C}}\\]</div>'

    def finalize(self):
        rule = filter_unknown_alternatives(self.rule)
        answer = _manualintegrate(rule)
        if answer:
            simp = sympy.simplify(sympy.trigsimp(answer))
            if simp != answer:
                answer = simp
                with self.new_step():
                    self.append('Simplify:')
                    self.append_raw(self.format_math_display(simp))
            with self.new_step():
                self.append('Add +C:')
                self.append_raw(self.format_math_constant(answer))
        self.lines.append('</ol>')
        return '\n'.join(self.lines)


# Register LogRule printer if available
if LogRule is not None:
    @prints_rule(LogRule)
    def print_Log(self, rule):
        with self.new_step():
            self.append(f"Log rule: {self.format_math(1 / rule.func)} integrates to "
                       f"{self.format_math(_manualintegrate(rule))}.")


# Register ReciprocalRule printer if available
if ReciprocalRule is not None:
    @prints_rule(ReciprocalRule)
    def print_Reciprocal(self, rule):
        with self.new_step():
            integrand = _get_context(rule)
            var = _get_symbol(rule)
            self.append(f"Integral of {self.format_math(integrand)} is ln:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(integrand, var), _manualintegrate(rule))))


# Register SinRule printer if available
if SinRule is not None:
    @prints_rule(SinRule)
    def print_Sin(self, rule):
        with self.new_step():
            self.append("Integral of sin is -cos:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))


# Register CosRule printer if available
if CosRule is not None:
    @prints_rule(CosRule)
    def print_Cos(self, rule):
        with self.new_step():
            self.append("Integral of cos is sin:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))


# Register ArcsinRule printer if available
if ArcsinRule is not None:
    @prints_rule(ArcsinRule)
    def print_Arcsin(self, rule):
        with self.new_step():
            self.append("Standard arcsine integral:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))


# Register ArcsinhRule printer if available (inverse hyperbolic sine)
if ArcsinhRule is not None:
    @prints_rule(ArcsinhRule)
    def print_Arcsinh(self, rule):
        with self.new_step():
            self.append("Inverse hyperbolic sine form:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))


# Register SinhRule printer if available
if SinhRule is not None:
    @prints_rule(SinhRule)
    def print_Sinh(self, rule):
        with self.new_step():
            self.append("Integral of sinh is cosh:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))


# Register CoshRule printer if available
if CoshRule is not None:
    @prints_rule(CoshRule)
    def print_Cosh(self, rule):
        with self.new_step():
            self.append("Integral of cosh is sinh:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))


# Register HyperbolicRule printer if available (generic hyperbolic)
if HyperbolicRule is not None:
    @prints_rule(HyperbolicRule)
    def print_Hyperbolic(self, rule):
        with self.new_step():
            messages = {
                'sinh': "Integral of sinh is cosh:",
                'cosh': "Integral of cosh is sinh:",
                'sech*tanh': "Integral of sech·tanh is -sech:",
                'csch*coth': "Integral of csch·coth is -csch:",
            }
            self.append(messages.get(getattr(rule, 'func', None), "Hyperbolic integral:"))
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), _manualintegrate(rule))))


# Register ReciprocalSqrtQuadraticRule printer if available
if ReciprocalSqrtQuadraticRule is not None:
    @prints_rule(ReciprocalSqrtQuadraticRule)
    def print_ReciprocalSqrtQuadratic(self, rule):
        with self.new_step():
            result = _manualintegrate(rule)
            if result.has(sympy.acosh) or result.has(sympy.asinh) or result.has(sympy.atanh):
                self.append("Inverse hyperbolic form:")
            else:
                self.append("Reciprocal square root of a quadratic:")
            self.append(self.format_math_display(
                sympy.Eq(sympy.Integral(_get_context(rule), _get_symbol(rule)), result)))


def print_html_steps(function, symbol):
    """Generate HTML steps for integrating a function."""
    rule = integral_steps(function, symbol)
    if isinstance(rule, DontKnowRule):
        raise ValueError("Cannot evaluate integral")
    return IntegralPrinter(rule).finalize()
