from django.test import SimpleTestCase

from mainapps.permit.models import CombinedPermissions
from mainapps.profile.default_staff_presets import get_default_staff_access_presets


class DefaultStaffPresetTests(SimpleTestCase):
    def test_agent_interaction_presets_include_voice_conversation_access(self):
        presets = {preset.name: set(preset.permissions) for preset in get_default_staff_access_presets()}

        for preset_name, permissions in presets.items():
            if CombinedPermissions.INTERACT_WITH_AGENT in permissions:
                self.assertIn(
                    CombinedPermissions.ORAL_CONVERSATION_WITH_AI,
                    permissions,
                    msg=f"{preset_name} should include voice conversation access when it can use agents.",
                )

    def test_operational_manager_presets_include_audit_trail_access(self):
        presets = {preset.name: set(preset.permissions) for preset in get_default_staff_access_presets()}

        for preset_name in [
            "IMS Administrator",
            "IMS POS Manager",
            "IMS Back Office Manager",
            "IMS Inventory Manager",
            "IMS Purchase Manager",
        ]:
            self.assertIn(
                CombinedPermissions.VIEW_AUDIT_TRAIL,
                presets[preset_name],
                msg=f"{preset_name} should include audit trail access.",
            )
