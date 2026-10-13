"""CSV reconciliation and catalogue queries; standard library only.

Build once with Catalogue.from_directory(). Queries return fresh dictionaries
so callers cannot mutate the stored catalogue. No files or services are read
after construction. Unspecified-data policies are documented in DATA.md.
"""

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from types import MappingProxyType

from .graph import AmbiguousCycleError, repair_hierarchy

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data"
SCHEMAS = {
    "bom.csv": ("parent_pn", "child_pn", "quantity"),
    "parts_master.csv": ("part_number", "revision", "description", "category", "unit_cost"),
    "service_parts.csv": ("part_number", "field_replaceable", "serial_from", "serial_to"),
}


class CatalogueDataError(ValueError):
    """Input data does not support an unambiguous catalogue."""


class PartNotFound(LookupError):
    """The normalized part is not in this machine."""


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Row:
    source: str
    values: dict[str, str]


@dataclass(frozen=True)
class Part:
    number: str
    description: str | None
    revision: str | None
    status: str
    total_quantity: int
    parents: tuple[str, ...]
    children: tuple[tuple[str, int], ...]
    # None means every serial; an empty tuple means no serial applies.
    serial_ranges: tuple[tuple[int, int], ...] | None
    available_revisions: tuple[str, ...] = ()
    has_service_record: bool = False


def normalize_part_number(value: str) -> str:
    return value.strip().upper()


def _fail(message: str, rows: list[Row]) -> None:
    locations = ", ".join(row.source for row in rows)
    raise CatalogueDataError(f"{message} ({locations})")


def _read_csv(path: Path, diagnostics: list[Diagnostic]) -> list[Row]:
    rows = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            expected = SCHEMAS[path.name]
            if (reader.fieldnames is None or len(reader.fieldnames) != len(expected)
                    or set(reader.fieldnames) != set(expected)):
                raise CatalogueDataError(f"{path.name}: expected columns {', '.join(expected)}")
            for values in reader:
                source = f"{path.name}:{reader.line_num}"
                if None in values or any(v is None for v in values.values()):
                    raise CatalogueDataError(f"{source}: row width does not match header")
                columns = ("parent_pn", "child_pn") if path.name == "bom.csv" else ("part_number",)
                for column in columns:
                    original = values[column]
                    normalized = normalize_part_number(original)
                    if not normalized:
                        raise CatalogueDataError(f"{source}: empty {column}")
                    if normalized != original:
                        diagnostics.append(Diagnostic("normalized_part_number", f"{column}: {original!r} -> {normalized}", (source,)))
                    values[column] = normalized
                rows.append(Row(source, values))
    except (OSError, UnicodeError, csv.Error) as error:
        raise CatalogueDataError(f"Cannot read {path.name}: {error}") from error
    return rows


def _quantity(rows: list[Row]) -> int:
    quantities = set()
    for row in rows:
        try:
            value = Decimal(row.values["quantity"].strip())
            if not value.is_finite() or value <= 0 or value != value.to_integral_value():
                raise ValueError
            quantities.add(int(value))
        except (InvalidOperation, ValueError, OverflowError):
            _fail("Quantity must be a finite positive integer", [row])
    if len(quantities) != 1:
        _fail("Conflicting quantities for one design relationship", rows)
    return quantities.pop()


def _master_record(rows: list[Row], diagnostics: list[Diagnostic]) -> tuple[str | None, str | None]:
    if not rows:
        return None, None
    revisions = defaultdict(list)
    for row in rows:
        revision = row.values["revision"].strip().upper()
        if not re.fullmatch(r"[A-Z]", revision):
            _fail("Revision must be a single A-Z letter", [row])
        revisions[revision].append(row)
        try:
            cost = Decimal(row.values["unit_cost"])
            if not cost.is_finite() or cost < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            diagnostics.append(Diagnostic("invalid_unused_cost", "Invalid unit_cost; not used by the required catalogue", (row.source,)))
    latest = max(revisions)
    for revision, versions in sorted(revisions.items()):
        descriptions = {row.values["description"] for row in versions}
        if len(descriptions) > 1 and revision == latest:
            _fail(f"Conflicting descriptions at selected revision {latest}", versions)
        if len(versions) > 1:
            diagnostics.append(Diagnostic("repeated_master_revision", f"Repeated master revision {revision}; selected revision is {latest}", tuple(row.source for row in versions)))
    selected = revisions[latest]
    if len({(r.values["category"], r.values["unit_cost"]) for r in selected}) > 1:
        diagnostics.append(Diagnostic("unused_master_conflict", "Selected revision differs in category/cost; required response is unambiguous", tuple(r.source for r in selected)))
    description = selected[0].values["description"]
    if not description.strip():
        diagnostics.append(Diagnostic("blank_description", "Existing master record has a blank description; preserved as supplied", tuple(r.source for r in selected)))
    if len(revisions) > 1:
        diagnostics.append(Diagnostic("selected_revision", f"Selected {latest} from {', '.join(sorted(revisions))}", tuple(r.source for r in rows)))
    return description, latest


