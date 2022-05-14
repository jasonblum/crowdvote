import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from taggit.managers import TaggableManager

from shared.models import BaseModel


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    class Meta:
        ordering = ["username"]
        verbose_name = "User"
        verbose_name_plural = "Users"


class Following(BaseModel):
    user = models.ForeignKey(
        CustomUser, related_name="followings", on_delete=models.PROTECT
    )
    followee = models.ForeignKey(
        CustomUser, related_name="followers", on_delete=models.PROTECT
    )
    tags = TaggableManager()

    class Meta:
        ordering = ["user__username"]
