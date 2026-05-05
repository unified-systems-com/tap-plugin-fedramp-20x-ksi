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
