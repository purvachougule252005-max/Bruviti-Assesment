from pathlib import Path
import hashlib
import random

import pytest

from parttrace import Catalogue, PartNotFound


@pytest.fixture
def appendix():
    return Catalogue.from_directory(Path(__file__).parent / "fixtures" / "appendix_q", root="AS-1")


def test_appendix_validation(appendix):
    assert appendix.validation() == {"parts": 4, "ready": 2, "missing": 1, "not_replaceable": 1}


def test_appendix_part_and_quantity(appendix):
    # Four directly + two assemblies containing three each = ten.
    assert appendix.part("FA-9") == {
        "part_number": "FA-9", "description": "...", "revision": "B",
        "status": "ready", "total_quantity": 10, "parents": ["AS-1", "AS-2"], "children": [],
    }


def test_appendix_paths_lexicographic_not_shortest_first(appendix):
    assert appendix.paths("FA-9") == {
        "part_number": "FA-9", "paths": [["AS-1", "AS-2", "FA-9"], ["AS-1", "FA-9"]],
    }


def test_appendix_serial_and_missing_precedence(appendix):
    assert appendix.serial(2500) == {"serial": 2500, "applicable_parts": 2}
    assert appendix.serial(1500) == {"serial": 1500, "applicable_parts": 2}
    assert appendix.part("EL-5") == {
        "part_number": "EL-5", "description": None, "revision": None, "status": "missing",
        "total_quantity": 2, "parents": ["AS-2"], "children": [],
    }


def test_root_included_once_and_children_are_per_parent(appendix):
    assert appendix.part("AS-1") == {
        "part_number": "AS-1", "description": "Example machine", "revision": "A",
        "status": "not_replaceable", "total_quantity": 1, "parents": [],
        "children": [{"part_number": "AS-2", "quantity": 2}, {"part_number": "FA-9", "quantity": 4}],
    }
    assert appendix.paths("AS-1") == {"part_number": "AS-1", "paths": [["AS-1"]]}
    assert appendix.part("AS-2")["children"] == [
        {"part_number": "EL-5", "quantity": 1}, {"part_number": "FA-9", "quantity": 3},
    ]


def test_normalization_deduplication_and_matching(export):
    cat = Catalogue.from_directory(export(
        bom=[(" r ", " a ", 2), ("R", "A", "2.0"), ("r", "a", 2)],
        master=[(" r", "a ", "Root"), ("a ", " b", "Current")],
        service=[(" A ", " y ")],
    ), root="r")
    assert cat.part(" a ")["total_quantity"] == 2
    assert cat.part("a")["revision"] == "B"
    assert cat.part("A")["status"] == "ready"
    assert cat.paths(" a ") == {"part_number": "A", "paths": [["R", "A"]]}
    assert cat.validation()["parts"] == 2
    assert len([d for d in cat.diagnostics if d.code == "duplicate_relationship"]) == 1


def test_repeated_assemblies_diamond_and_missing_master_parent(export):
    cat = Catalogue.from_directory(export(
        bom=[("R", "A", 2), ("R", "B", 3), ("R", "X", 4), ("A", "C", 5), ("B", "C", 7), ("C", "X", 2)],
        master=[("R", "A", "root"), ("A", "A", "left"), ("B", "A", "right"), ("X", "A", "leaf")],
        service=[("C", "Y"), ("X", "Y")],
    ), root="R")
    # C occurs 2*5 + 3*7 = 31 times, despite missing descriptive metadata.
    assert cat.part("C")["total_quantity"] == 31
    assert cat.part("C")["status"] == "missing"
    # Four direct X plus two in each of the 31 C assemblies.
    assert cat.part("X")["total_quantity"] == 66
    assert cat.part("X")["parents"] == ["C", "R"]
    assert cat.paths("X")["paths"] == [["R", "A", "C", "X"], ["R", "B", "C", "X"], ["R", "X"]]


