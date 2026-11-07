"""Small shared helpers: strict base model, hashing, issues."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    """Every model that crosses a module boundary rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


def canonical_json(obj: Any) -> str:
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


class Issue(Model):
    """A recorded reason a candidate was rejected."""

    stage: str
    code: str
    message: str
