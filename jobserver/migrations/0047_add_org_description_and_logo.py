# Generated by Django 3.2.4 on 2021-06-11 14:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobserver", "0046_add_project_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="org",
            name="description",
            field=models.TextField(default="", blank=True),
        ),
        migrations.AddField(
            model_name="org",
            name="logo",
            field=models.TextField(default="", blank=True),
        ),
    ]
