"""Dumps one JSON schema containing every exported API model (camelCase aliases)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pydantic.json_schema import models_json_schema  # noqa: E402

from app.models.schemas import EXPORTED_MODELS  # noqa: E402

_, schema = models_json_schema([(m, "serialization") for m in EXPORTED_MODELS], by_alias=True,
                               ref_template="#/$defs/{model}")
defs = schema.get("$defs", {})


def strip_titles(node, keep=False):
    """Field titles make json2ts emit one alias type per field; keep only model titles."""
    if isinstance(node, dict):
        if not keep:
            node.pop("title", None)
        for k, v in node.items():
            strip_titles(v, keep=False)
    elif isinstance(node, list):
        for v in node:
            strip_titles(v)


for d in defs.values():
    title = d.get("title")
    strip_titles(d)
    if title:
        d["title"] = title
root = {"title": "ChimeraApi", "type": "object", "additionalProperties": False,
        "properties": {name: {"$ref": f"#/$defs/{name}"} for name in defs}, "$defs": defs}
json.dump(root, sys.stdout, indent=1)
