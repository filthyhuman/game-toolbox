"""Tests for FrameExtractorTool (BaseTool integration)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.core.datatypes import ExtractionResult, PathList
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.frame_extractor.tool import FrameExtractorTool

# ── Fixtures ───────────────────────────────────────────────────────────────


def _make_mock_capture(*, read_frames: int = 3) -> MagicMock:
    """Create a mock ``cv2.VideoCapture`` that yields *read_frames* dummy frames."""
    cap = MagicMock()
    cap.isOpened.return_value = True
    dummy_frame = np.zeros((4, 4, 3), dtype=np.uint8)
    reads: list[tuple[bool, Any]] = [(True, dummy_frame)] * read_frames + [(False, None)]
    cap.read.side_effect = reads
    return cap


@pytest.fixture()
def tool() -> FrameExtractorTool:
    """Return a fresh FrameExtractorTool instance."""
    return FrameExtractorTool()


@pytest.fixture()
def fake_video(tmp_path: Path) -> Path:
    """Return a path to a fake video file."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00")
    return video


# ── Metadata & Parameters ─────────────────────────────────────────────────


class TestToolMetadata:
    """Tests for tool identity and parameter schema."""

    def test_tool_name_and_category(self, tool: FrameExtractorTool) -> None:
        """Tool exposes the expected name and category."""
        assert tool.name == "frame_extractor"
        assert tool.category == "Video"
        assert tool.display_name == "Frame Extractor"

    def test_define_parameters_returns_list(self, tool: FrameExtractorTool) -> None:
        """``define_parameters`` returns a non-empty list of ``ToolParameter``."""
        params = tool.define_parameters()
        assert len(params) >= 4
        assert all(isinstance(p, ToolParameter) for p in params)

    def test_parameter_names_are_unique(self, tool: FrameExtractorTool) -> None:
        """No two parameters share the same name."""
        names = [p.name for p in tool.define_parameters()]
        assert len(names) == len(set(names))

    def test_input_types_empty(self, tool: FrameExtractorTool) -> None:
        """Frame extractor is a pipeline entry point — no input types."""
        assert tool.input_types() == []

    def test_output_types_contain_pathlist(self, tool: FrameExtractorTool) -> None:
        """Output types include ``PathList``."""
        assert PathList in tool.output_types()


# ── Validation ─────────────────────────────────────────────────────────────


class TestToolValidation:
    """Tests for the BaseTool validation triggered by ``run()``."""

    def test_rejects_invalid_format_choice(self, tool: FrameExtractorTool, fake_video: Path, tmp_path: Path) -> None:
        """Validation raises when format is not in the allowed choices."""
        with pytest.raises(ValidationError, match="must be one of"):
            tool.run(
                params={
                    "video_path": fake_video,
                    "output_dir": tmp_path / "out",
                    "format": "tiff",
                },
            )

    def test_accepts_valid_format(self, tool: FrameExtractorTool) -> None:
        """Validation passes for a known format value."""
        # Calling validate directly avoids needing a real video.
        tool.validate({"format": "webp"})

    def test_accepts_none_for_optional_params(self, tool: FrameExtractorTool) -> None:
        """Optional parameters with ``default=None`` pass validation when absent."""
        tool.validate({"quality": None, "max_frames": None})


# ── Execution ──────────────────────────────────────────────────────────────


class TestToolExecution:
    """Tests for the full ``run()`` lifecycle."""

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_run_returns_extraction_result(
        self,
        mock_vc: MagicMock,
        mock_imwrite: MagicMock,
        tool: FrameExtractorTool,
        fake_video: Path,
        tmp_path: Path,
    ) -> None:
        """Happy path: ``run()`` returns an ``ExtractionResult``."""
        mock_vc.return_value = _make_mock_capture(read_frames=3)
        mock_imwrite.return_value = True

        result = tool.run(
            params={
                "video_path": fake_video,
                "output_dir": tmp_path / "out",
                "interval_ms": 100,
                "format": "webp",
                "quality": None,
                "max_frames": None,
            },
        )

        assert isinstance(result, ExtractionResult)
        assert result.frame_count == 3

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_run_uses_event_bus(
        self,
        mock_vc: MagicMock,
        mock_imwrite: MagicMock,
        fake_video: Path,
        tmp_path: Path,
    ) -> None:
        """Progress events are emitted through the injected event bus."""
        mock_vc.return_value = _make_mock_capture(read_frames=2)
        mock_imwrite.return_value = True
        bus = EventBus()
        events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: events.append(kw))

        tool = FrameExtractorTool(event_bus=bus)
        tool.run(
            params={
                "video_path": fake_video,
                "output_dir": tmp_path / "out",
                "interval_ms": 200,
                "format": "png",
                "quality": None,
                "max_frames": None,
            },
        )

        assert len(events) == 2
        assert events[0]["tool"] == "frame_extractor"

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_run_respects_max_frames(
        self,
        mock_vc: MagicMock,
        mock_imwrite: MagicMock,
        tool: FrameExtractorTool,
        fake_video: Path,
        tmp_path: Path,
    ) -> None:
        """``max_frames`` limits the number of extracted frames."""
        mock_vc.return_value = _make_mock_capture(read_frames=10)
        mock_imwrite.return_value = True

        result = tool.run(
            params={
                "video_path": fake_video,
                "output_dir": tmp_path / "out",
                "interval_ms": 50,
                "format": "jpg",
                "quality": 80,
                "max_frames": 4,
            },
        )

        assert result.frame_count == 4
