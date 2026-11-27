"""The hub: its guard (host, key, header), the JSON API over a scratch store and work folder, jobs, and previews."""
import json
import re
import time

import pytest

pytest.importorskip("starlette")
pytest.importorskip("multipart")

from starlette.testclient import TestClient  # noqa: E402

from panko import hub, pipeline, work  # noqa: E402
from panko.hub import api, preview  # noqa: E402
from panko.hub.jobs import Jobs  # noqa: E402
from panko.store import Store  # noqa: E402

TOKEN = "test-token"
H = {"X-Panko": "1"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(work, "PAGES", tmp_path / "pages")
    db = tmp_path / "t.db"
    monkeypatch.setattr(api, "_store", lambda: Store(db))
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setattr(api, "media_dirs", lambda: [media])
    monkeypatch.setattr(hub, "uploads_dir", lambda: tmp_path / "uploads")
    s = Store(db)
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "برّا", "tl": "berra", "gloss": "outside",
           "pos": "adverb", "examples": [{"ar": "الدراري كيلعبو برّا.", "tl": "d-drari kayl3bu berra.",
                                          "en": "The kids are playing outside."}]}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "كاس", "tl": "kas", "gloss": "glass",
           "pos": "noun"}, status="candidate")
    s.put({"id": "dw-3", "kind": "word", "variety": "darija", "ar": "زربوط", "tl": "zerbut", "gloss": "spinning top",
           "pos": "noun", "tags": ["panko::doubtful"]}, status="candidate")
    s.put({"id": "dw-4", "kind": "word", "variety": "darija", "ar": "<b>x</b><script>alert(1)</script>", "tl": "x",
           "gloss": '<img src=x onerror="alert(1)">', "pos": "noun"}, status="candidate")
    api.JOBS = Jobs()
    c = TestClient(hub.app(TOKEN), base_url="http://127.0.0.1:8770")
    c.get(f"/?t={TOKEN}", follow_redirects=False)
    return c, s, tmp_path


def wait(c, job, limit=20):
    for _ in range(limit * 20):
        j = c.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.05)
    raise AssertionError(f"job {job['id']} still {j['status']}")


# ---- the guard

def test_guard_needs_the_key_a_local_host_and_the_header(env):
    c, _, _ = env
    bare = TestClient(hub.app(TOKEN), base_url="http://127.0.0.1:8770")
    assert bare.get("/api/meta").status_code == 401
    assert bare.get("/").status_code == 401 and "panko hub" in bare.get("/").text
    assert bare.get("/media/x.jpg").status_code == 401                       # media need the key too
    assert bare.get("/?t=wrong", follow_redirects=False).status_code == 401
    r = bare.get(f"/?t={TOKEN}", follow_redirects=False)
    assert r.status_code == 303 and "httponly" in r.headers["set-cookie"].lower() \
        and "samesite=strict" in r.headers["set-cookie"].lower()
    assert bare.get("/api/meta").status_code == 200                          # the cookie now carries the key
    evil = TestClient(hub.app(TOKEN), base_url="http://evil.example:8770")
    assert evil.get(f"/?t={TOKEN}", follow_redirects=False).status_code == 403   # DNS rebinding
    assert c.post("/api/entries/reject", json={"ids": ["dw-2"]}).status_code == 403   # no X-Panko header
    assert c.post("/api/entries/reject", json={"ids": ["dw-2"]}, headers=H).status_code == 200


def test_index_names_its_assets_by_version(env):
    c, _, _ = env
    page = c.get("/").text
    assert "/static/app.js?v=" in page and "/static/app.css?v=" in page
    assert c.get("/static/app.js").status_code == 200


# ---- entries

def test_entries_filter_search_and_flags(env):
    c, _, _ = env
    r = c.get("/api/entries?status=candidate").json()
    assert r["total"] == 3 and {x["id"] for x in r["rows"]} == {"dw-2", "dw-3", "dw-4"}
    assert [x["id"] for x in c.get("/api/entries?status=candidate&flag=doubtful").json()["rows"]] == ["dw-3"]
    assert [x["id"] for x in c.get("/api/entries?status=all&q=glass").json()["rows"]] == ["dw-2"]
    assert [x["id"] for x in c.get("/api/entries?status=all&q=برا").json()["rows"]] == ["dw-1"]   # shadda ignored
    assert c.get("/api/entries?status=active&flag=no-example").json()["total"] == 0
    assert c.get("/api/entries/nope").status_code == 404
    # what a card has, for the filter: the opposite of what it lacks, on every card shown
    rows = c.get("/api/entries?status=all").json()
    for f in ("picture", "example"):
        has = c.get(f"/api/entries?status=all&flag=has-{f}").json()["rows"]
        assert len(has) == rows["flags"].get(f"has-{f}", 0) and all(f"no-{f}" not in x["flags"] for x in has)
    assert rows["flags"].get("has-audio", 0) + rows["flags"].get("no-audio", 0) == rows["total"]


