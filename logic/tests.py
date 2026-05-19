"""
Unit tests for the logic module: differentiation, integration, and math utilities.
"""
import unittest
import sympy
from sympy import Symbol, sin, cos, tan, exp, log, sqrt, pi, E, oo

from logic.diffsteps import diff_steps, DiffPrinter
from logic.intsteps import integral_steps, IntegralPrinter, _manualintegrate
from logic.limitsteps import print_html_steps as limit_html_steps
from logic.utils import Eval, latexify, arguments
from logic.logic import UserInput


class TestDifferentiation(unittest.TestCase):
    """Test cases for differentiation functionality."""

    def setUp(self):
        self.x = Symbol('x')
        self.y = Symbol('y')

    def test_constant_derivative(self):
        """Derivative of a constant is 0."""
        expr = sympy.Integer(5)
        result = sympy.diff(expr, self.x)
        self.assertEqual(result, 0)

    def test_linear_derivative(self):
        """Derivative of x is 1."""
        result = sympy.diff(self.x, self.x)
        self.assertEqual(result, 1)

    def test_power_rule(self):
        """Derivative of x^n is n*x^(n-1)."""
        expr = self.x ** 3
        result = sympy.diff(expr, self.x)
        self.assertEqual(result, 3 * self.x ** 2)

    def test_sum_rule(self):
        """Derivative of sum is sum of derivatives."""
        expr = self.x ** 2 + 3 * self.x + 5
        result = sympy.diff(expr, self.x)
        self.assertEqual(result, 2 * self.x + 3)

    def test_product_rule(self):
        """Derivative of product uses product rule."""
        expr = self.x * sin(self.x)
        result = sympy.diff(expr, self.x)
        expected = sin(self.x) + self.x * cos(self.x)
        self.assertEqual(sympy.simplify(result - expected), 0)

    def test_chain_rule(self):
        """Derivative with chain rule."""
        expr = sin(self.x ** 2)
        result = sympy.diff(expr, self.x)
        expected = 2 * self.x * cos(self.x ** 2)
        self.assertEqual(sympy.simplify(result - expected), 0)

    def test_trig_derivatives(self):
        """Test derivatives of trigonometric functions."""
        # sin -> cos
        self.assertEqual(sympy.diff(sin(self.x), self.x), cos(self.x))
        # cos -> -sin
        self.assertEqual(sympy.diff(cos(self.x), self.x), -sin(self.x))

    def test_exponential_derivative(self):
        """Derivative of e^x is e^x."""
        expr = exp(self.x)
        result = sympy.diff(expr, self.x)
        self.assertEqual(result, exp(self.x))

    def test_logarithm_derivative(self):
        """Derivative of ln(x) is 1/x."""
        expr = log(self.x)
        result = sympy.diff(expr, self.x)
        self.assertEqual(result, 1 / self.x)

    def test_diff_steps_generates_steps(self):
        """Test that diff_steps generates step-by-step output."""
        expr = self.x ** 2 + 3 * self.x
        steps = diff_steps(expr, self.x)
        self.assertIsNotNone(steps)

    def test_diff_printer_output(self):
        """Test that DiffPrinter produces HTML output."""
        expr = self.x ** 2
        steps = diff_steps(expr, self.x)
        printer = DiffPrinter(steps)
        html = printer.finalize()
        self.assertIsInstance(html, str)
        self.assertIn('<', html)  # Contains HTML tags


