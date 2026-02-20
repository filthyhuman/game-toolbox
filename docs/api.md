# API Reference

Public API documentation for `game_toolbox`. All public classes and functions
use Google-style docstrings and full type annotations enforced by
`mypy --strict`.

## Package Structure

```
game_toolbox
├── core                    # Framework internals
│   ├── base_tool           # BaseTool ABC + ToolParameter
│   ├── registry            # ToolRegistry (auto-discovery singleton)
│   ├── pipeline            # Pipeline + PipelineStage
│   ├── events              # EventBus (Observer pattern)
│   ├── config              # ConfigManager (TOML-backed settings)
│   ├── datatypes           # Shared value objects
│   └── exceptions          # Exception hierarchy
├── cli                     # Click-based CLI entry points
├── gui                     # PySide6 GUI layer
│   ├── app                 # QApplication bootstrap (main entry point)
│   ├── main_window         # MainWindow: sidebar + stacked pages + status bar
│   ├── tool_page           # ToolPage: parameter form + run button + progress + log
│   ├── pipeline_editor     # Visual pipeline editor (placeholder)
│   └── widgets             # Reusable composite widgets
│       ├── param_form      # Auto-generated form from ToolParameter schema
│       ├── progress_panel  # Progress bar + status label
│       ├── file_picker     # File/directory picker
│       └── format_selector # Format dropdown
└── tools                   # Concrete tool sub-packages
    ├── frame_extractor     # Video frame extraction
    ├── image_resizer       # Image resizing (exact, fit, fill, percent)
    ├── chroma_key          # Chroma key background removal
    ├── sprite_sheet        # Sprite sheet atlas generation
    ├── sprite_extractor    # Sprite extraction from sprite sheets
    ├── animation_cropper   # Animation frame analysis and centre-cropping
    └── atlas_unpacker      # Cocos2d texture atlas extraction
```

---

## `game_toolbox.core.base_tool`

### `ToolParameter`

```python
@dataclass
class ToolParameter:
```

Declarative parameter definition that drives auto-generated GUI forms and CLI
arguments.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | *required* | Unique parameter identifier. |
| `label` | `str` | *required* | Human-readable label for UI. |
| `type` | `type` | *required* | Python type (`str`, `int`, `float`, `bool`, `Path`, ...). |
| `default` | `Any` | `None` | Default value. `None` means the parameter is optional. |
| `choices` | `list[Any] \| None` | `None` | Constrained set of allowed values. |
| `min_value` | `float \| None` | `None` | Minimum allowed numeric value. |
| `max_value` | `float \| None` | `None` | Maximum allowed numeric value. |
| `help` | `str` | `""` | Help text shown in tooltips and CLI `--help`. |

### `BaseTool`

```python
class BaseTool(ABC):
```

Abstract base class implementing the **Template Method** pattern. Every tool in
the toolbox must subclass `BaseTool` and implement its abstract methods.

#### Class Attributes (override in subclass)

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique slug (e.g. `"frame_extractor"`). |
| `display_name` | `str` | Human-readable label (e.g. `"Frame Extractor"`). |
| `description` | `str` | One-line description shown in the sidebar. |
| `version` | `str` | Tool version string. Default: `"0.1.0"`. |
| `category` | `str` | Grouping category for the sidebar. Default: `"General"`. |
| `icon` | `str` | Icon name or path. Default: `""`. |

#### Constructor

```python
def __init__(self, event_bus: EventBus | None = None) -> None
```

Initialise the tool. If no `event_bus` is provided, a default instance is
created.

#### Abstract Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `define_parameters` | `() -> list[ToolParameter]` | Return the tool's parameter schema. |
| `input_types` | `() -> list[type]` | Data types this tool accepts (empty = entry point). |
| `output_types` | `() -> list[type]` | Data types this tool produces (empty = terminal). |
| `_do_execute` | `(params, input_data) -> Any` | Core logic. **Must not import from `gui/`.** |

#### Template Method Lifecycle

```python
def run(self, params: dict[str, Any], input_data: Any = None) -> Any
```

Public entry point. Calls the lifecycle hooks in order:

1. `validate(params)` -- check parameter constraints
2. `_pre_execute(params)` -- optional pre-processing hook
3. `_do_execute(params, input_data)` -- core logic (**abstract**)
4. `_post_execute(result)` -- optional post-processing hook

**Do not override `run()`.** Override the individual hooks instead.

#### Hooks

| Hook | Default | Description |
|------|---------|-------------|
| `validate(params)` | Checks `choices` constraints | Override for custom validation. Raises `ValidationError`. |
| `_pre_execute(params)` | No-op | Called before `_do_execute`. |
| `_post_execute(result)` | No-op | Called after `_do_execute`. |

---

## `game_toolbox.core.registry`

### `ToolRegistry`

```python
class ToolRegistry:  # Singleton
```

