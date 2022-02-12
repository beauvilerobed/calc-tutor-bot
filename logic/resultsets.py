import sys
import sympy
from sympy.core.symbol import Symbol
import docutils.core
from logic import diffsteps
from logic import intsteps


class ResultCard(object):
    """
    Operations to generate a result card.

    title -- Title of the card

    result_statement -- Statement evaluated to get result

    pre_output_function -- Takes input expression and a symbol, returns a
    SymPy object
    """
    def __init__(self, title, result_statement, pre_output_function,
                 **kwargs):
        self.card_info = kwargs
        self.title = title
        self.result_statement = result_statement
        self.pre_output_function = pre_output_function

    def eval(self, evaluator, components, parameters=None):
        if parameters is None:
            parameters = {}
        else:
            parameters = parameters.copy()

        parameters = self.default_parameters(parameters)

        for component, val in components.items():
            parameters[component] = val

        variable = components['variable']

        line = self.result_statement.format(_var=variable, **parameters)
        line = line % 'input_evaluated'
        result = evaluator.eval(line, use_none_for_exceptions=True,
                                repr_expression=False)

        return result

    def format_input(self, input_repr, components, **parameters):
        if parameters is None:
            parameters = {}
        parameters = self.default_parameters(parameters)
        variable = components['variable']
        if 'format_input_function' in self.card_info:
            return self.card_info['format_input_function'](
                self.result_statement, input_repr, components)
        return self.result_statement.format(_var=variable, **parameters) % input_repr

    def format_output(self, output, formatter):
        if 'format_output_function' in self.card_info:
            return self.card_info['format_output_function'](output, formatter)
        return formatter(output)

    def format_title(self, input_evaluated):
        if self.card_info.get('format_title_function'):
            return self.card_info['format_title_function'](self.title,
                                                           input_evaluated)
        return self.title

    def is_multivariate(self):
        return self.card_info.get('multivariate', True)

    def default_parameters(self, kwargs):
        if 'parameters' in self.card_info:
            for arg in self.card_info['parameters']:
                kwargs.setdefault(arg, '')
        return kwargs

    def __repr__(self):
        return "<ResultCard '{}'>".format(self.title)


class FakeResultCard(ResultCard):
    """ResultCard whose displayed expression != actual code.

    Used when creating the result to be displayed involves code that a user
    would not normally need to do."""

    def __init__(self, *args, **kwargs):
        super(FakeResultCard, self).__init__(*args, **kwargs)
        assert 'eval_method' in kwargs

    def eval(self, evaluator, components, parameters=None):
        if parameters is None:
            parameters = {}
        return self.card_info['eval_method'](evaluator, components, parameters)


class MultiResultCard(ResultCard):
    """Tries multiple statements and displays the first that works."""

    def __init__(self, title, *cards):
        super(MultiResultCard, self).__init__(title, '', lambda *args: '')
        self.cards = cards
        self.cards_used = []

    def eval(self, evaluator, components, parameters):
        self.cards_used = []
        results = []

        # TODO Implicit state is bad, come up with better API
        # in particular a way to store variable, cards used
        for card in self.cards:
            try:
                result = card.eval(evaluator, components, parameters)
            except ValueError:
                continue
            if result != None:
                if not any(result == r[1] for r in results):
                    self.cards_used.append(card)
                    results.append((card, result))
        if results:
            self.input_repr = evaluator.get("input_evaluated")
            self.components = components
            return results
        return "None"

    def format_input(self, input_repr, components):
        return None

    def format_output(self, output, formatter):
        if not isinstance(output, list):
            return output
        html = ["<ul>"]
        for card, result in output:
            html.append('<li id="changedisplaytonone2">')
            html.append('<div class="cell_input">')
            html.append(card.format_input(self.input_repr, self.components))
            html.append('</div>')
            html.append(card.format_output(result, formatter))
            html.append('<script type="math/tex; mode=display"> \mathrm{with\;constant = C}</script>')
            html.append("</li>")
        html.append("</ul>")
        return " ".join(html)


# Decide which result card set to use

def is_derivative(input_evaluated):
    return isinstance(input_evaluated, sympy.Derivative)

def is_integral(input_evaluated):
    return isinstance(input_evaluated, sympy.Integral)

def is_numbersymbol(input_evaluated):
    return isinstance(input_evaluated, sympy.NumberSymbol)

def is_constant(input_evaluated):
    # is_constant reduces trig identities (even with simplify=False?) so we
    # check free_symbols instead
    return (hasattr(input_evaluated, 'free_symbols') and
            not input_evaluated.free_symbols)

def is_approximatable_constant(input_evaluated):
    # is_constant, but exclude Integer/Float/infinity
    return (hasattr(input_evaluated, 'free_symbols') and
            not input_evaluated.free_symbols and
            not input_evaluated.is_Integer and
            not input_evaluated.is_Float and
            input_evaluated.is_finite is not True)

def is_trig(input_evaluated):
    try:
        if (isinstance(input_evaluated, sympy.Basic) and
            any(input_evaluated.find(func)
                for func in (sympy.sin, sympy.cos, sympy.tan,
                             sympy.csc, sympy.sec, sympy.cot))):
            return True
    except AttributeError:
        pass
    return False