class TestIntegration(unittest.TestCase):
    """Test cases for integration functionality."""

    def setUp(self):
        self.x = Symbol('x')

    def test_constant_integral(self):
        """Integral of constant c is c*x."""
        expr = sympy.Integer(5)
        result = sympy.integrate(expr, self.x)
        self.assertEqual(result, 5 * self.x)

    def test_power_rule_integral(self):
        """Integral of x^n is x^(n+1)/(n+1)."""
        expr = self.x ** 2
        result = sympy.integrate(expr, self.x)
        self.assertEqual(result, self.x ** 3 / 3)

    def test_linear_integral(self):
        """Integral of x is x^2/2."""
        result = sympy.integrate(self.x, self.x)
        self.assertEqual(result, self.x ** 2 / 2)

    def test_sum_rule_integral(self):
        """Integral of sum is sum of integrals."""
        expr = self.x ** 2 + 3 * self.x + 5
        result = sympy.integrate(expr, self.x)
        expected = self.x ** 3 / 3 + 3 * self.x ** 2 / 2 + 5 * self.x
        self.assertEqual(sympy.simplify(result - expected), 0)

    def test_trig_integrals(self):
        """Test integrals of trigonometric functions."""
        # integral of sin(x) is -cos(x)
        result = sympy.integrate(sin(self.x), self.x)
        self.assertEqual(result, -cos(self.x))
        # integral of cos(x) is sin(x)
        result = sympy.integrate(cos(self.x), self.x)
        self.assertEqual(result, sin(self.x))

    def test_exponential_integral(self):
        """Integral of e^x is e^x."""
        result = sympy.integrate(exp(self.x), self.x)
        self.assertEqual(result, exp(self.x))

    def test_logarithm_integral(self):
        """Integral of 1/x is ln|x|."""
        result = sympy.integrate(1 / self.x, self.x)
        self.assertEqual(result, log(self.x))

    def test_definite_integral(self):
        """Test definite integral evaluation."""
        expr = self.x ** 2
        result = sympy.integrate(expr, (self.x, 0, 1))
        self.assertEqual(result, sympy.Rational(1, 3))

    def test_integral_steps_generates_steps(self):
        """Test that integral_steps generates step objects."""
        from sympy.integrals.manualintegrate import integral_steps as sympy_integral_steps
        expr = self.x ** 2
        steps = sympy_integral_steps(expr, self.x)
        self.assertIsNotNone(steps)

    def test_manualintegrate_wrapper(self):
        """Test the _manualintegrate compatibility wrapper."""
        from sympy.integrals.manualintegrate import integral_steps as sympy_integral_steps
        expr = self.x ** 2
        rule = sympy_integral_steps(expr, self.x)
        result = _manualintegrate(rule)
        expected = self.x ** 3 / 3
        self.assertEqual(sympy.simplify(result - expected), 0)


class TestLimits(unittest.TestCase):
    """Test cases for limit functionality."""

    def setUp(self):
        self.x = Symbol('x')

    def test_simple_limit(self):
        """Test simple polynomial limit."""
        expr = self.x ** 2 + 2 * self.x
        result = sympy.limit(expr, self.x, 3)
        self.assertEqual(result, 15)

    def test_limit_zero_over_zero(self):
        """Test 0/0 indeterminate form with factoring."""
        expr = (self.x ** 2 - 1) / (self.x - 1)
        result = sympy.limit(expr, self.x, 1)
        self.assertEqual(result, 2)

    def test_limit_sin_x_over_x(self):
        """Test classic sin(x)/x limit."""
        expr = sin(self.x) / self.x
        result = sympy.limit(expr, self.x, 0)
        self.assertEqual(result, 1)

    def test_limit_infinity(self):
        """Test limit at infinity."""
        expr = 1 / self.x
        result = sympy.limit(expr, self.x, oo)
        self.assertEqual(result, 0)

    def test_limit_negative_infinity(self):
        """Test limit at negative infinity."""
        expr = self.x ** 2
        result = sympy.limit(expr, self.x, -oo)
        self.assertEqual(result, oo)

    def test_limit_exponential(self):
        """Test exponential limit."""
        expr = exp(-self.x)
        result = sympy.limit(expr, self.x, oo)
        self.assertEqual(result, 0)

    def test_limit_exponential_form(self):
        """Test exponential form (1+1/x)^x limit (definition of e)."""
        expr = (1 + 1/self.x)**self.x
        result = sympy.limit(expr, self.x, oo)
        self.assertEqual(result, sympy.E)
        # Test that steps are generated with the 1^infinity form
        html = limit_html_steps(expr, self.x, oo)
        self.assertIn('indeterminate', html.lower())
        self.assertIn('log technique', html.lower())

    def test_limit_steps_generates_html(self):
        """Test that limit_html_steps generates HTML output."""
        expr = self.x ** 2
        html = limit_html_steps(expr, self.x, 3)
        self.assertIsInstance(html, str)
        self.assertIn('<ol', html)
        self.assertIn('step', html)

    def test_limit_steps_0_over_0(self):
        """Test limit steps for 0/0 form."""
        expr = (self.x ** 2 - 1) / (self.x - 1)
        html = limit_html_steps(expr, self.x, 1)
        self.assertIn('indeterminate', html.lower())

    def test_limit_steps_lhopital(self):
        """Test limit steps uses L'Hôpital's rule."""
        # Use x^2 * sin(1/x) / x which requires L'Hôpital
        # Or use a non-special 0/0 form
        expr = (self.x - sin(self.x)) / self.x**3
        html = limit_html_steps(expr, self.x, 0)
        self.assertIn("pital", html)  # L'Hôpital
    
    def test_limit_special_sin_over_x(self):
        """Test special limit sin(x)/x -> 1."""
        expr = sin(self.x) / self.x
        html = limit_html_steps(expr, self.x, 0)
        self.assertIn("Standard trig limit", html)


