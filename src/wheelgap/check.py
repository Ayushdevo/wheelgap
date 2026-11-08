"""Decide, per package and target, whether a prebuilt wheel exists."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from packaging.markers import InvalidMarker, Marker, UndefinedComparison, UndefinedEnvironmentName
from packaging.tags import Tag
from packaging.utils import InvalidWheelFilename, canonicalize_name, parse_wheel_filename

from .sources import Edge, Package, Source
from .targets import Target


class Status(StrEnum):
    WHEEL = "wheel"  # a compatible wheel exists
    SOURCE = "source"  # no compatible wheel, but an sdist: installers will build it
    MISSING = "missing"  # no compatible wheel and no sdist: install fails
    UNKNOWN = "unknown"  # couldn't look the package up
    NOT_NEEDED = "n/a"  # markers say this package isn't installed on the target


SDIST_SUFFIXES = (".tar.gz", ".zip", ".tar.bz2", ".tgz", ".tar.xz")


@dataclass
class Row:
    package: Package
    results: dict[Target, Status] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(s in (Status.WHEEL, Status.NOT_NEEDED) for s in self.results.values())

    @property
    def needed(self) -> bool:
        return any(s is not Status.NOT_NEEDED for s in self.results.values())


def wheel_tags(files: list[str]) -> list[frozenset[Tag]]:
    out = []
    for f in files:
        if not f.endswith(".whl"):
            continue
        try:
            out.append(parse_wheel_filename(f)[3])
        except InvalidWheelFilename:
            continue
    return out


def has_sdist(files: list[str]) -> bool:
    return any(f.endswith(SDIST_SUFFIXES) for f in files)


def status_for(files: list[str] | None, target: Target, _wheels: list[frozenset[Tag]] | None = None) -> Status:
    if files is None:
        return Status.UNKNOWN
    wheels = _wheels if _wheels is not None else wheel_tags(files)
    if any(target.accepts(t) for t in wheels):
        return Status.WHEEL
    return Status.SOURCE if has_sdist(files) else Status.MISSING


_marker_cache: dict[str, Marker | None] = {}


def marker_holds(marker: str | None, target: Target) -> bool:
    if not marker:
        return True
    if marker not in _marker_cache:
        try:
            _marker_cache[marker] = Marker(marker)
        except InvalidMarker:
            _marker_cache[marker] = None
    m = _marker_cache[marker]
    if m is None:
        return True  # can't parse it: assume the package is needed rather than hide a gap
    try:
        return m.evaluate(target.marker_env)
    except (UndefinedComparison, UndefinedEnvironmentName):
        return True


def reachable(source: Source, target: Target) -> set[int]:
    """Indexes of packages installed on `target`, walking the lockfile graph from its roots."""
    by_name: dict[str, list[int]] = {}
    for i, p in enumerate(source.packages):
        by_name.setdefault(p.key, []).append(i)

    def follow(edge: Edge) -> list[int]:
        name, version, marker = edge
        if not marker_holds(marker, target):
            return []
        candidates = by_name.get(canonicalize_name(name), [])
        if version is not None:
            candidates = [i for i in candidates if source.packages[i].version == version] or candidates
        return candidates

    seen = set(source.roots)
    stack = list(source.roots)
    for edge in source.root_edges:
        stack.extend(follow(edge))
    while stack:
        i = stack.pop()
        seen.add(i)
        for edge in (source.edges or {}).get(i, []):
            for j in follow(edge):
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
    return seen


def applies(pkg: Package, target: Target) -> bool:
    return pkg.markers is None or any(marker_holds(m, target) for m in pkg.markers)


def check(sources: list[Source], targets: list[Target]) -> list[Row]:
    rows = []
    for source in sources:
        installed = {t: reachable(source, t) for t in targets} if source.edges is not None else None
        for i, pkg in enumerate(source.packages):
            if pkg.skip:
                continue
            files = None if pkg.error else pkg.files
            wheels = wheel_tags(files) if files is not None else []
            row = Row(pkg)
            for t in targets:
                needed = i in installed[t] if installed is not None else applies(pkg, t)
                row.results[t] = status_for(files, t, wheels) if needed else Status.NOT_NEEDED
            rows.append(row)
    return rows
