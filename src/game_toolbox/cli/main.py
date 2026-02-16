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


@cli.command(name="image-resizer")
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True, resolve_path=True))
@click.option(
    "-m",
    "--mode",
    required=True,
    type=click.Choice(["exact", "fit", "fill", "percent"]),
    help="Resize mode.",
)
@click.option("-W", "--width", type=int, default=None, help="Target width in pixels.")
@click.option("-H", "--height", type=int, default=None, help="Target height in pixels.")
@click.option("-p", "--percent", type=float, default=None, help="Scale percentage (1-1000).")
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(resolve_path=True),
    default=None,
    help="Output directory (default: 'resized/' next to first input).",
)
@click.option("--in-place", is_flag=True, default=False, help="Overwrite original files.")
@click.option(
    "-r",
    "--resample",
    default="lanczos",
    show_default=True,
    type=click.Choice(["lanczos", "bilinear", "bicubic", "nearest"]),
    help="Resampling filter.",
)
def image_resizer_cmd(
    inputs: tuple[str, ...],
    mode: str,
    width: int | None,
    height: int | None,
    percent: float | None,
    output_dir: str | None,
    in_place: bool,
    resample: str,
) -> None:
    """Resize images using exact, fit, fill, or percent mode.

    INPUTS can be image files, directories, or a mix of both.
    """
    from game_toolbox.core.events import EventBus
    from game_toolbox.tools.image_resizer import ImageResizerTool

    bus = EventBus()
    bus.subscribe("progress", lambda **kw: click.echo(f"  [{kw['current']:5d}/{kw['total']:5d}] {kw['message']}"))

    tool = ImageResizerTool(event_bus=bus)
    result = tool.run(
        params={
            "inputs": [Path(p) for p in inputs],
            "output_dir": Path(output_dir) if output_dir else None,
            "mode": mode,
            "width": width,
            "height": height,
            "percent": percent,
            "resample": resample,
            "in_place": in_place,
        },
    )

    location = "in-place" if result.in_place else str(result.images[0].path.parent) if result.images else "N/A"
    click.echo(f"Resized {result.count} images ({location})")


@cli.command(name="chroma-key")
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True, resolve_path=True))
@click.option(
    "-p",
    "--preset",
    default=None,
    type=click.Choice(["green", "blue", "magenta"]),
    help="Colour preset (default: green).",
)
@click.option("-c", "--color", "color_str", default=None, help="Custom RGB colour as 'R,G,B' (overrides preset).")
@click.option("-t", "--tolerance", type=float, default=30.0, show_default=True, help="Distance threshold (0-255).")
@click.option("-s", "--softness", type=float, default=10.0, show_default=True, help="Soft-edge transition band width.")
@click.option(
    "-f",
    "--format",
    "fmt",
    default="png",
    show_default=True,
    type=click.Choice(["png", "webp"]),
    help="Output image format (must support alpha).",
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(resolve_path=True),
    default=None,
    help="Output directory (default: 'keyed/' next to first input).",
)
@click.option("--in-place", is_flag=True, default=False, help="Overwrite original files.")
def chroma_key_cmd(
    inputs: tuple[str, ...],
    preset: str | None,
    color_str: str | None,
    tolerance: float,
    softness: float,
    fmt: str,
    output_dir: str | None,
    in_place: bool,
) -> None:
    """Remove solid-colour backgrounds from images and replace with transparency.

    INPUTS can be image files, directories, or a mix of both.
    If neither --preset nor --color is given, defaults to green.
    """
    from game_toolbox.core.events import EventBus
    from game_toolbox.tools.chroma_key import ChromaKeyTool

    bus = EventBus()
    bus.subscribe("progress", lambda **kw: click.echo(f"  [{kw['current']:5d}/{kw['total']:5d}] {kw['message']}"))

    tool = ChromaKeyTool(event_bus=bus)
    result = tool.run(
        params={
            "inputs": [Path(p) for p in inputs],
            "output_dir": Path(output_dir) if output_dir else None,
            "preset": preset or "green",
            "color": color_str,
            "tolerance": tolerance,
            "softness": softness,
            "output_format": fmt,
            "in_place": in_place,
        },
    )

    location = "in-place" if result.in_place else str(result.images[0].path.parent) if result.images else "N/A"
    click.echo(f"Keyed {result.count} images ({location})")


