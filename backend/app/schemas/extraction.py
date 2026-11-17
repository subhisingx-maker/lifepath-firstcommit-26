"""Shape of what the AI is ALLOWED to return. Anything else is rejected.

Each field here is a CLAIM by the model. Nothing is trusted until the pipeline
has re-checked it (quote against the document, date by the deterministic parser).
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["eligibility", "document", "deadline", "stage", "outcome_pathway", "fee", "warning", "other"]
RequirementLevel = Literal["mandatory", "conditional", "optional", "not_specified", "not_required"]
Outcome = Literal["selected", "waitlisted", "not_selected", "any"]

_EVENT_KEY = re.compile(r"^[a-z0-9_]{1,60}$")


def _blank_to_none(value):
    return None if isinstance(value, str) and not value.strip() else value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class HeaderField(_Strict):
    value: str = Field(min_length=1, max_length=300)
    source_page: int = Field(ge=1)
    supporting_quote: str = Field(min_length=1, max_length=600)


class AIItem(_Strict):
    category: Category
    name: str = Field(min_length=1, max_length=200)
    explanation: str = Field(default="", max_length=600)       # AI wording - NOT official text
    supporting_quote: str = Field(min_length=1, max_length=600)  # must be verbatim from the notice
    source_page: int = Field(ge=1)
    requirement_level: Optional[RequirementLevel] = None
    condition: Optional[str] = Field(default=None, max_length=400)
    event_key: Optional[str] = None
    outcome: Optional[Outcome] = None
    depends_on: list[str] = Field(default_factory=list, max_length=10)
    missing_information: Optional[str] = Field(default=None, max_length=400)

    @field_validator("requirement_level", "condition", "outcome", "missing_information", mode="before")
    @classmethod
    def _blank(cls, v):
        return _blank_to_none(v)

    @field_validator("explanation", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        return "" if v is None else v

    @field_validator("event_key", mode="before")
    @classmethod
    def _event_key(cls, v):
        v = _blank_to_none(v)
        if not isinstance(v, str):
            return None
        v = re.sub(r"[\s\-]+", "_", v.strip().lower())
        return v if _EVENT_KEY.match(v) else None

    @field_validator("depends_on", mode="before")
    @classmethod
    def _depends(cls, v):
        if v is None:
            return []
        return [str(x)[:200] for x in v if str(x).strip()][:10] if isinstance(v, list) else []

    @model_validator(mode="after")
    def _only_where_relevant(self):
        if self.category != "document":
            self.requirement_level = None
        if self.category != "deadline":
            self.event_key = None
        if self.category != "outcome_pathway":
            self.outcome = None
        return self
