# CLAUDE.md — game-toolbox

> Canonical project specification. Claude must read this file before every task and follow it strictly.
> When in doubt, this file wins over ad-hoc instructions.

---

## 1 · Project Identity

| Field | Value |
|---|---|
| **Name** | game-toolbox |
| **Repo** | `game-toolbox/` (already cloned, GitHub-hosted) |
| **Purpose** | A modular, extensible Python toolbox that collects standalone media / game-dev tools (video frame extraction, image processing, audio slicing, sprite-sheet generation, asset conversion …) under **one unified GUI**. Tools can run independently **or be chained into pipelines**. |
| **Package name** | `game_toolbox` (importable) |
| **Entry points** | GUI: `game-toolbox` / CLI: `game-toolbox <tool> [args]` / Library: `from game_toolbox.tools import …` |

---

## 2 · Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | **Python ≥ 3.11** | `match`, `type X = …` unions, `tomllib` in stdlib |
| Package / build | **uv** | `uv init`, `uv add`, `uv run`, `uv build`, `uv publish` — no pip, no setuptools |
| GUI framework | **PySide6** (Qt 6) | Native look, powerful widget set, signal/slot for Observer pattern |
| CLI framework | **click** | Decorator-based, composable groups — mirrors tool registry |
| Image / Video | **opencv-python-headless**, **Pillow** | Frame extraction, image transforms |
| Audio | **pydub** (optional) | Audio slicing tools |
| Testing | **pytest** ≥ 8, **pytest-qt**, **pytest-cov** | ≥ 80 % line coverage required |
| Linting | **ruff** | Replaces flake8 + isort + pycodestyle |
| Formatting | **ruff format** | Deterministic, fast |
| Type checking | **mypy --strict** | All public APIs fully annotated |
| CI | **GitHub Actions** | lint → typecheck → test → build — on every push & PR |
| Docs | Markdown: `README.md` + `docs/api.md` + per-tool `README.md` | API reference in `docs/`, tool docs inline |

---

## 3 · Repository Layout

```
game-toolbox/                          ← repo root (already exists)
├── CLAUDE.md                          ← THIS FILE — project bible
├── README.md                          ← user-facing docs, install, usage
├── LICENSE                            ← GPL-3.0-only
├── pyproject.toml                     ← single source of truth for uv + ruff + mypy
├── uv.lock                            ← committed lockfile
├── docs/
│   └── api.md                         ← API reference for all public modules
├── .github/
│   └── workflows/
│       └── ci.yml                     ← lint → typecheck → test → build
│
├── src/
│   └── game_toolbox/                  ← the installable package
│       ├── __init__.py                ← __version__, top-level re-exports
│       ├── __main__.py                ← `python -m game_toolbox` bootstrap
│       │
│       ├── core/                      ← framework internals (no tool logic here)
│       │   ├── __init__.py
│       │   ├── base_tool.py           ← BaseTool ABC — THE contract every tool implements
│       │   ├── registry.py            ← ToolRegistry singleton — auto-discovers tools
│       │   ├── pipeline.py            ← Pipeline & PipelineStage — chains tools via ports
│       │   ├── datatypes.py           ← shared value objects: ImageData, VideoData, PathList, ResizeResult, CropResult
│       │   ├── config.py              ← ConfigManager — per-tool + global settings (TOML-backed)
│       │   ├── events.py              ← EventBus — decoupled Observer for progress / status / errors
│       │   └── exceptions.py          ← ToolError, PipelineError, ValidationError hierarchy
│       │
│       ├── cli/                       ← headless CLI layer
│       │   ├── __init__.py
│       │   └── main.py               ← click group, registers each tool's CLI sub-command
│       │
│       ├── gui/                       ← PySide6 GUI layer
│       │   ├── __init__.py
│       │   ├── app.py                ← QApplication bootstrap, theme loading
│       │   ├── main_window.py        ← MainWindow: sidebar + stacked pages + status bar
│       │   ├── tool_page.py          ← ToolPage: base widget wrapping a tool's parameter form
│       │   ├── pipeline_editor.py    ← visual node-graph canvas for chaining tools
│       │   └── widgets/              ← reusable composite widgets
│       │       ├── __init__.py
│       │       ├── file_picker.py
│       │       ├── format_selector.py
│       │       ├── param_form.py     ← auto-generates form from tool's parameter schema
│       │       └── progress_panel.py
│       │
│       └── tools/                     ← EACH TOOL = its own sub-package
│           ├── __init__.py            ← discovery helper: collects all BaseTool subclasses
│           │
│           ├── frame_extractor/       ← example tool
│           │   ├── __init__.py        ← exports FrameExtractorTool
│           │   ├── tool.py            ← FrameExtractorTool(BaseTool)
│           │   ├── logic.py           ← pure functions / classes for extraction (no GUI imports)
│           │   ├── gui_panel.py       ← optional QWidget for tool-specific GUI beyond auto-form
│           │   ├── README.md          ← tool-level docs
│           │   └── tests/
│           │       ├── __init__.py
│           │       ├── test_logic.py
│           │       └── test_tool.py
│           │
│           ├── image_resizer/         ← image resizing (same structure)
│           │   ├── __init__.py
│           │   ├── tool.py
│           │   ├── logic.py
│           │   ├── gui_panel.py
│           │   ├── README.md
│           │   └── tests/
│           │       └── …
│           │
│           ├── chroma_key/            ← chroma key background removal
│           │   ├── __init__.py
│           │   ├── tool.py
│           │   ├── logic.py
│           │   ├── README.md
│           │   └── tests/
│           │       └── …
│           │
│           ├── sprite_sheet/          ← sprite sheet atlas generation
│           │   ├── __init__.py
│           │   ├── tool.py
│           │   ├── logic.py
│           │   ├── README.md
│           │   └── tests/
│           │       └── …
│           │
│           ├── animation_cropper/     ← animation frame analysis & centre-cropping
│           │   ├── __init__.py
│           │   ├── tool.py
│           │   ├── logic.py
│           │   ├── README.md
│           │   └── tests/
│           │       └── …
│           │
│           └── <next_tool>/           ← add more tools following the same skeleton
│               └── …
│
└── tests/                             ← project-wide / integration tests
    ├── __init__.py
    ├── conftest.py                    ← shared fixtures (tmp dirs, sample assets, Qt app)
    ├── test_registry.py
    ├── test_pipeline.py
    ├── test_config.py
    ├── test_events.py
    └── test_cli.py
```

