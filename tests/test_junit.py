from xml.etree import ElementTree as ET

import pytest

from wheelgap.check import Row, Status
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