def is_not_constant_basic(input_evaluated):
    return (not is_constant(input_evaluated) and
            isinstance(input_evaluated, sympy.Basic) and
            not is_logic(input_evaluated))

def is_uncalled_function(input_evaluated):
    return hasattr(input_evaluated, '__call__') and not isinstance(input_evaluated, sympy.Basic)

def is_logic(input_evaluated):
    return isinstance(input_evaluated, (sympy.And, sympy.Or, sympy.Not, sympy.Xor))

def is_sum(input_evaluated):
    return isinstance(input_evaluated, sympy.Sum)

def is_product(input_evaluated):
    return isinstance(input_evaluated, sympy.Product)


# Functions to convert input and extract variable used

def default_variable(arguments, evaluated):
    try:
        variables = list(evaluated.atoms(sympy.Symbol))
    except:
        variables = []

    return {
        'variables': variables,
        'variable': variables[0] if variables else None,
        'input_evaluated': evaluated
    }

def extract_first(arguments, evaluated):
    result = default_variable(arguments, evaluated)
    result['input_evaluated'] = arguments[1][0]
    return result

def extract_integral(arguments, evaluated):
    limits = arguments[1][1:]
    variables = []

    if not limits:
        variables = [arguments[1][0].atoms(sympy.Symbol).pop()]
        limits = variables
    else:
        for limit in limits:
            if isinstance(limit, tuple):
                variables.append(limit[0])
            else:
                variables.append(limit)

    return {
        'integrand': arguments[1][0],
        'variables': variables,
        'variable': variables[0],
        'limits': limits
    }

def extract_derivative(arguments, evaluated):
    variables = list(sorted(arguments[1][0].atoms(sympy.Symbol), key=lambda x: x.name))

    variable = arguments[1][1:]
    if variable:
        variables.remove(variable[0])
        variables.insert(0, variable[0])

    return {
        'function': arguments[1][0],
        'variables': variables,
        'variable': variables[0],
        'input_evaluated': arguments[1][0]
    }

# Formatting functions

_function_formatters = {}
def formats_function(name):
    def _formats_function(func):
        _function_formatters[name] = func
        return func
    return _formats_function

def format_by_type(result, arguments=None, formatter=None, function_name=None):
    """
    Format something based on its type and on the input to Gamma.
    """
    if arguments and not function_name:
        function_name = arguments[0]
    if function_name in _function_formatters:
        return _function_formatters[function_name](result, arguments, formatter)
    elif function_name in all_cards and 'format_output_function' in all_cards[function_name].card_info:
        return all_cards[function_name].format_output(result, formatter)
    elif isinstance(result, (list, tuple)):
        return format_list(result, formatter)
    else:
        return formatter(result)

def format_nothing(arg, formatter):
    return arg

def format_steps(arg, formatter):
    return '<div class="steps">{}</div>'.format(arg)

def format_long_integer(line, integer, variable):
    intstr = str(integer)
    if len(intstr) > 100:
        # \xe2 is Unicode ellipsis
        return intstr[:20] + "..." + intstr[len(intstr) - 21:]
    return line % intstr

def format_integral(line, result, components):
    if components['limits']:
        limits = ', '.join(map(repr, components['limits']))
    else:
        limits = ', '.join(map(repr, components['variables']))

    return line.format(_var=limits) % components['integrand']

def format_function_docs_input(line, function, components):
    function = getattr(components['input_evaluated'], '__name__', str(function))
    return line % function

def format_dict_title(*title):
    def _format_dict(dictionary, formatter):
        html = ['<table>',
                '<thead><tr><th>{}</th><th>{}</th></tr></thead>'.format(*title),
                '<tbody>']
        try:
            fdict = dictionary.iteritems()
            if not any(isinstance(i,Symbol) for i in dictionary.keys()):
                fdict = sorted(dictionary.iteritems())
            for key, val in fdict:
                html.append('<tr><td>{}</td><td>{}</td></tr>'.format(key, val))
        except (AttributeError, TypeError):  # not iterable/not a dict
            return formatter(dictionary)
        html.append('</tbody></table>')
        return '\n'.join(html)
    return _format_dict

def format_list(items, formatter):
    try:
        if len(items) == 0:
            return "<p>No result</p>"
        html = ['<ul>']
        for item in items:
            html.append('<li>{}</li>'.format(formatter(item)))
        html.append('</ul>')
        return '\n'.join(html)
    except TypeError:  # not iterable, like None
        return formatter(items)

def format_nested_list_title(*titles):
    def _format_nested_list_title(items, formatter):
        try:
            if len(items) == 0:
                return "<p>No result</p>"
            html = ['<table>', '<thead><tr>']
            for title in titles:
                html.append('<th>{}</th>'.format(title))
            html.append('</tr></thead>')
            html.append('<tbody>')
            for item in items:
                html.append('<tr>')
                for subitem in item:
                    html.append('<td>{}</td>'.format(formatter(subitem)))
                html.append('</tr>')
            html.append('</tbody></table>')
            return '\n'.join(html)
        except TypeError:  # not iterable, like None
            return formatter(items)
    return _format_nested_list_title

