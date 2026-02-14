"""ChromaKeyTool — BaseTool wrapper for chroma key background removal."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from game_toolbox.core.base_tool import BaseTool, ToolParameter
from game_toolbox.core.datatypes import ChromaKeyResult, PathList
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.chroma_key.logic import ALPHA_FORMATS, COLOR_PRESETS, chroma_key_batch
from game_toolbox.tools.image_resizer.logic import collect_image_paths


class ChromaKeyTool(BaseTool):
    """Remove solid-colour backgrounds from images and replace with transparency."""

    name = "chroma_key"
    display_name = "Chroma Key"
    description = "Remove green/blue/custom-colour backgrounds from images"
    version = "0.1.0"
    category = "Image"
    icon = "auto_fix_high"

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialise the chroma key tool.

        Args:
            event_bus: Shared event bus for progress reporting.
        """
        super().__init__(event_bus=event_bus)

    def define_parameters(self) -> list[ToolParameter]:
        """Return the parameter schema for chroma key removal."""
        return [
            ToolParameter(
                name="inputs",
                label="Input files/directories",
                type=list,
                help="List of image files or directories to process.",
            ),
            ToolParameter(
                name="output_dir",
                label="Output directory",
                type=Path,
                default=None,
                help="Directory for keyed images. None when using in-place mode.",
            ),
            ToolParameter(
                name="preset",
                label="Colour preset",
                type=str,
                default="green",
                choices=sorted(COLOR_PRESETS.keys()),
                help="Predefined chroma key colour (green, blue, magenta).",
            ),
            ToolParameter(
                name="color",
                label="Custom colour (R,G,B)",
                type=str,
                default=None,
                help="Custom RGB colour as 'R,G,B'. Overrides preset when set.",
            ),
            ToolParameter(
                name="tolerance",
                label="Tolerance",
                type=float,
                default=30.0,
                min_value=0,
                max_value=255,
                help="Euclidean distance threshold for full transparency (0-255).",
            ),
            ToolParameter(
                name="softness",
                label="Softness",
                type=float,
                default=10.0,
                min_value=0,
                help="Width of the soft-edge transition band in distance units.",
            ),
            ToolParameter(
                name="output_format",
                label="Output format",
                type=str,
                default="png",
                choices=sorted(ALPHA_FORMATS),
                help="Output image format (must support alpha: png, webp).",
            ),
            ToolParameter(
                name="in_place",
                label="In-place",
                type=bool,
                default=False,
                help="Overwrite original files instead of writing to output directory.",
            ),
        ]

    def input_types(self) -> list[type]:
        """Accept a ``PathList`` from a preceding pipeline stage."""
        return [PathList]

    def output_types(self) -> list[type]:
        """Produce a ``PathList`` of keyed image paths."""
        return [PathList]

    def validate(self, params: dict[str, Any]) -> None:
        """Validate parameters with chroma-key-specific rules.

        Args:
            params: Parameter dict to validate.

        Raises:
            ValidationError: If parameters are invalid.
        """
        super().validate(params)

        color_str = params.get("color")
        if color_str is not None:
            self._parse_color_string(color_str)

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> ChromaKeyResult:
        """Run the chroma key removal logic.

        Args:
            params: Validated parameter dictionary.
            input_data: Optional ``PathList`` from a preceding pipeline stage.

        Returns:
            A ``ChromaKeyResult`` with keyed image metadata.
        """
        # Resolve input paths from params or pipeline input.
        if input_data is not None and isinstance(input_data, PathList):
            image_paths = list(input_data.paths)
        else:
            raw_inputs: list[Path] = [Path(p) for p in params["inputs"]]
            image_paths = collect_image_paths(raw_inputs)

        # Resolve colour: custom string overrides preset.
        color = self._resolve_color(params)

        # Determine output directory.
        in_place: bool = params.get("in_place", False)
        if in_place:
            output_dir = None
        else:
            output_dir = params.get("output_dir")
            if output_dir is None:
                output_dir = image_paths[0].parent / "keyed"
            output_dir = Path(output_dir)

        return chroma_key_batch(
            input_paths=image_paths,
            output_dir=output_dir,
            color=color,
            tolerance=params.get("tolerance", 30.0),
            softness=params.get("softness", 10.0),
            output_format=params.get("output_format", "png"),
            event_bus=self.event_bus,
        )

    @staticmethod
    def _parse_color_string(color_str: str) -> tuple[int, int, int]:
        """Parse an 'R,G,B' string into a colour tuple.

        Args:
            color_str: Comma-separated RGB string (e.g. ``"0,177,64"``).

        Returns:
            A tuple of three integers in the range 0-255.

        Raises:
            ValidationError: If the string is malformed or values are out of range.
        """
        parts = color_str.split(",")
        if len(parts) != 3:
            msg = f"Colour must be 'R,G,B' (3 comma-separated values), got '{color_str}'"
            raise ValidationError(msg)

        try:
            rgb = tuple(int(p.strip()) for p in parts)
        except ValueError as exc:
            msg = f"Colour values must be integers, got '{color_str}'"
            raise ValidationError(msg) from exc

        for i, val in enumerate(rgb):
            if not 0 <= val <= 255:
                msg = f"Colour channel {i} must be 0-255, got {val}"
                raise ValidationError(msg)

        return rgb[0], rgb[1], rgb[2]

    @staticmethod
    def _resolve_color(params: dict[str, Any]) -> tuple[int, int, int]:
        """Resolve the target colour from params.

        Custom ``color`` string takes priority over ``preset``.

        Args:
            params: The parameter dictionary.

        Returns:
            An RGB colour tuple.
        """
        color_str = params.get("color")
        if color_str is not None:
            return ChromaKeyTool._parse_color_string(color_str)

        preset_name: str = params.get("preset", "green")
        return COLOR_PRESETS[preset_name]
