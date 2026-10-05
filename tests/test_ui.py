from html.parser import HTMLParser

from fastapi.testclient import TestClient

from freight_search.main import app


class SearchPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.controls = {}
        self.labels = set()
        self.options = {}
        self.select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("input", "select"):
            self.controls[attrs.get("name")] = attrs
        if tag == "label":
            self.labels.add(attrs.get("for"))
        if tag == "select":
            self.select = attrs["name"]
            self.options[self.select] = set()
        if tag == "option":
            self.options[self.select].add(attrs["value"])

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None


def test_search_page_without_database(monkeypatch, tmp_path):
    for name in ("HOST", "PORT", "DB", "USER", "PASSWORD"):
        monkeypatch.delenv(f"POSTGRES_{name}", raising=False)
    monkeypatch.chdir(tmp_path)
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    page = SearchPageParser()
    page.feed(response.text)
    assert set(page.controls) == {"q", "origin", "destination", "equipment_type", "status"}
    assert all(control["id"] in page.labels for control in page.controls.values())
    assert page.options["equipment_type"] == {"", "dry_van", "refrigerated", "flatbed"}
    assert page.options["status"] == {"", "available", "booked", "delivered"}