---

## 4 · Architecture & Design Patterns

### 4.1 Overview Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                        │
│   ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│   │  CLI (click)│  │  GUI (Qt 6)  │  │  Library API (import)  │  │
│   └──────┬─────┘  └──────┬───────┘  └───────────┬────────────┘  │
│          │               │                       │               │
│          └───────────────┼───────────────────────┘               │
│                          ▼                                       │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                     Core Framework                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐  │   │
│  │  │ Registry │ │ Pipeline │ │ EventBus │ │ ConfigMgr   │  │   │
│  │  │(Singleton│ │(Composite│ │(Observer)│ │ (Strategy)  │  │   │
│  │  │ +Factory)│ │ +Chain ) │ │          │ │             │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬──────┘  │   │
│  │       │            │            │               │         │   │
│  │       ▼            ▼            ▼               ▼         │   │
│  │  ┌────────────────────────────────────────────────────┐   │   │
│  │  │               BaseTool ABC (Template Method)       │   │   │
│  │  └────────────────────────────────────────────────────┘   │   │
│  └───────────────────────────────────────────────────────────┘   │
│                          │                                       │
│          ┌───────────────┼───────────────┐                       │
│          ▼               ▼               ▼                       │
│  ┌──────────────┐ ┌─────────────┐ ┌──────────────┐              │
│  │FrameExtractor│ │ImageResizer │ │  NextTool …  │   Tools      │
│  └──────────────┘ └─────────────┘ └──────────────┘              │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Patterns in Use

| Pattern | Where | Purpose |
|---|---|---|
| **Abstract Factory + Singleton** | `ToolRegistry` | Single registry discovers, instantiates, and caches tools by name |
| **Template Method** | `BaseTool` | Defines the skeleton: `validate → configure → execute → cleanup`. Subclasses override `_do_execute()` etc. |
| **Strategy** | `BaseTool.parameters` schema + `ConfigManager` | Each tool declares its parameters as a schema; the GUI and CLI consume them generically |
| **Observer** | `EventBus` (core) + Qt Signals (GUI) | Tools emit progress / log / error events; GUI and CLI subscribe independently |
| **Composite + Chain of Responsibility** | `Pipeline`, `PipelineStage` | A pipeline is a composite of stages; data flows through the chain, each stage transforms or filters |
| **Command** | CLI layer wraps each tool invocation as a reversible command object | Enables undo in GUI and clean CLI dispatch |
| **Adapter** | `gui/tool_page.py` | Adapts a headless `BaseTool` to a Qt widget page |
| **Dependency Injection** | Constructor injection throughout | Tools receive dependencies (logger, config, event_bus) — no global imports of singletons inside business logic |

