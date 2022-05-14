import os

from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def handle(self, *args, **options):

        if os.path.exists(settings.DATABASES["default"]["NAME"]):
            os.remove(settings.DATABASES["default"]["NAME"])
            self.stdout.write(self.style.SUCCESS("> Old database deleted"))

        call_command("migrate")
        self.stdout.write(self.style.SUCCESS("> New Database migrated"))

        User.objects.create_superuser("admin", "admin@admin.com", "admin")
        self.stdout.write(self.style.SUCCESS("> admin superuser created"))

        call_command("populate_database")
        self.stdout.write(self.style.SUCCESS("> Database populated"))

        call_command("populate_database_with_specific_test_data")
        self.stdout.write(
            self.style.SUCCESS(
                "> Added specific Test users, followings and votes added to make it easier to test..."
            )
        )
