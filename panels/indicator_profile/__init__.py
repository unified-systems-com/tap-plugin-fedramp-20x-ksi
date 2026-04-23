"""FedRAMP 20x KSI Indicator Profile — plugin-owned panel type.

Displays a single KSI indicator's full profile: hero header, requirement
statement with class-variant toggle, NIST controls, terms, references,
and change log. Data is loaded via a gryphon hub-and-spoke query that
returns the indicator and its parent theme in one pass.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from tap_web.utils import safe_json

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tap_web.models import Panel

logger = logging.getLogger(__name__)

CLASS_LABELS: dict[str, str] = {
    "a": "Class A — Pilot",
    "b": "Class B — Low",
    "c": "Class C — Moderate",
    "d": "Class D — High",
}


class KsiIndicatorProfilePanelType:
    """Panel type for the FedRAMP 20x KSI indicator profile page."""

    slug: ClassVar[str] = "fedramp-20x-ksi-indicator-profile"
    label: ClassVar[str] = "FedRAMP 20x KSI Indicator Profile"
    view: ClassVar[str] = "fedramp_20x_ksi/panels/indicator_profile.html"
    css: ClassVar[list[str]] = [
        "fedramp_20x_ksi/css/panel-ksi-indicator-profile.css",
    ]
    js: ClassVar[list[str]] = [
        "fedramp_20x_ksi/js/panel-ksi-indicator-profile.js",
    ]
    config_defaults: ClassVar[dict[str, Any]] = {}

    @classmethod
    def get_view_context(cls, panel: Panel, request: HttpRequest) -> dict[str, Any]:
        """Load the indicator + neighborhood and build template context."""
        entity_id = request.GET.get("entity_id", "")
        if not entity_id:
            return {"ksi_error": "No indicator specified.", "ksi": None}

        try:
            from tap_grid.models import Search
            from tap_grid.search import execute_search

            search = Search(
                search_type="gryphon",
                root="node",
                name="ksi-indicator-profile",
                definition={
                    "query": [
                        "MATCH (hub)-[e]-(neighbor)",
                        "WHERE hub.entity_id = $entity_id",
                        "RETURN hub, e, neighbor",
                    ]
                },
                default_limit=50,
                max_limit=100,
            )
            result = execute_search(
                search, inputs={"entity_id": entity_id}, layer="extended"
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("KSI profile search failed for %s", entity_id)
            return {"ksi_error": f"Failed to load indicator: {exc}", "ksi": None}

        # Extract subgraph from paginated or flat result.
        if "results" in result:
            subgraph = result["results"]
        else:
            subgraph = result

        nodes = subgraph.get("nodes", [])

        # Find the indicator (hub) and parent theme.
        indicator = None
        theme = None
        for n in nodes:
            etype = n.get("entity", {}).get("entity_type", "")
            eid = n.get("entity", {}).get("entity_id", "")
            if eid == entity_id:
                indicator = n
            elif etype == "ksi_theme":
                theme = n

        if indicator is None:
            return {"ksi_error": "Indicator not found.", "ksi": None}

        ind_node = indicator.get("node", {})
        ind_entity = indicator.get("entity", {})
        theme_node = theme.get("node", {}) if theme else {}
        theme_entity = theme.get("entity", {}) if theme else {}

        has_variants = bool(ind_node.get("class_variants"))

        # Resolve the initial display statement.
        # For direct-statement indicators: use description.
        # For class_variant indicators: use the first class's statement.
        display_statement = ind_node.get("description", "")
        if has_variants and not display_statement:
            cv = ind_node["class_variants"]
            first_class = (
                ind_node.get("classes", [])[0] if ind_node.get("classes") else None
            )
            if first_class and first_class in cv:
                display_statement = cv[first_class].get("statement", "")
            elif cv:
                display_statement = next(iter(cv.values())).get("statement", "")

        ksi = {
            "entity_id": ind_entity.get("entity_id", ""),
            "code": ind_node.get("code", ""),
            "name": ind_node.get("name", ""),
            "description": ind_node.get("description", ""),
            "classes": ind_node.get("classes", []),
            "class_variants": ind_node.get("class_variants"),
            "has_variants": has_variants,
            "controls": ind_node.get("controls", []),
            "status": ind_node.get("status", ""),
            "terms": ind_node.get("terms", []),
            "reference": ind_node.get("reference", ""),
            "reference_url": ind_node.get("reference_url", ""),
            "updated_log": ind_node.get("updated_log", []),
            "theme_code": theme_node.get("code", ""),
            "theme_name": theme_entity.get("name", theme_node.get("name", "")),
            "theme_short_name": theme_node.get("short_name", ""),
            "theme_icon_url": theme.get("icon_url", "") if theme else "",
        }

        # Build class label map for the template.
        class_info = []
        for c in ksi["classes"]:
            class_info.append({"key": c, "label": CLASS_LABELS.get(c, c.upper())})

        return {
            "ksi": ksi,
            "ksi_display_statement": display_statement,
            "ksi_class_info": class_info,
            "ksi_variants_json": (
                safe_json(ksi["class_variants"]) if has_variants else "null"
            ),
            "ksi_error": None,
        }