def eval_integral(evaluator, components, parameters=None):
    return sympy.integrate(components['integrand'], *components['limits'])

def eval_integral_manual(evaluator, components, parameters=None):
    return sympy.integrals.manualintegrate(components['integrand'],
                                           components['variable'])

def eval_diffsteps(evaluator, components, parameters=None):
    function = components.get('function', evaluator.get('input_evaluated'))

    return diffsteps.print_html_steps(function,
                                      components['variable'])

def eval_intsteps(evaluator, components, parameters=None):
    integrand = components.get('integrand', evaluator.get('input_evaluated'))

    return intsteps.print_html_steps(integrand, components['variable'])

# https://www.python.org/dev/peps/pep-0257/
def trim(docstring):
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)

def eval_function_docs(evaluator, components, parameters=None):
    docstring = trim(evaluator.get("input_evaluated").__doc__)
    return docutils.core.publish_parts(docstring, writer_name='html4css1',
                                       settings_overrides={'_disable_config': True})['html_body']

# Result cards

no_pre_output = lambda *args: ""

all_cards = {
    'integral': ResultCard(
        "Integral",
        "integrate(%s, {_var})",
        sympy.Integral),

    'integral_fake': FakeResultCard(
        "Integral",
        "integrate(%s, {_var})",
        lambda i, var: sympy.Integral(i, *var),
        eval_method=eval_integral,
        format_input_function=format_integral
    ),

    'integral_manual': ResultCard(
        "Integral",
        "sympy.integrals.manualintegrate(%s, {_var})",
        sympy.Integral),

    'integral_manual_fake': FakeResultCard(
        "Integral",
        "sympy.integrals.manualintegrate(%s, {_var})",
        lambda i, var: sympy.Integral(i, *var),
        eval_method=eval_integral_manual,
        format_input_function=format_integral
    ),

    'diffsteps': FakeResultCard(
        "Derivative Steps",
        "diff(%s, {_var})",
        no_pre_output,
        format_output_function=format_steps,
        eval_method=eval_diffsteps),

    'intsteps': FakeResultCard(
        "Integral Steps",
        "integrate(%s, {_var})",
        no_pre_output,
        format_output_function=format_steps,
        eval_method=eval_intsteps,
        format_input_function=format_integral),

    'satisfiable': ResultCard(
        "Satisfiability",
        "satisfiable(%s)",
        no_pre_output,
        multivariate=False,
        format_output_function=format_dict_title('Variable', 'Possible Value')
    ),
}

def get_card(name):
    return all_cards.get(name, None)


all_cards['integral_alternate_fake'] = MultiResultCard(
    "I don't know the steps but here is the answer",
    get_card('integral_fake'),
)

"""
Syntax:

(predicate, extract_components, result_cards)

predicate: str or func
  If a string, names a function that uses this set of result cards.
  If a function, the function, given the evaluated input, returns True if
  this set of result cards should be used.

extract_components: None or func
  If None, use the default function.
  If a function, specifies a function that parses the input expression into
  a components dictionary. For instance, for an integral, this function
  might extract the limits, integrand, and variable.

result_cards: None or list
  If None, do not show any result cards for this function beyond the
  automatically generated 'Result' and 'Simplification' cards (if they are
  applicable).
  If a list, specifies a list of result cards to display.
"""
result_sets = [
    ('integrate', extract_integral, ['integral_alternate_fake', 'intsteps']),
    ('diff', extract_derivative, ['diff', 'diffsteps']),
    ('help', extract_first, ['function_docs']),
    ('rsolve', None, None),
    ('product', None, []),  # suppress automatic Result card
    (is_approximatable_constant, None, ['root_to_polynomial']),
    (is_uncalled_function, None, ['function_docs']),
    (is_trig, None, ['trig_alternate']),
    (is_logic, None, ['satisfiable', 'truth_table']),
    (is_sum, None, ['doit']),
    (is_product, None, ['doit']),
    (is_sum, None, None),
    (is_product, None, None),
    (is_not_constant_basic, None, [ 'diff', 'integral_alternate'])
]

def is_function_handled(function_name):
    """Do any of the result sets handle this specific function?"""
    if function_name == "simplify":
        return True
    return any(name == function_name for (name, _, cards) in result_sets if cards is not None)

def find_result_set(function_name, input_evaluated):
    """
    Finds a set of result cards based on function name and evaluated input.

    Returns:

    - Function that parses the evaluated input into components. For instance,
      for an integral this would extract the integrand and limits of integration.
      This function will always extract the variables.
    - List of result cards.
    """
    result = []
    result_converter = default_variable

    for predicate, converter, result_cards in result_sets:
        if predicate == function_name:
            if converter:
                result_converter = converter
            if result_cards is None:
                return result_converter, result
            for card in result_cards:
                if card not in result:
                    result.append(card)
        elif callable(predicate) and predicate(input_evaluated):
            if converter:
                result_converter = converter
            if result_cards is None:
                return result_converter, result
            for card in result_cards:
                if card not in result:
                    result.append(card)

    return result_converter, result