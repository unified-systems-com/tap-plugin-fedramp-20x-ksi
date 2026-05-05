"""TAP FedRAMP 20x KSI plugin AppConfig."""

from tap_plugins.base import TapPluginConfig


class Fedramp20xKsiConfig(TapPluginConfig):
    def ready(self) -> None:
        super().ready()
        from plugins.fedramp_20x_ksi.panels.compliance_view import (
            KsiCompliancePanelType,
        )
        from plugins.fedramp_20x_ksi.panels.finding_profile import (
            KsiFindingProfilePanelType,
        )
        from plugins.fedramp_20x_ksi.panels.indicator_profile import (
            KsiIndicatorProfilePanelType,
        )
        from plugins.fedramp_20x_ksi.panels.finding_strip import (
            FindingStripPanelType,
        )
        from plugins.fedramp_20x_ksi.panels.findings_by_ksi import (
            FindingsByKsiPanelType,
        )
        from plugins.fedramp_20x_ksi.panels.findings_by_system import (
            FindingsBySystemPanelType,
        )
        from tap_web.registry import panel_type_registry

        panel_type_registry.register(
            "fedramp-20x-ksi-compliance", KsiCompliancePanelType
        )
        panel_type_registry.register(
            "fedramp-20x-ksi-indicator-profile", KsiIndicatorProfilePanelType
        )
        panel_type_registry.register(
            "fedramp-20x-ksi-finding-profile", KsiFindingProfilePanelType
        )
        panel_type_registry.register("finding_strip", FindingStripPanelType)
        panel_type_registry.register("findings_by_system", FindingsBySystemPanelType)
        panel_type_registry.register("findings_by_ksi", FindingsByKsiPanelType)