Singleton registry that auto-discovers all `BaseTool` subclasses from
`game_toolbox.tools.*` sub-packages.

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `discover` | `(event_bus=None) -> None` | Scan tool packages and instantiate all found tools. |
| `get` | `(name: str) -> BaseTool \| None` | Look up a tool by its `name` slug. |
| `all_tools` | `() -> dict[str, BaseTool]` | Return all registered tools as `{name: instance}`. |
| `reset` | `() -> None` | *Class method.* Reset the singleton (testing only). |

#### Usage

```python
from game_toolbox.core.registry import ToolRegistry

registry = ToolRegistry()
registry.discover()

tool = registry.get("frame_extractor")
result = tool.run(params={...})
```

---

## `game_toolbox.core.pipeline`

### `PipelineStage`

```python
@dataclass
class PipelineStage:
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tool_name` | `str` | *required* | Registry slug of the tool. |
| `params` | `dict[str, Any]` | `{}` | Parameters passed to `tool.run()`. |

### `Pipeline`

```python
class Pipeline:
```

Composite of `PipelineStage` objects executed in sequence. The output of
stage *N* is passed as `input_data` to stage *N+1*.

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(name: str)` | Create an empty pipeline with a descriptive name. |
| `add_stage` | `(tool_name, params=None)` | Append a stage. |
| `validate` | `() -> None` | Check the pipeline is non-empty. Raises `PipelineError`. |
| `run` | `(input_data=None) -> Any` | Execute all stages in order. |
| `stages` | *property* `-> list[PipelineStage]` | Ordered copy of the stage list. |

#### Usage

```python
from game_toolbox.core.pipeline import Pipeline

pipeline = Pipeline(name="video-to-thumbnails")
pipeline.add_stage("frame_extractor", params={"interval_ms": 1000, "format": "webp"})
pipeline.add_stage("image_resizer", params={"width": 256, "height": 256})
pipeline.run(input_data=Path("gameplay.mp4"))
```

---

## `game_toolbox.core.events`

### `EventBus`

```python
class EventBus:
```

Publish/subscribe event bus for decoupled communication. Tools emit progress
and status events; the GUI and CLI subscribe independently.

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `subscribe` | `(event: str, handler) -> None` | Register a handler for an event type. |
| `unsubscribe` | `(event: str, handler) -> None` | Remove a handler. Logs a warning if not found. |
| `emit` | `(event: str, **kwargs) -> None` | Fire an event, calling all handlers with `**kwargs`. |

Handlers that raise exceptions are caught and logged without interrupting
other handlers.

#### Standard Events

| Event | Keyword Args | Emitted by |
|-------|-------------|------------|
| `"progress"` | `tool`, `current`, `message`, (`total`) | Tools during item-by-item processing. |
| `"completed"` | `tool`, `message` | Tools after successful completion. |

#### Usage

```python
from game_toolbox.core.events import EventBus

bus = EventBus()
bus.subscribe("progress", lambda **kw: print(kw["message"]))

# Pass to a tool
tool = FrameExtractorTool(event_bus=bus)
tool.run(params={...})
```

---

## `game_toolbox.core.config`

### `ConfigManager`

```python
class ConfigManager:
```

Hierarchical configuration manager backed by TOML files. Global settings can
be overridden on a per-tool basis.

**Config directory layout:**

```
~/.config/game-toolbox/
├── config.toml                # Global settings
└── tools/
    ├── frame_extractor.toml   # Per-tool overrides
    └── image_resizer.toml
```

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(config_dir=None)` | Use custom dir or default `~/.config/game-toolbox/`. |
| `load` | `() -> None` | Read TOML files from disk. Missing files are skipped. |
| `get` | `(key, *, tool=None, default=None) -> Any` | Retrieve a value. Per-tool overrides take precedence. |
| `set_global` | `(key, value) -> None` | Set an in-memory global value. |
| `config_dir` | *property* `-> Path` | The configuration directory path. |

---

## `game_toolbox.core.datatypes`

Immutable value objects (`frozen=True` dataclasses) shared across tools and
pipelines.

### `PathList`

| Field | Type | Description |
|-------|------|-------------|
| `paths` | `tuple[Path, ...]` | Ordered tuple of filesystem paths. |
| `count` | *property* `-> int` | Number of paths. |

### `ImageData`

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path` | Path to the image file. |
| `width` | `int` | Image width in pixels. |
| `height` | `int` | Image height in pixels. |
| `format` | `str` | Image format string (e.g. `"webp"`). |

### `VideoData`

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path` | Path to the video file. |
| `fps` | `float` | Frames per second. |
| `frame_count` | `int` | Total number of frames. |
| `duration_s` | `float` | Duration in seconds. |

### `ExtractionResult`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output_dir` | `Path` | *required* | Directory containing extracted frames. |
| `frame_count` | `int` | *required* | Number of frames extracted. |
| `paths` | `tuple[Path, ...]` | `()` | Paths to the extracted frame files. |

### `ResizeResult`

| Field | Type | Description |
|-------|------|-------------|
| `images` | `tuple[ImageData, ...]` | Metadata for each resized image. |
| `count` | `int` | Number of images resized. |
| `in_place` | `bool` | Whether originals were overwritten. |

