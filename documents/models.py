from django.db import models
from django.contrib.auth.models import User


class Document(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    title = models.CharField(max_length=200)

    file = models.FileField(upload_to='documents/')

    extracted_text = models.TextField(blank=True, null=True)

    summary = models.TextField(blank=True, null=True)

    uploaded_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.title