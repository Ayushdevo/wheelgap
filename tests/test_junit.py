import json
from xml.etree import ElementTree as ET

import pytest

from wheelgap.check import Row, Status
from wheelgap.cli import main
from wheelgap.junit import junit_xml
from wheelgap.sources import Package
from wheelgap.targets import Target


@pytest.mark.parametrize("fail_on", ["source", "missing"])
def test_junit_statuses_and_suite_counts(fail_on):
    linux = Target(3, 13, False, "linux-x86_64")
    wasm = Target(3, 12, False, "pyodide-wasm32")
    statuses = [
        (Status.WHEEL, Status.NOT_NEEDED),
        (Status.SOURCE, Status.BUNDLED),
        (Status.MISSING, Status.MISSING),
        (Status.UNKNOWN, Status.UNKNOWN),
    ]
    rows = [Row(Package(f"pkg-{i}", "1.0"), {linux: a, wasm: b}) for i, (a, b) in enumerate(statuses)]
    suites = ET.fromstring(junit_xml(rows, [linux, wasm], fail_on)).findall("testsuite")
    assert [suite.get("name") for suite in suites] == ["3.13 linux-x86_64", "3.12 pyodide-wasm32"]
    assert [suite.get("tests") for suite in suites] == ["4", "4"]
    assert [suite.get("failures") for suite in suites] == ["3" if fail_on == "source" else "2", "2"]
    assert [suite.get("skipped") for suite in suites] == ["0", "1"]
    assert [failure.get("type") for failure in suites[0].findall(".//failure")] == (
        ["source", "missing", "unknown"] if fail_on == "source" else ["missing", "unknown"]
    )
    for suite in suites:
        for i, case in enumerate(suite.findall("testcase")):
            assert case.attrib == {"name": f"pkg-{i}", "classname": suite.get("name")}


def test_junit_empty_target_suite():
    target = Target(3, 13, False, "linux-x86_64")
    suite = ET.fromstring(junit_xml([], [target], "source")).find("testsuite")
    assert suite is not None
    assert suite.attrib == {"name": "linux-x86_64", "tests": "0", "failures": "0", "skipped": "0"}


@pytest.mark.parametrize("fail_on", ["source", "missing"])
def test_junit_reports_gap_on_only_affected_target(fail_on, tmp_path, fixtures):
    report = tmp_path / "wheelgap.xml"
    assert (
        main(
            [
                str(fixtures / "armgap"),
                "-p",
                "3.13",
                "-t",
                "linux-aarch64,musl-aarch64",
                "--glibc",
                "2.39",
                "--fail-on",
                fail_on,
                "--junit",
                str(report),
            ]
        )
        == 1
    )  # newglibc has no musllinux wheel or sdist
    suites = ET.parse(report).getroot().findall("testsuite")
    assert [suite.get("name") for suite in suites] == ["linux-aarch64", "musl-aarch64"]
    for suite, expected in zip(suites, [False, fail_on == "source"], strict=True):
        armlib = suite.find("./testcase[@name='armlib']")
        assert armlib is not None
        assert (armlib.find("failure") is not None) == expected


def test_junit_reports_platform_marker_as_skipped(tmp_path, fixtures):
    report = tmp_path / "wheelgap.xml"
    assert (
        main(
            [
                str(fixtures / "uvproj"),
                "-p",
                "3.13",
                "-t",
                "linux-x86_64,win-arm64",
                "--junit",
                str(report),
            ]
        )
        == 1
    )
    root = ET.parse(report).getroot()
    assert root.find("./testsuite[@name='linux-x86_64']/testcase[@name='winonly']/skipped") is not None
    assert root.find("./testsuite[@name='win-arm64']/testcase[@name='winonly']/failure") is not None
    assert root.find(".//testcase[@name='gitdep']") is None


@pytest.mark.parametrize("mode", [[], ["--json"], ["--markdown"], ["--quiet"]])
def test_junit_preserves_output_mode(tmp_path, fake_pypi, capsys, mode):
    args = ["nowheels", "-p", "3.13", "-t", "linux", "--exit-zero", *mode]
    assert main(args) == 0
    expected = capsys.readouterr()
    report = tmp_path / "wheelgap.xml"
    assert main([*args, "--junit", str(report)]) == 0
    assert capsys.readouterr() == expected
    assert ET.parse(report).find(".//failure") is not None


@pytest.mark.parametrize("json_mode", [False, True])
def test_junit_write_failure_returns_input_error(tmp_path, fixtures, capsys, json_mode):
    path = tmp_path / "absent" / "report.xml"
    args = [str(fixtures / "uvproj"), "-p", "3.13", "--junit", str(path)]
    assert main([*args, "--json"] if json_mode else args) == 2
    output = capsys.readouterr()
    assert "could not write JUnit report" in output.err
    if json_mode:
        assert json.loads(output.out)["error"]["type"] == "OSError"
    else:
        assert output.out == ""
