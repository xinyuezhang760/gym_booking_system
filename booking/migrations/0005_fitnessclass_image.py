# Generated by Django 5.2.4 on 2025-07-13 11:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0004_remove_fitnessclass_image_fitnessclass_max_capacity_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='fitnessclass',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='class_images/'),
        ),
    ]
