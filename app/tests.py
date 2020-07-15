from django.test import TestCase
from logic.utils import Eval
import json
from django.urls import reverse


class ViewTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('main')

    def test_get_main_page(self):
        """
        Test that the main page can be loaded.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class ApiTestCase(TestCase):
    """
    Tests to make sure that the chatBot app is
    properly working with the Django app.
    """

    def setUp(self):
        super().setUp()
        self.api_url = reverse('chatbot')

    def test_post(self):
        """
        Test that a response is returned.
        """
        data = {
            'text': 'How are you?'
        }
        response = self.client.post(
            self.api_url,
            data=json.dumps(data),
            content_type='application/json',
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('text', response.json())

    def test_other_post(self):
        """
        Test that a response is returned.
        """
        response = self.client.post(
            self.api_url,
            data=json.dumps({
                'text': 'Im stuck'
            }),
            content_type='application/json',
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('text', response.json())
        self.assertEqual(len(response.json()['text']), 1)

    def test_post_unicode(self):
        """
        Test that a response is returned.
        """
        response = self.client.post(
            self.api_url,
            data=json.dumps({
                'text': u'سلام'
            }),
            content_type='application/json',
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('text', response.json())
        self.assertEqual(len(response.json()['text']), 1)

    def test_escaped_unicode_post(self):
        """
        Test that unicode reponce
        """
        response = self.client.post(
            self.api_url,
            data=json.dumps({
                'text': '\u2013'
            }),
            content_type='application/json',
            format=json
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('text', response.json())

    def test_post_tags(self):
        post_data = {
            'text': 'Good morning.',
            'tags': [
                'user:jen@example.com'
            ]
        }
        response = self.client.post(
            self.api_url,
            data=json.dumps(post_data),
            content_type='application/json',
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('text', response.json())

    def test_get(self):
        response = self.client.get(self.api_url)

        self.assertEqual(response.status_code, 405)

    def test_patch(self):
        response = self.client.patch(self.api_url)

        self.assertEqual(response.status_code, 405)

    def test_put(self):
        response = self.client.put(self.api_url)

        self.assertEqual(response.status_code, 405)

    def test_delete(self):
        response = self.client.delete(self.api_url)

        self.assertEqual(response.status_code, 405)


class TestEval(TestCase):
    def test_eval1(self, object):
        e = Eval()
        assert e.eval("1+1") == "2"
        assert e.eval("1+1\n") == "2"
        assert e.eval("a=1+1") == ""
        assert e.eval("a=1+1\n") == ""
        assert e.eval("a=1+1\na") == "2"
        assert e.eval("a=1+1\na\n") == "2"
        assert e.eval("a=1+1\na=3") == ""
        assert e.eval("a=1+1\na=3\n") == ""

    def test_eval2(self, object):
        e = Eval()
        assert e.eval("\ndef f(x):\n\treturn x**2\nf(3)") == "9"
        assert e.eval("\ndef f(x):\n\treturn x**2\nf(3)\na = 5") == ""
        assert e.eval(
            "\ndef f(x):\n\treturn x**2\nif f(3) == 9:\n\ta = 1\nelse:\n\ta = 0\na") == "1"
        assert e.eval(
            "\ndef f(x):\n\treturn x**2 + 1\nif f(3) == 9:\n\ta = 1\nelse:\n\ta = 0\na") == "0"

    def test_eval3(self, object):
        e = Eval()
        assert e.eval("xxxx").startswith("Traceback")
        assert e.eval("""\
    def f(x):
        return x**2 + 1 + y
    if f(3) == 9:
        a = 1
    else:
        a = 0
    a
    """
                      ).startswith("Traceback")
