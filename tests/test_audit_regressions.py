"""Targeted regression tests for audit findings and spec compliance.

Covers:
- Whitespace-padded CSV headers
- Whitespace-padded description duplicate deduplication vs real conflicts
- Dominator repair edge cases and defensive empty parent handling
- Complex DAG total quantities and sorted paths
- Serial boundaries, inclusive endpoints, and non-integer 4xx rejection
- Case-insensitive URLs for both part endpoints
- Unambiguous vs genuinely ambiguous conflict handling
- Outside-machine record exclusion and 404 enforcement
"""

import csv
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from parttrace import Catalogue, CatalogueDataError, PartNotFound
from parttrace.api import create_app
from parttrace.graph import repair_hierarchy


def test_whitespace_padded_csv_headers_load_successfully(tmp_path):
    # Verify that replacement CSV exports with padded headers load without error.
    bom_path = tmp_path / "bom.csv"
    master_path = tmp_path / "parts_master.csv"
    service_path = tmp_path / "service_parts.csv"

    with bom_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([" parent_pn ", " child_pn ", " quantity "])
        w.writerow(["AS-40000", "EL-100", "2"])

    with master_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([" part_number ", " revision ", " description ", " category ", " unit_cost "])
        w.writerow(["AS-40000", "A", "Machine Root", "Assembly", "100.00"])
        w.writerow(["EL-100", "B", "Motor", "Electrical", "50.00"])

    with service_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([" part_number ", " field_replaceable ", " serial_from ", " serial_to "])
        w.writerow(["EL-100", "Y", "1000", "2000"])

    cat = Catalogue.from_directory(tmp_path, root="AS-40000")
    assert cat.validation() == {"parts": 2, "ready": 1, "missing": 0, "not_replaceable": 1}
    assert cat.part("el-100")["total_quantity"] == 2
    assert cat.part("el-100")["revision"] == "B"


def test_description_whitespace_padding_is_not_treated_as_conflict(export):
    # Same description with trailing whitespace is deduplicated rather than failing.
    cat = Catalogue.from_directory(export(
        master=[
            ("R", "A", "Main Pump"),
            ("R", "A", "Main Pump  "),
        ],
    ), root="R")
    assert cat.part("R")["description"] == "Main Pump"


def test_selected_revision_genuine_conflict_still_fails(export):
    # Truly contradictory descriptions at the selected revision fail.
    with pytest.raises(CatalogueDataError, match="Conflicting descriptions.*revision A"):
        Catalogue.from_directory(export(
            master=[
                ("R", "A", "Main Pump"),
                ("R", "A", "Alternate Motor"),
            ],
        ), root="R")


def test_dominator_empty_parents_defensive():
    # Calling repair_hierarchy on a single root node with no edges
    raw = {"R": set()}
    g, removed, order = repair_hierarchy(raw, "R")
    assert removed == ()
    assert order == ["R"]


def test_complex_dag_diamond_quantities_and_sorted_paths(export):
    # R -> A (x2), R -> B (x3)
    # A -> S (x4), B -> S (x5)
    # Total S: 2*4 + 3*5 = 8 + 15 = 23.
    # Paths for S: [["R", "A", "S"], ["R", "B", "S"]] sorted part-by-part.
    cat = Catalogue.from_directory(export(
        bom=[
            ("R", "A", 2),
            ("R", "B", 3),
            ("A", "S", 4),
            ("B", "S", 5),
        ],
        master=[
            ("R", "A", "Root Machine"),
            ("A", "A", "Assembly A"),
            ("B", "A", "Assembly B"),
            ("S", "C", "Shared Sub"),
        ],
        service=[
            ("S", "Y"),
        ],
    ), root="R")

    s_part = cat.part("S")
    assert s_part["total_quantity"] == 23
    assert s_part["parents"] == ["A", "B"]
    assert cat.paths("S") == {
        "part_number": "S",
        "paths": [["R", "A", "S"], ["R", "B", "S"]],
    }


