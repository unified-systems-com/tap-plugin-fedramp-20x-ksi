"""KSI Theme — a top-level grouping of related FedRAMP 20x Key Security Indicators."""

from typing import Any, ClassVar

from django.db import models

from tap_grid.models import BaseModel


class KsiTheme(BaseModel):
    """A top-level KSI theme such as KSI-IAM or KSI-CNA."""

    ENTITY_TYPE: ClassVar[str] = "ksi_theme"
    ENTITY_NAME: ClassVar[str] = "KSI Theme"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "A top-level grouping of related FedRAMP 20x Key Security Indicators."
    )
    ENTITY_ICON: ClassVar[str] = "ksi-theme"
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {"compliance": "fedramp-20x"}

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = {
        "code": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
    }

    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        "code": {"validation": "jsonschema", "schema": {"type": "string", "minLength": 1}},
        "name": {"validation": "jsonschema", "schema": {"type": "string", "minLength": 1}},
        "description": {"validation": "jsonschema", "schema": {"type": "string"}},
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["code", "name"]

    code = models.CharField(max_length=32, blank=True, default="", db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "ksi_theme"

    def get_name(self) -> str:
        return self.name or self.code

    def __str__(self) -> str:
        return self.get_name()
