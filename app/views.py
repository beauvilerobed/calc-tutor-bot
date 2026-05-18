from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import render
from django import forms
from django.views.generic import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from chatbot.llm_chat import llm_response
from logic.logic import UserInput
from mathtutor import settings
from app.analytics import get_analytics, get_client_ip
import json
import urllib.parse
import traceback
import logging

logger = logging.getLogger('calaun')


HOME_PAGE_EXAMPLES = [
    ('Calculus', [
        ['Derivatives', [
            # Basic rules
            ('Power rule basics', 'diff(x^5, x)'),
            ('Chain rule with trig', 'diff(sin(x^2), x)'),
            ('Product rule', 'diff(x^2 * ln(x), x)'),
            ('Quotient rule', 'diff(x/(x^2 + 1), x)'),
            # Intermediate
            ('Nested chain rule', 'diff(cos(x)^7, x)'),
            ('Multiple rules combined', 'diff(x*cos(x)*sin(x), x)'),
            ('Exponential functions', 'diff(exp(x^2), x)'),
            ('Logarithmic differentiation', 'diff(x^x, x)'),
            # Advanced
            ('Inverse trig functions', 'diff(arctan(x), x)'),
            ('Implicit style', 'diff(sqrt(1 - x^2), x)'),
        ]],
        ['Antiderivatives', [
            # Basic techniques
            ('Power rule for integrals', 'integrate(x^3, x)'),
            ('Basic trig integral', 'integrate(cos(x), x)'),
            ('Natural log pattern', 'integrate(1/x, x)'),
            # U-substitution
            ('U-sub with chain rule', 'integrate(x*exp(x^2), x)'),
            ('Trig substitution prep', 'integrate(sin(x)*cos(x), x)'),
            # Integration techniques
            ('Integration by parts', 'integrate(x*exp(x), x)'),
            ('Partial fractions', 'integrate(1/(x^2 - 1), x)'),
            ('Trig identities', 'integrate(sin(x)^2, x)'),
            # Advanced
            ('Inverse trig result', 'integrate(1/sqrt(1 - x^2), x)'),
            ('Hyperbolic functions', 'integrate(sinh(x), x)'),
        ]],
        ['Limits', [
            # Direct evaluation
            ('Direct substitution', 'limit(x^2 + 2*x, x, 3)'),
            ('Continuous function', 'limit(cos(x), x, 0)'),
            # Indeterminate forms
            ('Classic indeterminate form', 'limit((x^2 - 4)/(x - 2), x, 2)'),
            ('Factor and cancel', 'limit((x^2 - 1)/(x - 1), x, 1)'),
            ('Fundamental trig limit', 'limit(sin(x)/x, x, 0)'),
            ('Exponential limit', 'limit((exp(x) - 1)/x, x, 0)'),
            # Limits at infinity
            ('Limit at infinity', 'limit(1/x, x, oo)'),
            ('Rational function', 'limit((2*x^2 + 3)/(x^2 - 1), x, oo)'),
            ('Exponential dominance', 'limit(exp(x)/x^2, x, oo)'),
            # Special limits
            ('Definition of e', 'limit((1 + 1/x)^x, x, oo)'),
            # One-sided limits
            ('One-sided approach', 'limit(1/x, x, 0, "+")'),
        ]],
    ]),
]

class TextInputWidget(forms.widgets.TextInput):
    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        attrs['autocorrect'] = 'off'
        attrs['autocapitalize'] = 'off'
        return super(TextInputWidget, self).render(name, value, attrs)

class SearchForm(forms.Form):
    i = forms.CharField(
        required=False,
        widget=TextInputWidget(attrs={
            'placeholder': "Try a derivative, integral, or limit."
        }),
    )

def index(request):
    form = SearchForm()

    return render(request, "index.html", {
        "form": form,
        "MEDIA_URL": settings.STATIC_URL,
        "examples": HOME_PAGE_EXAMPLES
    })

def _detect_expression_type(input_str):
    """Detect the type of calculus expression."""
    input_lower = input_str.lower().strip()
    if input_lower.startswith('diff(') or input_lower.startswith('derivative('):
        return 'derivative'
    elif input_lower.startswith('integrate(') or input_lower.startswith('integral('):
        return 'integral'
    elif input_lower.startswith('limit('):
        return 'limit'
    else:
        return 'other'

