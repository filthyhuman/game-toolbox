"""Integration tests for the CLI layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
from click.testing import CliRunner

from game_toolbox.cli.main import cli


def _make_mock_capture(*, read_frames: int = 2) -> MagicMock:
    """Create a mock ``cv2.VideoCapture``."""
    cap = MagicMock()
    cap.isOpened.return_value = True
    dummy = np.zeros((4, 4, 3), dtype=np.uint8)
    reads: list[tuple[bool, Any]] = [(True, dummy)] * read_frames + [(False, None)]
    cap.read.side_effect = reads
    return cap


class TestFrameExtractorCommand:
    """Tests for the ``frame-extractor`` CLI sub-command."""

    def test_help_shows_options(self) -> None:
        """``--help`` displays usage information without errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["frame-extractor", "--help"])

        assert result.exit_code == 0
        assert "frame-extractor" in result.output
        assert "--interval" in result.output
        assert "--format" in result.output

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_extracts_frames_from_video(self, mock_vc: MagicMock, mock_imwrite: MagicMock, tmp_path: Path) -> None:
        """Happy path: CLI extracts frames and reports the count."""
        mock_vc.return_value = _make_mock_capture(read_frames=3)
        mock_imwrite.return_value = True

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"\x00")

        runner = CliRunner()
        result = runner.invoke(cli, ["frame-extractor", str(video_file)])

        assert result.exit_code == 0
        assert "Extracted 3 frames" in result.output

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_output_dir_is_next_to_video(self, mock_vc: MagicMock, mock_imwrite: MagicMock, tmp_path: Path) -> None:
        """Output directory is created in the same folder as the video."""
        mock_vc.return_value = _make_mock_capture(read_frames=1)
        mock_imwrite.return_value = True

        video_file = tmp_path / "clip.mp4"
        video_file.write_bytes(b"\x00")

        runner = CliRunner()
        result = runner.invoke(cli, ["frame-extractor", str(video_file)])

        assert result.exit_code == 0
        # Output line contains tmp_path (the video's parent)
        assert str(tmp_path) in result.output
        assert "frames-" in result.output

    @patch("game_toolbox.tools.frame_extractor.logic.cv2.imwrite")
    @patch("game_toolbox.tools.frame_extractor.logic.cv2.VideoCapture")
    def test_custom_interval_and_format(self, mock_vc: MagicMock, mock_imwrite: MagicMock, tmp_path: Path) -> None:
        """CLI passes custom --interval and --format to the tool."""
        mock_vc.return_value = _make_mock_capture(read_frames=2)
        mock_imwrite.return_value = True

        video_file = tmp_path / "game.mp4"
        video_file.write_bytes(b"\x00")

        runner = CliRunner()
        result = runner.invoke(cli, ["frame-extractor", str(video_file), "-i", "200", "-f", "png"])

        assert result.exit_code == 0
        assert "Extracted 2 frames" in result.output

    def test_missing_video_file_errors(self, tmp_path: Path) -> None:
        """CLI exits with an error when the video file does not exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["frame-extractor", str(tmp_path / "nope.mp4")])

        assert result.exit_code != 0


class TestTopLevelCli:
    """Tests for the root CLI group."""

    def test_version_flag(self) -> None:
        """``--version`` prints the package version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help_flag_shows_usage(self) -> None:
        """``--help`` on the root group shows usage text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Game Toolbox" in result.output
        assert "frame-extractor" in result.output