### `ChromaKeyResult`

| Field | Type | Description |
|-------|------|-------------|
| `images` | `tuple[ImageData, ...]` | Metadata for each keyed image. |
| `count` | `int` | Number of images processed. |
| `in_place` | `bool` | Whether originals were overwritten. |

### `CropResult`

| Field | Type | Description |
|-------|------|-------------|
| `images` | `tuple[ImageData, ...]` | Metadata for each cropped image (empty in analyse-only mode). |
| `count` | `int` | Number of images cropped (0 in analyse-only mode). |
| `suggested_width` | `int` | Suggested power-of-two crop width from union bounding box. |
| `suggested_height` | `int` | Suggested power-of-two crop height from union bounding box. |

### `SpriteFrame`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Frame name (derived from input filename stem). |
| `x` | `int` | X position in the sprite sheet (pixels). |
| `y` | `int` | Y position in the sprite sheet (pixels). |
| `width` | `int` | Frame width in pixels. |
| `height` | `int` | Frame height in pixels. |

### `SpriteSheetResult`

| Field | Type | Description |
|-------|------|-------------|
| `sheet` | `ImageData` | Metadata for the generated sprite sheet image. |
| `frames` | `tuple[SpriteFrame, ...]` | Position and size of each frame. |
| `columns` | `int` | Number of columns in the grid. |
| `rows` | `int` | Number of rows in the grid. |
| `padding` | `int` | Pixel padding between frames. |
| `metadata_path` | `Path` | Path to the generated metadata file. |

### `SpriteExtractionResult`

| Field | Type | Description |
|-------|------|-------------|
| `output_dir` | `Path` | Directory containing extracted sprites. |
| `images` | `tuple[ImageData, ...]` | Metadata for each extracted sprite. |
| `count` | `int` | Number of sprites extracted. |

### `AtlasUnpackResult`

| Field | Type | Description |
|-------|------|-------------|
| `output_dir` | `Path` | Directory containing extracted atlas sprites. |
| `images` | `tuple[ImageData, ...]` | Metadata for each extracted sprite. |
| `count` | `int` | Number of sprites extracted. |

---

## `game_toolbox.core.exceptions`

```
ToolboxError (base)
├── ToolError           # Tool execution failures
├── ValidationError     # Parameter validation failures
└── PipelineError       # Pipeline construction or execution failures
```

All exceptions inherit from `ToolboxError` which inherits from `Exception`.

---

## `game_toolbox.gui`

The GUI layer provides a PySide6-based graphical interface. It is entirely
optional — all tools work headlessly via CLI or library import.

### `gui.app`

#### `main`

```python
def main() -> None
```

Launch the Game Toolbox GUI application. Creates a `QApplication`, discovers
tools via `ToolRegistry`, builds the `MainWindow`, and enters the Qt event loop.

This is the entry point for the `game-toolbox-gui` console script.

---

### `gui.main_window`

#### `MainWindow`

```python
class MainWindow(QMainWindow):
```

Top-level window containing a sidebar and stacked tool pages.

##### Constructor

```python
def __init__(
    self,
    registry: ToolRegistry | None = None,
    event_bus: EventBus | None = None,
) -> None
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `registry` | `ToolRegistry \| None` | Tool registry used to populate the sidebar. |
| `event_bus` | `EventBus \| None` | Shared event bus for status-bar messages. |

##### Behaviour

- Groups tools by `tool.category` with bold non-selectable headers in the sidebar.
- Creates a `ToolPage` for each discovered tool and a `PipelineEditor` placeholder.
- Sidebar selection switches the `QStackedWidget` to the corresponding page.
- Subscribes to EventBus `"completed"` events and shows a 5-second status-bar message.

---

### `gui.tool_page`

#### `ToolPage`

```python
class ToolPage(QWidget):
```

Adapter widget that presents a `BaseTool` in the GUI with an auto-generated
parameter form, run button, progress panel, and log area.

##### Constructor

```python
def __init__(
    self,
    tool: BaseTool,
    event_bus: EventBus | None = None,
    parent: QWidget | None = None,
) -> None
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool` | `BaseTool` | The tool instance to display and execute. |
| `event_bus` | `EventBus \| None` | Shared event bus for progress events. |
| `parent` | `QWidget \| None` | Optional parent widget. |

##### Layout

```
QVBoxLayout
  QLabel <h2>Tool Name</h2>
  QLabel description
  ParamForm (auto-generated)
  [Run button + spacer]
  ProgressPanel (bar + status label)
  QTextEdit (read-only log, monospace)
