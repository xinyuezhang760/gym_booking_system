# Generated by Django 5.2.4 on 2025-07-13 12:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0008_reservation_feedback'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reservation',
            name='feedback',
            field=models.TextField(blank=True, null=True),
        ),
    ]
