import hashlib
import json
from typing import Any

from pydantic import BaseModel


def content_hash(obj: Any) -> str:
    """SHA-256 of canonical JSON (sorted keys, no whitespace)."""
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json")
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
