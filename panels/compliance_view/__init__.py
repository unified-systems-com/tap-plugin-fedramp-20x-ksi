"""FedRAMP 20x KSI Compliance View — plugin-owned panel type.

Displays all KSI indicators in a searchable, filterable table grouped by theme.
Data is loaded via a gryphon query and passed as a raw subgraph envelope to the
browser, where Tabulator renders the grouped table with client-side search and
class filtering.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from tap_web.utils import safe_json

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tap_web.models import Panel

logger = logging.getLogger(__name__)


class KsiCompliancePanelType:
    """Panel type for the FedRAMP 20x KSI compliance reference view."""

    slug: ClassVar[str] = "fedramp-20x-ksi-compliance"
    label: ClassVar[str] = "FedRAMP 20x KSI Compliance View"
    view: ClassVar[str] = "fedramp_20x_ksi/panels/compliance_view.html"
    css: ClassVar[list[str]] = [
        "tap_web/css/lib/tabulator.min.css",
        "fedramp_20x_ksi/css/panel-ksi-compliance.css",
    ]
    js: ClassVar[list[str]] = [
        "tap_web/js/lib/tabulator.min.js",
        "fedramp_20x_ksi/js/panel-ksi-compliance.js",
    ]
    config_defaults: ClassVar[dict[str, Any]] = {}

    @classmethod
    def get_view_context(cls, panel: Panel, request: HttpRequest) -> dict[str, Any]:
        """Execute the linked gryphon search and return the raw subgraph for JS.

        The subgraph envelope ({nodes, edges}) is passed directly to the browser
        via safe_json(). The JS handles joining indicators to themes via edges
        and building the grouped table.
        """
        from tap_web.panel import get_panel_search

        search = get_panel_search(panel)
        if search is None:
            return {
                "ksi_subgraph_json": safe_json({"nodes": [], "edges": []}),
                "ksi_error": "No search linked to this panel.",
            }

        try:
            from tap_grid.search import execute_search

            result = execute_search(search, layer="extended")
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "KSI compliance search execution failed for panel %s",
                panel.entity_id,
            )
            return {
                "ksi_subgraph_json": safe_json({"nodes": [], "edges": []}),
                "ksi_error": f"Search execution failed: {exc}",
            }

        # Extract the subgraph envelope from a paginated or flat result.
        if "results" in result:
            subgraph = result["results"]
        else:
            subgraph = result

        return {
            "ksi_subgraph_json": safe_json(subgraph),
            "ksi_error": None,
        }
