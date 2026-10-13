"""Generated exports checked against a separate, forward path enumeration oracle.

Production aggregates totals topologically and discovers paths backward. These
small graphs instead enumerate every root-down route and multiply its edges.
Expected metadata is generated before any noisy CSV representation is written.
"""

from collections import Counter
import random

import pytest
from fastapi.testclient import TestClient

from parttrace.api import create_app


@pytest.mark.parametrize("seed", range(20))
def test_generated_exports_against_independent_oracle(export, seed):
    rng = random.Random(seed)
    root = "AS-40000"
    names = [root] + rng.sample([f"TEST-{i:03}" for i in range(100)], 11)
    edges = {}
    # Every generated vertex is reachable, with additional forward links
    # producing shared subassemblies; numbering does not encode hierarchy.
    for i in range(1, len(names)):
        edges[names[rng.randrange(i)], names[i]] = rng.randint(1, 4)
        for j in range(i):
            if rng.random() < .2:
                edges[names[j], names[i]] = rng.randint(1, 4)
    adjacency = {p: [] for p in names}
    for (parent, child), quantity in edges.items():
        adjacency[parent].append((child, quantity))
    routes = {p: [] for p in names}
    totals = Counter()

    def enumerate_routes(part, path, amount):
        routes[part].append(path)
        totals[part] += amount
        for child, quantity in adjacency[part]:
            enumerate_routes(child, path + [child], amount * quantity)

    enumerate_routes(root, [root], 1)
    master, service, expected, ranges = [], [], {}, {}
    for index, part in enumerate(names):
        missing = index % 5 == 2
        ready = index % 3 != 0
        revision = rng.choice("BCZ")
        if not missing:
            master.extend([(part, "A", "Old description"), (part, revision, f"Selected {part}")])
        lower = rng.randint(1, 20)
        ranges[part] = None if index % 2 == 0 else (lower, lower + 10)
        lo, hi = ranges[part] or ("", "")
        service.append((part, "Y" if ready else "N", lo, hi))
        expected[part] = {
            "part_number": part, "description": None if missing else f"Selected {part}",
            "revision": None if missing else revision,
            "status": "missing" if missing else "ready" if ready else "not_replaceable",
            "total_quantity": totals[part],
            "parents": sorted(p for p, c in edges if c == part),
            "children": [{"part_number": c, "quantity": q} for c, q in sorted(adjacency[part])],
        }
    bom = [(p, c, q) for (p, c), q in edges.items()]
    # Add redundant exports, normalized identities, indisputable back edges,
    # and an outside parent referencing a real leaf. None alters the oracle.
    bom.extend(bom[:5])
    bom.extend([(names[-1], root, 99), (names[3], names[3], 7),
                ("OUTSIDE", names[-1], 1000), ("OUTSIDE", "OTHER", 1)])
    bom = [(f" {p.lower()} ", c.lower(), q) if i % 2 else (p, c, q)
           for i, (p, c, q) in enumerate(bom)]
    master.append(("OUTSIDE", "Z", "Excluded"))
    service.append(("OUTSIDE", "Y", "", ""))
    for rows in (bom, master, service):
        rng.shuffle(rows)
    directory = export(bom, master, service)
    with TestClient(create_app(directory)) as client:
        counts = Counter(p["status"] for p in expected.values())
        assert client.get("/api/validation").json() == {
            "parts": len(names), **{s: counts[s] for s in ("ready", "missing", "not_replaceable")}}
        for part in names:
            response = client.get(f"/api/parts/{part.lower()}")
            assert response.status_code == 200
            assert response.json() == expected[part]
            assert client.get(f"/api/parts/{part.lower()}/paths").json() == {
                "part_number": part, "paths": sorted(routes[part])}
        for serial in range(33):
            count = sum(p["status"] == "ready" and
                        (ranges[n] is None or ranges[n][0] <= serial <= ranges[n][1])
                        for n, p in expected.items())
            assert client.get(f"/api/serial/{serial}").json() == {
                "serial": serial, "applicable_parts": count}
        for outside in ("OUTSIDE", "OTHER", "UNKNOWN"):
            assert client.get(f"/api/parts/{outside}").status_code == 404
            assert client.get(f"/api/parts/{outside}/paths").status_code == 404
