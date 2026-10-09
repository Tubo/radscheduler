from django.db import migrations

# The groups were first made by hand in the admin; this makes sure every database has them.
GROUPS = ("Director of Training", "Office Staff", "Roster master")


def add_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in GROUPS:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("core", "0012_leave_decided_by"),
    ]

    operations = [migrations.RunPython(add_groups, migrations.RunPython.noop)]
