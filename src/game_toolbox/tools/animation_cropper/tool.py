"""AnimationCropperTool — BaseTool wrapper for animation frame cropping."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from game_toolbox.core.base_tool import BaseTool, ToolParameter
from game_toolbox.core.datatypes import CropResult, PathList
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.animation_cropper.logic import analyze_only, crop_batch
from game_toolbox.tools.image_resizer.logic import collect_image_paths


class AnimationCropperTool(BaseTool):
    """Analyse transparent animation frames and centre-crop them to a uniform size."""

    name = "animation_cropper"
    display_name = "Animation Cropper"
    description = "Analyse and centre-crop transparent animation frames"
    version = "0.1.0"
    category = "Image"
    icon = "crop"

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialise the animation cropper tool.

        Args:
            event_bus: Shared event bus for progress reporting.
        """
        super().__init__(event_bus=event_bus)

    def define_parameters(self) -> list[ToolParameter]:
        """Return the parameter schema for animation cropping."""
        return [
            ToolParameter(
                name="inputs",
                label="Input files/directories",
                type=list,
                help="List of image files or directories containing animation frames.",
            ),
            ToolParameter(
                name="output_dir",
                label="Output directory",
                type=Path,
                default=None,
                help="Directory for cropped images (default: 'cropped/' next to first input).",
            ),
            ToolParameter(
                name="width",
                label="Crop width",
                type=int,
                default=None,
                min_value=1,
                help="Target crop width in pixels. Omit to analyse only.",
            ),
            ToolParameter(
                name="height",
                label="Crop height",
                type=int,
                default=None,
                min_value=1,
                help="Target crop height in pixels. Omit to analyse only.",
            ),
            ToolParameter(
                name="output_format",
                label="Output format",
                type=str,
                default="png",
                choices=["png", "webp"],
                help="Output image format (must support transparency).",
            ),
        ]

    def input_types(self) -> list[type]:
        """Accept a ``PathList`` from a preceding pipeline stage."""
        return [PathList]

    def output_types(self) -> list[type]:
        """Produce a ``PathList`` of cropped image paths."""
        return [PathList]

    def validate(self, params: dict[str, Any]) -> None:
        """Validate parameters — width and height must both be given or both omitted.

        Args:
            params: Parameter dict to validate.

        Raises:
            ValidationError: If only one of width/height is provided.
        """
        super().validate(params)

        width = params.get("width")
        height = params.get("height")

        if (width is None) != (height is None):
            msg = "Both 'width' and 'height' must be provided together, or both omitted for analyse-only mode"
            raise ValidationError(msg)

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> CropResult:
        """Run the animation cropping logic.

        Args:
            params: Validated parameter dictionary.
            input_data: Optional ``PathList`` from a preceding pipeline stage.

        Returns:
            A ``CropResult`` with cropped image metadata and suggested size.
        """
        # Resolve input paths from params or pipeline input.
        if input_data is not None and isinstance(input_data, PathList):
            image_paths = list(input_data.paths)
        else:
            raw_inputs: list[Path] = [Path(p) for p in params["inputs"]]
            image_paths = collect_image_paths(raw_inputs)

        width: int | None = params.get("width")
        height: int | None = params.get("height")

        # Analyse-only mode when no dimensions given.
        if width is None or height is None:
            return analyze_only(input_paths=image_paths, event_bus=self.event_bus)

        # Determine output directory.
        output_dir = params.get("output_dir")
        if output_dir is None:
            output_dir = image_paths[0].parent / "cropped"
        output_dir = Path(output_dir)

        output_format: str = params.get("output_format", "png")

        return crop_batch(
            input_paths=image_paths,
            output_dir=output_dir,
            width=width,
            height=height,
            output_format=output_format,
            event_bus=self.event_bus,
        )