def _service_rule(
    rows: list[Row], has_master: bool, diagnostics: list[Diagnostic]
) -> tuple[str, tuple[tuple[int, int], ...] | None]:
    flags = set()
    for row in rows:
        flag = row.values["field_replaceable"].strip().upper()
        if flag not in {"Y", "N"}:
            diagnostics.append(Diagnostic("invalid_service_flag", "Unrecognized flag is not marked Y", (row.source,)))
        flags.add(flag == "Y")
    if not has_master:
        # Service data cannot make an absent master part ready.
        if len(flags) > 1:
            diagnostics.append(Diagnostic("ignored_service_conflict", "Conflicting flags cannot override missing master status", tuple(r.source for r in rows)))
        _diagnose_unused_ranges(rows, diagnostics)
        return "missing", ()
    if len(flags) > 1:
        _fail("Conflicting service replaceability records", rows)
    if True not in flags:
        _diagnose_unused_ranges(rows, diagnostics)
        return "not_replaceable", ()

    intervals = set()
    unrestricted = False
    for row in rows:
        interval = _serial_interval(row)
        if interval is None:
            unrestricted = True
            continue
        intervals.add(interval)
    if unrestricted:
        return "ready", None
    # A union prevents duplicate/overlapping ranges from counting a part twice.
    merged = []
    for lower, upper in sorted(intervals):
        if merged and lower <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], upper))
        else:
            merged.append((lower, upper))
    return "ready", tuple(merged)


def _serial_interval(row: Row) -> tuple[int, int] | None:
    lo, hi = (row.values[field].strip() for field in ("serial_from", "serial_to"))
    if not lo and not hi:
        return None
    if not re.fullmatch(r"[0-9]+", lo) or not re.fullmatch(r"[0-9]+", hi):
        _fail("Serial range requires two nonnegative serial bounds or two blanks", [row])
    try:
        lower, upper = int(lo), int(hi)
    except ValueError:
        _fail("Serial bound exceeds supported integer parsing limits", [row])
    if lower > upper:
        _fail("Serial range lower bound exceeds upper bound", [row])
    return lower, upper


def _diagnose_unused_ranges(rows: list[Row], diagnostics: list[Diagnostic]) -> None:
    for row in rows:
        try:
            _serial_interval(row)
        except CatalogueDataError as error:
            diagnostics.append(Diagnostic("ignored_invalid_serial_range", str(error), (row.source,)))


