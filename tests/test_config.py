"""config.toml reading/writing and the CONFIG tab's ConfigEditor."""

import tomllib

from olhclient.config import Config, read_values, write_values
from olhclient.core.config_editor import ConfigEditor

EXAMPLE = '''# my settings
base_url = "http://127.0.0.1:27003"   # local server
poll_interval = 5
something_else = "kept"

[future]
x = 1
'''


def test_write_keeps_comments_and_unknown_keys(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(EXAMPLE)
    write_values(path, {"base_url": "https://host:1/", "verify_tls": False}, {"poll_interval"})
    text = path.read_text()
    assert '# my settings\nbase_url = "https://host:1/"   # local server\n' in text
    assert "poll_interval" not in text
    data = tomllib.loads(text)
    assert data == {"base_url": "https://host:1/", "something_else": "kept", "verify_tls": False,
                    "future": {"x": 1}}
    assert text.index("verify_tls") < text.index("[future]")  # new keys stay top level


def test_write_creates_file_and_escapes(tmp_path):
    path = tmp_path / "sub" / "config.toml"
    write_values(path, {"username": 'a"b\\c', "poll_interval": 2.5, "check_updates": True})
    assert read_values(path) == {"username": 'a"b\\c', "poll_interval": 2.5, "check_updates": True}
    write_values(path, {"poll_interval": 3.0})
    assert "poll_interval = 3\n" in path.read_text()


def test_editor_shows_file_values_and_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(EXAMPLE)
    editor = ConfigEditor(path)
    assert editor.values["base_url"] == "http://127.0.0.1:27003"
    assert editor.values["poll_interval"] == "5"
    assert editor.values["start_minimized"] is False
    assert editor.explicit["base_url"] and not editor.explicit["origin"]
    assert {f["key"] for f in editor.fields} == set(Config.__dataclass_fields__)
    assert not editor.dirty


def test_editor_save_apply_and_restart_needed(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(EXAMPLE)
    applied = []
    editor = ConfigEditor(path, apply=applied.append)
    editor.setValue("poll_interval", "2")
    editor.setValue("start_minimized", True)
    assert editor.dirty
    assert editor.save()
    assert applied[-1].poll_interval == 2 and applied[-1].start_minimized
    assert not editor.restartNeeded  # neither needs a restart
    editor.useDefault("base_url")
    editor.setValue("origin", "https://127.0.0.1:27003")
    assert editor.save()
    assert editor.restartNeeded
    data = read_values(path)
    assert "base_url" not in data and data["origin"] == "https://127.0.0.1:27003"
    assert data["something_else"] == "kept"
    assert editor.saved["base_url"] == "http://127.0.0.1:27003"


def test_editor_rejects_bad_interval_and_reverts(tmp_path):
    path = tmp_path / "config.toml"
    editor = ConfigEditor(path)
    editor.setValue("poll_interval", "soon")
    assert "poll_interval" in editor.errors
    assert not editor.save()
    assert not path.exists()
    editor.revert()
    assert not editor.dirty and editor.values["poll_interval"] == "5"


def test_editor_reports_unreadable_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("base_url = ")
    editor = ConfigEditor(path)
    assert editor.loadError
    assert editor.values["base_url"] == "http://127.0.0.1:27003"


def test_editor_without_openlinkhub_hides_connection_settings(tmp_path):
    editor = ConfigEditor(tmp_path / "config.toml", openlinkhub=False)
    assert [f["key"] for f in editor.fields] == ["poll_interval", "check_updates", "start_minimized"]
