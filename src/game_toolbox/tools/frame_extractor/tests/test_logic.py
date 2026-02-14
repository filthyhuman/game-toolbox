"""Tests for frame extraction logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from game_toolbox.core.datatypes import ExtractionResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError
from game_toolbox.tools.frame_extractor.logic import (
    VideoInfo,
    _build_cv2_params,
    extract_frames,
    probe_video,
)

# ── Fixtures ───────────────────────────────────────────────────────────────


def _make_mock_capture(
    *,
    is_open: bool = True,
    fps: float = 30.0,
    frame_count: int = 300,
    read_frames: int = 5,
) -> MagicMock:
    """Create a mock ``cv2.VideoCapture`` that yields *read_frames* dummy frames."""
    cap = MagicMock()
    cap.isOpened.return_value = is_open

    def _get_prop(prop: int) -> float:
        if prop == cv2.CAP_PROP_FPS:
            return fps
        if prop == cv2.CAP_PROP_FRAME_COUNT:
            return float(frame_count)
        return 0.0

    cap.get.side_effect = _get_prop

    # Return a small BGR image for *read_frames* calls, then stop.
    dummy_frame = np.zeros((4, 4, 3), dtype=np.uint8)
    reads: list[tuple[bool, Any]] = [(True, dummy_frame)] * read_frames + [(False, None)]
    cap.read.side_effect = reads

    return cap


@pytest.fixture()
def fake_video(tmp_path: Path) -> Path:
    """Return a path to a fake video file (just needs to exist for the mock)."""
    video = tmp_path / "test_video.mp4"
    video.write_bytes(b"\x00")
    return video


# ── probe_video ────────────────────────────────────────────────────────────


class TestProbeVideo:
    """Tests for the ``probe_video`` helper."""

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_returns_video_info(self, mock_vc: MagicMock, fake_video: Path) -> None:
        """Happy path: returns correct metadata from a readable video."""
        mock_vc.return_value = _make_mock_capture(fps=24.0, frame_count=240)

        info = probe_video(fake_video)

        assert isinstance(info, VideoInfo)
        assert info.fps == 24.0
        assert info.total_frames == 240
        assert info.duration_s == pytest.approx(10.0)

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_raises_on_unopenable_video(self, mock_vc: MagicMock, tmp_path: Path) -> None:
        """Error case: ToolError when the capture cannot be opened."""
        mock_vc.return_value = _make_mock_capture(is_open=False)

        with pytest.raises(ToolError, match="could not be opened"):
            probe_video(tmp_path / "missing.mp4")

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_handles_zero_fps(self, mock_vc: MagicMock, fake_video: Path) -> None:
        """Edge case: duration is 0.0 when fps is 0 (corrupt metadata)."""
        mock_vc.return_value = _make_mock_capture(fps=0.0, frame_count=100)

        info = probe_video(fake_video)

        assert info.duration_s == 0.0


# ── _build_cv2_params ─────────────────────────────────────────────────────


class TestBuildCv2Params:
    """Tests for the internal ``_build_cv2_params`` helper."""

    def test_avif_returns_none(self) -> None:
        """AVIF uses Pillow, so cv2 params must be ``None``."""
        assert _build_cv2_params("avif", quality=80) is None

    def test_webp_default_quality(self) -> None:
        """WebP without quality override returns the format default."""
        params = _build_cv2_params("webp", quality=None)
        assert params == [cv2.IMWRITE_WEBP_QUALITY, 90]

    def test_jpg_custom_quality(self) -> None:
        """JPG with explicit quality returns overridden params."""
        params = _build_cv2_params("jpg", quality=75)
        assert params == [cv2.IMWRITE_JPEG_QUALITY, 75]

    def test_png_quality_maps_to_compression(self) -> None:
        """PNG quality is inverted and mapped to compression level 0-9."""
        params = _build_cv2_params("png", quality=100)
        assert params is not None
        assert params[1] == 0  # highest quality → lowest compression

        params_low = _build_cv2_params("png", quality=10)
        assert params_low is not None
        assert params_low[1] == 9  # lowest quality → highest compression


# ── extract_frames ─────────────────────────────────────────────────────────


class TestExtractFrames:
    """Tests for the main ``extract_frames`` function."""

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_extracts_expected_number_of_frames(
        self, mock_vc: MagicMock, mock_imwrite: MagicMock, fake_video: Path, tmp_path: Path
    ) -> None:
        """Happy path: extracts the correct number of frames as webp."""
        mock_vc.return_value = _make_mock_capture(read_frames=3)
        mock_imwrite.return_value = True
        output_dir = tmp_path / "out"

        result = extract_frames(fake_video, output_dir, interval_ms=100, fmt="webp")

        assert isinstance(result, ExtractionResult)
        assert result.frame_count == 3
        assert result.output_dir == output_dir
        assert len(result.paths) == 3
        assert all(p.suffix == ".webp" for p in result.paths)

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_respects_max_frames(
        self, mock_vc: MagicMock, mock_imwrite: MagicMock, fake_video: Path, tmp_path: Path
    ) -> None:
        """Edge case: stops after max_frames even if the video has more."""
        mock_vc.return_value = _make_mock_capture(read_frames=10)
        mock_imwrite.return_value = True

        result = extract_frames(fake_video, tmp_path / "out", max_frames=2)

        assert result.frame_count == 2

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_raises_on_invalid_video(self, mock_vc: MagicMock, tmp_path: Path) -> None:
        """Error case: ToolError for an unopenable video file."""
        mock_vc.return_value = _make_mock_capture(is_open=False)

        with pytest.raises(ToolError, match="could not be opened"):
            extract_frames(tmp_path / "nope.mp4", tmp_path / "out")

    def test_raises_on_unsupported_format(self, fake_video: Path, tmp_path: Path) -> None:
        """Error case: ToolError for an unknown image format."""
        with pytest.raises(ToolError, match="Unsupported format"):
            extract_frames(fake_video, tmp_path / "out", fmt="bmp")

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_creates_output_directory(
        self, mock_vc: MagicMock, mock_imwrite: MagicMock, fake_video: Path, tmp_path: Path
    ) -> None:
        """The output directory is created automatically if it does not exist."""
        mock_vc.return_value = _make_mock_capture(read_frames=1)
        mock_imwrite.return_value = True
        output_dir = tmp_path / "nested" / "deep" / "out"

        extract_frames(fake_video, output_dir)

        assert output_dir.is_dir()

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_emits_progress_events(
        self, mock_vc: MagicMock, mock_imwrite: MagicMock, fake_video: Path, tmp_path: Path
    ) -> None:
        """EventBus receives progress and completed events."""
        mock_vc.return_value = _make_mock_capture(read_frames=2)
        mock_imwrite.return_value = True
        bus = EventBus()
        progress_calls: list[dict[str, Any]] = []
        completed_calls: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: progress_calls.append(kw))
        bus.subscribe("completed", lambda **kw: completed_calls.append(kw))

        extract_frames(fake_video, tmp_path / "out", event_bus=bus)

        assert len(progress_calls) == 2
        assert progress_calls[0]["current"] == 1
        assert progress_calls[1]["current"] == 2
        assert len(completed_calls) == 1

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_filename_contains_timestamp(
        self, mock_vc: MagicMock, mock_imwrite: MagicMock, fake_video: Path, tmp_path: Path
    ) -> None:
        """Frame filenames encode the index and timestamp in seconds."""
        mock_vc.return_value = _make_mock_capture(read_frames=2)
        mock_imwrite.return_value = True

        result = extract_frames(fake_video, tmp_path / "out", interval_ms=500, fmt="jpg")

        assert result.paths[0].name == "frame_00000_0.000s.jpg"
        assert result.paths[1].name == "frame_00001_0.500s.jpg"

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_empty_video_returns_zero_frames(
        self, mock_vc: MagicMock, mock_imwrite: MagicMock, fake_video: Path, tmp_path: Path
    ) -> None:
        """A video that yields no readable frames returns an empty result."""
        mock_vc.return_value = _make_mock_capture(read_frames=0)

        result = extract_frames(fake_video, tmp_path / "out")

        assert result.frame_count == 0
        assert result.paths == ()
