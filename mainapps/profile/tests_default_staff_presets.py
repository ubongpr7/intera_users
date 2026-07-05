from django.test import SimpleTestCase

from mainapps.permit.models import CombinedPermissions
from mainapps.profile.default_staff_presets import get_default_staff_access_presets


class DefaultStaffPresetTests(SimpleTestCase):
    def test_operational_manager_presets_include_audit_trail_access(self):
        presets = {preset.name: set(preset.permissions) for preset in get_default_staff_access_presets()}

        for preset_name in [
            "Administrator",
            "POS Manager",
            "BO Manager",
            "Inventory Manager",
            "Purchase Manager",
        ]:
            self.assertIn(
                CombinedPermissions.VIEW_AUDIT_TRAIL,
                presets[preset_name],
                msg=f"{preset_name} should include audit trail access.",
            )
