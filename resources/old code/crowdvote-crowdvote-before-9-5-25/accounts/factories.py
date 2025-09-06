import factory
from factory.django import DjangoModelFactory

from .models import CustomUser, Following


class CustomUserFactory(DjangoModelFactory):
    class Meta:
        model = CustomUser
        django_get_or_create = ("username",)

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    email = factory.Faker("email")
    username = factory.Faker("user_name")


class FollowingFactory(DjangoModelFactory):
    class Meta:
        model = Following

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of tags were passed in, use them.
            for tag in extracted:
                self.tags.add(tag)