### 4.3 BaseTool ABC — The Contract

Every tool **must** subclass `BaseTool`. This is the central abstraction:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ToolParameter:
    """Declarative parameter definition — drives auto-generated GUI forms and CLI args."""
    name: str
    label: str
    type: type                          # str, int, float, bool, Path, list[str] …
    default: Any = None
    choices: list[Any] | None = None    # constrained set → dropdown / click.Choice
    min_value: float | None = None
    max_value: float | None = None
    help: str = ""

class BaseTool(ABC):
    """Template Method base for every tool in the toolbox."""

    # ── metadata (override in subclass) ────────────────────────
    name: str                       # unique slug e.g. "frame_extractor"
    display_name: str               # human label e.g. "Frame Extractor"
    description: str                # one-liner shown in sidebar
    version: str = "0.1.0"
    category: str = "General"       # groups tools in the sidebar
    icon: str = ""                  # path to .svg or material-icon name

    # ── parameter schema ───────────────────────────────────────
    @abstractmethod
    def define_parameters(self) -> list[ToolParameter]:
        """Return the list of parameters this tool accepts."""
        ...

    # ── I/O port declarations (for pipeline chaining) ─────────
    @abstractmethod
    def input_types(self) -> list[type]:
        """Data types this tool can receive (empty = entry point)."""
        ...

    @abstractmethod
    def output_types(self) -> list[type]:
        """Data types this tool produces (empty = terminal)."""
        ...

    # ── lifecycle (Template Method skeleton) ───────────────────
    def run(self, params: dict[str, Any], input_data: Any = None) -> Any:
        """Public entry — do NOT override."""
        self.validate(params)
        self._pre_execute(params)
        result = self._do_execute(params, input_data)
        self._post_execute(result)
        return result

    def validate(self, params: dict[str, Any]) -> None:
        """Validate params against define_parameters(). Override to add custom rules."""
        ...

    def _pre_execute(self, params: dict[str, Any]) -> None:
        """Hook before execution (optional override)."""
        pass

    @abstractmethod
    def _do_execute(self, params: dict[str, Any], input_data: Any) -> Any:
        """Core logic — MUST override. Pure computation, no GUI code."""
        ...

    def _post_execute(self, result: Any) -> None:
        """Hook after execution (optional override)."""
        pass
```

**Rules for tools:**
- Business logic lives in `logic.py` — the `tool.py` file only wires the `BaseTool` interface.
- `_do_execute` must NEVER import from `gui/` — keep it headless-testable.
- Tools emit progress via the injected `EventBus`, never via `print()`.
- Every tool folder has its own `tests/` sub-directory.

---

## 5 · OOP & Code Quality Standards

### 5.1 PEP Compliance

| Standard | Enforced by | Notes |
|---|---|---|
| **PEP 8** — style | `ruff` (rules: `E`, `W`, `F`, `I`, `N`, `UP`) | Line length 120 chars |
| **PEP 257** — docstrings | `ruff` (`D` rules) | Google-style docstrings on all public classes, methods, functions |
| **PEP 484 / 526 / 604** — typing | `mypy --strict` | All public signatures fully annotated; use `X \| None` not `Optional[X]` |
| **PEP 517 / 621** — packaging | `pyproject.toml` | All metadata in `[project]`; build-backend = uv |
| **PEP 585** — generic builtins | ruff `UP` rules | Use `list[str]` not `List[str]` |
| **PEP 8 naming** | ruff `N` rules | `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants |

### 5.2 OOP Rules

1. **Single Responsibility** — one class, one reason to change. Never mix GUI and business logic in the same class.
2. **Open/Closed** — new tools are added by creating a new sub-package; zero changes to `core/` or `gui/`.
3. **Liskov Substitution** — every `BaseTool` subclass must be usable anywhere a `BaseTool` is expected.
4. **Interface Segregation** — if a tool has no GUI-specific panel, it simply doesn't provide one; the auto-form handles it.
5. **Dependency Inversion** — high-level modules (`pipeline.py`, `main_window.py`) depend on `BaseTool` ABC, never on concrete tool classes.
6. **Composition over inheritance** — tools compose helper classes from `logic.py`; deep inheritance hierarchies are forbidden (max depth: BaseTool → ConcreteTool).
7. **No global mutable state** — the `ToolRegistry` singleton is the only exception and it is read-only after startup.
8. **Dataclasses / attrs for value objects** — `ToolParameter`, `ImageData`, `PipelineResult` etc. must be dataclasses or `@dataclass` with `frozen=True` where possible.

