# Generated by Django 3.2.4 on 2021-06-11 14:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobserver", "0044_fix_databricks_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="projects",
            field=models.ManyToManyField(
                related_name="members",
                through="jobserver.ProjectMembership",
                to="jobserver.Project",
            ),
        ),
    ]