```

##### Threading Model

Tool execution runs in a `_ToolWorker(QThread)`. A `_BridgeSignals(QObject)`
bridges EventBus callbacks (called from the worker thread) to Qt signals
delivered on the main thread. The page subscribes to EventBus events before
each run and unsubscribes afterwards.

| Signal | Args | Description |
|--------|------|-------------|
| `_BridgeSignals.progress` | `int, int, str` | `(current, total, message)` from `"progress"` events. |
| `_BridgeSignals.completed` | `str` | Tool name from `"completed"` events. |
| `_BridgeSignals.error` | `str` | Error message from `"error"` events. |
| `_BridgeSignals.log` | `str` | Log line from `"log"` events. |
| `_ToolWorker.finished_ok` | `object` | Emitted with the result on success. |
| `_ToolWorker.failed` | `str` | Emitted with the error message on failure. |

---

### `gui.pipeline_editor`

#### `PipelineEditor`

```python
class PipelineEditor(QWidget):
```

Placeholder widget for the visual pipeline editor. Displays a "coming soon"
message. Will be replaced with a node-graph canvas in a future release.

---

### `gui.widgets.param_form`

#### `ParamForm`

```python
class ParamForm(QWidget):
```

Dynamically generated form from `ToolParameter` definitions.

| Parameter type | Widget |
|----------------|--------|
| `str` | `QLineEdit` |
| `int` | `QSpinBox` |
| `bool` | `QCheckBox` |
| `Path` | `QLineEdit` (with placeholder) |
| choices | `QComboBox` |

##### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_values` | `() -> dict[str, Any]` | Collect current form values as a parameter dictionary. |

---

### `gui.widgets.progress_panel`

#### `ProgressPanel`

```python
class ProgressPanel(QWidget):
```

Displays a progress bar (0-100) and a status label.

##### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `set_progress` | `(value: int) -> None` | Update the progress bar (clamped to 0-100). |
| `set_status` | `(message: str) -> None` | Update the status label text. |
| `reset` | `() -> None` | Reset bar to 0 and label to "Ready." |

---

## `game_toolbox.tools.frame_extractor`

### `frame_extractor.logic`

#### `extract_frames`

```python
def extract_frames(
    video_path: Path,
    output_dir: Path,
    *,
    interval_ms: int = 500,
    fmt: str = "webp",
    quality: int | None = None,
    max_frames: int | None = None,
    event_bus: EventBus | None = None,
) -> ExtractionResult
```

Extract frames from a video at regular time intervals.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `video_path` | `Path` | *required* | Input video file path. |
| `output_dir` | `Path` | *required* | Output directory (created automatically). |
| `interval_ms` | `int` | `500` | Interval between frames in milliseconds. |
| `fmt` | `str` | `"webp"` | Output format: `"png"`, `"webp"`, `"jpg"`, `"avif"`. |
| `quality` | `int \| None` | `None` | Quality 1-100. Format default if `None`. |
| `max_frames` | `int \| None` | `None` | Maximum frames. `None` extracts all. |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `ExtractionResult` with `output_dir`, `frame_count`, and `paths`.

**Raises:** `ToolError` if the video cannot be opened or the format is unsupported.

#### `probe_video`

```python
def probe_video(video_path: Path) -> VideoInfo
```

Open a video file and read its metadata without extracting frames.

**Returns:** `VideoInfo(fps, total_frames, duration_s)`.

**Raises:** `ToolError` if the video cannot be opened.

#### `VideoInfo`

```python
@dataclass(frozen=True)
class VideoInfo:
    fps: float
    total_frames: int
    duration_s: float
```

#### Constants

| Name | Type | Description |
|------|------|-------------|
| `SUPPORTED_FORMATS` | `dict[str, dict]` | Format metadata (extension, cv2 params). |
| `DEFAULT_QUALITY` | `dict[str, int]` | Default quality per format. |

### `frame_extractor.tool`

#### `FrameExtractorTool`

```python
class FrameExtractorTool(BaseTool):
```

| Attribute | Value |
|-----------|-------|
| `name` | `"frame_extractor"` |
| `display_name` | `"Frame Extractor"` |
| `category` | `"Video"` |
| `input_types()` | `[]` (pipeline entry point) |
| `output_types()` | `[PathList]` |

Wraps `extract_frames()` via the `BaseTool` template method lifecycle.
Pass parameters as a dict to `run()`:

```python
from pathlib import Path
from game_toolbox.tools.frame_extractor import FrameExtractorTool

tool = FrameExtractorTool()
result = tool.run(params={
    "video_path": Path("video.mp4"),
    "output_dir": Path("frames-out"),
    "interval_ms": 200,
    "format": "png",
    "quality": 90,
    "max_frames": 10,
})
```

---

## `game_toolbox.tools.image_resizer`

### `image_resizer.logic`

#### `collect_image_paths`

```python
def collect_image_paths(inputs: list[Path]) -> list[Path]
```

Collect image file paths from a mix of files and directories. Directories are
scanned non-recursively. Results are sorted and deduplicated.

**Supported extensions:** `.png`, `.jpg`, `.jpeg`, `.webp`, `.avif`, `.bmp`, `.tiff`

**Returns:** Sorted list of resolved `Path` objects.

**Raises:** `ToolError` if no image files are found.

#### `validate_resize_params`

```python
def validate_resize_params(
    *,
    mode: str,
    width: int | None,
    height: int | None,
    percent: float | None,
    resample: str,
) -> None
```

Validate resize parameters before processing.

**Raises:** `ValidationError` if parameters are invalid for the chosen mode.