### 5.3 Ruff Configuration (in pyproject.toml)

```toml
[tool.ruff]
target-version = "py311"
line-length = 120
src = ["src"]

[tool.ruff.lint]
select = [
    "E", "W",     # pycodestyle
    "F",           # pyflakes
    "I",           # isort
    "N",           # pep8-naming
    "UP",          # pyupgrade
    "D",           # pydocstyle
    "B",           # flake8-bugbear
    "SIM",         # flake8-simplify
    "RUF",         # ruff-specific
]
ignore = ["D100", "D104"]  # missing docstring in __init__.py / public package

[tool.ruff.lint.pydocstyle]
convention = "google"
```

### 5.4 Mypy Configuration

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
packages = ["game_toolbox"]
```

---

## 6 · Testing Strategy

### 6.1 Principles

- **Every tool has unit tests** in `tools/<name>/tests/`.
- **Core framework** has integration tests in top-level `tests/`.
- **No test may import from `gui/`** unless it is an explicit GUI test using `pytest-qt`.
- Tests follow **Arrange → Act → Assert** structure.
- Use **fixtures and factories** (in `conftest.py`) — never raw file paths or magic strings.
- Mock external dependencies (filesystem, OpenCV capture, network) — tools must be testable offline.

### 6.2 Coverage Requirements

| Scope | Minimum coverage |
|---|---|
| `core/` | 90 % |
| `tools/*/logic.py` | 90 % |
| `tools/*/tool.py` | 80 % |
| `cli/` | 80 % |
| `gui/` | 60 % (harder to test; focus on signal wiring) |
| **Overall** | **80 %** |

### 6.3 Running Tests

```bash
uv run pytest                           # all tests
uv run pytest --cov=game_toolbox --cov-report=term-missing   # with coverage
uv run pytest tests/                    # framework tests only
uv run pytest src/game_toolbox/tools/frame_extractor/tests/  # single tool
```

### 6.4 Test File Conventions

```python
"""Tests for FrameExtractorTool logic."""

import pytest
from game_toolbox.tools.frame_extractor.logic import extract_frames


class TestExtractFrames:
    """Group related tests in classes — PascalCase, prefixed with Test."""

    def test_extracts_first_frame(self, tmp_path: Path, sample_video: Path) -> None:
        """Test names describe the expected behavior, not the method name."""
        # Arrange
        output_dir = tmp_path / "out"
        # Act
        result = extract_frames(sample_video, output_dir, interval_ms=100)
        # Assert
        assert result.frame_count >= 1
        assert (output_dir / "frame_00000_0.000s.webp").exists()

    def test_raises_on_invalid_video(self, tmp_path: Path) -> None:
        """Expect ToolError for unreadable input."""
        with pytest.raises(ToolError, match="could not be opened"):
            extract_frames(tmp_path / "nope.mp4", tmp_path / "out")
```

---

## 7 · Packaging with uv

### 7.1 pyproject.toml (key sections)

```toml
[project]
name = "game-toolbox"
version = "0.1.0"
description = "Modular media & game-dev toolbox with GUI and pipeline support"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = [
    "PySide6>=6.6",
    "click>=8.1",
    "opencv-python-headless>=4.9",
    "Pillow>=10.0",
]

[project.optional-dependencies]
audio = ["pydub>=0.25"]
dev = [
    "pytest>=8.0",
    "pytest-qt>=4.3",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
]

[project.scripts]
game-toolbox = "game_toolbox.cli.main:cli"

