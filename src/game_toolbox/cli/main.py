"""CLI entry point — click group that registers each tool's sub-command."""

from __future__ import annotations

import datetime
from pathlib import Path

import click

from game_toolbox.tools.frame_extractor.logic import SUPPORTED_FORMATS


def _build_output_dir(video_path: Path) -> Path:
    """Create a timestamped output directory next to the video file.

    The directory is named ``frames-YYYYMMDD_HHMMSS`` and placed in the
    same directory as the input video.

    Args:
        video_path: Resolved path to the input video.

    Returns:
        A ``Path`` to the (not yet created) output directory.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return video_path.parent / f"frames-{timestamp}"


@click.group()
@click.version_option(package_name="game-toolbox")
def cli() -> None:
    """Game Toolbox — modular media & game-dev CLI."""


@cli.command(name="frame-extractor")
@click.argument("video", type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option("-i", "--interval", default=500, show_default=True, help="Interval in ms between frames.")
@click.option(
    "-f",
    "--format",
    "fmt",
    default="webp",
    show_default=True,
    type=click.Choice(sorted(SUPPORTED_FORMATS.keys())),
    help="Output image format.",
)
@click.option("-q", "--quality", type=int, default=None, help="Quality 1-100 (overrides format default).")
@click.option("--max", "max_frames", type=int, default=None, help="Maximum number of frames to extract.")
def frame_extractor_cmd(
    video: str,
    interval: int,
    fmt: str,
    quality: int | None,
    max_frames: int | None,
) -> None:
    """Extract frames from a video file at configurable intervals.

    Frames are saved in a 'frames-TIMESTAMP' directory next to the video.
    """
    video_path = Path(video)
    output_dir = _build_output_dir(video_path)

    from game_toolbox.core.events import EventBus
    from game_toolbox.tools.frame_extractor import FrameExtractorTool

    bus = EventBus()
    bus.subscribe("progress", lambda **kw: click.echo(f"  [{kw['current']:5d}] {kw['message']}"))

    tool = FrameExtractorTool(event_bus=bus)
    result = tool.run(
        params={
            "video_path": video_path,
            "output_dir": output_dir,
            "interval_ms": interval,
            "format": fmt,
            "quality": quality,
            "max_frames": max_frames,
        },
    )

    click.echo(f"Extracted {result.frame_count} frames to {result.output_dir}")
