import json
import sys
import sysconfig

import pytest

from wheelgap import cli
from wheelgap.cli import main
from wheelgap.targets import ALIASES, PLATFORMS


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_gaps_exit_1(capsys, fixtures):
    code, out, _ = run(capsys, str(fixtures / "uvproj"), "-p", "3.13", "-t", "linux-x86_64,musl-aarch64")
    assert code == 1
    assert "fastlib" in out and "● source" in out
    assert "purewheel" not in out  # fine everywhere, so hidden
    assert "have gaps" in out
    assert "skipped 2 non-index packages" in out
    assert "\033[" not in out  # no colour when not a TTY


def test_docker_platform_names_on_cli(capsys, fixtures):
    code, out, err = run(
        capsys,
        str(fixtures / "uvproj"),
        "-p",
        "3.13",
        "-t",
        "linux/amd64,linux/arm64,linux/arm64/v8",
        "--json",
    )
    assert code == 1
    assert not err
    data = json.loads(out)
    assert [target["label"] for target in data["targets"]] == ["linux-x86_64", "linux-aarch64"]


def test_exit_zero_and_all(capsys, fixtures):
    code, out, _ = run(capsys, str(fixtures / "uvproj"), "-p", "3.13", "--all", "--exit-zero")
    assert code == 0
    assert "purewheel" in out and "–" in out


def test_clean_exit_0(capsys, fixtures):
    code, out, _ = run(capsys, str(fixtures / "pylockproj"), "-p", "3.13", "-t", "linux-aarch64")
    assert code == 0
    assert "The 1 package has a wheel for 1 target." in out


def test_json(capsys, fixtures):
    code, out, _ = run(capsys, str(fixtures / "uvproj"), "-p", "3.13,3.14t", "-t", "win-amd64", "--json")
    assert code == 1
    data = json.loads(out)
    assert [t["label"] for t in data["targets"]] == ["3.13 win-amd64", "3.14t win-amd64"]
    fastlib = next(p for p in data["packages"] if p["name"] == "fastlib")
    assert fastlib["results"] == {"3.13 win-amd64": "wheel", "3.14t win-amd64": "source"}
    assert {"name": "gitdep", "reason": "git"} in data["skipped"]
    assert data["summary"]["with_gaps"] >= 1


def test_color_always(capsys, fixtures):
    _, out, _ = run(capsys, str(fixtures / "uvproj"), "-p", "3.13", "--color", "always")
    assert "\033[33m" in out


def test_adhoc_packages(capsys, fake_pypi):
    code, out, _ = run(capsys, "nowheels", "purewheel", "-p", "3.13", "-t", "linux")
    assert code == 1
    assert "nowheels" in out and "0.9" in out


@pytest.mark.parametrize("input_name", ["pipenvproj", "pipenvproj/Pipfile.lock"])
def test_pipfile_lock_json(capsys, fixtures, fake_pypi, input_name):
    code, out, err = run(
        capsys, str(fixtures / input_name), "-p", "3.13", "-t", "linux-x86_64,musl-aarch64,win-amd64", "--json"
    )
    assert code == 1
    assert not err
    data = json.loads(out)
    assert data["sources"] == ["Pipfile.lock"]
    packages = {p["name"]: p for p in data["packages"]}
    assert packages["fastlib"]["version"] == "2.0.0"
    assert packages["fastlib"]["results"] == {"linux-x86_64": "wheel", "musl-aarch64": "source", "win-amd64": "source"}
    assert packages["winonly"]["results"] == {"linux-x86_64": "n/a", "musl-aarch64": "n/a", "win-amd64": "wheel"}
    assert packages["purewheel"]["results"] == {"linux-x86_64": "wheel", "musl-aarch64": "wheel", "win-amd64": "wheel"}
    assert data["skipped"] == [
        {"name": "gitdep", "reason": "git"},
        {"name": "localpkg", "reason": "path"},
        {"name": "archivepkg", "reason": "file"},
        {"name": "editablepkg", "reason": "editable"},
    ]
    assert sorted(fake_pypi) == [
        "https://pypi.org/pypi/fastlib/2.0.0/json",
        "https://pypi.org/pypi/purewheel/3.1/json",
        "https://pypi.org/pypi/winonly/311/json",
    ]


@pytest.mark.parametrize("input_name", ["pdmproj", "pdmproj/pdm.lock"])
def test_pdm_lock_json(capsys, fixtures, fake_pypi, input_name):
    code, out, err = run(capsys, str(fixtures / input_name), "-p", "3.13", "-t", "linux-x86_64,musl-aarch64", "--json")
    assert code == 1
    assert not err
    data = json.loads(out)
    assert data["sources"] == ["pdm.lock"]
    packages = {p["name"]: p for p in data["packages"]}
    assert packages["fastlib"]["results"] == {"linux-x86_64": "source", "musl-aarch64": "wheel"}
    assert "backport" not in packages  # marker excludes it on 3.13
    assert data["skipped"] == [{"name": "localpkg", "reason": "path"}]
    assert not fake_pypi