#### `resize_image`

```python
def resize_image(
    input_path: Path,
    output_path: Path,
    *,
    mode: str,
    width: int | None = None,
    height: int | None = None,
    percent: float | None = None,
    resample: str = "lanczos",
    event_bus: EventBus | None = None,
) -> ImageData
```

Resize a single image file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_path` | `Path` | *required* | Source image path. |
| `output_path` | `Path` | *required* | Destination path (parent dir created automatically). |
| `mode` | `str` | *required* | `"exact"`, `"fit"`, `"fill"`, or `"percent"`. |
| `width` | `int \| None` | `None` | Target width (required for exact/fit/fill). |
| `height` | `int \| None` | `None` | Target height (required for exact/fit/fill). |
| `percent` | `float \| None` | `None` | Scale percentage 1-1000 (required for percent). |
| `resample` | `str` | `"lanczos"` | Resampling filter: `lanczos`, `bilinear`, `bicubic`, `nearest`. |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `ImageData` with the output path, dimensions, and format.

**Raises:** `ToolError` if the image cannot be opened or saved. `ValidationError` if parameters are invalid.

#### Resize Modes

| Mode | Description |
|------|-------------|
| `exact` | Force target dimensions, ignoring aspect ratio. |
| `fit` | Fit within the bounding box, preserving aspect ratio. Shorter side has padding room. |
| `fill` | Fill the bounding box, preserving aspect ratio. Excess is cropped from center. |
| `percent` | Scale by percentage (e.g. `50` = half size, `200` = double size). |

#### `resize_batch`

```python
def resize_batch(
    input_paths: list[Path],
    output_dir: Path | None,
    *,
    mode: str,
    width: int | None = None,
    height: int | None = None,
    percent: float | None = None,
    resample: str = "lanczos",
    event_bus: EventBus | None = None,
) -> ResizeResult
```

Resize a batch of images. When `output_dir` is `None`, images are resized
in-place (originals overwritten).

**Returns:** `ResizeResult` with image metadata, count, and in-place flag.

#### Constants

| Name | Type | Description |
|------|------|-------------|
| `IMAGE_EXTENSIONS` | `frozenset[str]` | Recognised image file extensions. |
| `RESAMPLE_FILTERS` | `dict[str, Image.Resampling]` | Map of filter names to Pillow constants. |
| `VALID_MODES` | `frozenset[str]` | Set of valid resize mode strings. |

### `image_resizer.tool`

#### `ImageResizerTool`

```python
class ImageResizerTool(BaseTool):
```

| Attribute | Value |
|-----------|-------|
| `name` | `"image_resizer"` |
| `display_name` | `"Image Resizer"` |
| `category` | `"Image"` |
| `input_types()` | `[PathList]` |
| `output_types()` | `[PathList]` |

Wraps `resize_batch()` via the `BaseTool` template method lifecycle.
Accepts `PathList` as pipeline input (e.g. from Frame Extractor).

```python
from pathlib import Path
from game_toolbox.tools.image_resizer import ImageResizerTool

tool = ImageResizerTool()
result = tool.run(params={
    "inputs": [Path("sprites/")],
    "output_dir": Path("resized/"),
    "mode": "fit",
    "width": 256,
    "height": 256,
    "percent": None,
    "resample": "lanczos",
    "in_place": False,
})
```

---

## `game_toolbox.tools.chroma_key`

### `chroma_key.logic`

#### `remove_chroma_key`

```python
def remove_chroma_key(
    input_path: Path,
    output_path: Path,
    *,
    color: tuple[int, int, int],
    tolerance: float = 30.0,
    softness: float = 10.0,
    event_bus: EventBus | None = None,
) -> ImageData
```

Remove a chroma key colour from a single image. Pixels within `tolerance`
Euclidean distance become fully transparent. Pixels in the `softness` band
receive proportional alpha.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_path` | `Path` | *required* | Source image path. |
| `output_path` | `Path` | *required* | Destination path (parent dir created automatically). |
| `color` | `tuple[int, int, int]` | *required* | Target RGB colour to remove. |
| `tolerance` | `float` | `30.0` | Euclidean distance threshold (0-255). |
| `softness` | `float` | `10.0` | Soft-edge transition band width. |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `ImageData` with the output path, dimensions, and format.

**Raises:** `ToolError` if the image cannot be opened or saved.

#### `chroma_key_batch`

```python
def chroma_key_batch(
    input_paths: list[Path],
    output_dir: Path | None,
    *,
    color: tuple[int, int, int],
    tolerance: float = 30.0,
    softness: float = 10.0,
    output_format: str = "png",
    event_bus: EventBus | None = None,
) -> ChromaKeyResult
```

Remove chroma key from a batch of images. When `output_dir` is `None`,
images are processed in-place.

**Returns:** `ChromaKeyResult` with image metadata, count, and in-place flag.

#### `validate_chroma_params`

```python
def validate_chroma_params(
    *,
    color: tuple[int, int, int],
    tolerance: float,
    softness: float,
    output_format: str,
) -> None
```