[project.gui-scripts]
game-toolbox-gui = "game_toolbox.gui.app:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/game_toolbox"]
```

### 7.2 Common uv Commands

```bash
uv sync                        # install all deps from lockfile
uv sync --extra dev            # include dev dependencies
uv add <package>               # add a runtime dependency
uv add --dev <package>         # add a dev dependency
uv run game-toolbox --help     # run CLI entry point
uv run game-toolbox-gui        # launch GUI
uv run pytest                  # run tests
uv run ruff check src/         # lint
uv run ruff format src/        # format
uv run mypy src/               # type check
uv build                       # produce wheel + sdist in dist/
uv publish                     # publish to PyPI (needs token)
```

---

## 8 · Tool Discovery & Registration

`ToolRegistry` auto-discovers tools at startup. **Zero manual registration required.**

### How it works:

1. On import, `registry.py` scans `game_toolbox.tools.*` sub-packages.
2. Any module containing a class that subclasses `BaseTool` is collected.
3. The registry instantiates each tool (with dependency injection of EventBus, ConfigManager).
4. GUI sidebar and CLI sub-commands are generated automatically from the registry.

### Adding a new tool — checklist:

```
1. mkdir src/game_toolbox/tools/<tool_name>/
2. Create __init__.py, tool.py, logic.py, README.md, tests/
3. Subclass BaseTool in tool.py — implement all abstract methods
4. Put pure computation in logic.py
5. (Optional) Create gui_panel.py with a QWidget for custom UI
6. Write tests in tests/
7. Done — restart the app, tool appears automatically
```

---

## 9 · Pipeline System

Pipelines chain tools by connecting the **output ports** of one tool to the **input ports** of the next.

```python
# Programmatic pipeline construction
from game_toolbox.core.pipeline import Pipeline

pipeline = Pipeline(name="video-to-thumbnails")
pipeline.add_stage("frame_extractor", params={"interval_ms": 1000, "format": "webp"})
pipeline.add_stage("image_resizer", params={"width": 256, "height": 256})
pipeline.run(input_data=Path("gameplay.mp4"))
```

**Rules:**
- `output_types()` of stage N must overlap with `input_types()` of stage N+1 — validated at build time.
- Pipelines can be serialized to / loaded from TOML files for reproducibility.
- The GUI pipeline editor renders stages as draggable nodes on a canvas.

---

## 10 · GUI Architecture

```
MainWindow
├── QSplitter
│   ├── Sidebar (QListWidget)            ← grouped by tool.category
│   │   ├── 📁 Image                     (bold, non-selectable header)
│   │   │   ├── Animation Cropper
│   │   │   ├── Chroma Key
│   │   │   ├── Image Resizer
│   │   │   └── Sprite Sheet
│   │   ├── 📁 Video
│   │   │   └── Frame Extractor
│   │   └── 📁 Pipelines
│   │       └── Pipeline Editor
│   └── QStackedWidget                   ← one ToolPage per tool
│       ├── ToolPage[AnimationCropper]
│       │   ├── QLabel <h2> + description
│       │   ├── ParamForm (auto-generated from define_parameters())
│       │   ├── [Run] button
│       │   ├── ProgressPanel (bar + status label)
│       │   └── QTextEdit log (read-only, monospace)
│       ├── ToolPage[ChromaKey]
│       ├── ToolPage[ImageResizer]
│       ├── ToolPage[SpriteSheet]
│       ├── ToolPage[FrameExtractor]
│       └── PipelineEditorPage
└── QStatusBar                           ← shows "X completed." on EventBus events
```

### 10.1 Bootstrap (`app.py`)

`main()` creates a `QApplication`, an `EventBus`, a `ToolRegistry` (with
`discover(event_bus=…)`), and a `MainWindow(registry=…, event_bus=…)`.

### 10.2 MainWindow (`main_window.py`)

- Accepts `registry` and `event_bus` in its constructor.
- `_populate_tools()` groups tools by `tool.category`, adds bold non-selectable
  category headers and selectable tool items to the sidebar, creates a
  `ToolPage` per tool and a `PipelineEditor` placeholder.
- Sidebar `currentItemChanged` signal switches the `QStackedWidget` via an
  `_item_to_index` mapping (keyed by `id(item)`).
- Subscribes to the EventBus `"completed"` event to show status-bar messages.

### 10.3 ToolPage (`tool_page.py`)

- Layout: heading → description → `ParamForm` → Run button → `ProgressPanel` → log `QTextEdit`.
- **`_ToolWorker(QThread)`**: runs `tool.run(params)` off the main thread;
  emits `finished_ok(object)` or `failed(str)`.
- **`_BridgeSignals(QObject)`**: thread-safe bridge — EventBus callbacks (called
  from the worker thread) emit Qt signals that are delivered to main-thread slots.
- Before each run the page subscribes to EventBus `progress` / `completed` /
  `log` / `error` events; after the run it unsubscribes.
- Error messages are appended to the log in red via `QTextCharFormat`.

### 10.4 GUI Rules

- Tool execution runs in a `QThread` — GUI never blocks.
- `ToolPage` uses `ParamForm` widget which auto-generates fields from `define_parameters()` schema.
- If a tool provides a `gui_panel.py` widget, it is embedded below the auto-form.
- All GUI ↔ tool communication goes through `EventBus` and Qt signals — no direct method calls on running tools.

---

## 11 · Git & CI Conventions

### Branching

- `main` — stable, all CI green, deployable.
- `develop` — integration branch, PRs merge here first.
- `feature/<tool-name>` or `feature/<description>` — short-lived feature branches.
- `fix/<description>` — bugfix branches.

### Commit Messages

Follow **Conventional Commits**:

```
feat(frame-extractor): add AVIF output support
fix(pipeline): validate port compatibility before run
refactor(core): extract EventBus from Registry
test(image-resizer): add edge-case tests for non-square input
docs: update CLAUDE.md with pipeline section
chore(ci): add mypy to GitHub Actions workflow
```

### CI Pipeline (`.github/workflows/ci.yml`)

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra dev
      - run: uv run ruff check src/ tests/
      - run: uv run ruff format --check src/ tests/
      - run: uv run mypy src/
      - run: uv run pytest --cov=game_toolbox --cov-fail-under=80
```