def test_serial_boundaries_inclusive(export):
    # Ready part with range 1000-2000 applies to 1000 and 2000, but not 999 or 2001.
    cat = Catalogue.from_directory(export(
        bom=[("R", "P", 1)],
        master=[("R", "A", "Root"), ("P", "A", "Part P")],
        service=[("P", "Y", "1000", "2000")],
    ), root="R")

    assert cat.serial(999)["applicable_parts"] == 0
    assert cat.serial(1000)["applicable_parts"] == 1
    assert cat.serial(1500)["applicable_parts"] == 1
    assert cat.serial(2000)["applicable_parts"] == 1
    assert cat.serial(2001)["applicable_parts"] == 0


def test_serial_endpoints_via_http(export):
    app = create_app(export(
        bom=[("R", "P", 1)],
        master=[("R", "A", "Root"), ("P", "A", "Part P")],
        service=[("P", "Y", "1000", "2000")],
    ), root="R")

    with TestClient(app) as client:
        # Valid integer serials
        res = client.get("/api/serial/1000")
        assert res.status_code == 200
        assert res.json() == {"serial": 1000, "applicable_parts": 1}

        res = client.get("/api/serial/0")
        assert res.status_code == 200
        assert res.json() == {"serial": 0, "applicable_parts": 0}

        # Non-integer strings must return 422 (a 4xx error)
        for invalid in ["2500.0", "1500.5", "-1", "abc", "1e3", ""]:
            if invalid:
                res = client.get(f"/api/serial/{invalid}")
                assert res.status_code == 422, f"Expected 422 for serial {invalid!r}"


def test_case_insensitive_url_matching_for_both_endpoints(export):
    app = create_app(export(
        bom=[("R", "FA-30019", 1)],
        master=[("R", "A", "Root"), ("FA-30019", "B", "Washer")],
        service=[("FA-30019", "Y")],
    ), root="R")

    with TestClient(app) as client:
        for spelling in ["FA-30019", "fa-30019", "Fa-30019"]:
            res_part = client.get(f"/api/parts/{spelling}")
            assert res_part.status_code == 200
            assert res_part.json()["part_number"] == "FA-30019"

            res_paths = client.get(f"/api/parts/{spelling}/paths")
            assert res_paths.status_code == 200
            assert res_paths.json()["part_number"] == "FA-30019"


def test_outside_and_unknown_parts_return_404(export):
    app = create_app(export(
        bom=[("R", "IN-1", 1), ("OUT-1", "OUT-2", 1)],
        master=[("R", "A", "Root"), ("IN-1", "A", "Inside"), ("OUT-1", "A", "Outside")],
        service=[("IN-1", "Y"), ("OUT-1", "Y")],
    ), root="R")

    with TestClient(app) as client:
        assert client.get("/api/parts/OUT-1").status_code == 404
        assert client.get("/api/parts/OUT-1/paths").status_code == 404
        assert client.get("/api/parts/UNKNOWN").status_code == 404
        assert client.get("/api/parts/UNKNOWN/paths").status_code == 404


def test_cycle_repair_removes_upward_edge_and_preserves_catalogue(export):
    # R -> A -> B -> A (B -> A points back up to assembly A that B sits inside)
    cat = Catalogue.from_directory(export(
        bom=[("R", "A", 2), ("A", "B", 3), ("B", "A", 99)],
        master=[("R", "A", "Root"), ("A", "A", "Assy A"), ("B", "A", "Assy B")],
        service=[("A", "Y"), ("B", "Y")],
    ), root="R")

    assert cat.validation()["parts"] == 3
    assert cat.part("A")["total_quantity"] == 2
    assert cat.part("B")["total_quantity"] == 6
    assert cat.paths("B")["paths"] == [["R", "A", "B"]]
    assert cat.part("B")["children"] == []
    assert any(d.code == "removed_upward_edge" for d in cat.diagnostics)
