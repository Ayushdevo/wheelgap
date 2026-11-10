import json
from pathlib import Path

import pytest

from wheelgap.check import Status
from wheelgap.cli import main

SCHEMA = json.loads((Path(__file__).parents[1] / "docs" / "wheelgap-output.schema.json").read_text(encoding="utf-8"))
JSON_TYPES = {"array": list, "integer": int, "null": type(None), "object": dict, "string": str}


def assert_conforms(value, schema, path="$"):
    """Check the subset of draft 2020-12 used by the report schema."""
    if "$ref" in schema:
        schema = SCHEMA["$defs"][schema["$ref"].removeprefix("#/$defs/")]
    types = schema["type"]
    if isinstance(types, str):
        types = [types]
    assert type(value) in [JSON_TYPES[t] for t in types], path
    if "enum" in schema:
        assert value in schema["enum"], path
    if "minimum" in schema:
        assert value >= schema["minimum"], path
    if type(value) is list:
        for index, item in enumerate(value):
            assert_conforms(item, schema["items"], f"{path}[{index}]")
    if type(value) is dict:
        assert set(schema.get("required", [])) <= value.keys(), path
        props = schema.get("properties", {})
        for key, item in value.items():
            child = props.get(key, schema.get("additionalProperties"))
            assert child is not None, f"{path}.{key} is undocumented"
            assert_conforms(item, child, f"{path}.{key}")


@pytest.mark.parametrize(
    ("fixture", "ignore"),
    [("uvproj", "purewheel"), ("armgap", "newglibc")],
)
def test_json_dependency_report_matches_schema(fixture, ignore, fixtures, capsys):
    assert (
        main(
            [
                str(fixtures / fixture),
                "-p",
                "3.13,3.14t",
                "-t",
                "linux-aarch64,win-arm64",
                "--json",
                "--explain",
                "--ignore",
                ignore,
                "--offline",
            ]
        )
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert_conforms(report, SCHEMA)
    assert report["ignored"] == [ignore]
    assert set(SCHEMA["$defs"]["status"]["enum"]) == {status.value for status in Status}
    labels = {target["label"] for target in report["targets"]}
    assert all(set(p["results"]) == labels for p in report["packages"])


def test_bundled_and_unknown_fields_match_schema(tmp_path, fake_pypi, capsys):
    lock = tmp_path / "pyodide-lock.json"
    lock.write_text(
        json.dumps(
            {
                "info": {"abi_version": "2025_0", "python": "3.13.2", "version": "0.29.0"},
                "packages": {"fastlib": {"name": "fastlib", "version": "2.0.0"}},
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(["fastlib==2.0.0", "missingproject", "-p", "3.13", "-t", "pyodide", "--pyodide-lock", str(lock), "--json"])
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert_conforms(report, SCHEMA)
    assert report["packages"][0]["bundled"] == "2.0.0"
    assert report["packages"][1]["error"]
