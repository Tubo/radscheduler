# Generated by Django 4.2.6 on 2024-01-17 12:34

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_user_phone"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={"ordering": ["username"]},
        ),
    ]