---

## 12 · Claude Task Rules

When working on this project, Claude must:

### Always

- Read this file before starting any task.
- Follow the repository layout exactly — do not invent new top-level directories.
- Put business logic in `logic.py`, wiring in `tool.py`, GUI in `gui_panel.py`.
- Write Google-style docstrings on every public class and function.
- Add full type annotations to every function signature and class attribute.
- Write unit tests alongside every new feature or tool.
- Use `uv run` to execute all commands — never bare `python`, `pip`, or `pytest`.
- Emit progress through `EventBus`, not `print()`.
- Use `Path` objects (from `pathlib`), never raw string paths.
- Use `dataclass` or `frozen=True` dataclass for value objects.
- Validate inputs in `validate()` and raise `ToolError` / `ValidationError` for bad input.

### Never

- Put GUI imports inside `core/` or `tools/*/logic.py`.
- Create deep inheritance hierarchies (max: ABC → one concrete class).
- Use mutable default arguments, global mutable state, or `type: ignore` without justification.
- Skip type annotations or docstrings for public APIs.
- Commit code that fails `ruff check`, `ruff format --check`, or `mypy --strict`.
- Merge without tests passing and coverage ≥ 80 %.
- Use `print()` for user-facing output — use `logging` or `EventBus`.
- Hardcode file paths, magic numbers, or format-specific logic outside the relevant tool.

### When adding a new tool

1. Copy the structure from an existing tool folder.
2. Implement all `BaseTool` abstract methods.
3. Keep `_do_execute` free of GUI code.
4. Declare `input_types` / `output_types` for pipeline compatibility.
5. Write ≥ 3 test cases: happy path, edge case, error case.
6. Add a `README.md` inside the tool folder describing usage.
7. Add a CLI sub-command in `cli/main.py` following the existing pattern.
8. Update documentation:
   - `README.md` — add the tool to the "Available Tools" section (CLI usage, options table, library usage, link to tool README).
   - `docs/api.md` — add the tool to the package structure tree and add full API docs (logic functions, tool class, parameters, usage example).
   - `CLAUDE.md` — add the tool to the repository layout tree (section 3), the GUI sidebar tree (section 10), and update any relevant datatypes references.
9. Run `uv run ruff check && uv run mypy src/ && uv run pytest` before considering the task done.

### When modifying core/

1. Ensure backward compatibility — existing tools must not break.
2. Add integration tests in top-level `tests/`.
3. Update this file if the architecture changes.

---

## 13 · Quick-Start for Development

```bash
# Clone (already done)
cd game-toolbox

# Install dependencies
uv sync --extra dev

# Run the GUI
uv run game-toolbox-gui

# Run tools via CLI
uv run game-toolbox frame-extractor video.mp4 --interval 100 --format webp
uv run game-toolbox image-resizer sprites/ -m fit -W 256 -H 256

# Run all quality checks
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest --cov=game_toolbox --cov-report=term-missing
```
