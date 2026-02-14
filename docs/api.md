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
└── tools                   # Concrete tool sub-packages
    └── frame_extractor     # Video frame extraction
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
| `"progress"` | `tool`, `current`, `message` | Tools during frame-by-frame processing. |
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
