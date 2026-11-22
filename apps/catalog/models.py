from django.db import models


class Category(models.Model):
    name = models.JSONField()
    description = models.JSONField()
    icon_url = models.URLField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
