"""FrameExtractorTool — BaseTool wrapper for video frame extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from game_toolbox.core.base_tool import BaseTool, ToolParameter
from game_toolbox.core.datatypes import ExtractionResult, PathList
from game_toolbox.core.events import EventBus
from game_toolbox.tools.frame_extractor.logic import SUPPORTED_FORMATS, extract_frames


class FrameExtractorTool(BaseTool):
    """Extract frames from video files at configurable time intervals."""

    name = "frame_extractor"
    display_name = "Frame Extractor"
    description = "Extract frames from a video at regular intervals"
    version = "0.1.0"
    category = "Video"
    icon = "movie"

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialise the frame extractor tool.

        Args:
            event_bus: Shared event bus for progress reporting.
        """
        super().__init__(event_bus=event_bus)

    def define_parameters(self) -> list[ToolParameter]:
        """Return the parameter schema for frame extraction."""
        return [
            ToolParameter(
                name="video_path",
                label="Video file",
                type=Path,
                help="Path to the input video file.",
            ),
            ToolParameter(
                name="output_dir",
                label="Output directory",
                type=Path,
                help="Directory where extracted frames are saved.",
            ),
            ToolParameter(
                name="interval_ms",
                label="Interval (ms)",
                type=int,
                default=500,
                min_value=1,
                help="Time interval between extracted frames in milliseconds.",
            ),
            ToolParameter(
                name="format",
                label="Image format",
                type=str,
                default="webp",
                choices=list(SUPPORTED_FORMATS.keys()),
                help="Output image format.",
            ),
            ToolParameter(
                name="quality",
                label="Quality",
                type=int,
                default=None,
                min_value=1,
                max_value=100,
                help="Image quality (1-100). Uses format default if not set.",
            ),
            ToolParameter(
                name="max_frames",
                label="Max frames",
                type=int,
                default=None,
                min_value=1,
                help="Maximum number of frames to extract.",
            ),
        ]

    def input_types(self) -> list[type]:
        """Accept no pipeline input — this is an entry-point tool."""
        return []

    def output_types(self) -> list[type]:
        """Produce a ``PathList`` of extracted frame paths."""
        return [PathList]

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> ExtractionResult:
        """Run the frame extraction logic.

        Args:
            params: Validated parameter dictionary.
            input_data: Unused — this tool is a pipeline entry point.

        Returns:
            An ``ExtractionResult`` with output directory, count, and paths.
        """
        return extract_frames(
            video_path=params["video_path"],
            output_dir=params["output_dir"],
            interval_ms=params.get("interval_ms", 500),
            fmt=params.get("format", "webp"),
            quality=params.get("quality"),
            max_frames=params.get("max_frames"),
            event_bus=self.event_bus,
        )
