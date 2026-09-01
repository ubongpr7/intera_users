from django.db import migrations


HOSPERATOR_PERMISSIONS = (
    ("Organization", "hosperator.organization.read", "View Hosperator organization settings"),
    ("Organization", "hosperator.organization.manage", "Manage Hosperator organization settings"),
    ("Patient Registry", "hosperator.patient.read", "View patient registry records"),
    ("Patient Registry", "hosperator.patient.write", "Create and update patient registry records"),
    ("Patient Registry", "hosperator.patient.manage", "Manage patient registry records"),
    ("Patient Registry", "hosperator.patient.verify_relationship", "Verify patient relationships"),
    ("Scheduling", "hosperator.appointment.read", "View appointments"),
    ("Scheduling", "hosperator.appointment.write", "Create and update appointments"),
    ("Scheduling", "hosperator.appointment.manage", "Manage appointments"),
    ("Clinical Operations", "hosperator.encounter.read", "View clinical encounters"),
    ("Clinical Operations", "hosperator.encounter.write", "Create and update clinical encounters"),
    ("Clinical Operations", "hosperator.encounter.complete", "Complete clinical encounters"),
    ("Clinical Operations", "hosperator.encounter.manage", "Manage clinical encounters"),
    ("Fertility Care", "hosperator.fertility_cycle.read", "View fertility cycles"),
    ("Fertility Care", "hosperator.fertility_cycle.write", "Create and update fertility cycles"),
    ("Fertility Care", "hosperator.fertility_cycle.manage", "Manage fertility cycles"),
    ("Clinical Operations", "hosperator.order.read", "View clinical orders"),
    ("Clinical Operations", "hosperator.order.write", "Create and update clinical orders"),
    ("Clinical Operations", "hosperator.order.manage", "Manage clinical orders"),
    ("Clinical Operations", "hosperator.task.read", "View care tasks"),
    ("Clinical Operations", "hosperator.task.write", "Create and update care tasks"),
    ("Clinical Operations", "hosperator.task.complete", "Complete care tasks"),
    ("Clinical Operations", "hosperator.task.manage", "Manage care tasks"),
)


def seed_hosperator_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")

    categories = {}
    for category_name, codename, description in HOSPERATOR_PERMISSIONS:
        category = categories.get(category_name)
        if category is None:
            category, _ = PermissionCategory.objects.get_or_create(
                platform="hosperator",
                name=category_name,
                defaults={"description": f"Hosperator {category_name.lower()} permissions"},
            )
            categories[category_name] = category
        CustomUserPermission.objects.get_or_create(
            platform="hosperator",
            codename=codename,
            defaults={
                "category": category,
                "name": description,
                "description": description,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("permit", "0007_alter_customuserpermission_options_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_hosperator_permissions, migrations.RunPython.noop),
    ]
