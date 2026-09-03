from django.db import migrations


IMS_NAME_MAPPING = {
    "Administrator": "IMS Administrator",
    "POS Manager": "IMS POS Manager",
    "Cashier": "IMS Cashier",
    "BO Manager": "IMS Back Office Manager",
    "Inventory Manager": "IMS Inventory Manager",
    "Purchase Manager": "IMS Purchase Manager",
    "Warehouse Staff": "IMS Warehouse Staff",
    "Viewer": "IMS Viewer",
}


def rename_or_merge_system_definitions(model_name, apps):
    Model = apps.get_model("profile", model_name)
    Assignment = apps.get_model("profile", "StaffRoleAssignment") if model_name == "StaffRole" else None

    for old_name, new_name in IMS_NAME_MAPPING.items():
        source = Model.objects.filter(
            name__iexact=old_name,
            platform="intera_ims",
            is_system=True,
            profile__isnull=True,
        ).first()
        if not source:
            continue

        target = Model.objects.filter(
            name__iexact=new_name,
            platform="intera_ims",
            is_system=True,
            profile__isnull=True,
        ).first()
        if target:
            target.permissions.add(*source.permissions.all())
            if Assignment is not None:
                for assignment in Assignment.objects.filter(role_id=source.pk):
                    if Assignment.objects.filter(user_id=assignment.user_id, role_id=target.pk).exists():
                        assignment.delete()
                    else:
                        assignment.role_id = target.pk
                        assignment.save(update_fields=["role"])
            else:
                through = Model.users.through
                for user_id in through.objects.filter(staffgroup_id=source.pk).values_list("user_id", flat=True):
                    through.objects.get_or_create(user_id=user_id, staffgroup_id=target.pk)
            source.delete()
            continue

        source.name = new_name
        source.save(update_fields=["name"])


def qualify_ims_system_access_names(apps, schema_editor):
    del schema_editor
    rename_or_merge_system_definitions("StaffRole", apps)
    rename_or_merge_system_definitions("StaffGroup", apps)


class Migration(migrations.Migration):
    dependencies = [
        ("profile", "0011_companyprofileaddress_shared_address_id"),
    ]

    operations = [
        migrations.RunPython(qualify_ims_system_access_names, migrations.RunPython.noop),
    ]
