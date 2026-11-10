"""Render one JUnit test suite per checked target."""

from xml.etree import ElementTree as ET

from .check import Row, Status
from .targets import Target

_FAILURES = {
    Status.SOURCE: "No compatible wheel; a source build is available",
    Status.MISSING: "No compatible wheel or source distribution",
    Status.UNKNOWN: "Wheel availability could not be checked",
}


def junit_xml(rows: list[Row], targets: list[Target], fail_on: str) -> str:
    root = ET.Element("testsuites")
    multi_py = len({target.python for target in targets}) > 1
    for target in targets:
        label = target.label(multi_py)
        suite = ET.SubElement(root, "testsuite", name=label, tests=str(len(rows)))
        failures = skipped = 0
        for row in rows:
            case = ET.SubElement(suite, "testcase", name=row.package.name, classname=label)
            status = row.results[target]
            if status == Status.NOT_NEEDED:
                ET.SubElement(case, "skipped")
                skipped += 1
            elif status in _FAILURES and not (status == Status.SOURCE and fail_on == "missing"):
                ET.SubElement(case, "failure", type=status.value, message=_FAILURES[status])
                failures += 1
        suite.set("failures", str(failures))
        suite.set("skipped", str(skipped))
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
