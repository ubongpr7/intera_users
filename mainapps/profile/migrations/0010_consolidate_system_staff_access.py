from django.db import migrations


SYSTEM_NAMES = (
    "Administrator",
    "POS Manager",
    "Cashier",
    "BO Manager",
    "Inventory Manager",
    "Purchase Manager",
    "Warehouse Staff",
    "Viewer",
)


def consolidate(model_name, apps):
    Model = apps.get_model("profile", model_name)
    through = Model.users.through if model_name == "StaffGroup" else None
    Assignment = apps.get_model("profile", "StaffRoleAssignment") if model_name == "StaffRole" else None

    for name in SYSTEM_NAMES:
        rows = list(Model.objects.filter(name__iexact=name, platform="intera_ims").order_by("profile_id", "id"))
        if not rows:
            continue

        canonical = next((row for row in rows if row.profile_id is None), rows[0])
        for duplicate in rows:
            if duplicate.pk == canonical.pk:
                continue
            if through is not None:
                for user_id in through.objects.filter(staffgroup_id=duplicate.pk).values_list("user_id", flat=True):
                    through.objects.get_or_create(user_id=user_id, staffgroup_id=canonical.pk)
            else:
                Assignment.objects.filter(role_id=duplicate.pk).update(role_id=canonical.pk)
            duplicate.delete()

        canonical.profile_id = None
        canonical.is_system = True
        canonical.created_by_id = None
        canonical.name = name
        canonical.save(update_fields=["profile", "is_system", "created_by", "name"])


def consolidate_system_staff_access(apps, schema_editor):
    del schema_editor
    consolidate("StaffRole", apps)
    consolidate("StaffGroup", apps)


class Migration(migrations.Migration):
    dependencies = [
        ("profile", "0009_alter_staffgroup_unique_together_and_more"),
    ]

    operations = [
        migrations.RunPython(consolidate_system_staff_access, migrations.RunPython.noop),
    ]
