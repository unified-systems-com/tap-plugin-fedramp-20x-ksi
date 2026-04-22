"""KSI Indicator — a single measurable FedRAMP 20x Key Security Indicator within a theme."""

from typing import Any, ClassVar

from django.db import models

from tap_grid.models import BaseModel


class KsiIndicator(BaseModel):
    """An individual KSI such as KSI-IAM-01."""

    ENTITY_TYPE: ClassVar[str] = "ksi_indicator"
    ENTITY_NAME: ClassVar[str] = "KSI Indicator"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "A single measurable FedRAMP 20x Key Security Indicator within a theme."
    )
    ENTITY_ICON: ClassVar[str] = "ksi-indicator"
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "fedramp-20x"}

    _STATUS_VALUES = ["draft", "published", "deprecated"]
    _BASELINE_VALUES = ["low", "moderate"]

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = {
        "code": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "validation_json": {"type": ["object", "null"]},
        "status": {"type": "string", "enum": _STATUS_VALUES},
        "baselines": {
            "type": "array",
            "items": {"type": "string", "enum": _BASELINE_VALUES},
            "minItems": 1,
            "uniqueItems": True,
        },
    }

    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        "code": {"validation": "jsonschema", "schema": {"type": "string", "minLength": 1}},
        "name": {"validation": "jsonschema", "schema": {"type": "string", "minLength": 1}},
        "description": {"validation": "jsonschema", "schema": {"type": "string"}},
        "validation_json": {
            "validation": "jsonschema",
            "schema": {"type": ["object", "null"]},
        },
        "status": {
            "validation": "jsonschema",
            "schema": {"type": "string", "enum": _STATUS_VALUES},
        },
        "baselines": {
            "validation": "jsonschema",
            "schema": {
                "type": "array",
                "items": {"type": "string", "enum": _BASELINE_VALUES},
                "minItems": 1,
                "uniqueItems": True,
            },
        },
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["code", "name", "status", "baselines"]

    code = models.CharField(max_length=32, blank=True, default="", db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    validation_json = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=16, blank=True, default="")
    baselines = models.JSONField(default=list, blank=True)

    class Meta(BaseModel.Meta):
        db_table = "ksi_indicator"

    def get_name(self) -> str:
        return self.name or self.code

    def __str__(self) -> str:
        return self.get_name()
