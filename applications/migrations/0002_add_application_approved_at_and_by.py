# Generated by Django 3.2.5 on 2021-10-26 09:25

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("applications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="approved_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="application",
            name="approved_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="approved_applications",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="application",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(("approved_at", None), ("approved_by", None)),
                    models.Q(
                        models.Q(("approved_at", None), _negated=True),
                        models.Q(("approved_by", None), _negated=True),
                    ),
                    _connector="OR",
                ),
                name="applications_application_both_approved_at_and_approved_by_set",
            ),
        ),
    ]