class Catalogue:
    def __init__(self, root: str, parts: dict[str, Part], diagnostics: list[Diagnostic]):
        self.root = root
        self._parts = MappingProxyType(dict(parts))
        self.diagnostics = tuple(diagnostics)
        counts = Counter(part.status for part in parts.values())
        self._counts = {"parts": len(parts), **{s: counts[s] for s in ("ready", "missing", "not_replaceable")}}

    @classmethod
    def from_directory(cls, directory: str | Path = DEFAULT_DATA, *, root: str = "AS-40000") -> "Catalogue":
        root = normalize_part_number(root)
        if not root:
            raise CatalogueDataError("Machine root cannot be blank")
        directory = Path(directory)
        diagnostics: list[Diagnostic] = []
        tables = {name: _read_csv(directory / name, diagnostics) for name in SCHEMAS}
        relationships: dict[tuple[str, str], list[Row]] = defaultdict(list)
        raw_graph: dict[str, set[str]] = defaultdict(set)
        for row in tables["bom.csv"]:
            parent, child = row.values["parent_pn"], row.values["child_pn"]
            relationships[parent, child].append(row)
            raw_graph[parent].add(child)
        try:
            graph, removed, order = repair_hierarchy(raw_graph, root)
        except AmbiguousCycleError as error:
            locations = tuple(r.source for rows in relationships.values() for r in rows)
            raise CatalogueDataError(f"{error}. Inspect BOM relationships ({', '.join(locations)})") from error
        for parent, child in removed:
            diagnostics.append(Diagnostic("removed_upward_edge", f"{parent} -> {child}: self-containment or unavoidable rooted ancestor", tuple(r.source for r in relationships[parent, child])))
        quantities = {}
        for (parent, child), rows in sorted(relationships.items()):
            if parent not in graph:
                diagnostics.append(Diagnostic("outside_machine_relationship", f"Excluded {parent} -> {child}", tuple(r.source for r in rows)))
                continue
            if child not in graph[parent]:
                continue
            quantities[parent, child] = _quantity(rows)
            if len(rows) > 1:
                diagnostics.append(Diagnostic("duplicate_relationship", f"{parent} -> {child}: {len(rows)} rows describe one relationship", tuple(r.source for r in rows)))

        master, service = defaultdict(list), defaultdict(list)
        for filename, grouped in (("parts_master.csv", master), ("service_parts.csv", service)):
            for row in tables[filename]:
                number = row.values["part_number"]
                if number in graph:
                    grouped[number].append(row)
                else:
                    diagnostics.append(Diagnostic("outside_machine_record", f"Excluded metadata for {number}", (row.source,)))

        totals = dict.fromkeys(graph, 0)
        totals[root] = 1
        parents: dict[str, list[str]] = {p: [] for p in graph}
        for parent in order:
            for child in sorted(graph[parent]):
                totals[child] += totals[parent] * quantities[parent, child]
                parents[child].append(parent)
        parts = {}
        for number in sorted(graph):
            description, revision = _master_record(master[number], diagnostics)
            status, intervals = _service_rule(service[number], bool(master[number]), diagnostics)
            if len(service[number]) > 1:
                diagnostics.append(Diagnostic("repeated_service_part", f"Reconciled {len(service[number])} service rows for {number}", tuple(r.source for r in service[number])))
            parts[number] = Part(number, description, revision, status, totals[number],
                                 tuple(sorted(parents[number])),
                                 tuple((c, quantities[number, c]) for c in sorted(graph[number])), intervals,
                                 tuple(sorted({r.values["revision"].strip().upper() for r in master[number]})),
                                 bool(service[number]))
        return cls(root, parts, diagnostics)

    def _lookup(self, number: str) -> Part:
        normalized = normalize_part_number(number)
        try:
            return self._parts[normalized]
        except KeyError:
            raise PartNotFound(normalized) from None

    def validation(self) -> dict:
        return dict(self._counts)

    def part(self, number: str) -> dict:
        part = self._lookup(number)
        return {
            "part_number": part.number, "description": part.description,
            "revision": part.revision, "status": part.status,
            "total_quantity": part.total_quantity, "parents": list(part.parents),
            "children": [{"part_number": c, "quantity": q} for c, q in part.children],
        }

    def paths(self, number: str) -> dict:
        part = self._lookup(number)
        # Walk backward from the target so unrelated branches are not explored.
        # Iterative traversal also works for graphs deeper than Python's call stack.
        pending = [(part.number, (part.number,))]
        paths = []
        while pending:
            current, reverse_path = pending.pop()
            if current == self.root:
                paths.append(list(reversed(reverse_path)))
            else:
                pending.extend((parent, reverse_path + (parent,)) for parent in self._parts[current].parents)
        return {"part_number": part.number, "paths": sorted(paths)}

    def serial(self, serial: int) -> dict:
        if type(serial) is not int or serial < 0:
            raise ValueError("Serial must be a nonnegative integer")
        applicable = sum(
            part.status == "ready" and (part.serial_ranges is None or any(lo <= serial <= hi for lo, hi in part.serial_ranges))
            for part in self._parts.values()
        )
        return {"serial": serial, "applicable_parts": applicable}

    def search(self, query: str, limit: int = 50) -> dict:
        """Optional demo search; never widens membership beyond this machine."""
        query = query.strip()
        needle = query.casefold()
        matches = [p for p in self._parts.values()
                   if needle in p.number.casefold() or needle in (p.description or "").casefold()]
        matches.sort(key=lambda p: (p.number.casefold() != needle,
                                   not p.number.casefold().startswith(needle), p.number))
        return {"query": query, "total": len(matches), "limit": limit, "parts": [
            {"part_number": p.number, "description": p.description, "status": p.status}
            for p in matches[:limit]
        ]}

    def explain(self, number: str, serial: int | None = None) -> dict:
        """Optional explanations derived from the same records as required queries."""
        part = self._lookup(number)
        if serial is not None and (type(serial) is not int or serial < 0):
            raise ValueError("Serial must be a nonnegative integer")
        if part.status == "missing":
            status_reason = "In the machine BOM, but absent from the parts master. Service records cannot override missing status."
        elif part.status == "ready":
            status_reason = "Present in the parts master and marked Y in the service list. Check the machine serial before ordering."
        elif not part.has_service_record:
            status_reason = "Present in the parts master, but has no service-list record marking it Y."
        else:
            status_reason = "Present in the parts master, but its service records are not marked Y."
        revision_reason = (f"Selected {part.revision}, the highest letter among {', '.join(part.available_revisions)}."
                           if part.revision else "No master record, so description and revision are unknown.")
        terms = []
        phrases = []
        for parent in part.parents:
            assembly = self._parts[parent]
            per_parent = dict(assembly.children)[part.number]
            contribution = assembly.total_quantity * per_parent
            terms.append({"parent": parent, "assembly_occurrences": assembly.total_quantity,
                          "per_parent": per_parent, "contribution": contribution})
            noun = "assembly" if assembly.total_quantity == 1 else "assemblies"
            phrases.append(f"{contribution} directly in {self.root}" if parent == self.root else
                           f"{assembly.total_quantity} {parent} {noun} × {per_parent} each")
        quantity_reason = ("The machine root occurs once." if part.number == self.root else
                           " + ".join(phrases) + f" = {part.total_quantity}.")
        if len(terms) > 4:
            quantity_reason = (" + ".join(str(term["contribution"]) for term in terms)
                               + f" = {part.total_quantity} across {len(terms)} parent relationships. "
                               + "Expand the table for each multiplication.")
        compatibility = None
        if serial is not None:
            applicable = part.status == "ready" and (part.serial_ranges is None or
                         any(lo <= serial <= hi for lo, hi in part.serial_ranges))
            if part.status != "ready":
                reason = f"Not applicable: status is {part.status}; serial matching only includes ready parts."
            elif part.serial_ranges is None:
                reason = "Applicable: no serial restriction is recorded, so this ready part fits every accepted serial."
            else:
                ranges = ", ".join(f"{lo}–{hi}" for lo, hi in part.serial_ranges)
                reason = (f"Applicable: {serial} falls within {ranges} (both endpoints included)." if applicable else
                          f"Not applicable: {serial} falls outside {ranges} (both endpoints included).")
            compatibility = {"serial": serial, "applicable": applicable, "reason": reason}
        return {"part_number": part.number,
                "revision": {"selected": part.revision, "available": list(part.available_revisions), "reason": revision_reason},
                "status": {"value": part.status, "reason": status_reason},
                "quantity": {"total": part.total_quantity, "terms": terms, "reason": quantity_reason},
                "compatibility": compatibility}

    def quality(self) -> dict:
        counts = Counter(d.code for d in self.diagnostics)
        return {"root": self.root, "validation": self.validation(),
                "normalized_cells": counts["normalized_part_number"],
                "duplicate_rows_ignored": sum(len(d.sources) - 1 for d in self.diagnostics if d.code == "duplicate_relationship"),
                "outside_relationships": counts["outside_machine_relationship"],
                "removed_relationships": [{"reason": d.message, "sources": list(d.sources)}
                                          for d in self.diagnostics if d.code == "removed_upward_edge"],
                "multiple_revision_parts": counts["selected_revision"],
                "diagnostic_counts": dict(sorted(counts.items()))}
