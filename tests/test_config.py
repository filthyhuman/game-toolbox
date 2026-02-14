"""Integration tests for the ConfigManager."""

from __future__ import annotations

from pathlib import Path

from game_toolbox.core.config import ConfigManager


class TestConfigManagerDefaults:
    """Tests for in-memory configuration."""

    def test_get_returns_default_when_empty(self) -> None:
        """An empty config returns the provided default."""
        cfg = ConfigManager(config_dir=Path("/nonexistent"))
        assert cfg.get("theme", default="dark") == "dark"

    def test_set_global_and_get(self) -> None:
        """Values set via ``set_global`` are retrievable."""
        cfg = ConfigManager(config_dir=Path("/nonexistent"))
        cfg.set_global("language", "en")

        assert cfg.get("language") == "en"

    def test_get_returns_none_when_no_default(self) -> None:
        """Without a default, missing keys return ``None``."""
        cfg = ConfigManager(config_dir=Path("/nonexistent"))
        assert cfg.get("missing_key") is None


class TestConfigManagerToml:
    """Tests for TOML-based configuration loading."""

    def test_load_global_config(self, tmp_path: Path) -> None:
        """Global config.toml values are loaded correctly."""
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text('[ui]\ntheme = "dark"\n')

        cfg = ConfigManager(config_dir=config_dir)
        cfg.load()

        assert cfg.get("ui") == {"theme": "dark"}

    def test_load_per_tool_config(self, tmp_path: Path) -> None:
        """Per-tool TOML files override global values."""
        config_dir = tmp_path / "cfg"
        tools_dir = config_dir / "tools"
        tools_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text("quality = 80\n")
        (tools_dir / "frame_extractor.toml").write_text("quality = 95\n")

        cfg = ConfigManager(config_dir=config_dir)
        cfg.load()

        assert cfg.get("quality", tool="frame_extractor") == 95
        assert cfg.get("quality") == 80

    def test_load_missing_dir_is_silent(self, tmp_path: Path) -> None:
        """Loading from a non-existent directory does not raise."""
        cfg = ConfigManager(config_dir=tmp_path / "does_not_exist")
        cfg.load()

        assert cfg.get("anything") is None