def test_pdm_lock_entry_without_files_is_looked_up(capsys, fake_pypi, tmp_path):
    (tmp_path / "pdm.lock").write_text(
        '[[package]]\nname = "purewheel"\nversion = "3.1"\n\n'
        '[[package]]\nname = "nowheels"\nversion = "0.9"\nfiles = []\n',
        encoding="utf-8",
    )
    code, out, _ = run(capsys, str(tmp_path), "-p", "3.13", "-t", "linux-x86_64", "--json")
    packages = {p["name"]: p for p in json.loads(out)["packages"]}
    assert packages["purewheel"]["results"] == {"linux-x86_64": "wheel"}  # filled in from PyPI
    assert packages["nowheels"]["results"] == {"linux-x86_64": "missing"}  # an empty list is taken as recorded
    assert fake_pypi == ["https://pypi.org/pypi/purewheel/3.1/json"]
    assert code == 1


def test_pdm_lock_marker_on_older_python(capsys, fixtures, fake_pypi):
    code, out, err = run(capsys, str(fixtures / "pdmproj"), "-p", "3.12", "-t", "linux-x86_64", "--json")
    assert code == 1
    assert not err
    packages = {p["name"]: p for p in json.loads(out)["packages"]}
    assert packages["backport"]["results"] == {"linux-x86_64": "source"}
    assert not fake_pypi


def test_pipfile_lock_in_current_directory(capsys, fixtures, fake_pypi, monkeypatch):
    monkeypatch.chdir(fixtures / "pipenvproj")
    code, out, err = run(capsys, "-p", "3.13", "-t", "linux-x86_64")
    assert code == 0
    assert not err
    assert "skipped 4 non-index packages" in out
    assert "editablepkg (editable)" in out
    assert "All 2 packages have a wheel for 1 target." in out


def test_malformed_pipfile_lock_exits_2(capsys, tmp_path, fake_pypi):
    path = tmp_path / "Pipfile.lock"
    path.write_text("{invalid", encoding="utf-8")
    code, _, err = run(capsys, str(path))
    assert code == 2
    assert "JSONDecodeError" in err
    assert not fake_pypi


def test_errors_exit_2(capsys, fixtures):
    code, _, err = run(capsys, str(fixtures / "empty"))
    assert code == 2 and "no lockfile found" in err
    code, _, err = run(capsys, str(fixtures / "uvproj"), "-t", "solaris")
    assert code == 2 and "unknown target" in err
    code, _, err = run(capsys, str(fixtures / "uvproj"), "-p", "four")
    assert code == 2


def test_list_targets(capsys):
    code, out, err = run(capsys, "--list-targets")
    assert code == 0 and not err
    lines = out.splitlines()
    assert lines[0].split() == ["name", "aliases", "accepts"]
    alpine = next(line for line in lines if line.startswith("musl-x86_64 "))
    assert "alpine" in alpine and "musl <= 1.2" in alpine
    assert "linux/arm64" in out


def test_list_targets_json_includes_every_platform_and_alias(capsys):
    code, out, err = run(capsys, "--list-targets", "--json")
    assert code == 0 and not err
    rows = json.loads(out)
    assert [row["name"] for row in rows] == list(PLATFORMS)
    assert {alias: row["name"] for row in rows for alias in row["aliases"]} == ALIASES
    by_name = {row["name"]: row for row in rows}
    assert "glibc <= 2.36" in by_name["linux-x86_64"]["accepts"]
    assert "macOS <= 14.0" in by_name["macos-arm64"]["accepts"]
    assert by_name["pyodide"]["accepts"] == "pyodide wasm32"


def test_list_targets_respects_compatibility_overrides(capsys):
    flags = ("--list-targets", "--glibc", "2.28", "--musl", "1.1", "--macos", "13.0")
    code, out, err = run(capsys, *flags)
    assert code == 0 and not err
    assert "glibc <= 2.28" in out

    code, out, err = run(capsys, *flags, "--json")
    assert code == 0 and not err
    by_name = {row["name"]: row["accepts"] for row in json.loads(out)}
    assert "glibc <= 2.28" in by_name["linux-aarch64"]
    assert "musl <= 1.1" in by_name["musl-aarch64"]
    assert "macOS <= 13.0" in by_name["macos-x86_64"]


def test_list_targets_rejects_invalid_compatibility_version(capsys):
    code, out, err = run(capsys, "--list-targets", "--glibc", "bad")
    assert code == 2 and not out
    assert "can't parse glibc version" in err


