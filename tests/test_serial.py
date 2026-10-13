import pytest

from parttrace import Catalogue, CatalogueDataError


@pytest.fixture
def serial_catalogue(export):
    return Catalogue.from_directory(export(
        bom=[("R", "BOUNDED", 10), ("R", "ALL", 20), ("R", "NO", 1), ("R", "MISSING", 1)],
        master=[("R", "A", "root"), ("BOUNDED", "A", "bounded"), ("ALL", "A", "all"), ("NO", "A", "no")],
        service=[("BOUNDED", "Y", 10, 20), ("ALL", "Y"), ("NO", "N"), ("MISSING", "Y")],
    ), root="R")


@pytest.mark.parametrize("serial, expected", [(0, 1), (9, 1), (10, 2), (15, 2), (20, 2), (21, 1), (10**20, 1)])
def test_inclusive_bounds_and_distinct_part_counts(serial_catalogue, serial, expected):
    assert serial_catalogue.serial(serial) == {"serial": serial, "applicable_parts": expected}
    assert serial_catalogue.part("BOUNDED")["status"] == "ready"


def test_multiple_ranges_form_a_union_without_double_counting(export):
    cat = Catalogue.from_directory(export(
        master=[("R", "A", "part")],
        service=[("R", "Y", 10, 20), ("R", "Y", 15, 30), ("R", "Y", 10, 20), ("R", "Y", 40, 40)],
    ), root="R")
    assert [cat.serial(s)["applicable_parts"] for s in (9, 10, 20, 30, 31, 39, 40, 41)] == [0, 1, 1, 1, 0, 0, 1, 0]


def test_unrestricted_record_covers_every_serial(export):
    cat = Catalogue.from_directory(export(master=[("R", "A", "part")], service=[("R", "Y", 10, 20), ("R", "Y")]), root="R")
    assert cat.serial(0)["applicable_parts"] == 1
    assert cat.serial(21)["applicable_parts"] == 1


@pytest.mark.parametrize("lo,hi", [("", "20"), ("10", ""), ("20", "10"), ("bad", "20"), ("1.5", "20"), ("-1", "20")])
def test_invalid_ready_range_is_rejected(export, lo, hi):
    with pytest.raises(CatalogueDataError, match="[Ss]erial"):
        Catalogue.from_directory(export(master=[("R", "A", "part")], service=[("R", "Y", lo, hi)]), root="R")


def test_unrestricted_row_does_not_hide_an_invalid_record(export):
    with pytest.raises(CatalogueDataError, match="serial bounds"):
        Catalogue.from_directory(export(master=[("R", "A", "part")], service=[("R", "Y"), ("R", "Y", "", "10")]), root="R")


def test_nonreplaceable_range_is_irrelevant(export):
    cat = Catalogue.from_directory(export(master=[("R", "A", "part")], service=[("R", "N", "bad", "range")]), root="R")
    assert cat.part("R")["status"] == "not_replaceable"
    assert cat.serial(10)["applicable_parts"] == 0
    assert any(d.code == "ignored_invalid_serial_range" for d in cat.diagnostics)


@pytest.mark.parametrize("serial", [-1, 2.5, "2500", True, None])
def test_engine_accepts_only_nonnegative_integer_values(serial_catalogue, serial):
    # HTTP string parsing belongs to Phase 3; this checks the engine boundary.
    with pytest.raises(ValueError, match="nonnegative integer"):
        serial_catalogue.serial(serial)
