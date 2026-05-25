from django.db import models


class ChatbotRequest(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip = models.CharField(max_length=64)
    calculus_related = models.BooleanField(default=True)
    had_steps = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['-timestamp'])]


class SolverRequest(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip = models.CharField(max_length=64)
    expression_type = models.CharField(max_length=32)

    class Meta:
        indexes = [models.Index(fields=['-timestamp'])]