def test_outside_assembly_cannot_add_parent_or_quantity(export):
    cat = Catalogue.from_directory(export(
        bom=[("R", "X", 2), ("OUT", "X", 100), ("OUT", "Y", "invalid")],
        master=[("X", "A", "leaf"), ("OUT", "BAD", "outside")],
        service=[("X", "Y"), ("OUT", "Y", "bad", "range")],
    ), root="R")
    assert cat.part("X")["total_quantity"] == 2
    assert cat.part("X")["parents"] == ["R"]
    assert cat.validation()["parts"] == 2
    for number in ("OUT", "Y", "UNKNOWN"):
        for lookup in (cat.part, cat.paths):
            with pytest.raises(PartNotFound):
                lookup(number)


def test_highest_revision_and_description_are_from_same_record(export):
    cat = Catalogue.from_directory(export(
        master=[("R", "Z", "new"), ("R", "B", "middle"), ("R", "A", "old")],
    ), root="R")
    assert cat.part("R")["description"] == "new"
    assert cat.part("R")["revision"] == "Z"


def test_missing_root_still_defines_the_machine(export):
    cat = Catalogue.from_directory(export(), root="R")
    assert cat.validation() == {"parts": 1, "ready": 0, "missing": 1, "not_replaceable": 0}
    assert cat.part("R")["total_quantity"] == 1
    assert cat.paths("R")["paths"] == [["R"]]


def test_responses_cannot_mutate_catalogue(appendix):
    part = appendix.part("AS-1")
    part["children"][0]["quantity"] = 999
    part["parents"].append("FAKE")
    paths = appendix.paths("FA-9")
    paths["paths"][0].append("FAKE")
    counts = appendix.validation()
    counts["parts"] = 99
    assert appendix.part("AS-1")["children"][0]["quantity"] == 2
    assert appendix.part("AS-1")["parents"] == []
    assert appendix.paths("FA-9")["paths"][0] == ["AS-1", "AS-2", "FA-9"]
    assert appendix.validation()["parts"] == 4


@pytest.mark.parametrize("seed", range(5))
def test_row_permutations_preserve_answers(export, seed):
    bom = [("R", "Z", 2), ("Z", "B", 3), ("B", "Z", 7), ("R", "X", 4), ("Z", "X", 5), ("R", "Z", 2)]
    master = [("R", "A", "root"), ("Z", "A", "assembly"), ("X", "B", "new"), ("X", "A", "old")]
    service = [("X", "Y", 10, 20), ("X", "Y", 15, 30)]
    baseline = Catalogue.from_directory(export(bom, master, service), root="R")
    rng = random.Random(seed)
    for rows in (bom, master, service):
        rng.shuffle(rows)
    shuffled = Catalogue.from_directory(export(bom, master, service), root="R")
    assert shuffled.validation() == baseline.validation()
    for p in ("R", "Z", "B", "X"):
        assert shuffled.part(p) == baseline.part(p)
        assert shuffled.paths(p) == baseline.paths(p)
    assert shuffled.serial(20) == baseline.serial(20)


def test_does_not_reread_csv_during_queries(export):
    directory = export(master=[("R", "A", "original")])
    cat = Catalogue.from_directory(directory, root="R")
    (directory / "parts_master.csv").write_text("corrupted after load", encoding="utf-8")
    assert cat.part("R")["description"] == "original"
    assert cat.validation()["parts"] == 1
    assert cat.serial(0)["applicable_parts"] == 0


def test_long_chain_has_no_recursion_limit(export):
    # Assemblies need not be numbered in topological or lexical order.
    names = [f"P-{n}" for n in range(1200)]
    bom = [(a, b, 1) for a, b in zip(names, names[1:])]
    cat = Catalogue.from_directory(export(bom=bom), root=names[0])
    assert cat.paths(names[-1])["paths"] == [names]
    assert cat.part(names[-1])["total_quantity"] == 1


def test_default_data_is_repo_relative_and_never_modified(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[1] / "data"
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.csv")}
    monkeypatch.chdir(tmp_path)
    cat = Catalogue.from_directory()
    assert cat.part("AS-40000")["total_quantity"] == 1
    assert cat.paths("as-40000")["paths"] == [["AS-40000"]]
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.csv")}