class TestEvalUtility(unittest.TestCase):
    """Test cases for the Eval utility class."""

    def setUp(self):
        self.eval = Eval()

    def test_simple_arithmetic(self):
        """Test simple arithmetic evaluation."""
        result = self.eval.eval("1 + 1")
        self.assertEqual(result, "2")

    def test_variable_assignment(self):
        """Test variable assignment returns empty string."""
        result = self.eval.eval("a = 5")
        self.assertEqual(result, "")

    def test_variable_usage(self):
        """Test using assigned variable."""
        self.eval.eval("a = 5")
        result = self.eval.eval("a")
        self.assertEqual(result, "5")

    def test_expression_with_newlines(self):
        """Test multiline expressions."""
        result = self.eval.eval("a = 2\nb = 3\na + b")
        self.assertEqual(result, "5")

    def test_function_definition_and_call(self):
        """Test defining and calling a function."""
        result = self.eval.eval("def f(x):\n    return x ** 2\nf(3)")
        self.assertEqual(result, "9")

    def test_invalid_expression_returns_traceback(self):
        """Test that invalid expressions return traceback."""
        result = self.eval.eval("undefined_variable")
        self.assertIn("Traceback", result)


class TestUserInput(unittest.TestCase):
    """Test cases for the UserInput class."""

    def setUp(self):
        self.user_input = UserInput()

    def test_simple_expression(self):
        """Test processing a simple expression."""
        result = self.user_input.change_to_cards("1 + 1")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_derivative_expression(self):
        """Test processing a derivative expression."""
        result = self.user_input.change_to_cards("diff(x**2, x)")
        self.assertIsInstance(result, list)

    def test_integral_expression(self):
        """Test processing an integral expression."""
        result = self.user_input.change_to_cards("integrate(x**2, x)")
        self.assertIsInstance(result, list)

    def test_limit_expression(self):
        """Test processing a limit expression."""
        result = self.user_input.change_to_cards("limit(x**2, x, 2)")
        self.assertIsInstance(result, list)

    def test_invalid_input_returns_error(self):
        """Test that invalid input returns an error card."""
        result = self.user_input.change_to_cards("((((")
        self.assertIsInstance(result, list)
        # Should have an error card
        has_error = any("Error" in str(card.get("title", "")) for card in result)
        self.assertTrue(has_error)


class TestSymbolicMath(unittest.TestCase):
    """Test cases for various symbolic math operations."""

    def setUp(self):
        self.x = Symbol('x')
        self.y = Symbol('y')

    def test_simplify(self):
        """Test expression simplification."""
        expr = (self.x ** 2 - 1) / (self.x - 1)
        result = sympy.simplify(expr)
        self.assertEqual(result, self.x + 1)

    def test_expand(self):
        """Test expression expansion."""
        expr = (self.x + 1) ** 2
        result = sympy.expand(expr)
        self.assertEqual(result, self.x ** 2 + 2 * self.x + 1)

    def test_factor(self):
        """Test expression factoring."""
        expr = self.x ** 2 - 1
        result = sympy.factor(expr)
        self.assertEqual(result, (self.x - 1) * (self.x + 1))

    def test_solve_linear(self):
        """Test solving linear equation."""
        result = sympy.solve(self.x + 1, self.x)
        self.assertEqual(result, [-1])

    def test_solve_quadratic(self):
        """Test solving quadratic equation."""
        result = sympy.solve(self.x ** 2 - 4, self.x)
        self.assertEqual(sorted(result), [-2, 2])

    def test_limit(self):
        """Test limit calculation."""
        expr = sin(self.x) / self.x
        result = sympy.limit(expr, self.x, 0)
        self.assertEqual(result, 1)

    def test_series_expansion(self):
        """Test Taylor series expansion."""
        expr = exp(self.x)
        result = sympy.series(expr, self.x, 0, 4)
        # First few terms: 1 + x + x^2/2 + x^3/6
        self.assertIn(self.x, result.free_symbols)


class TestLatexOutput(unittest.TestCase):
    """Test cases for LaTeX output generation."""

    def setUp(self):
        self.x = Symbol('x')

    def test_latex_simple_expression(self):
        """Test LaTeX generation for simple expression."""
        expr = self.x ** 2
        latex = sympy.latex(expr)
        self.assertEqual(latex, "x^{2}")

    def test_latex_fraction(self):
        """Test LaTeX generation for fractions."""
        expr = 1 / self.x
        latex = sympy.latex(expr)
        self.assertIn("frac", latex)

    def test_latex_integral(self):
        """Test LaTeX generation for integrals."""
        expr = sympy.Integral(self.x ** 2, self.x)
        latex = sympy.latex(expr)
        self.assertIn("int", latex)

    def test_latex_derivative(self):
        """Test LaTeX generation for derivatives."""
        expr = sympy.Derivative(self.x ** 2, self.x)
        latex = sympy.latex(expr)
        self.assertIn("frac", latex)  # d/dx notation


if __name__ == '__main__':
    unittest.main()
