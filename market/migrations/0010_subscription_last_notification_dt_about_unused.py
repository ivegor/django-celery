# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-07-31 17:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0009_DefaultBuyPriceIzZero'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='last_notification_dt_about_unused',
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]
