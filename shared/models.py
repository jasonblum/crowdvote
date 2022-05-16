from django.db import models


class BaseModel(models.Model):
    dt_updated = models.DateTimeField(
        auto_now=True, editable=False, help_text="DateTime this record was created."
    )
    dt_created = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text="DateTime this record last updated.",
    )

    class Meta:
        abstract = True

    def get_id_display(self):
        return f"{self.__class__.__name__[0]}-{self.id}"

    def __str__(self):
        return f"{self.get_id_display()}"
