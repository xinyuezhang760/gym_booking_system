# Generated by Django 5.2.4 on 2025-07-13 10:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0003_rename_created_at_reservation_timestamp'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fitnessclass',
            name='image',
        ),
        migrations.AddField(
            model_name='fitnessclass',
            name='max_capacity',
            field=models.PositiveIntegerField(default=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='fitnessclass',
            name='capacity',
            field=models.PositiveIntegerField(),
        ),
    ]