def test_edit_only_editable_fields(env):
    c, s, _ = env
    r = c.patch("/api/entries/dw-2", json={"fields": {"gloss": "glass, cup", "tags": ["topic::kitchen"]}}, headers=H)
    assert r.status_code == 200 and s.get("dw-2")["gloss"] == "glass, cup"
    assert c.patch("/api/entries/dw-2", json={"fields": {"status": "active"}}, headers=H).status_code == 400
    assert c.patch("/api/entries/dw-2", json={"fields": {"MyNotes": "x"}}, headers=H).status_code == 400
    assert s.get("dw-2")["status"] == "candidate"


def test_activate_reject_restore(env):
    c, s, _ = env
    assert c.post("/api/entries/activate", json={"ids": ["dw-2", "dw-3"]}, headers=H).json()["activated"] == ["dw-2", "dw-3"]
    assert "panko::doubtful" not in s.get("dw-3")["tags"]                       # naming it clears the doubt
    r = c.post("/api/entries/reject", json={"ids": ["dw-1", "dw-4"]}, headers=H).json()
    assert r == {"retired": ["dw-4"], "skipped": ["dw-1"]}                       # active cards aren't rejected here
    assert c.post("/api/entries/restore", json={"ids": ["dw-4"]}, headers=H).json()["restored"] == ["dw-4"]
    assert s.get("dw-4")["status"] == "candidate"


def test_preview_is_sandboxed_and_media_inline(env, monkeypatch):
    c, s, tmp = env
    from panko.media import audio  # one voice whose audio isn't made yet, whatever keys this machine has
    monkeypatch.setattr(audio, "voice_count", lambda variety: 1)
    monkeypatch.setattr(audio, "speak", lambda text, variety, prefix="_panko_", slot=0, dry=None:
                        audio.Voiced(f"{prefix}test_{slot}.mp3", "not generated yet"))
    (tmp / "media" / "pic.jpg").write_bytes(b"\xff\xd8jpeg")
    s.put({**s.get("dw-1"), "image": {"file": "pic.jpg", "credit": "test"}})
    p = c.get("/api/entries/dw-1/preview").json()
    assert "cards" in p, p
    assert [x["name"] for x in p["cards"]] and "front" not in p["cards"][0]
    r = c.get("/api/entries/dw-1/preview?side=back&card=0&theme=dark")
    assert r.headers["content-type"].startswith("text/html")
    assert "sandbox allow-scripts" in r.headers["content-security-policy"]
    assert "default-src 'none'" in r.text and "data:image/jpeg;base64," in r.text and 'src="pic.jpg"' not in r.text
    assert "nightMode" in r.text
    assert "audio on sync" in r.text                                           # no clip yet: no dead player


def test_preview_fill_follows_anki_rules():
    f = {"A": "x", "B": "", "Audio": "[sound:a.mp3]"}
    assert preview.fill("{{#A}}yes{{/A}}{{#B}}no{{/B}}{{^B}}empty{{/B}}", f) == "yesempty"
    assert preview.fill("{{type:A}}", f).startswith("<input")
    assert "pk-play" in preview.fill("{{Audio}}", f, have=lambda n: True)
    assert preview.fill("{{Audio}}{{Audio}}", f, have=lambda n: False) == preview.LATER
    assert preview._empty("<div> </div><script>x()</script>") and not preview._empty("<img src=x>")


def test_media_serves_only_plain_names(env):
    c, _, tmp = env
    (tmp / "media" / "a.mp3").write_bytes(b"ID3")
    assert c.get("/media/a.mp3").content == b"ID3"
    assert c.get("/media/..%2Ft.db").status_code in (400, 404)
    assert c.get("/media/.hidden").status_code == 400
    assert c.get("/media/missing.mp3").status_code == 404


# ---- sources, jobs, paid steps

def test_add_source_by_upload_then_read_a_unit_and_ingest(env, monkeypatch):
    c, s, tmp = env
    r = c.post("/api/upload", files=[("files", ("lesson 1.txt", "كاس\nبرّا\n".encode(), "text/plain"))], headers=H)
    path = r.json()["path"]
    assert path.endswith("lesson-1.txt") and str(tmp) in path
    src = c.post("/api/sources", json={"path": path, "kind": "lesson", "title": "Lesson 1"}, headers=H).json()
    assert src["units"] == 1
    lst = c.get("/api/sources").json()["sources"]
    assert lst[0]["title"] == "Lesson 1" and lst[0]["todo"] == 1
    u = c.get(f"/api/sources/{src['id']}/units/c001").json()
    assert "كاس" in u["text"] and u["state"] == "todo"
    item = {"kind": "word", "ar": "زيت", "tl": "zit", "gloss": "oil", "pos": "noun",
            "verdict": {"verdict": "ok", "summary": "fine"}, "picture": {"choice": "skip"}}
    assert work.submit(src["id"], "c001", {"items": [item]})["ok"]
    from panko import checks, evidence
    monkeypatch.setattr(checks, "morph_for", lambda v: None)
    monkeypatch.setattr(evidence, "_hits", lambda ar, tl="": [])
    j = wait(c, c.post(f"/api/sources/{src['id']}/ingest", json={}, headers=H).json()["job"])
    assert j["status"] == "done" and j["result"]["new"] == 1
    assert any(e["ar"] == "زيت" for e in s.entries("candidate"))


