"""SpriteSheetTool — BaseTool wrapper for sprite sheet generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from game_toolbox.core.base_tool import BaseTool, ToolParameter
from game_toolbox.core.datatypes import ImageData, PathList, SpriteSheetResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.image_resizer.logic import collect_image_paths
from game_toolbox.tools.sprite_sheet.logic import VALID_METADATA_FORMATS, generate_sprite_sheet


class SpriteSheetTool(BaseTool):
    """Pack multiple images into a single sprite sheet atlas with metadata."""

    name = "sprite_sheet"
    display_name = "Sprite Sheet"
    description = "Generate a sprite sheet atlas from multiple images"
    version = "0.1.0"
    category = "Image"
    icon = "grid_view"

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialise the sprite sheet tool.

        Args:
            event_bus: Shared event bus for progress reporting.
        """
        super().__init__(event_bus=event_bus)

    def define_parameters(self) -> list[ToolParameter]:
        """Return the parameter schema for sprite sheet generation."""
        return [
            ToolParameter(
                name="inputs",
                label="Input files/directories",
                type=list,
                help="List of image files or directories to pack into a sprite sheet.",
            ),
            ToolParameter(
                name="output",
                label="Output file",
                type=Path,
                default=None,
                help="Path for the output sprite sheet image (default: sprite-sheet/ next to first input).",
            ),
            ToolParameter(
                name="columns",
                label="Columns",
                type=int,
                default=None,
                min_value=1,
                help="Number of columns in the grid (auto if not set).",
            ),
            ToolParameter(
                name="padding",
                label="Padding",
                type=int,
                default=1,
                min_value=0,
                help="Pixel padding between frames.",
            ),
            ToolParameter(
                name="metadata_format",
                label="Metadata format",
                type=str,
                default="json",
                choices=sorted(VALID_METADATA_FORMATS),
                help="Format for the metadata file (json, css, xml).",
            ),
        ]

    def input_types(self) -> list[type]:
        """Accept a ``PathList`` from a preceding pipeline stage."""
        return [PathList]

    def output_types(self) -> list[type]:
        """Produce an ``ImageData`` representing the generated sprite sheet."""
        return [ImageData]

    def validate(self, params: dict[str, Any]) -> None:
        """Validate parameters with sprite-sheet-specific rules.

        Args:
            params: Parameter dict to validate.

        Raises:
            ValidationError: If parameters are invalid.
        """
        super().validate(params)

        columns = params.get("columns")
        if columns is not None and columns < 1:
            msg = f"Columns must be >= 1, got {columns}"
            raise ValidationError(msg)

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> SpriteSheetResult:
        """Run the sprite sheet generation logic.

        Args:
            params: Validated parameter dictionary.
            input_data: Optional ``PathList`` from a preceding pipeline stage.

        Returns:
            A ``SpriteSheetResult`` with sheet metadata and frame positions.
        """
        # Resolve input paths from params or pipeline input.
        if input_data is not None and isinstance(input_data, PathList):
            image_paths = list(input_data.paths)
        else:
            raw_inputs: list[Path] = [Path(p) for p in params["inputs"]]
            image_paths = collect_image_paths(raw_inputs)

        # Resolve output path: default to sprite-sheet/ next to first input.
        raw_output: Path | None = params.get("output")
        output = image_paths[0].parent / "sprite-sheet" / "sprite_sheet.png" if raw_output is None else Path(raw_output)

        return generate_sprite_sheet(
            input_paths=image_paths,
            output_path=output,
            columns=params.get("columns"),
            padding=params.get("padding", 1),
            metadata_format=params.get("metadata_format", "json"),
            event_bus=self.event_bus,
        )
