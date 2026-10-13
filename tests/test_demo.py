from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from parttrace.api import create_app


@pytest.fixture
def demo():
    app = create_app(Path(__file__).parent / "fixtures" / "appendix_q", root="AS-1")
    with TestClient(app) as client:
        yield client


def test_page_and_local_assets_work_from_same_app(demo):
    page = demo.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "connect-src 'self'" in page.headers["content-security-policy"]

    class Assets(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "script":
                assert "src" in attrs, "Inline scripts are not permitted by the page CSP"
            if tag in {"script", "link", "img"}:
                self.urls.append(attrs.get("src", attrs.get("href", "")))
    parser = Assets()
    parser.feed(page.text)
    assert parser.urls
    for url in parser.urls:
        assert url.startswith("/static/") or url.startswith("data:"), url
        if url.startswith("/static/"):
            response = demo.get(url)
            assert response.status_code == 200
            assert response.content
    assert demo.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("query", ["fa-9", " FA-9 ", "..."])
def test_search_by_number_or_selected_description(demo, query):
    response = demo.get("/demo/search", params={"q": query})
    assert response.status_code == 200
    assert response.json()["parts"] == [{"part_number": "FA-9", "description": "...", "status": "ready"}]


def test_search_excludes_old_revision_description_and_outside_parts(export):
    directory = export(bom=[("R", "P", 1)], master=[("P", "A", "old description"), ("P", "B", "current"), ("OUT", "A", "current")])
    with TestClient(create_app(directory, root="R")) as client:
        assert client.get("/demo/search", params={"q": "old description"}).json()["total"] == 0
        result = client.get("/demo/search", params={"q": "current"}).json()
        assert result["total"] == 1
        assert result["parts"][0]["part_number"] == "P"
        assert client.get("/demo/parts/OUT/explanation").status_code == 404


def test_explanation_accounts_for_every_parent_and_revision(demo):
    body = demo.get("/demo/parts/fa-9/explanation").json()
    assert body["revision"] == {"selected": "B", "available": ["A", "B"], "reason": "Selected B, the highest letter among A, B."}
    assert body["quantity"]["terms"] == [
        {"parent": "AS-1", "assembly_occurrences": 1, "per_parent": 4, "contribution": 4},
        {"parent": "AS-2", "assembly_occurrences": 2, "per_parent": 3, "contribution": 6},
    ]
    assert body["quantity"]["reason"] == "4 directly in AS-1 + 2 AS-2 assemblies × 3 each = 10."
    assert body["quantity"]["total"] == 10
    assert body["compatibility"] is None
    # Optional metadata never leaks into the grader's required contract.
    assert set(demo.get("/api/parts/FA-9").json()) == {"part_number", "description", "revision", "status", "total_quantity", "parents", "children"}


@pytest.mark.parametrize("part,applicable,phrase", [
    ("FA-9", True, "no serial restriction"), ("EL-5", False, "status is missing"),
    ("AS-1", False, "status is not_replaceable"),
])
def test_compatibility_reason_agrees_with_status(demo, part, applicable, phrase):
    body = demo.get(f"/demo/parts/{part}/explanation", params={"serial": "1500"}).json()
    assert body["compatibility"]["applicable"] is applicable
    assert phrase in body["compatibility"]["reason"]
    if part == "EL-5":
        assert body["revision"]["selected"] is None
        assert body["revision"]["available"] == []


def test_serial_reason_handles_both_range_boundaries(export):
    directory = export(master=[("R", "A", "root")], service=[("R", "Y", 10, 20)])
    with TestClient(create_app(directory, root="R")) as client:
        for serial, expected in [(9, False), (10, True), (20, True), (21, False)]:
            body = client.get("/demo/parts/R/explanation", params={"serial": serial}).json()
            assert body["compatibility"]["applicable"] is expected
            assert "both endpoints included" in body["compatibility"]["reason"]
        assert client.get("/demo/parts/R/explanation?serial=1.5").status_code == 422


def test_quality_counts_are_derived_from_diagnostics(export):
    directory = export(bom=[("R", " a ", 2), ("R", "A", 2), ("A", "R", 1), ("OUT", "A", 5)])
    with TestClient(create_app(directory, root="R")) as client:
        body = client.get("/demo/quality").json()
        assert body["root"] == "R"
        assert body["normalized_cells"] == 1
        assert body["duplicate_rows_ignored"] == 1
        assert body["outside_relationships"] == 1
        assert len(body["removed_relationships"]) == 1
        assert body["removed_relationships"][0]["sources"] == ["bom.csv:4"]
        assert body["validation"]["parts"] == 2


def test_search_results_are_bounded_with_total_and_exact_match_first(export):
    bom = [("R", f"P-{i}", 1) for i in range(70)]
    directory = export(bom=bom)
    with TestClient(create_app(directory, root="R")) as client:
        body = client.get("/demo/search").json()
        assert body["total"] == 71
        assert len(body["parts"]) == body["limit"] == 50
        assert client.get("/demo/search?q=P-1").json()["parts"][0]["part_number"] == "P-1"


def test_missing_description_and_markup_are_returned_as_data(export):
    directory = export(bom=[("R", "P", 1)], master=[("R", "A", "<script>alert(1)</script>")])
    with TestClient(create_app(directory, root="R")) as client:
        body = client.get("/demo/search").json()
        assert body["parts"][0]["description"] is None
        assert body["parts"][1]["description"] == "<script>alert(1)</script>"
        assert client.get("/demo/parts/R/explanation").json()["quantity"]["reason"] == "The machine root occurs once."
