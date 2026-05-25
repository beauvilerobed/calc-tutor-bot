"""Tests for the analytics module."""

from django.test import TestCase, RequestFactory

from app.analytics import Analytics, get_client_ip
from app.models import ChatbotRequest, SolverRequest


class TestAnalytics(TestCase):
    """Tests for the Analytics class."""

    def setUp(self):
        self.analytics = Analytics()

    def test_log_chatbot_request(self):
        self.analytics.log_chatbot_request(
            ip_address='192.168.1.1',
            was_calculus_related=True,
            had_steps_context=False,
        )

        self.assertEqual(ChatbotRequest.objects.count(), 1)
        entry = ChatbotRequest.objects.get()
        self.assertEqual(entry.ip, '192.168.1.1')
        self.assertTrue(entry.calculus_related)
        self.assertFalse(entry.had_steps)

    def test_log_solver_request(self):
        self.analytics.log_solver_request(
            ip_address='192.168.1.2',
            expression_type='derivative',
        )

        self.assertEqual(SolverRequest.objects.count(), 1)
        entry = SolverRequest.objects.get()
        self.assertEqual(entry.ip, '192.168.1.2')
        self.assertEqual(entry.expression_type, 'derivative')

    def test_rate_limit_allows_under_limit(self):
        ip = '192.168.1.3'

        for i in range(10):
            is_allowed, remaining, retry_after = self.analytics.check_rate_limit(
                ip, max_requests=10, window_seconds=60
            )
            self.assertTrue(is_allowed, f"Request {i+1} should be allowed")
            self.assertEqual(remaining, 10 - i - 1)
            self.assertEqual(retry_after, 0)

    def test_rate_limit_blocks_over_limit(self):
        ip = '192.168.1.4'

        for _ in range(10):
            self.analytics.check_rate_limit(ip, max_requests=10, window_seconds=60)

        is_allowed, remaining, retry_after = self.analytics.check_rate_limit(
            ip, max_requests=10, window_seconds=60
        )

        self.assertFalse(is_allowed)
        self.assertEqual(remaining, 0)
        self.assertGreater(retry_after, 0)

    def test_rate_limit_independent_per_ip(self):
        ip1 = '192.168.1.5'
        ip2 = '192.168.1.6'

        for _ in range(10):
            self.analytics.check_rate_limit(ip1, max_requests=10, window_seconds=60)

        is_allowed, _, _ = self.analytics.check_rate_limit(
            ip2, max_requests=10, window_seconds=60
        )
        self.assertTrue(is_allowed)

    def test_get_stats(self):
        self.analytics.log_chatbot_request('ip1', True, False)
        self.analytics.log_chatbot_request('ip1', True, True)
        self.analytics.log_chatbot_request('ip2', False, False)

        self.analytics.log_solver_request('ip1', 'derivative')
        self.analytics.log_solver_request('ip2', 'integral')
        self.analytics.log_solver_request('ip3', 'derivative')

        stats = self.analytics.get_stats(hours=1)

        self.assertEqual(stats['chatbot']['total_requests'], 3)
        self.assertEqual(stats['chatbot']['unique_users'], 2)
        self.assertEqual(stats['chatbot']['calculus_related'], 2)
        self.assertEqual(stats['chatbot']['with_steps_context'], 1)

        self.assertEqual(stats['solver']['total_requests'], 3)
        self.assertEqual(stats['solver']['unique_users'], 3)
        self.assertEqual(stats['solver']['by_type']['derivative'], 2)
        self.assertEqual(stats['solver']['by_type']['integral'], 1)

    def test_get_stats_excludes_old_entries(self):
        from datetime import timedelta
        from django.utils import timezone

        ChatbotRequest.objects.create(ip='old', calculus_related=True, had_steps=False)
        SolverRequest.objects.create(ip='old', expression_type='derivative')
        old_time = timezone.now() - timedelta(hours=48)
        ChatbotRequest.objects.filter(ip='old').update(timestamp=old_time)
        SolverRequest.objects.filter(ip='old').update(timestamp=old_time)

        self.analytics.log_chatbot_request('new', True, False)
        self.analytics.log_solver_request('new', 'integral')

        stats = self.analytics.get_stats(hours=24)
        self.assertEqual(stats['chatbot']['total_requests'], 1)
        self.assertEqual(stats['solver']['total_requests'], 1)


class TestGetClientIP(TestCase):
    """Tests for the get_client_ip function."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_get_ip_from_remote_addr(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'

        ip = get_client_ip(request)
        self.assertEqual(ip, '10.0.0.1')

    def test_get_ip_from_x_forwarded_for(self):
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 10.0.0.1'
        request.META['REMOTE_ADDR'] = '10.0.0.1'

        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.1')

    def test_get_ip_x_forwarded_for_single(self):
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '198.51.100.1'

        ip = get_client_ip(request)
        self.assertEqual(ip, '198.51.100.1')