Validate chroma key parameters before processing.

**Raises:** `ValidationError` if parameters are out of range or unsupported.

#### Constants

| Name | Type | Description |
|------|------|-------------|
| `COLOR_PRESETS` | `dict[str, tuple[int, int, int]]` | Predefined chroma key colours (green, blue, magenta). |
| `ALPHA_FORMATS` | `frozenset[str]` | Output formats that support alpha (`png`, `webp`). |

### `chroma_key.tool`

#### `ChromaKeyTool`

```python
class ChromaKeyTool(BaseTool):
```

| Attribute | Value |
|-----------|-------|
| `name` | `"chroma_key"` |
| `display_name` | `"Chroma Key"` |
| `category` | `"Image"` |
| `input_types()` | `[PathList]` |
| `output_types()` | `[PathList]` |

Wraps `chroma_key_batch()` via the `BaseTool` template method lifecycle.
Accepts `PathList` as pipeline input (e.g. from Image Resizer).

```python
from pathlib import Path
from game_toolbox.tools.chroma_key import ChromaKeyTool

tool = ChromaKeyTool()
result = tool.run(params={
    "inputs": [Path("sprites/")],
    "output_dir": Path("keyed/"),
    "preset": "green",
    "color": None,
    "tolerance": 30.0,
    "softness": 10.0,
    "output_format": "png",
    "in_place": False,
})
```

---

## `game_toolbox.tools.sprite_sheet`

### `sprite_sheet.logic`

#### `generate_sprite_sheet`

```python
def generate_sprite_sheet(
    input_paths: list[Path],
    output_path: Path,
    *,
    columns: int | None = None,
    padding: int = 1,
    metadata_format: str = "json",
    event_bus: EventBus | None = None,
) -> SpriteSheetResult
```

Pack multiple images into a single sprite sheet atlas. Images are laid out in
a grid. If `columns` is `None`, it is auto-calculated as `ceil(sqrt(n))`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_paths` | `list[Path]` | *required* | Image file paths to pack. |
| `output_path` | `Path` | *required* | Destination path for the sprite sheet. |
| `columns` | `int \| None` | `None` | Grid columns (`None` for auto). |
| `padding` | `int` | `1` | Pixel padding between frames. |
| `metadata_format` | `str` | `"json"` | Metadata format: `json`, `css`, `xml`. |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `SpriteSheetResult` with sheet metadata, frame positions, and metadata file path.

**Raises:** `ToolError` if images cannot be opened or saved. `ValidationError` if parameters are invalid.

#### `validate_sprite_params`

```python
def validate_sprite_params(
    *,
    columns: int | None,
    padding: int,
    metadata_format: str,
    input_count: int,
) -> None
```

Validate sprite sheet parameters before processing.

**Raises:** `ValidationError` if parameters are out of range or unsupported.

#### Constants

| Name | Type | Description |
|------|------|-------------|
| `VALID_METADATA_FORMATS` | `frozenset[str]` | Supported metadata formats (`json`, `css`, `xml`). |

### `sprite_sheet.tool`

#### `SpriteSheetTool`

```python
class SpriteSheetTool(BaseTool):
```

| Attribute | Value |
|-----------|-------|
| `name` | `"sprite_sheet"` |
| `display_name` | `"Sprite Sheet"` |
| `category` | `"Image"` |
| `input_types()` | `[PathList]` |
| `output_types()` | `[ImageData]` |

Wraps `generate_sprite_sheet()` via the `BaseTool` template method lifecycle.
Accepts `PathList` as pipeline input (e.g. from Chroma Key).

```python
from pathlib import Path
from game_toolbox.tools.sprite_sheet import SpriteSheetTool

tool = SpriteSheetTool()
result = tool.run(params={
    "inputs": [Path("sprites/")],
    "output": Path("atlas.png"),
    "columns": 4,
    "padding": 1,
    "metadata_format": "json",
})
```

---

## `game_toolbox.tools.sprite_extractor`

### `sprite_extractor.logic`

#### `validate_extraction_params`

```python
def validate_extraction_params(
    *,
    mode: str,
    output_format: str,
    frame_width: int | None = None,
    frame_height: int | None = None,
    columns: int | None = None,
    rows: int | None = None,
    metadata_path: Path | None = None,
) -> None
```

Validate sprite extraction parameters before processing.

**Raises:** `ValidationError` if parameters are invalid for the chosen mode.

#### `extract_grid`

```python
def extract_grid(
    sheet_path: Path,
    output_dir: Path,
    base_name: str,
    *,
    frame_width: int | None = None,
    frame_height: int | None = None,
    columns: int | None = None,
    rows: int | None = None,
    output_format: str = "png",
    event_bus: EventBus | None = None,
) -> SpriteExtractionResult
```

Extract sprites from a sheet using a regular grid layout. Provide either
`(frame_width, frame_height)` or `(columns, rows)`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sheet_path` | `Path` | *required* | Path to the sprite sheet image. |
| `output_dir` | `Path` | *required* | Output directory for extracted sprites. |
| `base_name` | `str` | *required* | Base filename for output sprites. |
| `frame_width` | `int \| None` | `None` | Width of each grid cell. |
| `frame_height` | `int \| None` | `None` | Height of each grid cell. |
| `columns` | `int \| None` | `None` | Number of grid columns. |
| `rows` | `int \| None` | `None` | Number of grid rows. |
| `output_format` | `str` | `"png"` | Output format: `bmp`, `png`, `tiff`, `webp`. |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `SpriteExtractionResult` with extracted sprite metadata.

