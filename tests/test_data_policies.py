import csv

import pytest

from parttrace import Catalogue, CatalogueDataError


@pytest.mark.parametrize("quantity", ["", "0", "-1", "0.5", "bad", "NaN", "Infinity"])
def test_invalid_retained_quantity_is_rejected(export, quantity):
    with pytest.raises(CatalogueDataError, match="positive integer.*bom.csv:2"):
        Catalogue.from_directory(export(bom=[("R", "X", quantity)]), root="R")


def test_conflicting_quantities_do_not_get_summed_or_overwritten(export):
    with pytest.raises(CatalogueDataError, match="Conflicting quantities.*bom.csv:2, bom.csv:3"):
        Catalogue.from_directory(export(bom=[("R", "X", 2), ("r", "x", 3)]), root="R")


def test_selected_revision_description_conflict_is_rejected(export):
    with pytest.raises(CatalogueDataError, match="Conflicting descriptions.*revision B"):
        Catalogue.from_directory(export(master=[("R", "B", "one"), ("R", "B", "two")]), root="R")


def test_old_revision_conflict_and_unused_metadata_do_not_change_result(export):
    cat = Catalogue.from_directory(export(master=[
        ("R", "A", "old one"), ("R", "A", "old two"),
        ("R", "B", "current", "A", "1"), ("R", "B", "current", "B", "bad cost"),
    ]), root="R")
    assert cat.part("R")["description"] == "current"
    assert {d.code for d in cat.diagnostics} >= {"unused_master_conflict", "invalid_unused_cost"}


@pytest.mark.parametrize("revision", ["", "AB", "1", "?"])
def test_undefined_revision_order_is_not_invented(export, revision):
    with pytest.raises(CatalogueDataError, match="single A-Z letter"):
        Catalogue.from_directory(export(master=[("R", revision, "part")]), root="R")


def test_blank_description_is_not_a_missing_part(export):
    cat = Catalogue.from_directory(export(master=[("R", "A", "")]), root="R")
    assert cat.part("R")["description"] == ""
    assert cat.part("R")["revision"] == "A"
    assert cat.part("R")["status"] == "not_replaceable"
    assert any(d.code == "blank_description" for d in cat.diagnostics)


def test_conflicting_service_flags_are_rejected(export):
    with pytest.raises(CatalogueDataError, match="Conflicting service replaceability"):
        Catalogue.from_directory(export(master=[("R", "A", "part")], service=[("R", "Y"), ("R", "N")]), root="R")


def test_unrecognized_flag_is_not_y(export):
    cat = Catalogue.from_directory(export(master=[("R", "A", "part")], service=[("R", "unknown")]), root="R")
    assert cat.part("R")["status"] == "not_replaceable"
    assert any(d.code == "invalid_service_flag" for d in cat.diagnostics)


def test_missing_master_takes_precedence_over_conflicting_service(export):
    cat = Catalogue.from_directory(export(service=[("R", "Y", "bad", "range"), ("R", "N")]), root="R")
    assert cat.part("R")["status"] == "missing"
    assert cat.serial(100)["applicable_parts"] == 0
    assert {d.code for d in cat.diagnostics} >= {"ignored_service_conflict", "ignored_invalid_serial_range"}


def test_identical_master_and_service_rows_do_not_inflate_counts(export):
    cat = Catalogue.from_directory(export(
        master=[("R", "A", "part"), ("r ", "a", "part")],
        service=[("R", "Y"), ("r", "y")],
    ), root="R")
    assert cat.validation() == {"parts": 1, "ready": 1, "missing": 0, "not_replaceable": 0}
    assert cat.serial(0)["applicable_parts"] == 1


def test_utf8_bom_and_reordered_headers_are_supported(export):
    directory = export(master=[("R", "A", "part")])
    with (directory / "bom.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["quantity", "child_pn", "parent_pn"])
        writer.writerow([2, "X", "R"])
    assert Catalogue.from_directory(directory, root="R").part("X")["total_quantity"] == 2


@pytest.mark.parametrize("text", [
    "parent_pn,child_pn\nR,X\n",
    "parent_pn,child_pn,quantity\nR,X\n",
    "parent_pn,child_pn,quantity\nR,X,2,extra\n",
    "parent_pn,child_pn,quantity\nR,,2\n",
    "parent_pn,child_pn,quantity\nR,\"unterminated,2\n",
    "parent_pn,parent_pn,quantity\nR,X,2\n",
])
def test_malformed_csv_is_rejected(export, text):
    directory = export()
    (directory / "bom.csv").write_text(text, encoding="utf-8")
    with pytest.raises(CatalogueDataError, match="bom.csv"):
        Catalogue.from_directory(directory, root="R")


def test_missing_file_has_a_clear_error(tmp_path):
    with pytest.raises(CatalogueDataError, match="Cannot read bom.csv"):
        Catalogue.from_directory(tmp_path)
