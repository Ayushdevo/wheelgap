import json

import pytest

from wheelgap.sources import SourceError, find_lockfile, load_inputs, parse_requirements


def by_name(source):
    return {p.name: p for p in source.packages}


def test_uv_lock(fixtures):
    (src,) = load_inputs([str(fixtures / "uvproj")])
    pkgs = by_name(src)
    assert src.label == "uv.lock"
    assert pkgs["demo"].skip == "editable"
    assert pkgs["gitdep"].skip == "git"
    assert pkgs["fastlib"].files == [
        "fastlib-2.0.0-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        "fastlib-2.0.0-cp313-cp313-macosx_11_0_arm64.whl",
        "fastlib-2.0.0-cp313-cp313-win_amd64.whl",
        "fastlib-2.0.0.tar.gz",
    ]
    assert pkgs["puresdist"].files == ["puresdist-1.0.tar.gz"]
    assert src.roots == [0]
    assert ("winonly", None, "sys_platform == 'win32'") in src.edges[0]
    assert ("devtool", None, None) in src.edges[0]


def test_poetry_lock(fixtures):
    (src,) = load_inputs([str(fixtures / "poetryproj" / "poetry.lock")])
    pkgs = by_name(src)
    assert pkgs["fastlib"].files == ["fastlib-2.0.0-cp313-cp313-musllinux_1_2_aarch64.whl", "fastlib-2.0.0.tar.gz"]
    assert pkgs["backport"].markers == ['python_version < "3.13"']
    assert pkgs["localpkg"].skip == "directory"


def test_pylock(fixtures):
    (src,) = load_inputs([str(fixtures / "pylockproj")])
    pkgs = by_name(src)
    assert pkgs["fastlib"].files == ["fastlib-2.0.0-cp313-abi3-manylinux_2_28_aarch64.whl"]
    assert pkgs["macpkg"].files == ["macpkg-1.0.tar.gz"]
    assert pkgs["macpkg"].markers == ["sys_platform == 'darwin'"]


def test_requirements(fixtures):
    src = parse_requirements(fixtures / "reqproj" / "requirements.txt")
    pkgs = by_name(src)
    assert pkgs["fastlib"].version == "2.0.0"
    assert pkgs["fastlib"].files is None
    assert pkgs["unpinned"].version is None
    assert pkgs["winonly"].markers == ['sys_platform == "win32"']
    assert pkgs["purewheel"].version == "3.1"  # pulled in via -r
    assert pkgs["./localpkg"].skip == "editable"
    assert len(src.packages) == 5


@pytest.mark.parametrize("input_name", ["pipenvproj", "pipenvproj/Pipfile.lock"])
def test_pipfile_lock(fixtures, input_name):
    (src,) = load_inputs([str(fixtures / input_name)])
    pkgs = by_name(src)
    assert src.label == "Pipfile.lock"
    assert len(src.packages) == 7
    assert pkgs["fastlib"].version == "2.0.0"
    assert pkgs["fastlib"].markers is None
    assert pkgs["winonly"].version == "311"
    assert pkgs["winonly"].markers == ["sys_platform == 'win32'"]
    assert pkgs["purewheel"].version == "3.1"
    assert pkgs["purewheel"].markers == ["python_version >= '3.11'"]
    assert pkgs["gitdep"].skip == "git"
    assert pkgs["localpkg"].skip == "path"
    assert pkgs["archivepkg"].skip == "file"
    assert pkgs["editablepkg"].skip == "editable"
    assert all(p.origin == "Pipfile.lock" for p in src.packages)
    assert all(p.files is None for p in src.packages)
    assert all(pkgs[name].skip is None for name in ("fastlib", "winonly", "purewheel"))
    assert all(pkgs[name].version is None for name in ("gitdep", "localpkg", "archivepkg", "editablepkg"))


@pytest.mark.parametrize("section", ["default", "develop"])
def test_pipfile_lock_with_one_section(tmp_path, section):
    path = tmp_path / "Pipfile.lock"
    path.write_text(json.dumps({section: {"purewheel": {"version": "==3.1"}}}), encoding="utf-8")
    (src,) = load_inputs([str(path)])
    assert [(p.name, p.version) for p in src.packages] == [("purewheel", "3.1")]


def test_empty_pipfile_lock(tmp_path):
    path = tmp_path / "Pipfile.lock"
    path.write_text("{}", encoding="utf-8")
    (src,) = load_inputs([str(tmp_path)])
    assert src.label == "Pipfile.lock"
    assert src.packages == []


def test_adhoc_specs():
    (src,) = load_inputs(["numpy==2.3.4", "psycopg2"])
    assert [(p.name, p.version) for p in src.packages] == [("numpy", "2.3.4"), ("psycopg2", None)]


def test_wildcard_pin_is_not_a_pin():
    (src,) = load_inputs(["numpy==2.*"])
    assert src.packages[0].version is None


def test_missing_file_errors():
    with pytest.raises(SourceError, match="no such file"):
        load_inputs(["nope/uv.lock"])


def test_no_lockfile_in_dir(fixtures):
    with pytest.raises(SourceError, match="no lockfile found"):
        find_lockfile(fixtures / "empty")


def test_bad_requirement():
    with pytest.raises(SourceError):
        load_inputs(["not a valid ! spec"])
