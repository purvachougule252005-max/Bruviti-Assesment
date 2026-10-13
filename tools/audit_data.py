"""Phase 1 evidence collection only; not the production catalogue engine.

Run from any directory with Python 3.10+: python tools/audit_data.py
Writes audit/findings.json. Reads source CSVs without modifying them.
"""
from collections import Counter, defaultdict, deque
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TOP = "AS-40000"


def pn(value):
    return value.strip().upper()


def groups(rows, key):
    result = defaultdict(list)
    for line, row in rows:
        result[key(row)].append({"line": line, **row})
    return result


def main():
    report = {"purpose": "Phase 1 observations; proposed normalization and graph analysis, not verified API results", "files": {}}
    tables = {}
    for name in ("bom", "parts_master", "service_parts"):
        path = ROOT / "data" / (name + ".csv")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [(reader.line_num, row) for row in reader]
            headers = reader.fieldnames
        tables[name] = rows
        counts = Counter(tuple(row.items()) for _, row in rows)
        report["files"][name] = {
            "rows": len(rows), "headers": headers,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "exact_duplicate_surplus": sum(n-1 for n in counts.values()),
            "blank_cells": dict(Counter(k for _, r in rows for k, v in r.items() if v is not None and not v.strip())),
            "malformed_rows": [line for line, r in rows if None in r or any(v is None for v in r.values())],
        }
    changes = []
    variants = defaultdict(set)
    for name, rows in tables.items():
        columns = ("parent_pn", "child_pn") if name == "bom" else ("part_number",)
        for line, row in rows:
            for col in columns:
                value = row[col]
                variants[pn(value)].add(value)
                if value != pn(value):
                    changes.append({"file": name, "line": line, "column": col, "raw": value, "normalized": pn(value)})
    report["normalization"] = {"changed_cells": changes, "variant_groups": {k: sorted(v) for k, v in variants.items() if len(v) > 1}, "unexpected_pn_format": sorted(k for k in variants if not re.fullmatch(r"[A-Z]+-\d+", k))}
    bom = groups(tables["bom"], lambda r: (pn(r["parent_pn"]), pn(r["child_pn"])))
    edges = defaultdict(dict)
    invalid_quantities = []
    conflicts = []
    for (parent, child), rows in bom.items():
        quantities = set()
        for row in rows:
            try:
                value = Decimal(row["quantity"].strip())
                if not value.is_finite() or value <= 0 or value != value.to_integral_value():
                    raise ValueError("not a positive integer")
                quantities.add(int(value))
            except (InvalidOperation, ValueError):
                invalid_quantities.append(row)
        if len(quantities) == 1:
            edges[parent][child] = next(iter(quantities))
        elif len(quantities) > 1:
            conflicts.append({"parent": parent, "child": child, "rows": rows})
    report["bom"] = {
        "unique_pairs": len(bom), "normalized_duplicate_surplus": sum(len(v)-1 for v in bom.values()),
        "duplicate_groups": [{"parent": p, "child": c, "rows": rows} for (p,c), rows in bom.items() if len(rows)>1],
        "quantity_conflicts": conflicts, "invalid_quantities": invalid_quantities,
        "self_edges": [p for p,c in bom if p == c],
        "quantity_distribution": dict(Counter(r["quantity"] for _, r in tables["bom"])),
    }
    master = groups(tables["parts_master"], lambda r: pn(r["part_number"]))
    service = groups(tables["service_parts"], lambda r: pn(r["part_number"]))
    master_rev = groups(tables["parts_master"], lambda r: (pn(r["part_number"]), r["revision"].strip().upper()))
    report["master"] = {
        "unique_parts": len(master),
        "revision_distribution": dict(Counter(r["revision"] for _, r in tables["parts_master"])),
        "multiple_revision_parts": {p: sorted({r["revision"] for r in rows}) for p, rows in master.items() if len({r["revision"] for r in rows})>1},
        "same_revision_duplicates": [{"part": p, "revision": rev, "rows": rows} for (p,rev), rows in master_rev.items() if len(rows)>1],
        "invalid_revisions": [r for _,r in tables["parts_master"] if not re.fullmatch("[A-Z]", r["revision"].strip().upper())],
    }
    invalid_costs = []
    for line, r in tables["parts_master"]:
        try:
            cost = Decimal(r["unit_cost"])
            if not cost.is_finite() or cost < 0:
                raise ValueError("invalid cost")
        except (InvalidOperation, ValueError):
            invalid_costs.append({"line": line, **r})
    report["master"]["invalid_costs"] = invalid_costs
    range_kinds = Counter()
    bad_ranges = []
    for line, r in tables["service_parts"]:
        lo, hi = r["serial_from"].strip(), r["serial_to"].strip()
        if not lo and not hi:
            range_kinds["unbounded"] += 1
        elif not lo or not hi:
            range_kinds["one_sided"] += 1
            bad_ranges.append({"line": line, **r})
        elif not re.fullmatch(r"[+-]?\d+", lo) or not re.fullmatch(r"[+-]?\d+", hi):
            range_kinds["malformed"] += 1
            bad_ranges.append({"line": line, **r})
        elif int(lo)>int(hi):
            range_kinds["reversed"] += 1
            bad_ranges.append({"line": line, **r})
        else:
            range_kinds["bounded"] += 1
    report["service"] = {"unique_parts": len(service), "flag_distribution": dict(Counter(r["field_replaceable"] for _,r in tables["service_parts"])), "duplicate_part_groups": {p: rows for p,rows in service.items() if len(rows)>1}, "range_kinds": dict(range_kinds), "range_issues": bad_ranges}
    # Inspect rooted DFS back edges in two traversal orders to expose ambiguity.
    def walk(reverse=False):
        state, path, removed = {}, [], []
        def visit(node):
            state[node] = 1
            path.append(node)
            for child in sorted(edges.get(node, {}), reverse=reverse):
                if state.get(child) == 1:
                    removed.append({"parent": node, "child": child, "root_path": path.copy(), "lines": [r["line"] for r in bom[node,child]]})
                elif not state.get(child):
                    visit(child)
            path.pop()
            state[node] = 2
        visit(TOP)
        return set(state), removed
    reachable, removed = walk()
    _, reverse_removed = walk(True)
    banned = {(r["parent"],r["child"]) for r in removed}
    # This is an audit projection, conditional on unambiguous quantities/cycle repair.
    indegree = {p: 0 for p in reachable}
    for p in reachable:
        for c in edges.get(p, {}):
            if (p,c) not in banned:
                indegree[c] += 1
    queue = deque(sorted(p for p,d in indegree.items() if d == 0))
    quantity, paths, depth = defaultdict(int, {TOP:1}), defaultdict(int, {TOP:1}), defaultdict(int)
    order = []
    while queue:
        p = queue.popleft()
        order.append(p)
        for c,q in edges.get(p, {}).items():
            if (p,c) in banned:
                continue
            quantity[c] += quantity[p]*q
            paths[c] += paths[p]
            depth[c] = max(depth[c], depth[p]+1)
            indegree[c] -= 1
            if indegree[c] == 0:
                queue.append(c)
    bom_nodes = {p for pair in bom for p in pair}
    # Independent reachability probes identify every cyclic region, including outside the machine.
    reach_cache = {}
    for node in bom_nodes:
        seen, pending = set(), list(edges.get(node, {}))
        while pending:
            child = pending.pop()
            if child not in seen:
                seen.add(child)
                pending.extend(edges.get(child, {}))
        reach_cache[node] = seen
    cycle_components = set()
    for node in bom_nodes:
        if node in reach_cache[node]:
            cycle_components.add(tuple(sorted(c for c in reach_cache[node] if node in reach_cache[c])))
    all_parts = bom_nodes | set(master) | set(service)
    status = {p: "missing" if p not in master else "ready" if any(r["field_replaceable"].strip().upper()=="Y" for r in service.get(p,[])) else "not_replaceable" for p in reachable}
    report["graph"] = {
        "raw_bom_nodes": len(bom_nodes), "reachable_parts": len(reachable),
        "all_cycle_components": sorted(cycle_components),
        "excluded_outside_parent_edges": [{"parent": p, "child": c, "quantity": q} for p in sorted(bom_nodes-reachable) for c,q in sorted(edges.get(p, {}).items())],
        "removed_back_edges": removed, "reverse_order_removed_back_edges": reverse_removed,
        "repair_same_in_both_orders": banned == {(r["parent"],r["child"]) for r in reverse_removed},
        "post_repair_topological_nodes": len(order), "max_depth_edges": max(depth.values()),
        "outside_machine_all_sources": sorted(all_parts-reachable), "outside_machine_bom": sorted(bom_nodes-reachable),
        "outside_machine_master": sorted(set(master)-reachable), "outside_machine_service": sorted(set(service)-reachable),
        "missing_master": sorted(reachable-set(master)), "missing_service": sorted(reachable-set(service)),
        "service_missing_master": sorted(set(service)-set(master)),
        "status_projection": dict(Counter(status.values())),
        "largest_quantities": sorted(quantity.items(), key=lambda x:(-x[1],x[0]))[:10],
        "largest_path_counts": sorted(paths.items(), key=lambda x:(-x[1],x[0]))[:10],
        "multiple_path_parts": sum(n>1 for n in paths.values()),
        "root_master_rows": master.get(TOP, []), "root_service_rows": service.get(TOP, []),
    }
    report["normalization"]["changed_cells_by_file"] = dict(Counter(r["file"] for r in changes))
    report["service"]["range_pairs"] = [{"from": lo, "to": hi, "rows": n} for (lo,hi),n in sorted(Counter((r["serial_from"],r["serial_to"]) for _,r in tables["service_parts"] if r["serial_from"]).items())]
    output = ROOT / "audit" / "findings.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)+"\n", encoding="utf-8")
    print(f"Wrote {output}")
    print(json.dumps({"files":report["files"], "normalization_changed_cells":len(changes), "bom_pairs":len(bom), "bom_duplicate_surplus":report["bom"]["normalized_duplicate_surplus"], "bom_quantity_conflicts":conflicts, "invalid_quantities":invalid_quantities, "master_unique_parts":len(master), "multi_revision_parts":len(report["master"]["multiple_revision_parts"]), "same_revision_duplicates":report["master"]["same_revision_duplicates"], "invalid_revisions":report["master"]["invalid_revisions"], "invalid_costs":invalid_costs, "service":report["service"], "graph":report["graph"]}, indent=2))


if __name__ == "__main__":
    main()
