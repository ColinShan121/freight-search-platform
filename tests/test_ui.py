from html.parser import HTMLParser

from fastapi.testclient import TestClient

from freight_search.main import app


class SearchPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = {}
        self.form = None
        self.buttons = {}
        self.labels = set()
        self.options = {}
        self.select = None
        self.links = []
        self.ids = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            assert attrs["id"] not in self.ids
            self.ids[attrs["id"]] = attrs
        if tag == "a":
            self.links.append(attrs)
        if tag == "form":
            self.form = attrs["id"]
            self.forms[self.form] = {}
        if tag in ("input", "select", "textarea"):
            self.forms[self.form][attrs.get("name")] = attrs
        if tag == "button" and "id" in attrs:
            self.buttons[attrs["id"]] = attrs
        if tag == "label":
            self.labels.add(attrs.get("for"))
        if tag == "select":
            self.select = (self.form, attrs["name"])
            self.options[self.select] = set()
        if tag == "option":
            self.options[self.select].add(attrs["value"])

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None
        if tag == "form":
            self.form = None


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
    assert set(page.forms) == {"search-form", "create-form"}
    search = page.forms["search-form"]
    create = page.forms["create-form"]
    assert set(search) == {"q", "origin", "destination", "equipment_type", "status"}
    assert set(create) == {"origin", "destination", "cargo_description", "equipment_type", "status"}
    assert all(control["id"] in page.labels for controls in page.forms.values() for control in controls.values())
    for form_id in page.forms:
        assert page.options[(form_id, "equipment_type")] == {"", "dry_van", "refrigerated", "flatbed"}
    assert page.options[("search-form", "status")] == {"", "available", "booked", "delivered"}
    assert page.options[("create-form", "status")] == {"available", "booked", "delivered"}
    assert search["q"]["maxlength"] == "200"
    for name, limit in (("origin", "120"), ("destination", "120"), ("cargo_description", "2000")):
        assert create[name]["maxlength"] == limit
    assert all("required" in control for control in create.values())
    assert {"clear-filters", "previous-page", "next-page", "create-submit"} <= page.buttons.keys()
    for name in ("clear-filters", "previous-page", "next-page"):
        assert page.buttons[name]["type"] == "button"
    assert "disabled" in page.buttons["previous-page"]
    assert "disabled" in page.buttons["next-page"]
    assert "Local portfolio demonstration" in response.text
    hrefs = {link["href"] for link in page.links}
    assert {"#main-content", "#search-section", "#add-listing"} <= hrefs
    for href in hrefs:
        if href.startswith("#"):
            assert href[1:] in page.ids
    assert page.ids["main-content"]["tabindex"] == "-1"
    assert "https://github.com/ColinShan121/freight-search-platform" in hrefs
    assert "Find your next freight load" in response.text
    for name in ("message", "create-message"):
        assert page.ids[name]["role"] == "status"
        assert page.ids[name]["aria-live"] == "polite"
