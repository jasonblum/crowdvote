# Generated manually for choice description field
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('democracy', '0008_add_decision_snapshot'),
    ]

    operations = [
        migrations.AlterField(
            model_name='choice',
            name='description',
            field=models.TextField(blank=True, help_text='Detailed description of what this choice represents'),
        ),
    ]
