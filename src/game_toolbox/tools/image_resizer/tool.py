"""ImageResizerTool — BaseTool wrapper for image resizing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from game_toolbox.core.base_tool import BaseTool, ToolParameter
from game_toolbox.core.datatypes import PathList, ResizeResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.image_resizer.logic import (
    RESAMPLE_FILTERS,
    VALID_MODES,
    collect_image_paths,
    resize_batch,
)


class ImageResizerTool(BaseTool):
    """Resize images using multiple modes: exact, fit, fill, or percent."""

    name = "image_resizer"
    display_name = "Image Resizer"
    description = "Resize images with exact, fit, fill, or percent modes"
    version = "0.1.0"
    category = "Image"
    icon = "photo_size_select_large"

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialise the image resizer tool.

        Args:
            event_bus: Shared event bus for progress reporting.
        """
        super().__init__(event_bus=event_bus)

    def define_parameters(self) -> list[ToolParameter]:
        """Return the parameter schema for image resizing."""
        return [
            ToolParameter(
                name="inputs",
                label="Input files/directories",
                type=list,
                help="List of image files or directories to resize.",
            ),
            ToolParameter(
                name="output_dir",
                label="Output directory",
                type=Path,
                default=None,
                help="Directory for resized images. None when using in-place mode.",
            ),
            ToolParameter(
                name="mode",
                label="Resize mode",
                type=str,
                choices=sorted(VALID_MODES),
                help="Resize strategy: exact, fit, fill, or percent.",
            ),
            ToolParameter(
                name="width",
                label="Width",
                type=int,
                default=None,
                min_value=1,
                help="Target width in pixels (required for exact/fit/fill).",
            ),
            ToolParameter(
                name="height",
                label="Height",
                type=int,
                default=None,
                min_value=1,
                help="Target height in pixels (required for exact/fit/fill).",
            ),
            ToolParameter(
                name="percent",
                label="Scale percent",
                type=float,
                default=None,
                min_value=1,
                max_value=1000,
                help="Scale percentage (required for percent mode).",
            ),
            ToolParameter(
                name="resample",
                label="Resample filter",
                type=str,
                default="lanczos",
                choices=sorted(RESAMPLE_FILTERS.keys()),
                help="Resampling algorithm for interpolation.",
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
        """Produce a ``PathList`` of resized image paths."""
        return [PathList]

    def validate(self, params: dict[str, Any]) -> None:
        """Validate parameters with mode-specific rules.

        Args:
            params: Parameter dict to validate.

        Raises:
            ValidationError: If parameters are invalid for the chosen mode.
        """
        super().validate(params)

        mode = params.get("mode")
        if mode is None:
            return

        if mode in {"exact", "fit", "fill"} and (params.get("width") is None or params.get("height") is None):
            msg = f"Mode '{mode}' requires both 'width' and 'height'"
            raise ValidationError(msg)

        if mode == "percent" and params.get("percent") is None:
            msg = "Mode 'percent' requires 'percent'"
            raise ValidationError(msg)

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> ResizeResult:
        """Run the image resize logic.

        Args:
            params: Validated parameter dictionary.
            input_data: Optional ``PathList`` from a preceding pipeline stage.

        Returns:
            A ``ResizeResult`` with resized image metadata.
        """
        # Resolve input paths from params or pipeline input.
        if input_data is not None and isinstance(input_data, PathList):
            image_paths = list(input_data.paths)
        else:
            raw_inputs: list[Path] = [Path(p) for p in params["inputs"]]
            image_paths = collect_image_paths(raw_inputs)

        # Determine output directory.
        in_place: bool = params.get("in_place", False)
        if in_place:
            output_dir = None
        else:
            output_dir = params.get("output_dir")
            if output_dir is None:
                # Default: "resized/" next to first input.
                output_dir = image_paths[0].parent / "resized"
            output_dir = Path(output_dir)

        return resize_batch(
            input_paths=image_paths,
            output_dir=output_dir,
            mode=params["mode"],
            width=params.get("width"),
            height=params.get("height"),
            percent=params.get("percent"),
            resample=params.get("resample", "lanczos"),
            event_bus=self.event_bus,
        )