@cli.command(name="animation-cropper")
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True, resolve_path=True))
@click.option("-W", "--width", type=int, default=None, help="Crop width in pixels (omit for analyse-only).")
@click.option("-H", "--height", type=int, default=None, help="Crop height in pixels (omit for analyse-only).")
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(resolve_path=True),
    default=None,
    help="Output directory (default: 'cropped/' next to first input).",
)
@click.option(
    "-f",
    "--format",
    "fmt",
    default="png",
    show_default=True,
    type=click.Choice(["png", "webp"]),
    help="Output image format.",
)
def animation_cropper_cmd(
    inputs: tuple[str, ...],
    width: int | None,
    height: int | None,
    output_dir: str | None,
    fmt: str,
) -> None:
    """Analyse and centre-crop transparent animation frames.

    INPUTS can be image files, directories, or a mix of both.
    Omit --width and --height to analyse only (prints suggested crop size).
    """
    from game_toolbox.core.events import EventBus
    from game_toolbox.tools.animation_cropper import AnimationCropperTool

    bus = EventBus()
    bus.subscribe("progress", lambda **kw: click.echo(f"  [{kw['current']:5d}/{kw['total']:5d}] {kw['message']}"))
    bus.subscribe("log", lambda **kw: click.echo(f"  {kw['message']}"))

    tool = AnimationCropperTool(event_bus=bus)
    result = tool.run(
        params={
            "inputs": [Path(p) for p in inputs],
            "output_dir": Path(output_dir) if output_dir else None,
            "width": width,
            "height": height,
            "output_format": fmt,
        },
    )

    if result.count == 0:
        click.echo(f"Suggested crop size: {result.suggested_width}x{result.suggested_height}")
    else:
        click.echo(
            f"Cropped {result.count} frames to {width}x{height} "
            f"(suggested: {result.suggested_width}x{result.suggested_height})"
        )


@cli.command(name="sprite-sheet")
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True, resolve_path=True))
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(resolve_path=True),
    default=None,
    help="Output sprite sheet file (default: sprite-sheet/ next to first input).",
)
@click.option("-c", "--columns", type=int, default=None, help="Number of columns (default: auto).")
@click.option("-p", "--padding", type=int, default=1, show_default=True, help="Pixel padding between frames.")
@click.option(
    "-m",
    "--metadata",
    "metadata_format",
    default="json",
    show_default=True,
    type=click.Choice(["json", "css", "xml"]),
    help="Metadata output format.",
)
def sprite_sheet_cmd(
    inputs: tuple[str, ...],
    output_path: str | None,
    columns: int | None,
    padding: int,
    metadata_format: str,
) -> None:
    """Pack multiple images into a single sprite sheet atlas with metadata.

    INPUTS can be image files, directories, or a mix of both.
    """
    from game_toolbox.core.events import EventBus
    from game_toolbox.tools.sprite_sheet import SpriteSheetTool

    bus = EventBus()
    bus.subscribe("progress", lambda **kw: click.echo(f"  [{kw['current']:5d}/{kw['total']:5d}] {kw['message']}"))

    tool = SpriteSheetTool(event_bus=bus)
    result = tool.run(
        params={
            "inputs": [Path(p) for p in inputs],
            "output": Path(output_path) if output_path else None,
            "columns": columns,
            "padding": padding,
            "metadata_format": metadata_format,
        },
    )

    click.echo(
        f"Generated {result.columns}x{result.rows} sprite sheet "
        f"({result.sheet.width}x{result.sheet.height}px, "
        f"{len(result.frames)} frames) → {result.sheet.path}"
    )


@cli.command(name="sprite-extractor")
@click.argument("input_image", type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option("-n", "--name", "base_name", default=None, help="Base filename for output sprites.")
@click.option(
    "-m",
    "--mode",
    default="grid",
    show_default=True,
    type=click.Choice(["grid", "auto", "metadata"]),
    help="Extraction mode.",
)
@click.option("-W", "--width", "frame_width", type=int, default=None, help="Frame width in pixels (grid mode).")
@click.option("-H", "--height", "frame_height", type=int, default=None, help="Frame height in pixels (grid mode).")
@click.option("-c", "--columns", type=int, default=None, help="Number of columns (grid mode).")
@click.option("-r", "--rows", type=int, default=None, help="Number of rows (grid mode).")
@click.option(
    "-f",
    "--format",
    "fmt",
    default="png",
    show_default=True,
    type=click.Choice(["bmp", "png", "tiff", "webp"]),
    help="Output image format.",
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(resolve_path=True),
    default=None,
    help="Output directory (default: sprites/ next to input).",
)
@click.option(
    "--metadata",
    "metadata_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    default=None,
    help="Path to JSON metadata file (metadata mode).",
)
def sprite_extractor_cmd(
    input_image: str,
    base_name: str | None,
    mode: str,
    frame_width: int | None,
    frame_height: int | None,
    columns: int | None,
    rows: int | None,
    fmt: str,
    output_dir: str | None,
    metadata_path: str | None,
) -> None:
    """Extract individual sprites from a sprite sheet image.

    Supports grid-based, auto-detect, and metadata-based extraction modes.
    """
    from game_toolbox.core.events import EventBus
    from game_toolbox.tools.sprite_extractor import SpriteExtractorTool

    bus = EventBus()
    bus.subscribe("progress", lambda **kw: click.echo(f"  [{kw['current']:5d}/{kw['total']:5d}] {kw['message']}"))

    tool = SpriteExtractorTool(event_bus=bus)
    result = tool.run(
        params={
            "input": Path(input_image),
            "output_dir": Path(output_dir) if output_dir else None,
            "base_name": base_name,
            "mode": mode,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "columns": columns,
            "rows": rows,
            "output_format": fmt,
            "metadata_path": Path(metadata_path) if metadata_path else None,
        },
    )

    click.echo(f"Extracted {result.count} sprites to {result.output_dir}")
