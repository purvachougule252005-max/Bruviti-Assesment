from pathlib import Path

from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient
import pytest

from parttrace import CatalogueDataError
from parttrace.api import create_app, get_catalogue


@pytest.fixture
def client():
    # HTTP transport stays in-process; the autouse socket blocker stays active.
    app = create_app(Path(__file__).parent / "fixtures" / "appendix_q", root="AS-1")
    with TestClient(app) as connection:
        yield connection


def test_health_exact_body_and_status(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"] == "application/json"


def test_appendix_validation_over_http(client):
    response = client.get("/api/validation")
    assert response.status_code == 200
    assert response.json() == {"parts": 4, "ready": 2, "missing": 1, "not_replaceable": 1}
    assert all(type(v) is int for v in response.json().values())


@pytest.mark.parametrize("spelling", ["FA-9", "fa-9", "Fa-9", "%20fa-9%20"])
def test_part_contract_and_case_insensitive_matching(client, spelling):
    response = client.get(f"/api/parts/{spelling}")
    assert response.status_code == 200
    assert response.json() == {
        "part_number": "FA-9", "description": "...", "revision": "B", "status": "ready",
        "total_quantity": 10, "parents": ["AS-1", "AS-2"], "children": [],
    }
    assert type(response.json()["total_quantity"]) is int


@pytest.mark.parametrize("spelling", ["FA-9", "fa-9", "Fa-9", "%20fa-9%20"])
def test_paths_contract_order_and_case_insensitive_matching(client, spelling):
    response = client.get(f"/api/parts/{spelling}/paths")
    assert response.status_code == 200
    assert response.json() == {"part_number": "FA-9", "paths": [["AS-1", "AS-2", "FA-9"], ["AS-1", "FA-9"]]}


def test_null_fields_are_present_for_missing_part(client):
    response = client.get("/api/parts/EL-5")
    assert response.status_code == 200
    assert response.json() == {
        "part_number": "EL-5", "description": None, "revision": None,
        "status": "missing", "total_quantity": 2, "parents": ["AS-2"], "children": [],
    }


def test_root_and_sorted_direct_children(client):
    response = client.get("/api/parts/AS-1")
    assert response.status_code == 200
    assert response.json() == {
        "part_number": "AS-1", "description": "Example machine", "revision": "A",
        "status": "not_replaceable", "total_quantity": 1, "parents": [],
        "children": [{"part_number": "AS-2", "quantity": 2}, {"part_number": "FA-9", "quantity": 4}],
    }
    children = client.get("/api/parts/AS-2").json()["children"]
    assert children == [{"part_number": "EL-5", "quantity": 1}, {"part_number": "FA-9", "quantity": 3}]
    assert all(type(c["quantity"]) is int for c in children)
    assert client.get("/api/parts/AS-1/paths").json() == {"part_number": "AS-1", "paths": [["AS-1"]]}


@pytest.mark.parametrize("number", ["OUT", "out", "UNKNOWN"])
@pytest.mark.parametrize("suffix", ["", "/paths"])
def test_both_part_endpoints_exclude_outside_and_unknown_parts(export, number, suffix):
    directory = export(
        bom=[("R", "X", 2), ("OUT", "X", 99)],
        master=[("OUT", "A", "outside"), ("X", "A", "inside")], service=[("OUT", "Y")],
    )
    with TestClient(create_app(directory, root="R")) as client:
        response = client.get(f"/api/parts/{number}{suffix}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Part not found in machine"}
        assert client.get("/api/parts/X").json()["parents"] == ["R"]


@pytest.mark.parametrize("serial,value", [("2500", 2500), ("0002500", 2500), ("0", 0), ("100000000000000000000", 10**20)])
def test_serial_exact_contract_and_integer_types(client, serial, value):
    response = client.get(f"/api/serial/{serial}")
    assert response.status_code == 200
    assert response.json() == {"serial": value, "applicable_parts": 2}
    assert type(response.json()["serial"]) is int
    assert type(response.json()["applicable_parts"]) is int


@pytest.mark.parametrize("serial", ["2.5", "2500.0", "1e3", "abc", "NaN", "Infinity", "-1", "%2B2500", "%202500", "２５００"])
def test_invalid_serial_returns_422(client, serial):
    response = client.get(f"/api/serial/{serial}")
    assert response.status_code == 422
    assert response.json() == {"detail": "Serial must contain only ASCII digits (0-9)"}


def test_serial_bounds_and_no_range_over_http(export):
    directory = export(bom=[("R", "A", 10)], master=[("R", "A", "root"), ("A", "A", "part")],
                       service=[("R", "Y"), ("A", "Y", 10, 20)])
    with TestClient(create_app(directory, root="R")) as client:
        for serial, expected in [(9, 1), (10, 2), (20, 2), (21, 1)]:
            response = client.get(f"/api/serial/{serial}")
            assert response.status_code == 200
            assert response.json() == {"serial": serial, "applicable_parts": expected}


@pytest.mark.parametrize("route", ["/health", "/api/validation", "/api/parts/R", "/api/parts/R/paths", "/api/serial/1"])
def test_requests_without_completed_startup_are_not_ready(export, route):
    app = create_app(export(), root="R")
    # Omitting the context manager intentionally skips ASGI startup here.
    with TestClient(app) as started:
        assert started.get("/health").status_code == 200
    with TestClient(app, raise_server_exceptions=True) as restarted:
        assert restarted.get("/health").status_code == 200
    client = TestClient(app)
    try:
        response = client.get(route)
        assert response.status_code == 503
        assert response.json() == {"detail": "Catalogue is not ready"}
    finally:
        client.close()


def test_bad_data_aborts_startup_and_never_publishes_partial_catalogue(export):
    directory = export(bom=[("R", "X", 2), ("R", "X", 3)])
    app = create_app(directory, root="R")
    with pytest.raises(CatalogueDataError, match="Conflicting quantities"):
        with TestClient(app):
            pytest.fail("Startup unexpectedly succeeded")
    assert app.state.catalogue is None


def test_requests_use_one_snapshot_and_next_startup_reloads(export):
    directory = export(master=[("R", "A", "original")])
    app = create_app(directory, root="R")
    with TestClient(app) as client:
        snapshot = app.state.catalogue
        export(master=[("R", "B", "replacement")])
        assert client.get("/api/parts/R").json()["description"] == "original"
        assert client.get("/api/validation").status_code == 200
        assert app.state.catalogue is snapshot
    assert app.state.catalogue is None
    with TestClient(app) as client:
        assert client.get("/api/parts/R").json()["revision"] == "B"


@pytest.mark.parametrize("bad_counts", [
    {"parts": "4", "ready": 2, "missing": 1, "not_replaceable": 1},
    {"parts": 4, "ready": 2, "missing": 1, "not_replaceable": 1, "extra": 99},
    {"parts": True, "ready": 2, "missing": 1, "not_replaceable": 1},
])
def test_response_schema_rejects_engine_contract_regressions(client, bad_counts):
    class BrokenCatalogue:
        def validation(self):
            return bad_counts
    client.app.dependency_overrides[get_catalogue] = lambda: BrokenCatalogue()
    with pytest.raises(ResponseValidationError):
        client.get("/api/validation")


def test_generated_schema_is_local_and_documents_required_nulls(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    part = schema["components"]["schemas"]["PartResponse"]
    assert set(part["required"]) == {"part_number", "description", "revision", "status", "total_quantity", "parents", "children"}
    assert {v["type"] for v in part["properties"]["description"]["anyOf"]} == {"string", "null"}
    assert part["additionalProperties"] is False
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