def input(request):
    if request.method == "GET":
        form = SearchForm(request.GET)
        if form.is_valid():
            input = form.cleaned_data["i"]
            
            # Log solver usage
            ip = get_client_ip(request)
            expr_type = _detect_expression_type(input)
            get_analytics().log_solver_request(ip, expr_type)
            
            evaluated = UserInput().change_to_cards(input)
            if not evaluated:
                evaluated = [{
                    "title": "Input",
                    "input": input,
                    "output": "Can't handle the input."
                }]
            return render(request, "result.html", {
                "input": input,
                "result": evaluated,
                "form": form,
                "MEDIA_URL": settings.STATIC_URL,
            })


def process_variables_and_expressions(request, card_name):
    variable_from_input = request.GET.get('variable')
    expression_from_input = request.GET.get('expression')

    if not variable_from_input or not expression_from_input:
        raise Http404

    unquoted_variable = urllib.parse.unquote(variable_from_input)
    unquoted_expression = urllib.parse.unquote(expression_from_input)

    parameters = {}
    for key, val in request.GET.items():
        parameters[key] = ''.join(val)

    return unquoted_variable, unquoted_expression, parameters


def return_result_as_card(request, card_name):
    unquoted_variable, unquoted_expression, parameters = process_variables_and_expressions(
        request, card_name)
    try:
        result = UserInput().evaluate_card(
            card_name, unquoted_expression, unquoted_variable, parameters)
    except ValueError as e:
        return HttpResponse(json.dumps({
            'error': e
        }), content_type="application/json")
    except:
        trace = traceback.format_exc(5)
        return HttpResponse(json.dumps({
            'error': ('There was an error. For reference'
                      'the last five traceback entries are: ' + trace)
        }), content_type="application/json")

    return HttpResponse(json.dumps(result), content_type="application/json")
      
def reference_guide(request):
    return render(request, "reference.html", {
        "MEDIA_URL": settings.STATIC_URL,
        "table_active": "selected",
    })


@method_decorator(csrf_exempt, name='dispatch')
class LLMChatBotApiView(View):
    """LLM-powered chatbot that helps students understand solution steps."""
    
    def post(self, request, *args, **kwargs):
        # Rate limiting check
        ip = get_client_ip(request)
        analytics = get_analytics()
        
        # 10 requests per minute per IP
        is_allowed, remaining, retry_after = analytics.check_rate_limit(
            ip, max_requests=10, window_seconds=60
        )
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {ip[:12]}...")
            return JsonResponse({
                'text': (
                    "You've sent too many messages. "
                    f"Please wait {retry_after} seconds and try again. "
                    "This limit helps ensure fair access for all students."
                ),
                'rate_limited': True,
                'retry_after': retry_after,
            }, status=429)
        
        # Parse request
        input_data = json.loads(request.body.decode('utf-8'))
        msg = input_data.get('text', '')
        steps_html = input_data.get('steps', '')
        history = input_data.get('history', [])
        
        # Log the request
        analytics.log_chatbot_request(
            ip_address=ip,
            was_calculus_related=True,  # Will be determined by llm_chat
            had_steps_context=bool(steps_html)
        )
        
        # Get response
        response = llm_response(msg, steps_html, history)
        
        result = JsonResponse({
            'text': response
        }, status=200)
        
        # Add rate limit headers
        result['X-RateLimit-Remaining'] = remaining
        result['X-RateLimit-Limit'] = 10
        
        return result


def stats_page(request):
    """Public stats page showing usage analytics."""
    hours = int(request.GET.get('hours', 24))
    stats = get_analytics().get_stats(hours=hours)
    
    # Calculate percentages for the breakdown bars
    total_solver = stats['solver']['total_requests']
    if total_solver > 0:
        stats['solver']['by_type_with_pct'] = {
            k: {'count': v, 'pct': round(v / total_solver * 100)}
            for k, v in stats['solver']['by_type'].items()
        }
    else:
        stats['solver']['by_type_with_pct'] = {}
    
    return render(request, 'stats.html', {
        'stats': stats,
        'hours': hours,
    })


def privacy_page(request):
    return render(request, "privacy.html")


def handler404(request, exception):
    return render(request, "404.html")


def handler500(request):
    return render(request, "500.html")
