import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from taggit.managers import TaggableManager

from shared.models import BaseModel


class CustomUser(AbstractUser):
    class Meta:
        ordering = ["username"]
        verbose_name = "User"
        verbose_name_plural = "Users"


class Following(BaseModel):
    follower = models.ForeignKey(
        CustomUser,
        related_name="followings",
        on_delete=models.PROTECT,
        help_text="The user doing the following.",
    )
    followee = models.ForeignKey(
        CustomUser,
        related_name="followers",
        on_delete=models.PROTECT,
        help_text="The user being followed.",
    )
    tags = TaggableManager()

    class Meta:
        ordering = [
            "follower__username",
            "followee__username",
        ]
