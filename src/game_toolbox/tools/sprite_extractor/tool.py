"""SpriteExtractorTool — BaseTool wrapper for sprite extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from game_toolbox.core.base_tool import BaseTool, ToolParameter
from game_toolbox.core.datatypes import ImageData, PathList, SpriteExtractionResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.sprite_extractor.logic import (
    VALID_OUTPUT_FORMATS,
    extract_auto_detect,
    extract_from_metadata,
    extract_grid,
    validate_extraction_params,
)


class SpriteExtractorTool(BaseTool):
    """Extract individual sprites from a sprite sheet image."""

    name = "sprite_extractor"
    display_name = "Sprite Extractor"
    description = "Extract individual sprites from a sprite sheet"
    version = "0.1.0"
    category = "Image"
    icon = "grid_on"

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialise the sprite extractor tool.

        Args:
            event_bus: Shared event bus for progress reporting.
        """
        super().__init__(event_bus=event_bus)

    def define_parameters(self) -> list[ToolParameter]:
        """Return the parameter schema for sprite extraction."""
        return [
            ToolParameter(
                name="input",
                label="Sprite sheet image",
                type=Path,
                help="Path to the sprite sheet image file.",
            ),
            ToolParameter(
                name="output_dir",
                label="Output directory",
                type=Path,
                default=None,
                help="Directory for extracted sprites (default: sprites/ next to input).",
            ),
            ToolParameter(
                name="base_name",
                label="Base name",
                type=str,
                default=None,
                help="Base filename for output sprites (default: input filename stem).",
            ),
            ToolParameter(
                name="mode",
                label="Extraction mode",
                type=str,
                default="grid",
                choices=["grid", "auto", "metadata"],
                help="Extraction mode: grid (regular grid), auto (alpha detection), metadata (JSON).",
            ),
            ToolParameter(
                name="frame_width",
                label="Frame width",
                type=int,
                default=None,
                min_value=1,
                help="Width of each frame in pixels (grid mode, alternative to columns/rows).",
            ),
            ToolParameter(
                name="frame_height",
                label="Frame height",
                type=int,
                default=None,
                min_value=1,
                help="Height of each frame in pixels (grid mode, alternative to columns/rows).",
            ),
            ToolParameter(
                name="columns",
                label="Columns",
                type=int,
                default=None,
                min_value=1,
                help="Number of columns in the grid (grid mode, alternative to frame size).",
            ),
            ToolParameter(
                name="rows",
                label="Rows",
                type=int,
                default=None,
                min_value=1,
                help="Number of rows in the grid (grid mode, alternative to frame size).",
            ),
            ToolParameter(
                name="output_format",
                label="Output format",
                type=str,
                default="png",
                choices=sorted(VALID_OUTPUT_FORMATS),
                help="Output image format for extracted sprites.",
            ),
            ToolParameter(
                name="metadata_path",
                label="Metadata file",
                type=Path,
                default=None,
                help="Path to JSON metadata file (metadata mode only).",
            ),
        ]

    def input_types(self) -> list[type]:
        """Accept ``ImageData`` from a preceding pipeline stage."""
        return [ImageData]

    def output_types(self) -> list[type]:
        """Produce a ``PathList`` of extracted sprite paths."""
        return [PathList]

    def validate(self, params: dict[str, Any]) -> None:
        """Validate parameters with sprite-extractor-specific rules.

        Args:
            params: Parameter dict to validate.

        Raises:
            ValidationError: If parameters are invalid.
        """
        super().validate(params)

        mode = params.get("mode", "grid")
        output_format = params.get("output_format", "png")
        metadata_path = params.get("metadata_path")

        validate_extraction_params(
            mode=mode,
            output_format=output_format,
            frame_width=params.get("frame_width"),
            frame_height=params.get("frame_height"),
            columns=params.get("columns"),
            rows=params.get("rows"),
            metadata_path=Path(metadata_path) if metadata_path is not None else None,
        )

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> SpriteExtractionResult:
        """Run the sprite extraction logic.

        Args:
            params: Validated parameter dictionary.
            input_data: Optional ``ImageData`` from a preceding pipeline stage.

        Returns:
            A ``SpriteExtractionResult`` with extracted sprite metadata.

        Raises:
            ValidationError: If the input cannot be resolved.
        """
        # Resolve input path from params or pipeline input.
        if input_data is not None and isinstance(input_data, ImageData):
            sheet_path = input_data.path
        else:
            raw_input = params.get("input")
            if raw_input is None:
                msg = "No input sprite sheet provided"
                raise ValidationError(msg)
            sheet_path = Path(raw_input)

        # Resolve output directory.
        raw_output: Path | None = params.get("output_dir")
        output_dir = sheet_path.parent / "sprites" if raw_output is None else Path(raw_output)

        # Resolve base name.
        base_name: str = params.get("base_name") or sheet_path.stem

        mode: str = params.get("mode", "grid")
        output_format: str = params.get("output_format", "png")

        match mode:
            case "grid":
                return extract_grid(
                    sheet_path,
                    output_dir,
                    base_name,
                    frame_width=params.get("frame_width"),
                    frame_height=params.get("frame_height"),
                    columns=params.get("columns"),
                    rows=params.get("rows"),
                    output_format=output_format,
                    event_bus=self.event_bus,
                )
            case "metadata":
                meta_path = params.get("metadata_path")
                assert meta_path is not None
                return extract_from_metadata(
                    sheet_path,
                    Path(meta_path),
                    output_dir,
                    base_name,
                    output_format=output_format,
                    event_bus=self.event_bus,
                )
            case "auto":
                return extract_auto_detect(
                    sheet_path,
                    output_dir,
                    base_name,
                    output_format=output_format,
                    event_bus=self.event_bus,
                )
            case _:  # pragma: no cover
                msg = f"Unknown mode: {mode}"
                raise ValidationError(msg)
