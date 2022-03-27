from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import render
from django import forms
from django.views.generic.base import TemplateView
from django.views.generic import View
from chatbot.chat import chatbot_response
from logic.logic import UserInput
from mathtutor import settings
import json
import urllib
import urllib.parse
import traceback


HOME_PAGE_EXAMPLES = [
    ('Calculus', [
        ['Derivatives', [
            ('Learn how to use power rule and Chain rule', 'diff(cos(x)^7, x)'),
            ('See the steps for derivatives of this function',
             'diff(x^4 / (1 + (tan(sin(x))))^2)'),
            ('Learn multiple ways to derive functions', 'diff(cot(y), y)'),
            ('And if we don\'t know, we will let you know',
             'diff(x^x, x)'),
            ('Learn how to us the product rule on multiple functions', 'diff(x*cos(x)*sin(x)*tan(x), x)'),

        ]],
        ['Antiderivatives', [
            ('Learn how to integrate this function', 'integrate(cot(x))'),
            ('Learn common integrals', 'integrate(1/z, z)'),
            ('Learn steps for these integrals',
             'integrate(exp(2x) / (1 + exp(x)), x)'),
            'integrate(1 /(x^2-x-2),x)',
            'integrate((2+3/x)**2)',
            ('And if we don\'t know, we will let you know',
             'integrate(1/sqrt(x^2+1), x)'),
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
    i = forms.CharField(required=False, widget=TextInputWidget())

def index(request):
    form = SearchForm()

    return render(request, "index.html", {
        "form": form,
        "MEDIA_URL": settings.STATIC_URL,
        "examples": HOME_PAGE_EXAMPLES
    })

def input(request):
    if request.method == "GET":
        form = SearchForm(request.GET)
        if form.is_valid():
            input = form.cleaned_data["i"]
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


class ChatBotAppView(TemplateView):
    template_name = 'app.html'


class ChatBotApiView(View):
    def post(self, request, *args, **kwargs):
        input_data = json.loads(request.body.decode('utf-8'))
        msg = input_data['text']
        response = chatbot_response(msg)

        return JsonResponse({
            'text': [
                response
            ]
        }, status=200)


def handler404(request, exception):
    return render(request, "404.html")


def handler500(request):
    return render(request, "500.html")
