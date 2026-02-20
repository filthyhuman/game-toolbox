"""AtlasUnpackerTool — BaseTool wrapper for Cocos2d atlas extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from game_toolbox.core.base_tool import BaseTool, ToolParameter
from game_toolbox.core.datatypes import AtlasUnpackResult, PathList
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.atlas_unpacker.logic import (
    extract_atlas,
    probe_atlas,
    validate_atlas_params,
)


class AtlasUnpackerTool(BaseTool):
    """Extract individual sprites from Cocos2d texture atlas files.

    Parses ``.plist`` atlas descriptors paired with ``.pvr.ccz``, ``.pvr``,
    or ``.png`` textures. Handles CCZ decompression, PVR v2/v3 pixel
    formats, and sprite rotation/trimming.
    """

    name = "atlas_unpacker"
    display_name = "Atlas Unpacker"
    description = "Extract sprites from Cocos2d texture atlas (.plist + .pvr.ccz)"
    version = "0.1.0"
    category = "Image"
    icon = "unarchive"

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialise the atlas unpacker tool.

        Args:
            event_bus: Shared event bus for progress reporting.
        """
        super().__init__(event_bus=event_bus)

    def define_parameters(self) -> list[ToolParameter]:
        """Return the parameter schema for atlas unpacking."""
        return [
            ToolParameter(
                name="input",
                label="Plist file",
                type=Path,
                help="Path to the Cocos2d .plist atlas descriptor.",
            ),
            ToolParameter(
                name="output_dir",
                label="Output directory",
                type=Path,
                default=None,
                help="Directory for extracted sprites (default: unpacked/ next to input).",
            ),
            ToolParameter(
                name="skip_existing",
                label="Skip existing",
                type=bool,
                default=False,
                help="Skip sprites whose output file already exists.",
            ),
            ToolParameter(
                name="pvrtextool",
                label="PVRTexToolCLI path",
                type=Path,
                default=None,
                help="Path to PVRTexToolCLI (only needed for PVRTC textures).",
            ),
            ToolParameter(
                name="dry_run",
                label="Dry run",
                type=bool,
                default=False,
                help="Show atlas metadata without extracting sprites.",
            ),
        ]

    def input_types(self) -> list[type]:
        """Accept ``PathList`` from a preceding pipeline stage."""
        return [PathList]

    def output_types(self) -> list[type]:
        """Produce a ``PathList`` of extracted sprite paths."""
        return [PathList]

    def validate(self, params: dict[str, Any]) -> None:
        """Validate parameters with atlas-unpacker-specific rules.

        When ``input`` is ``None`` validation is skipped for the plist path
        because the path may arrive later via pipeline ``input_data``.

        Args:
            params: Parameter dict to validate.

        Raises:
            ValidationError: If parameters are invalid.
        """
        super().validate(params)

        raw_input = params.get("input")
        if raw_input is None:
            # Input may come from pipeline — skip plist validation here.
            return

        plist_path = Path(raw_input)
        output_dir = params.get("output_dir")

        validate_atlas_params(
            plist_path=plist_path,
            output_dir=Path(output_dir) if output_dir is not None else None,
        )

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> AtlasUnpackResult:
        """Run the atlas extraction logic.

        Args:
            params: Validated parameter dictionary.
            input_data: Optional ``PathList`` from a preceding pipeline stage.

        Returns:
            An ``AtlasUnpackResult`` with extracted sprite metadata.

        Raises:
            ValidationError: If the input cannot be resolved.
        """
        # Resolve input path from params or pipeline input.
        if input_data is not None and isinstance(input_data, PathList):
            if input_data.count == 0:
                msg = "Empty PathList received from pipeline"
                raise ValidationError(msg)
            plist_path = input_data.paths[0]
        else:
            raw_input = params.get("input")
            if raw_input is None:
                msg = "No input .plist file provided"
                raise ValidationError(msg)
            plist_path = Path(raw_input)

        # Dry run: return metadata only.
        dry_run: bool = params.get("dry_run", False)
        if dry_run:
            info = probe_atlas(plist_path)
            self.event_bus.emit(
                "log",
                tool="atlas_unpacker",
                message=(
                    f"Atlas: {plist_path.name}\n"
                    f"Texture: {info['texture']}\n"
                    f"Frames: {info['frame_count']}\n"
                    f"Metadata: {info['metadata']}"
                ),
            )
            return AtlasUnpackResult(
                output_dir=plist_path.parent,
                images=(),
                count=0,
            )

        # Resolve output directory.
        raw_output: Path | None = params.get("output_dir")
        output_dir = plist_path.parent / "unpacked" if raw_output is None else Path(raw_output)

        # Resolve optional parameters.
        skip_existing: bool = params.get("skip_existing", False)
        raw_pvrtextool = params.get("pvrtextool")
        pvrtextool = Path(raw_pvrtextool) if raw_pvrtextool is not None else None

        return extract_atlas(
            plist_path,
            output_dir,
            skip_existing=skip_existing,
            pvrtextool=pvrtextool,
            event_bus=self.event_bus,
        )
