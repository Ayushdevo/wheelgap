import json

import pytest

from wheelgap.cli import main


def test_ignore_only_gap_keeps_result_and_exits_zero(capsys, fake_pypi):
    assert main(["nowheels", "-p", "3.13", "-t", "linux", "--ignore", "NoWheels", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["packages"][0]["ignored"] is True
    assert report["packages"][0]["results"] == {"linux-x86_64": "source"}


def test_ignore_normalizes_separators(capsys, monkeypatch):
    from wheelgap import pypi

    monkeypatch.setattr(
        pypi,
        "fetch_json",
        lambda *a, **kw: {
            "info": {"version": "1"},
            "urls": [{"filename": "my_pkg-1.tar.gz"}],
        },
    )
    assert main(["my_pkg==1", "-p", "3.13", "-t", "linux", "--ignore", "MY.PKG"]) == 0
    assert "ignored: my_pkg" in capsys.readouterr().out


@pytest.mark.parametrize("mode", [[], ["--quiet"], ["--markdown"]])
def test_ignore_lists_accepted_gaps_in_all_text_modes(capsys, fake_pypi, mode):
    assert main(["nowheels", "winonly", "-p", "3.13", "-t", "linux", "--ignore", " nowheels,winonly ", *mode]) == 0
    out = capsys.readouterr().out
    assert "ignored:" in out and "nowheels" in out and "winonly" in out
    assert "Source builds are allowed" not in out


def test_unignored_gap_still_fails(capsys, fake_pypi):
    assert main(["nowheels", "winonly", "-p", "3.13", "-t", "linux", "--ignore", "nowheels"]) == 1


def test_repeatable_ignore(capsys, fake_pypi):
    assert (
        main(["nowheels", "winonly", "-p", "3.13", "-t", "linux", "--ignore", "nowheels", "--ignore", "winonly"]) == 0
    )


def test_cli_ignore_overrides_config(capsys, fake_pypi, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[tool.wheelgap]\nignore = ["nowheels"]\n', encoding="utf-8")
    args = ["nowheels", "-p", "3.13", "-t", "linux"]
    assert main(args) == 0
    assert main([*args, "--ignore", "winonly"]) == 1
    assert main([*args, "--ignore", ""]) == 1


def test_invalid_ignore_config(capsys, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.wheelgap]\nignore = [123]\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 2
    assert "ignore must be a list of strings" in capsys.readouterr().err


def test_ignore_and_fail_on_missing(capsys, fake_pypi):
    assert (
        main(["nowheels", "winonly", "-p", "3.13", "-t", "linux", "--fail-on", "missing", "--ignore", "winonly"]) == 0
    )
    assert "Source builds are allowed" in capsys.readouterr().out
