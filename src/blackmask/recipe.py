"""Typed editable draft contract, shared by all future interfaces."""

from dataclasses import dataclass, field
from typing import Any

from .guidance import identifier


@dataclass(frozen=True)
class Recipe:
    developed_id: str
    notes: str = ""
    groups: list[dict[str, Any]] = field(default_factory=list)
    device: str = "auto"
    cleanup_enabled: bool = False
    cleanup_strength: float = 0.35
    shading: dict[str, Any] = field(default_factory=lambda: {"enabled": False, "opacity": 0.0})

    local_exposure: dict[str, Any] = field(default_factory=lambda: {"enabled": False, "ev": 0.0})

    shadow_fade: dict[str, Any] = field(
        default_factory=lambda: {"enabled": False, "amount": 0.0, "preserve_highlights": 1.0}
    )
    background: dict[str, Any] | None = None
    spatial_fade: dict[str, Any] | None = None

    local_sharpening: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "amount": 0.0,
            "radius_px": 1.0,
            "noise_threshold": 0.001,
        }
    )
    background_light: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "developed_id": self.developed_id,
            "guides_file": "guides.json",
            "notes": self.notes,
            "groups": self.groups,
            "matting": {"tile_size_px": 1024, "overlap_px": 256, "device": self.device},
            "color_cleanup": {"enabled": self.cleanup_enabled, "strength": self.cleanup_strength},
            "shading": self.shading,
            "local_exposure": self.local_exposure,
            "shadow_fade": self.shadow_fade,
            "local_sharpening": self.local_sharpening,
            **({"background": self.background} if self.background is not None else {}),
            **({"spatial_fade": self.spatial_fade} if self.spatial_fade is not None else {}),
            **(
                {"background_light": self.background_light}
                if self.background_light is not None
                else {}
            ),
        }

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        developed_id: str,
        *,
        max_margin_px: int | None = None,
        dimensions_wh: tuple[int, int] | None = None,
    ) -> "Recipe":
        expected = cls(developed_id).to_dict()
        if (
            set(value)
            - {
                "local_exposure",
                "shadow_fade",
                "background",
                "spatial_fade",
                "local_sharpening",
                "background_light",
            }
            != set(expected)
            - {
                "local_exposure",
                "shadow_fade",
                "background",
                "spatial_fade",
                "local_sharpening",
                "background_light",
            }
            or type(value.get("schema_version")) is not int
            or value["schema_version"] != 2
            or value["developed_id"] != developed_id
            or value["guides_file"] != "guides.json"
            or not isinstance(value["notes"], str)
        ):
            raise ValueError("Invalid recipe keys, schema or master identity")
        from .effects import validate_cleanup, validate_shading
        from .exposure import validate_exposure
        from .shadow_fade import validate_shadow_fade
        from .sharpening import validate_local_sharpening

        validate_local_sharpening(value.get("local_sharpening", cls(developed_id).local_sharpening))
        validate_shadow_fade(value.get("shadow_fade", cls(developed_id).shadow_fade))
        if "background" in value:
            from .background import validate_background

            validate_background(value["background"])
        validate_exposure(value.get("local_exposure", {"enabled": False, "ev": 0.0}))
        validate_cleanup(value["color_cleanup"])
        validate_shading(value["shading"])
        if "background_light" in value:
            from .background_light import validate_background_light

            if dimensions_wh is None:
                raise ValueError("Native dimensions required to validate background light recipe")
            validate_background_light(value["background_light"], *dimensions_wh)
        if "spatial_fade" in value:
            from .spatial_fade import validate_spatial_fade

            if dimensions_wh is None:
                raise ValueError("Native dimensions required to validate spatial fade recipe")
            validate_spatial_fade(value["spatial_fade"], *dimensions_wh)
            if value["spatial_fade"]["enabled"] and value["shading"]["enabled"]:
                raise ValueError("Inward shading and spatial fade cannot both be enabled")
        for section in ("matting",):
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
            developed_id,
            value["notes"],
            groups,
            value["matting"]["device"],
            value["color_cleanup"]["enabled"],
            float(value["color_cleanup"]["strength"]),
            dict(value["shading"]),
            dict(value.get("local_exposure", {"enabled": False, "ev": 0.0})),
            dict(value.get("shadow_fade", cls(developed_id).shadow_fade)),
            dict(value["background"]) if "background" in value else None,
            dict(value["spatial_fade"]) if "spatial_fade" in value else None,
            dict(value.get("local_sharpening", cls(developed_id).local_sharpening)),
            dict(value["background_light"]) if "background_light" in value else None,
        )
