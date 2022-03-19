import time
from django import template
import urllib
import urllib.parse
register = template.Library()


@register.inclusion_tag('card.html')
def show_card(cell, input):
    return {'cell': cell, 'input': input}

@register.tag(name='make_example')
def do_make_example(parser, token):
    try:
        _, example = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            "%r tag requires a single argument" % token.contents.split()[0])

    return ExampleLinkNode(example)

class ExampleLinkNode(template.Node):
    def __init__(self, example):
        self.example = template.Variable(example)

    def render(self, context):
        example = self.example.resolve(context)

        if isinstance(example, tuple):
            title, example = example[0], example[1]
        else:
            title, example = None, example

        buf = []
        if title:
            buf.append('<span>{}</span>'.format(title))

        buf.append('<a href="/input/?i={0}">{1}</a>'.format(
            urllib.parse.quote(example), example))
        return ' '.join(buf)