def test_paid_run_estimates_first_and_runs_only_when_confirmed(env, monkeypatch):
    c, _, tmp = env
    t = tmp / "l.txt"
    t.write_text("x")
    sid = c.post("/api/sources", json={"path": str(t), "title": "L"}, headers=H).json()["id"]
    ran = []
    monkeypatch.setattr(pipeline, "estimate", lambda sid, units, n: {"units": ["c001"], "usd": 0.4, "usd_batch": 0.2})
    monkeypatch.setattr(pipeline, "run", lambda sid, units, n, **kw: ran.append(kw) or
                        {"done": ["c001"], "waiting": [], "failed": [], "spent": 0.3})
    r = c.post(f"/api/sources/{sid}/run", json={"n": 1}, headers=H).json()
    assert r == {"estimate": {"units": ["c001"], "usd": 0.4, "usd_batch": 0.2}} and not ran
    j = wait(c, c.post(f"/api/sources/{sid}/run", json={"n": 1, "confirm": True, "budget": 0.6, "batch": True},
                       headers=H).json()["job"])
    assert j["status"] == "done" and j["paid"] and ran[0]["budget"] == 0.6 and ran[0]["batch"] is True
    assert "spent $0.30" in j["log"][-1]


def test_sync_needs_confirm(env):
    c, _, _ = env
    r = c.post("/api/sync", json={}, headers=H)
    assert r.status_code == 400 and "confirm" in r.json()["error"]


def test_jobs_capture_output_and_failures():
    jobs = Jobs()

    def ok(job):
        print("hello from the job")
        return 42
    a = jobs.submit("t", "ok", ok)
    b = jobs.submit("t", "bad", lambda job: 1 / 0)
    for _ in range(100):
        if a.status == "done" and b.status == "failed":
            break
        time.sleep(0.02)
    assert a.result == 42 and "hello from the job" in a.log
    assert b.error.startswith("ZeroDivisionError") and any("Traceback" in x for x in b.log)


def test_overview_and_meta(env):
    c, _, _ = env
    o = c.get("/api/overview").json()
    assert o["counts"]["darija"]["candidate"] == 3 and o["counts"]["darija"]["doubtful"] == 1
    assert any("inbox" in s["text"] for s in o["steps"])
    m = c.get("/api/meta").json()
    assert m["config"], m
    assert m["config"] and any(v["name"] == "darija" for v in m["varieties"])


# ---- card design, picture choices, voices, tags

@pytest.fixture
def cfg(tmp_path, monkeypatch):
    from panko import config
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "panko.toml").write_text(
        '[learner]\nlanguage = "Moroccan Arabic"\nvarieties = ["darija"]\n\n[images]\nchain = ["commons", "generate"]\n')
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    config.settings.cache_clear()
    yield tmp_path
    config.settings.cache_clear()


def test_card_design_previews_saves_and_resets(env, cfg):
    c, _, _ = env
    d = c.get("/api/design").json()
    assert d["design"] == d["default"] and "extra1" in d["slots"]
    draft = {**d["design"], "word_back": ["word", "gloss", "extra1"], "extras": [{"slot": "extra1", "label": "Mnemonic"}]}
    r = c.post("/api/design/preview", json={"design": draft, "id": "dw-1", "side": "back"}, headers=H)
    assert r.status_code == 200 and r.headers["x-panko-entry"] == "dw-1" and "Recognition" in r.headers["x-panko-cards"]
    assert "Your mnemonic for this card." in r.text and "sandbox" in r.headers["content-security-policy"]
    assert c.get("/api/design").json()["design"] == d["default"]            # a preview saves nothing
    r = c.post("/api/design", json={"design": draft}, headers=H).json()
    assert r["design"]["extras"] == [{"slot": "extra1", "label": "Mnemonic"}]
    assert "Mnemonic" in (cfg / "config" / "hub.toml").read_text()
    assert c.post("/api/design", json={"reset": True}, headers=H).json()["design"] == d["default"]


def test_picture_choices(env, cfg):
    c, _, _ = env
    p = c.get("/api/pictures/prefs").json()
    assert p["drawings"] and [x["name"] for x in p["providers"] if x["on"]] == ["commons", "generate"]
    assert c.post("/api/pictures/prefs", json={"chain": ["nonsense"]}, headers=H).status_code == 400
    assert c.post("/api/pictures/prefs", json={"quality": "ultra"}, headers=H).status_code == 400
    p = c.post("/api/pictures/prefs", json={"chain": ["wikidata", "commons"], "quality": "medium",
                                            "rules": ["no text", " "]}, headers=H).json()
    assert not p["drawings"] and p["quality"] == "medium" and p["rules"] == ["no text"]


def test_voices_without_a_key_say_so(env, cfg):
    c, _, _ = env
    v = c.get("/api/voices").json()
    assert v["ready"] is False and v["chosen"] == {"darija": []} and v["voices"] == []


def test_cards_by_tag_and_tags_in_search(env):
    c, s, _ = env
    s.put({**s.get("dw-2"), "tags": ["topic::food"]})
    r = c.get("/api/entries?status=all&tag=topic::food").json()
    assert [x["id"] for x in r["rows"]] == ["dw-2"] and ["topic::food", 1] in r["tags"]
    assert [x["id"] for x in c.get("/api/entries?status=all&q=food").json()["rows"]] == ["dw-2"]


def test_no_picture_leaves_the_queue_and_can_be_undone(env, monkeypatch):
    c, s, tmp = env
    from panko.media import choose
    monkeypatch.setattr(choose, "decisions_path", lambda: tmp / "decisions.json")
    s.put({**s.get("dw-1"), "tags": ["topic::religion"]})
    before = c.get("/api/pictures?status=active").json()
    assert "dw-1" in before["ids"] and ["topic::religion", 1] in before["tags"]
    assert c.post("/api/pictures/none", json={"ids": ["dw-1", "nope"]}, headers=H).json()["changed"] == ["dw-1"]
    after = c.get("/api/pictures?status=active").json()
    assert "dw-1" not in after["ids"] and after["none"] == 1
    assert "no-picture" not in c.get("/api/entries?status=active").json()["rows"][0]["flags"]
    c.post("/api/pictures/none", json={"ids": ["dw-1"], "undo": True}, headers=H)
    assert "dw-1" in c.get("/api/pictures?status=active").json()["ids"]


def test_drawings_are_made_from_the_hub_price_first(env, monkeypatch):
    c, s, tmp = env
    import json

    from panko.media import pictures
    from panko.providers import imagegen
    monkeypatch.setattr(api, "_drawings_file", lambda: tmp / "drawings.json")
    (tmp / "drawings.json").write_text(json.dumps({"dw-2": "a glass of tea", "dw-3": "a spinning top", "gone": "x"}))
    monkeypatch.setattr(imagegen.Generate, "ready", lambda self: False)
    st = c.get("/api/pictures?status=candidate").json()
    assert st["drawings_waiting"] == 2 and st["draw_ready"] is False and "llm_ready" in st
    r = c.post("/api/pictures/draw", json={}, headers=H)
    assert r.status_code == 400 and "OPENAI_API_KEY" in r.json()["error"]            # no key: says which one
    monkeypatch.setattr(imagegen.Generate, "ready", lambda self: True)
    est = c.post("/api/pictures/draw", json={}, headers=H).json()["estimate"]
    assert est["cards"] == 2 and "usd" not in est and "usd_per_image" in est["price"]  # no price set: none invented
    drawn = []
    monkeypatch.setattr(pictures, "draw", lambda todo, store=None: drawn.append(dict(todo)) or {k: "f.jpg" for k in todo})
    from panko import config
    real = config.settings
    monkeypatch.setattr(config, "settings", lambda: {**real(), "images": {**real().get("images", {}), "generate": {
        **real().get("images", {}).get("generate", {}), "usd_per_image": 0.05}}})
    assert c.post("/api/pictures/draw", json={}, headers=H).json()["estimate"]["usd"] == 0.1
    j = c.post("/api/pictures/draw", json={"confirm": True, "budget": 0.07}, headers=H).json()["job"]
    assert wait(c, j)["status"] == "done" and len(drawn[0]) == 1                       # the budget pays for one


def test_sources_from_before_the_queue_are_listed_with_their_cards(env):
    c, s, _ = env
    s.add_source("deck-x", "deck", "Anki deck: X", trust=30)
    s.add_sighting("dw-2", "deck-x", "mentioned")
    known = c.get("/api/sources").json()["known"]
    assert {"id": "deck-x", "kind": "deck", "title": "Anki deck: X", "date": "", "trust": 30, "entries": 1,
            "queued": False} in known
    assert [x["id"] for x in c.get("/api/entries?status=all&source=deck-x").json()["rows"]] == ["dw-2"]


def test_retired_cards_say_why_and_duplicates_point_both_ways(env):
    c, s, _ = env
    assert c.post("/api/entries/reject", json={"ids": ["dw-2"]}, headers=H).json()["retired"] == ["dw-2"]
    assert s.get("dw-2")["retired_why"] == "rejected in the inbox"
    s.put({"id": "dw-9", "kind": "word", "variety": "darija", "ar": "برا", "tl": "berra", "gloss": "outside",
           "merged_into": "same as dw-1 برّا"}, status="retired")
    d = c.get("/api/entries/dw-9").json()
    assert d["kept"]["id"] == "dw-1" and d["duplicates"] == []
    assert [x["id"] for x in c.get("/api/entries/dw-1").json()["duplicates"]] == ["dw-9"]
    s.add_source("deck-x", "deck", "Anki deck: X")
    s.add_sighting("dw-9", "deck-x", "mentioned")
    assert "Anki deck: X" in [x["title"] for x in c.get("/api/entries/dw-1").json()["sightings"]]
    ids = lambda st: [r["id"] for r in c.get(f"/api/entries?status={st}").json()["rows"]]  # noqa: E731
    assert ids("rejected") == ["dw-2"] and ids("duplicate") == ["dw-9"] and ids("retired") == ["dw-2"]
    assert c.get("/api/entries?status=all").json()["rows"][-1]["status"] == "duplicate"
    counts = c.get("/api/overview").json()["counts"]["darija"]
    assert (counts["rejected"], counts["duplicate"], counts["retired"]) == (1, 1, 2)
    assert c.post("/api/entries/restore", json={"ids": ["dw-9"]}, headers=H).json()["restored"] == []
    c.post("/api/entries/restore", json={"ids": ["dw-2"]}, headers=H)
    assert "retired_why" not in s.get("dw-2") and s.get("dw-2")["status"] == "candidate"


def test_a_second_source_with_the_same_title_keeps_the_first(env):
    c, _, tmp = env
    a, b = tmp / "a.txt", tmp / "b.txt"
    a.write_text("x")
    b.write_text("y")
    one = c.post("/api/sources", json={"path": str(a), "title": "Lesson 1"}, headers=H).json()
    two = c.post("/api/sources", json={"path": str(b), "title": "Lesson 1"}, headers=H).json()
    assert (one["id"], two["id"]) == ("lesson-1", "lesson-1-2")
    assert "llm_ready" in c.get("/api/sources/lesson-1").json()
    r = c.post("/api/sources", json={"path": str(tmp), "title": "a folder"}, headers=H)
    assert r.status_code == 400 and "photos of pages" in r.json()["error"]


def test_setup_needs_a_language(env):
    c, _, _ = env
    r = c.post("/api/setup", json={"answers": {"language": "  "}}, headers=H)
    assert r.status_code == 400 and "language" in r.json()["error"]


def test_a_rejected_word_seen_again_stays_rejected_and_a_duplicate_counts_for_the_card_kept(env, monkeypatch):
    c, s, tmp = env
    from panko import checks, evidence
    monkeypatch.setattr(checks, "morph_for", lambda v: None)
    monkeypatch.setattr(evidence, "_hits", lambda ar, tl="": [])
    c.post("/api/entries/reject", json={"ids": ["dw-2"]}, headers=H)                       # كاس kas, rejected
    s.put({"id": "dw-9", "kind": "word", "variety": "darija", "ar": "زيت", "tl": "zit", "gloss": "oil", "pos": "noun",
           "merged_into": "same as dw-1 برّا"}, status="retired")
    t = tmp / "l2.txt"
    t.write_text("x")
    sid = c.post("/api/sources", json={"path": str(t), "title": "Lesson 2"}, headers=H).json()["id"]
    ok = {"verdict": {"verdict": "ok", "summary": "fine"}, "picture": {"choice": "skip"}}
    items = [{"kind": "word", "ar": "كاس", "tl": "kas", "gloss": "glass", "pos": "noun", **ok},
             {"kind": "word", "ar": "زيت", "tl": "zit", "gloss": "oil", "pos": "noun", **ok}]
    assert work.submit(sid, "c001", {"items": items})["ok"]
    rep = work.ingest_source(sid, s)
    assert rep["new"] == 0 and [x["id"] for x in rep["rejected_again"]] == ["dw-2"]
    assert s.get("dw-2")["status"] == "retired"
    assert not any(e["ar"] in ("كاس", "زيت") for e in s.entries("candidate"))
    seen = {r["entry_id"] for r in s.db.execute("SELECT entry_id FROM sightings WHERE source_id = ?", (sid,))}
    assert seen == {"dw-2", "dw-1"}


def test_the_flag_list_counts_only_flags_some_card_has(env):
    c, s, _ = env
    s.put({**s.get("dw-2"), "check": {"morph": [{"field": "ar", "text": "كاس", "problem": "pos"}]}})
    flags = c.get("/api/entries?status=candidate").json()["flags"]
    assert flags["check"] == 1 and flags["doubtful"] == 1 and "in-anki" not in flags


def test_share_as_a_file_makes_a_package_to_download(env, monkeypatch):
    pytest.importorskip("anki")
    c, _, tmp = env
    from panko.anki import apkg
    from panko.media import audio
    monkeypatch.setattr(apkg, "MEDIA_DIRS", [])
    monkeypatch.setattr(audio, "speak", lambda *a, **k: None)
    monkeypatch.setattr(api, "exports_dir", lambda: tmp / "exports")
    j = wait(c, c.post("/api/export/apkg", json={"varieties": ["darija"]}, headers=H).json()["job"])
    assert j["status"] == "done" and j["result"]["notes"] == 1, j
    r = c.get(f"/export/file/{j['result']['name']}")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and len(r.content) > 100
    assert c.get("/export/file/..%2Fpanko.db").status_code == 404


def test_cards_filter_by_words_or_phrases(env):
    c, s, _ = env
    s.put({"id": "dp-1", "kind": "phrase", "variety": "darija", "ar": "لا باس", "tl": "labas", "gloss": "fine"},
          status="candidate")
    ids = lambda k: {r["id"] for r in c.get(f"/api/entries?status=candidate&kind={k}").json()["rows"]}  # noqa: E731
    assert ids("phrase") == {"dp-1"} and "dp-1" not in ids("word") and len(ids("")) == 4


def test_preview_drops_audio_not_made_yet():
    """Audio that can't be inlined would fail to load in the sandbox (and be reported); it shows as made-on-sync."""
    from panko.cards.render import say_button
    from panko.hub import preview as P
    ok = P.PLAY.format(src="data:audio/mpeg;base64,AA")
    out = P.inline_images(ok + "<p>x</p>" + say_button(["a.mp3", "b.mp3"]) + P.PLAY.format(src="c.mp3"), [])
    assert out.startswith(ok) and out.count(P.LATER) == 2
    assert not re.search(r'<audio[^>]*src="(?!data:)', out)


def test_clash_choices_are_yours_and_fine_groups_stay_out(env, monkeypatch):
    """Per-card choices save marked as yours; a fine group leaves the list; apply makes a same-word inbox card a
    duplicate of the kept one and leaves keep choices in the file."""
    from panko import clashes
    c, s, tmp = env
    path = tmp / "work" / "clashes.json"
    monkeypatch.setattr(api, "_clash_path", lambda: path)
    s.put({"id": "dw-5", "kind": "word", "variety": "darija", "ar": "قدح", "tl": "qde7", "gloss": "glass, cup"},
          status="candidate")
    s.put({"id": "dw-6", "kind": "word", "variety": "darija", "ar": "خارج", "tl": "kharij", "gloss": "outside"},
          status="candidate")
    d = c.get("/api/clashes").json()
    assert d["total"] == 2 and d["undecided"] == 2
    glass = next(g for g in d["groups"] if g["sense"] == "glass")
    out = next(g for g in d["groups"] if g["sense"] == "outside")
    assert c.post("/api/clashes/choose", json={"id": "dw-5", "choice": "same", "same": "dw-5"}, headers=H).status_code == 400
    assert c.post("/api/clashes/choose", json={"id": "dw-5", "choice": "same", "same": "dw-2"},
                  headers=H).json()["decision"] == {"same": "dw-2", "drop": "the same word as dw-2", "by": "you"}
    c.post("/api/clashes/choose", json={"id": "dw-2", "choice": "keep"}, headers=H)
    assert c.get("/api/clashes").json()["undecided"] == 1          # the model is asked only about the other group
    # the model's suggestions never replace yours
    assert clashes.merge(clashes.load(path), {"dw-5": {"gloss": "cup"}, "dw-6": {"gloss": "out"}})["dw-5"]["by"] == "you"
    assert c.post("/api/clashes/fine", json={"key": out["key"]}, headers=H).json()["fine"] == 1
    assert [g["sense"] for g in c.get("/api/clashes").json()["groups"]] == ["glass"]
    r = c.post("/api/clashes/apply", json={}, headers=H).json()
    assert r["duplicates"] == 1 and s.get("dw-5")["status"] == "retired"
    assert s.get("dw-5")["merged_into"].startswith("same as dw-2") and [x["id"] for x in s.duplicates_of("dw-2")] == ["dw-5"]
    assert clashes.load(path) == {"dw-2": {"keep": True, "by": "you"}}
    c.post("/api/clashes/fine", json={"key": out["key"], "undo": True}, headers=H)
    assert glass["key"] == "dw-2|dw-5" and c.get("/api/clashes").json()["total"] == 1


def test_mode_shows_chat_after_a_tool_call_and_api_by_key(env, monkeypatch):
    """The status bar's mode: chat counts as connected after a recent Panko tool call; API mode needs a model."""
    from panko import modes, providers
    c, _, _ = env
    monkeypatch.setattr(providers, "chain", lambda kind: [])
    m = c.get("/api/overview").json()["modes"]
    assert m == {"chat": {"last": "", "ago": None, "active": False}, "api": {"ready": False, "provider": "", "model": ""}}
    monkeypatch.setattr(modes, "_last_write", 0.0)
    modes.mark_chat("panko_sources")
    m = c.get("/api/overview").json()["modes"]
    assert m["chat"]["active"] and m["chat"]["ago"] < 5
    assert c.get("/api/setup").json().get("modes", m)["chat"]["active"]


def test_choose_a_photo_yourself(env, monkeypatch):
    """A free search for one card, then the photo you click goes on the card and is kept as your decision."""
    c, s, tmp = env
    from panko.media import choose, pictures
    monkeypatch.setattr(choose, "decisions_path", lambda: tmp / "decisions.json")
    monkeypatch.setattr(api, "_chosen_dir", lambda: tmp / "chosen")
    monkeypatch.setattr(pictures, "_media", lambda: tmp / "media")
    asked = []
    monkeypatch.setattr(pictures, "candidates", lambda q, per_provider=6, errors=None: asked.append(q) or [
        {"thumb": f"https://pics.example/{i}.jpg", "title": f"pic {i}", "author": "A", "license": "CC BY 4.0",
         "provider": "commons", "page": f"https://pics.example/{i}"} for i in range(3)])
    monkeypatch.setattr(pictures, "_download", lambda cand, path: path.write_bytes(b"\xff\xd8" + cand["thumb"].encode()))
    r = c.get("/api/pictures/candidates?id=dw-1").json()
    assert asked == ["outside"] and len(r["candidates"]) == 3 and r["chosen"] is None
    assert c.post("/api/pictures/choose", json={"id": "dw-1", "dir": "/etc", "index": 0}, headers=H).status_code == 400
    got = c.post("/api/pictures/choose", json={"id": "dw-1", "dir": r["dir"], "index": 2}, headers=H).json()
    e = s.get("dw-1")
    assert e["image"]["file"] == got["image"]["file"] and (tmp / "media" / e["image"]["file"]).exists()
    assert "CC BY 4.0" in e["image"]["credit"]
    assert choose.load_decisions(tmp / "decisions.json")["dw-1"] == {"photo": {"dir": r["dir"], "index": 2}, "by": "you"}
    # changing it later gives the file a new name, so Anki takes the new picture
    again = c.post("/api/pictures/choose", json={"id": "dw-1", "dir": r["dir"], "index": 1}, headers=H).json()
    assert again["image"]["file"] != got["image"]["file"]
    rows = c.get("/api/pictures?status=active").json()["decisions"]
    assert rows[0]["id"] == "dw-1" and rows[0]["file"] == again["image"]["file"] and rows[0]["by"] == "you"
    # the model's sheet comes first next time: the chooser opens on it
    assert c.get("/api/pictures/candidates?id=dw-1").json()["chosen"] == 1


def test_search_photos_for_every_card_free(env, monkeypatch):
    """Search all: every card waiting gets its photos searched in the background (no model, no spend); the chooser
    then opens on them without searching again, and a second search-all skips them."""
    c, s, tmp = env
    from panko.media import choose, pictures
    monkeypatch.setattr(choose, "decisions_path", lambda: tmp / "decisions.json")
    monkeypatch.setattr(api, "_chosen_dir", lambda: tmp / "chosen")
    monkeypatch.setattr(api, "_photo_sources", lambda: {"ready": ["commons"], "need_key": ["pexels"]})
    asked = []
    monkeypatch.setattr(pictures, "candidates", lambda q, per_provider=6, errors=None: asked.append(q) or [
        {"thumb": f"https://pics.example/{q}.jpg", "title": q, "provider": "commons"}])
    before = c.get("/api/pictures?status=active").json()
    assert before["searched"] == 0 and before["todo"] > 0 and before["sources"]["need_key"] == ["pexels"]
    j = wait(c, c.post("/api/pictures/search", json={"status": "active"}, headers=H).json()["job"])
    assert j["status"] == "done", (j["error"], j["log"])
    assert not j["paid"] and j["result"]["searched"] == before["todo"]
    assert "pexels left out" in "".join(j["log"])
    after = c.get("/api/pictures?status=active").json()
    assert after["searched"] == after["todo"] and all(x["searched"] == 1 for x in after["cards"])
    n = len(asked)
    r = c.get("/api/pictures/candidates?id=dw-1").json()
    assert len(asked) == n and r["from"] == "searched earlier" and r["query"] == "outside"
    assert c.post("/api/pictures/search", json={"status": "active"}, headers=H).status_code == 400   # nothing left
    # a photo from a kept search can be chosen
    monkeypatch.setattr(pictures, "_media", lambda: tmp / "media")
    monkeypatch.setattr(pictures, "_download", lambda cand, path: path.write_bytes(b"\xff\xd8"))
    assert c.post("/api/pictures/choose", json={"id": "dw-1", "dir": r["dir"], "index": 0}, headers=H).json()["image"]



def test_a_photo_site_that_fails_is_named_and_its_cards_searched_again(env, monkeypatch):
    """Wikimedia refusing (403) must not leave cards with only the other sites' photos for good."""
    c, s, tmp = env
    from panko.media import choose, pictures
    monkeypatch.setattr(choose, "decisions_path", lambda: tmp / "decisions.json")
    monkeypatch.setattr(api, "_chosen_dir", lambda: tmp / "chosen")
    monkeypatch.setattr(api, "_photo_sources", lambda: {"ready": ["commons", "openverse"], "need_key": []})
    down = {"on": True}

    def search(q, per_provider=6, errors=None):
        if down["on"] and errors is not None:
            errors["commons"] = "Client error '403 Forbidden'"
        return [{"thumb": "https://pics.example/o.jpg", "provider": "openverse"}]
    monkeypatch.setattr(pictures, "candidates", search)
    j = wait(c, c.post("/api/pictures/search", json={"status": "active"}, headers=H).json()["job"])
    assert j["result"]["searched"] == 0 and j["result"]["sites_failed"] == ["commons"]
    assert "Wikimedia Commons failed: Client error '403" in "".join(j["log"])
    assert c.get("/api/pictures?status=active").json()["searched"] == 0
    assert c.get("/api/pictures/candidates?id=dw-1").json()["failed"] == ["Wikimedia Commons"]
    down["on"] = False
    j = wait(c, c.post("/api/pictures/search", json={"status": "active", "again": True}, headers=H).json()["job"])
    assert j["result"]["failed"] == 0 and j["result"]["searched"] >= 1


def test_wikimedia_gets_a_name_it_accepts():
    """Wikimedia answers 403 to a vague name from a server: Panko's carries a way to reach its authors."""
    from panko import USER_AGENT
    from panko.providers.images import web
    assert "github.com/" in USER_AGENT and web.UA["User-Agent"] == USER_AGENT



def test_select_all_gets_every_match_and_its_doubtful_ones(env):
    """The inbox's "select all N": every card the filters match, on every page, and which are doubtful."""
    c, s, _ = env
    d = c.get("/api/entries?status=candidate&ids=1").json()
    assert set(d["ids"]) == {"dw-2", "dw-3", "dw-4"} and d["doubtful"] == ["dw-3"] and d["total"] == 3
    assert c.get("/api/entries?status=candidate&flag=doubtful&ids=1").json()["ids"] == ["dw-3"]
    assert c.get("/api/entries?status=candidate&q=glass&ids=1").json()["ids"] == ["dw-2"]


def test_examples_page_lists_what_needs_one(env):
    c, s, _ = env
    d = c.get("/api/examples?status=candidate").json()
    assert d["todo"] == 3 and d["other"] == 0 and {x["id"] for x in d["cards"]} == {"dw-2", "dw-3", "dw-4"}
    assert ["panko::doubtful", 1] in d["tags"]
    assert c.get("/api/examples?status=candidate&tag=panko::doubtful").json()["todo"] == 1
    assert c.get("/api/examples").json()["todo"] == 0          # dw-1 has one
    r = c.post("/api/examples", json={"status": "candidate", "ids": ["dw-2"]}, headers=H)
    assert r.status_code in (200, 400)                         # an estimate, or why the model isn't ready; nothing spent
    assert not s.get("dw-2").get("examples")


# ---- jobs across restarts

def _restart(path):
    """What a restart leaves: the file, read by a new hub."""
    api.JOBS = Jobs(path)
    return api.JOBS


def test_a_paid_job_cut_off_by_a_restart_is_priced_again_before_it_resumes(env, monkeypatch):
    c, _, tmp = env
    path = tmp / "jobs.json"
    api.JOBS = Jobs(path)
    t = tmp / "l.txt"
    t.write_text("x")
    sid = c.post("/api/sources", json={"path": str(t), "title": "L"}, headers=H).json()["id"]
    ran = []
    monkeypatch.setattr(pipeline, "estimate", lambda sid, units, n: {"units": ["c001"], "usd": 0.4, "usd_batch": 0.2})
    monkeypatch.setattr(pipeline, "run", lambda sid, units, n, **kw: ran.append(kw) or
                        {"done": ["c001"], "waiting": [], "failed": [], "spent": 0.3})
    j = wait(c, c.post(f"/api/sources/{sid}/run", json={"n": 1, "confirm": True, "budget": 0.6}, headers=H).json()["job"])
    rows = json.loads(path.read_text())
    assert rows[0]["id"] == j["id"] and rows[0]["replay"]["handler"] == "run_source" and rows[0]["replay"]["path"] == {"sid": sid}
    rows[0]["status"] = "running"                                   # the server stopped halfway through
    path.write_text(json.dumps(rows))
    _restart(path)
    old = c.get(f"/api/jobs/{j['id']}").json()
    assert old["status"] == "interrupted" and old["resumable"] and "restart" in old["log"][-1]
    assert api.resume_interrupted() == []                           # paid: never by itself
    r = c.post(f"/api/jobs/{j['id']}/resume", json={}, headers=H).json()
    assert "estimate" in r and len(ran) == 1                        # the old yes isn't reused
    new = wait(c, c.post(f"/api/jobs/{j['id']}/resume", json={"confirm": True, "budget": 0.5}, headers=H).json()["job"])
    assert new["status"] == "done" and ran[-1]["budget"] == 0.5
    assert c.get(f"/api/jobs/{j['id']}").json()["resumed_as"] == new["id"]
    assert c.post(f"/api/jobs/{j['id']}/resume", json={}, headers=H).status_code == 400


def test_a_free_job_cut_off_by_a_restart_carries_on_by_itself_once(env, monkeypatch):
    c, _, tmp = env
    path = tmp / "jobs.json"
    monkeypatch.setitem(api.HANDLERS, "fake_free", lambda req: api._start("fake", "Fake", lambda job: req.body["x"]))
    replay = {"handler": "fake_free", "path": {}, "query": {}, "body": {"x": 7}}
    path.write_text(json.dumps([
        {"id": "a1", "kind": "fake", "title": "Fake", "status": "running", "started": 1.0, "created": 1.0, "replay": replay},
        {"id": "a2", "kind": "fake", "title": "Fake", "status": "queued", "created": 2.0, "replay": {**replay, "resumed": 1}},
        {"id": "a3", "kind": "fake", "title": "Paid", "status": "running", "created": 3.0, "paid": True, "replay": replay},
        {"id": "a4", "kind": "fake", "title": "Old", "status": "done", "created": 0.5, "log": ["fine"]}]))
    jobs = _restart(path)
    started = api.resume_interrupted()
    assert len(started) == 1 and jobs.get("a1").resumed_as == started[0]
    assert wait(c, {"id": started[0]})["result"] == 7
    assert jobs.get("a2").resumable() and jobs.get("a3").resumable()   # cut off twice / paid: they wait for you
    assert jobs.get("a4").status == "done" and jobs.get("a4").log == ["fine"]
    again = _restart(path)                                            # and all of it is still there after another
    assert again.get("a1").resumed_as == started[0] and again.get(started[0]).status == "done"
