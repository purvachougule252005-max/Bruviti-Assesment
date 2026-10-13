import pytest

from parttrace import Catalogue, CatalogueDataError


def test_self_loops_and_return_to_root(export):
    cat = Catalogue.from_directory(export(bom=[
        ("R", "R", 9), ("R", "A", 2), ("A", "A", 5), ("A", "R", 99), ("A", "X", 3),
    ]), root="R")
    assert cat.part("R")["total_quantity"] == 1
    assert cat.part("R")["parents"] == []
    assert cat.part("A")["total_quantity"] == 2
    assert cat.part("X")["total_quantity"] == 6
    assert len([d for d in cat.diagnostics if d.code == "removed_upward_edge"]) == 3


def test_deep_ancestor_cycle_is_repaired_with_source_lines(export):
    cat = Catalogue.from_directory(export(bom=[
        ("R", "Z", 2), ("Z", "B", 3), ("B", "A", 4), ("A", "Z", 5),
    ]), root="R")
    assert cat.part("A")["total_quantity"] == 24
    assert cat.part("Z")["parents"] == ["R"]
    assert cat.paths("A")["paths"] == [["R", "Z", "B", "A"]]
    removed = [d for d in cat.diagnostics if d.code == "removed_upward_edge"]
    assert len(removed) == 1
    assert "A -> Z" in removed[0].message
    assert removed[0].sources == ("bom.csv:5",)


def test_diamond_with_return_to_common_ancestor(export):
    cat = Catalogue.from_directory(export(bom=[
        ("R", "H", 1), ("H", "A", 2), ("H", "B", 3),
        ("A", "C", 5), ("B", "C", 7), ("C", "H", 99),
    ]), root="R")
    assert cat.part("C")["total_quantity"] == 31
    assert cat.paths("C")["paths"] == [["R", "H", "A", "C"], ["R", "H", "B", "C"]]


def test_deeper_to_shallower_edge_is_not_automatically_a_cycle(export):
    cat = Catalogue.from_directory(export(bom=[
        ("R", "A", 2), ("R", "X", 3), ("A", "B", 4), ("B", "X", 5),
    ]), root="R")
    assert cat.part("X")["total_quantity"] == 43
    assert cat.part("X")["parents"] == ["B", "R"]
    assert not any(d.code == "removed_upward_edge" for d in cat.diagnostics)


@pytest.mark.parametrize("reverse", [False, True])
def test_multi_entry_cycle_is_reported_instead_of_guessed(export, reverse):
    bom = [("R", "A", 1), ("R", "B", 1), ("A", "B", 1), ("B", "A", 1)]
    if reverse:
        bom.reverse()
    with pytest.raises(CatalogueDataError, match="no unambiguous rooted-ancestor repair"):
        Catalogue.from_directory(export(bom=bom), root="R")


def test_disconnected_cycle_does_not_prevent_machine_loading(export):
    cat = Catalogue.from_directory(export(bom=[
        ("R", "X", 2), ("OUT1", "OUT2", 1), ("OUT2", "OUT1", 1),
    ]), root="R")
    assert cat.validation()["parts"] == 2
    assert cat.part("X")["total_quantity"] == 2