def test_defaults_from_pyproject(capsys, fixtures):
    code, out, _ = run(capsys, str(fixtures / "configproj"), "--json")
    assert code == 1
    assert [t["label"] for t in json.loads(out)["targets"]] == ["3.13 win-amd64", "3.14t win-amd64"]


def test_flags_beat_pyproject(capsys, fixtures):
    _, out, _ = run(capsys, str(fixtures / "configproj"), "-p", "3.13", "-t", "linux-x86_64", "--json")
    assert [t["label"] for t in json.loads(out)["targets"]] == ["linux-x86_64"]


def test_bad_pyproject_exit_2(capsys, fixtures, tmp_path):
    (tmp_path / "uv.lock").write_bytes((fixtures / "uvproj" / "uv.lock").read_bytes())
    (tmp_path / "pyproject.toml").write_text("[tool.wheelgap]\nglibc = 2.31\n")
    code, _, err = run(capsys, str(tmp_path))
    assert code == 2 and "glibc must be a string" in err


def test_running_python_reports_freethreaded(monkeypatch):
    monkeypatch.setattr(sysconfig, "get_config_var", lambda name: 1 if name == "Py_GIL_DISABLED" else None)
    assert cli.running_python() == f"{sys.version_info.major}.{sys.version_info.minor}t"


@pytest.mark.skipif(not sysconfig.get_config_var("Py_GIL_DISABLED"), reason="needs a free-threaded build")
def test_default_python_on_freethreaded_build(capsys, fixtures):
    code = main([str(fixtures / "pylockproj"), "-t", "linux-aarch64", "--json"])
    assert code in (0, 1)
    assert json.loads(capsys.readouterr().out)["targets"][0]["python"].endswith("t")


def project_with_lock(tmp_path, fixtures):
    (tmp_path / "uv.lock").write_bytes((fixtures / "uvproj" / "uv.lock").read_bytes())
    return tmp_path


def test_python_version_file_sets_default(capsys, fixtures, tmp_path):
    project = project_with_lock(tmp_path, fixtures)
    (project / ".python-version").write_text("3.14t\n", encoding="utf-8")
    code, out, err = run(capsys, str(project), "-t", "win-amd64", "--json")
    assert code == 1 and not err
    assert [t["python"] for t in json.loads(out)["targets"]] == ["3.14t"]


def test_python_version_file_several_lines_and_patch_versions(capsys, fixtures, tmp_path):
    project = project_with_lock(tmp_path, fixtures)
    (project / ".python-version").write_text("3.13.1\n# both builds\n\n3.14t\n", encoding="utf-8")
    _, out, _ = run(capsys, str(project), "-t", "win-amd64", "--json")
    assert [t["python"] for t in json.loads(out)["targets"]] == ["3.13", "3.14t"]


def test_flags_beat_python_version_file(capsys, fixtures, tmp_path):
    project = project_with_lock(tmp_path, fixtures)
    (project / ".python-version").write_text("3.14t\n", encoding="utf-8")
    _, out, _ = run(capsys, str(project), "-p", "3.12", "-t", "win-amd64", "--json")
    assert [t["python"] for t in json.loads(out)["targets"]] == ["3.12"]


def test_pyproject_beats_python_version_file(capsys, fixtures, tmp_path):
    project = project_with_lock(tmp_path, fixtures)
    (project / ".python-version").write_text("3.14t\n", encoding="utf-8")
    (project / "pyproject.toml").write_text('[tool.wheelgap]\npython = ["3.12"]\n', encoding="utf-8")
    _, out, _ = run(capsys, str(project), "-t", "win-amd64", "--json")
    assert [t["python"] for t in json.loads(out)["targets"]] == ["3.12"]


def test_python_version_file_skips_unusable_lines(capsys, fixtures, tmp_path):
    project = project_with_lock(tmp_path, fixtures)
    (project / ".python-version").write_text("system\npypy@3.10\n3.13\n", encoding="utf-8")
    code, out, err = run(capsys, str(project), "-t", "win-amd64", "--json")
    assert code == 1
    assert "ignoring 'system'" in err and "ignoring 'pypy@3.10'" in err
    assert [t["python"] for t in json.loads(out)["targets"]] == ["3.13"]


def test_python_version_file_with_nothing_usable_uses_running_python(capsys, fixtures, tmp_path):
    project = project_with_lock(tmp_path, fixtures)
    (project / ".python-version").write_text("system\n", encoding="utf-8")
    _, out, _ = run(capsys, str(project), "-t", "win-amd64", "--json")
    assert [t["python"] for t in json.loads(out)["targets"]] == [cli.running_python()]
