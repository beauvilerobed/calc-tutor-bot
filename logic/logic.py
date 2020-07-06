import sys
import traceback
import collections
from logic.utils import Eval, latexify, arguments, removeSymPy, \
    custom_implicit_transformation, synonyms, OTHER_SYMPY_FUNCTIONS
from logic.resultsets import find_result_set, get_card, format_by_type, \
    is_function_handled
from sympy import latex, series, sympify, solve, Derivative, \
    Integral, Symbol, diff, integrate
import sympy
from sympy.core.function import FunctionClass
from sympy.parsing.sympy_parser import stringify_expr, eval_expr, \
    standard_transformations, convert_xor, TokenError

PREEXEC = """from __future__ import division
from sympy import *
import sympy
from sympy.solvers.diophantine import diophantine
"""

def makeLatexReadable(*args):
    TeXcode = []
    for obj in args:
        if hasattr(obj, 'as_latex'):
            TeXcode.append(obj.as_latex())
        else:
            TeXcode.append(latex(obj))

    tag = '<script type="math/tex; mode=display">'
    if len(args) == 1:
        obj = args[0]
        if (isinstance(obj, sympy.Basic) and
            not obj.free_symbols and not obj.is_Integer and
            not obj.is_Float and
            obj.is_finite is not False and
            hasattr(obj, 'evalf')):
            tag = '<script type="math/tex; mode=display" data-numeric="true" ' \
                  'data-output-repr="{}" data-approximation="{}">'.format(
                      repr(obj), latex(obj.evalf(15)))

    TeXcode = ''.join(TeXcode)

    return ''.join([tag, TeXcode, '</script>'])

class UserInput(object):

    def changeToCards(self, s):
        result = None

        try:
            result = self.evaluateUserInput(s)
        except TokenError:
            return [
                {"title": "Input", "input": s},
                {"title": "Error", "input": s, "error": "Invalid input"}
            ]
        except Exception as e:
            return self.handleInputError(s, e)

        if result:
            parsed, arguments, evaluator, evaluated = result

            cards = []

            try:
                cards.extend(self.prepareCards(parsed, arguments, evaluator, evaluated))
            except ValueError as e:
                return self.handleInputError(s, e)

            return cards

    def handleInputError(self, s, e):
        if isinstance(e, SyntaxError):
            error = {
                "msg": e.msg,
                "offset": e.offset
            }
            if e.text:
                error["input_start"] = e.text[:e.offset]
                error["input_end"] = e.text[e.offset:]
            return [
                {"title": "Input", "input": s},
                {"title": "Error", "input": s, "exception_info": error}
            ]
        elif isinstance(e, ValueError):
            return [
                {"title": "Input", "input": s},
                {"title": "Error", "input": s, "error": e}
            ]
        else:
            trace = traceback.format_exc()
            trace = ("There was an error in Gamma.\n"
                     "For reference, the stack trace is:\n\n" + trace)
            return [
                {"title": "Input", "input": s},
                {"title": "Error", "input": s, "error": trace}
            ]


    def evaluateUserInput(self, s):
        namespace = {}
        exec(PREEXEC , namespace)

        evaluator = Eval(namespace)
        # change to True to spare the user from exceptions:
        if not len(s):
            return None

        transformations = []
        transformations.append(synonyms)
        transformations.extend(standard_transformations)
        transformations.extend((convert_xor, custom_implicit_transformation))
        parsed = stringify_expr(s, {}, namespace, transformations)
        try:
            evaluated = eval_expr(parsed, {}, namespace)
        except SyntaxError:
            raise
        except Exception as e:
            raise ValueError(str(e))
        input_repr = repr(evaluated)
        namespace['input_evaluated'] = evaluated

        return parsed, arguments(parsed, evaluator), evaluator, evaluated

    def getCardsAndComponents(self, arguments, evaluator, evaluated):
        first_func_name = arguments[0]
        # is the top-level function call to a function such as factorint or
        # simplify?
        is_function = False
        # is the top-level function being called?
        is_applied = arguments.args or arguments.kwargs

        first_func = evaluator.get(first_func_name)
        is_function = (
            first_func and
            not isinstance(first_func, FunctionClass) and
            not isinstance(first_func, sympy.Atom) and
            first_func_name and first_func_name[0].islower() and
            not first_func_name in OTHER_SYMPY_FUNCTIONS)

        if is_applied:
            convert_input, cards = find_result_set(arguments[0], evaluated)
        else:
            convert_input, cards = find_result_set(None, evaluated)

        components = convert_input(arguments, evaluated)
        if 'input_evaluated' in components:
            evaluated = components['input_evaluated']

        evaluator.set('input_evaluated', evaluated)

        return components, cards, evaluated, (is_function and is_applied)

    def prepareCards(self, parsed, arguments, evaluator, evaluated):
        components, cards, evaluated, is_function = self.getCardsAndComponents(arguments, evaluator, evaluated)

        if is_function:
            latex_input = ''.join(['<script type="math/tex; mode=display">',
                                   latexify(parsed, evaluator),
                                   '</script>'])
        else:
            latex_input = makeLatexReadable(evaluated)

        result = []

        result.append({
            "title": "Input",
            "input": removeSymPy(parsed),
            "output": latex_input
        })

        # If no result cards were found, but the top-level call is to a
        # function, then add a special result card to show the result
        if not cards and not components['variable'] and is_function:
            result.append({
                'title': 'Result',
                'input': removeSymPy(parsed),
                'output': format_by_type(evaluated, arguments, makeLatexReadable)
            })
        else:
            var = components['variable']

            # result of the function before the rest of the cards
            if is_function and not is_function_handled(arguments[0]):
                result.append(
                    {"title": "Result", "input": "",
                     "output": format_by_type(evaluated, arguments, makeLatexReadable)})

            for card_name in cards:
                card = get_card(card_name)

                if not card:
                    continue

                try:
                    result.append({
                        'card': card_name,
                        'var': repr(var),
                        'title': card.format_title(evaluated),
                        'input': card.format_input(repr(evaluated), components),
                        'pre_output': latex(
                            card.pre_output_function(evaluated, var)),
                        'parameters': card.card_info.get('parameters', [])
                    })
                except (SyntaxError, ValueError) as e:
                    pass
        return result

    def getCardInfo(self, card_name, expression, variable):
        card = get_card(card_name)

        if not card:
            raise KeyError

        _, arguments, evaluator, evaluated = self.evaluateUserInput(expression)
        variable = sympy.Symbol(variable)
        components, cards, evaluated, _ = self.getCardsAndComponents(arguments, evaluator, evaluated)
        components['variable'] = variable

        return {
            'var': repr(variable),
            'title': card.format_title(evaluated),
            'input': card.format_input(repr(evaluated), components),
            'pre_output': latex(card.pre_output_function(evaluated, variable))
        }

    def evaluateCard(self, card_name, expression, variable, parameters):
        card = get_card(card_name)

        if not card:
            raise KeyError

        _, arguments, evaluator, evaluated = self.evaluateUserInput(expression)
        variable = sympy.Symbol(variable)
        components, cards, evaluated, _ = self.getCardsAndComponents(arguments, evaluator, evaluated)
        components['variable'] = variable
        evaluator.set(str(variable), variable)
        result = card.eval(evaluator, components, parameters)

        return {
            'value': repr(result),
            'output': card.format_output(result, makeLatexReadable)
        }
