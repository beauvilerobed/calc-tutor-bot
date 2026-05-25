"""
Simple analytics for tracking usage.

Tracks:
- Chatbot requests (per IP, timestamp, calculus-related or not)
- Solver requests (expression type: derivative, integral, limit)
- Rate limiting state

Request logs are persisted to the database so stats are consistent across
multiple workers and survive process restarts. Rate limiting stays in-memory
per worker — that's fine because the limit is conservative and per-IP.
"""

import time
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger('calaun')


class Analytics:
    """DB-backed analytics tracker with in-memory rate limiting."""

    def __init__(self):
        self._rate_limits = defaultdict(list)  # IP -> list of timestamps

    def log_chatbot_request(self, ip_address, was_calculus_related=True,
                            had_steps_context=False):
        """Persist a chatbot API request."""
        from app.models import ChatbotRequest
        ChatbotRequest.objects.create(
            ip=ip_address,
            calculus_related=was_calculus_related,
            had_steps=had_steps_context,
        )
        logger.info(f"Chatbot request from {ip_address[:12]}... "
                   f"(calculus={was_calculus_related}, steps={had_steps_context})")

    def log_solver_request(self, ip_address, expression_type):
        """Persist a solver request (derivative, integral, limit, other)."""
        from app.models import SolverRequest
        SolverRequest.objects.create(
            ip=ip_address,
            expression_type=expression_type,
        )
        logger.info(f"Solver request from {ip_address[:12]}... ({expression_type})")

    def check_rate_limit(self, ip_address, max_requests=10, window_seconds=60):
        """
        Check if IP is rate limited.

        Default: 10 requests per minute per IP for chatbot.
        This is conservative to ensure fair access for all users.

        Returns:
            tuple: (is_allowed, requests_remaining, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window_seconds

        self._rate_limits[ip_address] = [
            ts for ts in self._rate_limits[ip_address]
            if ts > window_start
        ]

        current_count = len(self._rate_limits[ip_address])

        if current_count >= max_requests:
            oldest = min(self._rate_limits[ip_address])
            retry_after = int(oldest + window_seconds - now) + 1
            return False, 0, retry_after

        self._rate_limits[ip_address].append(now)
        remaining = max_requests - current_count - 1

        return True, remaining, 0

    def get_stats(self, hours=24):
        """Get usage statistics for the last N hours."""
        from app.models import ChatbotRequest, SolverRequest

        cutoff = timezone.now() - timedelta(hours=hours)

        chatbot_qs = ChatbotRequest.objects.filter(timestamp__gt=cutoff)
        solver_qs = SolverRequest.objects.filter(timestamp__gt=cutoff)

        chatbot_total = chatbot_qs.count()
        chatbot_unique = chatbot_qs.values('ip').distinct().count()
        chatbot_calc = chatbot_qs.filter(calculus_related=True).count()
        chatbot_steps = chatbot_qs.filter(had_steps=True).count()

        solver_total = solver_qs.count()
        solver_unique = solver_qs.values('ip').distinct().count()
        solver_by_type = {
            row['expression_type']: row['n']
            for row in solver_qs.values('expression_type').annotate(n=Count('id'))
        }

        return {
            'period_hours': hours,
            'chatbot': {
                'total_requests': chatbot_total,
                'unique_users': chatbot_unique,
                'calculus_related': chatbot_calc,
                'with_steps_context': chatbot_steps,
            },
            'solver': {
                'total_requests': solver_total,
                'unique_users': solver_unique,
                'by_type': solver_by_type,
            }
        }


_analytics = None


def get_analytics():
    """Get or create the analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = Analytics()
    return _analytics


def get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip
