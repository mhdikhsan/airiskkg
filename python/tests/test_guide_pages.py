"""The user guide at /guide: what it may say, and that it renders what the library holds."""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import threading
import time
import urllib.request

import pytest

from airiskkg.paths import REPO_ROOT

STATIC = REPO_ROOT / "python" / "src" / "airiskkg" / "webapp" / "static"
NEW_FILES = ("guide.html", "guide.js", "guide.css", "guide_content.js")
ROUTES = ("home", "tour", "concepts", "workbench", "walkthrough", "reading", "under-the-hood", "library", "limits", "glossary")
PROSE = STATIC / "guide_content.js"


def _text(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


@pytest.mark.ui
def test_the_guide_is_served_and_the_workbench_links_to_it(client) -> None:
    response = client.get("/guide")
    assert response.status_code == 200
    assert b"guide.js" in response.data
    response.close()
    assert 'href="/guide"' in _text("index.html")


@pytest.mark.ui
def test_every_element_id_the_guide_wires_exists() -> None:
    script = _text("guide.js")
    available = set(re.findall(r'id="([\w-]+)"', _text("guide.html"))) | set(re.findall(r'id: "([\w-]+)"', script))
    assert not set(re.findall(r'\$\("#([\w-]+)"\)', script)) - available


@pytest.mark.ui
def test_the_library_version_starts_with_a_number(client) -> None:
    body = client.get("/api/kb-version").get_json()
    assert re.match(r"\d+\.\d+", body["version"])
    assert body["fingerprint"] and body["loadedOn"]


@pytest.mark.ui
def test_no_count_is_written_into_the_guide() -> None:
    tiles = re.search(r"tiles: \[(.*?)\n  \],", _text("guide_content.js"), re.S).group(1)
    assert not re.search(r"count: \d", tiles)
    assert not re.search(r"\b(34|33|141|30) (motifs|AI risk patterns|roles|controls)\b", _text("guide_content.js"))


@pytest.mark.ui
def test_the_word_pattern_always_names_its_level() -> None:
    bare = re.compile(r"(?<!AI risk )(?<!design )(?<!design-)\bpatterns?\b(?!-based)", re.I)
    hits = [f"{name}: {m.group(0)}" for name in NEW_FILES for m in bare.finditer(_text(name))]
    assert not hits, hits


@pytest.mark.ui
def test_a_finding_is_never_called_confirmed() -> None:
    near = re.compile(r"confirmed\W+(\w+\W+){0,2}finding|finding\W+(\w+\W+){0,2}confirmed", re.I)
    assert not [name for name in NEW_FILES if near.search(_text(name))]


@pytest.mark.ui
@pytest.mark.parametrize("phrase", ["concern", "risk-neutral", "applicability condition", "drawing", "Zhang", "Ikhsan", "\u00b7", "&middot;"])
def test_the_prose_keeps_the_reviewed_wording(phrase) -> None:
    assert phrase.lower() not in PROSE.read_text(encoding="utf-8").lower()


@pytest.mark.ui
def test_the_page_loads_nothing_from_elsewhere_and_no_private_graph() -> None:
    page = _text("guide.html") + _text("guide.css")
    assert not re.search(r"""(src|href)=["']https?:|@import|url\(["']?https?:""", page)
    for name in NEW_FILES:
        assert "example_local" not in _text(name) and "example_UC" not in _text(name)


@pytest.fixture(scope="module")
def served():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app
    from test_canvas_renders import _free_port

    port = _free_port()
    app = create_app(local_examples=False)
    threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, use_reloader=False, threaded=True), daemon=True
    ).start()
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/kb-version", timeout=2)
            break
        except OSError:
            time.sleep(0.5)
    return f"http://127.0.0.1:{port}"

