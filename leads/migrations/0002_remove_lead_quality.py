# Generated by Django 2.2.3 on 2019-09-07 18:44

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lead',
            name='quality',
        ),
    ]