**Raises:** `ToolError` if the image cannot be opened.

#### `extract_from_metadata`

```python
def extract_from_metadata(
    sheet_path: Path,
    metadata_path: Path,
    output_dir: Path,
    base_name: str,
    *,
    output_format: str = "png",
    event_bus: EventBus | None = None,
) -> SpriteExtractionResult
```

Extract sprites using JSON metadata from the Sprite Sheet Generator tool.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sheet_path` | `Path` | *required* | Path to the sprite sheet image. |
| `metadata_path` | `Path` | *required* | Path to the JSON metadata file. |
| `output_dir` | `Path` | *required* | Output directory for extracted sprites. |
| `base_name` | `str` | *required* | Base filename for output sprites. |
| `output_format` | `str` | `"png"` | Output format. |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `SpriteExtractionResult` with extracted sprite metadata.

**Raises:** `ToolError` if the image or metadata cannot be read.

#### `extract_auto_detect`

```python
def extract_auto_detect(
    sheet_path: Path,
    output_dir: Path,
    base_name: str,
    *,
    output_format: str = "png",
    min_area: int = 16,
    event_bus: EventBus | None = None,
) -> SpriteExtractionResult
```

Auto-detect and extract sprites using alpha-based connected components.
Regions smaller than `min_area` are filtered as noise. Results are sorted
top-to-bottom, left-to-right.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sheet_path` | `Path` | *required* | Path to the sprite sheet image. |
| `output_dir` | `Path` | *required* | Output directory for extracted sprites. |
| `base_name` | `str` | *required* | Base filename for output sprites. |
| `output_format` | `str` | `"png"` | Output format. |
| `min_area` | `int` | `16` | Minimum bounding-box area to keep. |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `SpriteExtractionResult` with extracted sprite metadata.

**Raises:** `ToolError` if the image cannot be opened.

#### Constants

| Name | Type | Description |
|------|------|-------------|
| `VALID_OUTPUT_FORMATS` | `frozenset[str]` | Supported output formats (`bmp`, `png`, `tiff`, `webp`). |

### `sprite_extractor.tool`

#### `SpriteExtractorTool`

```python
class SpriteExtractorTool(BaseTool):
```

| Attribute | Value |
|-----------|-------|
| `name` | `"sprite_extractor"` |
| `display_name` | `"Sprite Extractor"` |
| `category` | `"Image"` |
| `input_types()` | `[ImageData]` |
| `output_types()` | `[PathList]` |

Wraps `extract_grid()`, `extract_from_metadata()`, and `extract_auto_detect()`
via the `BaseTool` template method lifecycle. Accepts `ImageData` as pipeline
input (e.g. from Sprite Sheet Generator).

```python
from pathlib import Path
from game_toolbox.tools.sprite_extractor import SpriteExtractorTool

tool = SpriteExtractorTool()
result = tool.run(params={
    "input": Path("sheet.png"),
    "output_dir": Path("sprites/"),
    "mode": "grid",
    "frame_width": 32,
    "frame_height": 32,
    "output_format": "png",
})
```

---

## `game_toolbox.tools.animation_cropper`

### `animation_cropper.logic`

#### `analyze_bounding_box`

```python
def analyze_bounding_box(image_path: Path) -> tuple[int, int, int, int]
```

Compute the bounding box of non-transparent content in an RGBA image. Uses
NumPy to find rows and columns with any non-zero alpha.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_path` | `Path` | *required* | Path to an image file. |

**Returns:** `(x, y, width, height)` tuple. Returns `(0, 0, 0, 0)` for fully transparent images.

**Raises:** `ToolError` if the image cannot be opened.

#### `compute_union_bbox`

```python
def compute_union_bbox(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]
```

Compute the union bounding box of multiple bounding boxes. Empty bounding
boxes `(0, 0, 0, 0)` are skipped.

**Returns:** `(x, y, width, height)` of the union. Returns `(0, 0, 0, 0)` if
all inputs are empty or the list is empty.

#### `crop_frame`

```python
def crop_frame(
    image_path: Path,
    output_path: Path,
    width: int,
    height: int,
    output_format: str = "png",
) -> ImageData
```

Centre-crop a single frame to the given dimensions. The crop region is
centred on the image centre. If the crop window exceeds the source
dimensions, the source is pasted onto a transparent canvas of the target size.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_path` | `Path` | *required* | Source image path. |
| `output_path` | `Path` | *required* | Destination path (parent dir created automatically). |
| `width` | `int` | *required* | Target crop width in pixels. |
| `height` | `int` | *required* | Target crop height in pixels. |
| `output_format` | `str` | `"png"` | Output format: `"png"` or `"webp"`. |

