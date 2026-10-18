"""Typed editable draft contract, shared by all future interfaces."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Recipe:
    master_id: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "master_id": self.master_id,
            "guides_file": "guides.json",
            "notes": self.notes,
            "groups": [],
            "matting": {"tile_size_px": 1024, "overlap_px": 256, "device": "auto"},
            "color_cleanup": {"enabled": False, "strength": 0.35},
            "shading": {"enabled": False, "opacity": 0.0},
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any], master_id: str) -> "Recipe":
        expected = cls(master_id).to_dict()
        if (
            set(value) != set(expected)
            or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1
            or value["master_id"] != master_id
            or value["guides_file"] != "guides.json"
            or not isinstance(value["notes"], str)
        ):
            raise ValueError("Invalid recipe keys, schema or master identity")
        # Later cards extend these sections with their actual application paths.
        for section in ("matting", "color_cleanup", "shading"):
            current = value[section]
            reference = expected[section]
            if not isinstance(current, dict) or set(current) != set(reference):
                raise ValueError(f"Invalid recipe {section}")
            for key, default in reference.items():
                if type(current[key]) is not type(default) or current[key] != default:
                    raise ValueError(f"Unsupported I01 recipe setting {section}.{key}")
        if value["groups"] != []:
            raise ValueError("Guide groups arrive in I02")
        return cls(master_id, value["notes"])
