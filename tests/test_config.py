from pathlib import Path

from leetcode_vim.config import Config, config_path, load_config, save_config


def test_save_and_load_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))

    cfg = Config(workspace=Path("/tmp/work"), language="python", session="abc", csrf="def")
    save_config(cfg)

    loaded = load_config()
    assert loaded is not None
    assert loaded.workspace == Path('/tmp/work')
    assert loaded.language == 'python'
    assert loaded.session == 'abc'
    assert loaded.csrf == 'def'


def test_config_path_uses_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert str(config_path()).startswith(str(tmp_path / "xdg"))