**Returns:** `ImageData` with the output path, dimensions, and format.

**Raises:** `ToolError` if the image cannot be opened or saved.

#### `analyze_only`

```python
def analyze_only(
    input_paths: list[Path],
    event_bus: EventBus | None = None,
) -> CropResult
```

Analyse all frames and return the suggested crop size without writing files.

**Returns:** `CropResult` with `count=0`, empty `images`, and suggested dimensions.

#### `crop_batch`

```python
def crop_batch(
    input_paths: list[Path],
    output_dir: Path,
    width: int,
    height: int,
    output_format: str = "png",
    event_bus: EventBus | None = None,
) -> CropResult
```

Two-pass operation: first analyse all frames to compute the union bounding
box and suggested size, then centre-crop each frame.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_paths` | `list[Path]` | *required* | Image file paths to process. |
| `output_dir` | `Path` | *required* | Directory for cropped images. |
| `width` | `int` | *required* | Target crop width. |
| `height` | `int` | *required* | Target crop height. |
| `output_format` | `str` | `"png"` | Output format: `"png"` or `"webp"`. |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `CropResult` with cropped image metadata and suggested size.

### `animation_cropper.tool`

#### `AnimationCropperTool`

```python
class AnimationCropperTool(BaseTool):
```

| Attribute | Value |
|-----------|-------|
| `name` | `"animation_cropper"` |
| `display_name` | `"Animation Cropper"` |
| `category` | `"Image"` |
| `input_types()` | `[PathList]` |
| `output_types()` | `[PathList]` |

Wraps `analyze_only()` and `crop_batch()` via the `BaseTool` template method
lifecycle. When `width` and `height` are both `None`, runs in analyse-only
mode. Accepts `PathList` as pipeline input.

```python
from pathlib import Path
from game_toolbox.tools.animation_cropper import AnimationCropperTool

tool = AnimationCropperTool()

# Analyse only
result = tool.run(params={
    "inputs": [Path("frames/")],
    "output_dir": None,
    "width": None,
    "height": None,
    "output_format": "png",
})
print(f"Suggested: {result.suggested_width}x{result.suggested_height}")

# Crop
result = tool.run(params={
    "inputs": [Path("frames/")],
    "output_dir": Path("cropped/"),
    "width": 128,
    "height": 128,
    "output_format": "png",
})
```

---

## `game_toolbox.tools.atlas_unpacker`

### `atlas_unpacker.logic`

#### `validate_atlas_params`

```python
def validate_atlas_params(
    *,
    plist_path: Path | None,
    output_dir: Path | None,
) -> None
```

Validate atlas unpack parameters before processing.

**Raises:** `ValidationError` if the plist path is missing, does not exist, or has wrong extension.

#### `extract_atlas`

```python
def extract_atlas(
    plist_path: Path,
    output_dir: Path,
    *,
    skip_existing: bool = False,
    pvrtextool: Path | None = None,
    event_bus: EventBus | None = None,
) -> AtlasUnpackResult
```

Extract all sprite frames from a Cocos2d `.plist` + texture atlas pair.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `plist_path` | `Path` | *required* | Path to the `.plist` atlas descriptor. |
| `output_dir` | `Path` | *required* | Output directory (created automatically). |
| `skip_existing` | `bool` | `False` | Skip sprites whose output file already exists. |
| `pvrtextool` | `Path \| None` | `None` | Path to PVRTexToolCLI (PVRTC only). |
| `event_bus` | `EventBus \| None` | `None` | Optional bus for progress events. |

**Returns:** `AtlasUnpackResult` with output directory, image metadata, and count.

**Raises:** `ToolError` if the texture cannot be found, loaded, or parsed.

#### `probe_atlas`

```python
def probe_atlas(plist_path: Path) -> dict[str, Any]
```

Return metadata about an atlas without extracting any images. Useful for
dry-run / preview in the GUI.

**Returns:** A dict with keys: `plist`, `texture`, `frame_count`,
`frame_names`, `metadata`.

### `atlas_unpacker.tool`

#### `AtlasUnpackerTool`

```python
class AtlasUnpackerTool(BaseTool):
```

| Attribute | Value |
|-----------|-------|
| `name` | `"atlas_unpacker"` |
| `display_name` | `"Atlas Unpacker"` |
| `category` | `"Image"` |
| `input_types()` | `[PathList]` |
| `output_types()` | `[PathList]` |

Wraps `extract_atlas()` and `probe_atlas()` via the `BaseTool` template
method lifecycle. Accepts `PathList` as pipeline input.

```python
from pathlib import Path
from game_toolbox.tools.atlas_unpacker import AtlasUnpackerTool

tool = AtlasUnpackerTool()
result = tool.run(params={
    "input": Path("GameObjects.plist"),
    "output_dir": Path("sprites/"),
    "skip_existing": False,
    "pvrtextool": None,
    "dry_run": False,
})
```
