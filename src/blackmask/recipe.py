"""Typed editable draft contract, shared by all future interfaces."""

from dataclasses import dataclass, field
from typing import Any

from .guidance import identifier


@dataclass(frozen=True)
class Recipe:
    master_id: str
    notes: str = ""
    groups: list[dict[str, Any]] = field(default_factory=list)
    device: str = "auto"
    cleanup_enabled: bool = False
    cleanup_strength: float = 0.35

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "master_id": self.master_id,
            "guides_file": "guides.json",
            "notes": self.notes,
            "groups": self.groups,
            "matting": {"tile_size_px": 1024, "overlap_px": 256, "device": self.device},
            "color_cleanup": {"enabled": self.cleanup_enabled, "strength": self.cleanup_strength},
            "shading": {"enabled": False, "opacity": 0.0},
        }

    @classmethod
    def from_dict(
        cls, value: dict[str, Any], master_id: str, *, max_margin_px: int | None = None
    ) -> "Recipe":
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
        from .effects import validate_cleanup

        validate_cleanup(value["color_cleanup"])
        # Shading remains unavailable until its actual application path exists.
        for section in ("matting", "shading"):
            current = value[section]
            reference = expected[section]
            if not isinstance(current, dict) or set(current) != set(reference):
                raise ValueError(f"Invalid recipe {section}")
            for key, default in reference.items():
                if section == "matting" and key == "device":
                    if current[key] not in ("auto", "cpu", "mps"):
                        raise ValueError("Unsupported matting device")
                    continue
                if type(current[key]) is not type(default) or current[key] != default:
                    raise ValueError(f"Unsupported recipe setting {section}.{key}")
        groups = value["groups"]
        if not isinstance(groups, list):
            raise TypeError("Groups must be a list")
        seen = set()
        for group in groups:
            if (
                not isinstance(group, dict)
                or not {"id", "keep", "material_policy"} <= set(group)
                or set(group)
                - {"id", "keep", "material_policy", "selected_candidate", "morphology"}
            ):
                raise ValueError("Invalid group keys")
            stable_id = identifier(group["id"])
            if (
                stable_id in seen
                or type(group["keep"]) is not bool
                or group["material_policy"] not in ("opaque_core", "unknown_interior")
            ):
                raise ValueError("Invalid/duplicate group or material policy")
            selected = group.get("selected_candidate")
            if selected is not None and (type(selected) is not int or selected not in (0, 1, 2)):
                raise ValueError("Selected candidate must be 0, 1 or 2")
            if "morphology" in group:
                morphology = group["morphology"]
                if (
                    not isinstance(morphology, dict)
                    or set(morphology) != {"foreground_erosion_px", "unknown_dilation_px"}
                    or any(
                        type(margin) is not int
                        or margin < 0
                        or (max_margin_px is not None and margin > max_margin_px)
                        for margin in morphology.values()
                    )
                    or not group["keep"]
                    or selected is None
                ):
                    raise ValueError(
                        "Invalid morphology settings: explicit native margins and kept selected candidate required"
                    )
            seen.add(stable_id)
        return cls(
            master_id,
            value["notes"],
            groups,
            value["matting"]["device"],
            value["color_cleanup"]["enabled"],
            float(value["color_cleanup"]["strength"]),
        )