@pytest.fixture(scope="module")
def browser(served):
    import websockets
    from test_canvas_interaction import _Page
    from test_canvas_renders import _browser, _free_port

    binary = _browser()
    if not binary:
        pytest.skip("no Chromium-family browser to drive")
    port = _free_port()
    process = subprocess.Popen(
        [binary, "--headless=new", "--disable-gpu", "--no-sandbox", f"--remote-debugging-port={port}",
         "--window-size=1400,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    loop = asyncio.new_event_loop()

    async def connect():
        tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
        target = next(tab for tab in tabs if tab["type"] == "page")
        handle = _Page(await websockets.connect(target["webSocketDebuggerUrl"], max_size=None))
        await handle.send("Page.enable")
        await handle.send("Runtime.enable")
        await handle.send("Page.addScriptToEvaluateOnNewDocument", {"source": (
            "window.__errors=[];addEventListener('error',e=>__errors.push(e.message));"
            "addEventListener('unhandledrejection',e=>__errors.push(String(e.reason)));")})
        return handle

    handle = loop.run_until_complete(connect())
    yield loop, handle, served
    process.terminate()
    loop.close()


@pytest.mark.browser
class TestGuideInABrowser:
    @staticmethod
    def _open(context, path, ready):
        loop, handle, base = context
        loop.run_until_complete(handle.send("Page.navigate", {"url": base + path}))
        ok = loop.run_until_complete(handle.js(f"""(async () => {{
            for (let i = 0; i < 300; i++) {{
                try {{ if ({ready}) return true; }} catch (e) {{}}
                await new Promise((r) => setTimeout(r, 100));
            }}
            return false;
        }})()"""))
        assert ok, f"{path} never showed {ready}"

    @staticmethod
    def _api(context, path):
        return json.load(urllib.request.urlopen(context[2] + path))

    def test_every_tile_shows_what_the_api_returns(self, browser) -> None:
        self._open(browser, "/guide#/home", "document.querySelector('.g-tile .g-count')")
        loop, handle, _ = browser
        shown = json.loads(loop.run_until_complete(handle.js(
            "JSON.stringify(Object.fromEntries([...document.querySelectorAll('.g-tile .g-count')].map(e=>[e.dataset.count,+e.textContent])))")))
        library, vocabulary = self._api(browser, "/api/library"), self._api(browser, "/api/vocabulary")
        assert shown["motifs"] == library["stats"]["motifs"]
        assert shown["riskPatterns"] == library["stats"]["riskPatterns"]
        assert shown["roles"] == len(vocabulary["roles"])
        assert shown["controls"] == library["stats"]["controls"]
        assert shown["taxonomyEntries"] == library["stats"]["taxonomyEntries"]
        assert loop.run_until_complete(handle.js("__errors.length")) == 0

    def test_every_route_renders_and_history_works(self, browser) -> None:
        loop, handle, _ = browser
        for route in ROUTES:
            self._open(browser, f"/guide#/{route}", "document.querySelector('#guide-main article')")
            assert loop.run_until_complete(handle.js("__errors.join(';')")) == "", route
        self._open(browser, "/guide#/nowhere", "location.hash === '#/home' && document.querySelector('.g-hero')")
        self._open(browser, "/guide#/tour", "document.querySelector('.g-stepper')")
        loop.run_until_complete(handle.js("location.hash = '#/glossary'; 1"))
        time.sleep(0.5)
        loop.run_until_complete(handle.js("history.back(); 1"))
        time.sleep(0.8)
        assert loop.run_until_complete(handle.js("!!document.querySelector('.g-stepper')"))
        loop.run_until_complete(handle.js("history.forward(); 1"))
        time.sleep(0.8)
        assert loop.run_until_complete(handle.js("!!document.querySelector('#guide-glossary-filter')"))

    def test_the_library_tabs_count_the_loaded_library(self, browser) -> None:
        from airiskkg.assessment_runner import knowledge_base_fingerprint

        self._open(browser, "/guide#/library", "document.querySelector('[data-tab=control]')")
        loop, handle, _ = browser
        tabs = json.loads(loop.run_until_complete(handle.js(
            "JSON.stringify(Object.fromEntries([...document.querySelectorAll('[data-tab]')].map(e=>[e.dataset.tab,+e.textContent])))")))
        version = knowledge_base_fingerprint()
        stats = self._api(browser, "/api/library")["stats"]
        assert tabs == {
            "risk": version.risk_patterns, "motif": version.motifs, "role": version.pattern_roles,
            "category": stats["dataCategories"], "control": stats["controls"],
        }
        assert loop.run_until_complete(handle.js("/^Library version \\d/.test(document.querySelector('#guide-library-version').textContent)"))

    @pytest.mark.parametrize("kind, entry, tab, title", [
        ("motif", "RetrievalAugmentedGenerationMotif", "motifs", "Retrieval Augmented Generation"),
        ("risk", "PromptInjectionRiskPattern", "risks", "Prompt injection"),
    ])
    def test_open_in_workbench_lands_on_the_entry(self, browser, kind, entry, tab, title) -> None:
        loop, handle, _ = browser
        self._open(browser, f"/guide#/library/{kind}/{entry}", "document.querySelector('#guide-open-entry')")
        target = loop.run_until_complete(handle.js("document.querySelector('#guide-open-entry').getAttribute('href')"))
        self._open(browser, target, f"document.querySelector('#library-detail, .library-detail').textContent.includes('{title}')")
        assert loop.run_until_complete(handle.js("document.querySelector('.library-tab.active').dataset.libraryTab")) == tab

    @pytest.mark.parametrize("route", ["home", "under-the-hood"])
    def test_a_narrow_window_does_not_scroll_sideways(self, browser, route) -> None:
        loop, handle, _ = browser
        loop.run_until_complete(handle.send("Emulation.setDeviceMetricsOverride", {
            "width": 400, "height": 800, "deviceScaleFactor": 1, "mobile": False}))
        try:
            self._open(browser, f"/guide#/{route}", "document.querySelector('#guide-main article')")
            time.sleep(0.5)
            over = loop.run_until_complete(handle.js("document.documentElement.scrollWidth - window.innerWidth"))
            assert over <= 0, f"{route} overflows by {over}px"
        finally:
            loop.run_until_complete(handle.send("Emulation.clearDeviceMetricsOverride"))
