"""Buildability tagging tests (M6.2) — fake Anthropic + fake DB, fully offline."""

from __future__ import annotations

from radar.llm import buildability


class FakeContent:
    def __init__(self, text):
        self.text = text


class FakeResp:
    def __init__(self, text):
        self.content = [FakeContent(text)]


class FakeMessages:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        return FakeResp(self.reply)


class FakeAnthropic:
    def __init__(self, reply):
        self.messages = FakeMessages(reply)


def test_coerce_exact_word():
    assert buildability._coerce("wrapper") == "wrapper"
    assert buildability._coerce("  Integration\n") == "integration"


def test_coerce_word_in_sentence():
    assert buildability._coerce("This is native_complex for sure.") == "native_complex"


def test_coerce_garbage_returns_none():
    assert buildability._coerce("banana") is None
    assert buildability._coerce("") is None


def test_classify_app_passes_prompt_and_model():
    a = FakeAnthropic("wrapper")
    label = buildability.classify_app(a, "Webby", "A wrapper around a website")
    assert label == "wrapper"
    call = a.messages.calls[0]
    assert call["model"] == buildability.HAIKU
    assert "Webby" in call["messages"][0]["content"]


def test_classify_app_uncoercible_returns_none():
    assert buildability.classify_app(FakeAnthropic("dunno"), "X", "y") is None


# --- tag_untagged over a fake DB ------------------------------------------


class FakeQuery:
    def __init__(self, db, table):
        self.db, self.table = db, table

    def select(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def update(self, fields, **k):
        self.db.updates.append(fields)
        return self

    def execute(self):
        if self.table == "apps" and not self.db._update_mode:
            return type("R", (), {"data": self.db.untagged})()
        return type("R", (), {"data": []})()


class FakeDB:
    def __init__(self, untagged):
        self.untagged = untagged
        self.updates = []
        self._update_mode = False

    def table(self, name):
        return FakeQuery(self, name)


def test_tag_untagged_writes_labels():
    db = FakeDB(
        [
            {"app_id": 1, "name": "A", "description": "wrapper over an API"},
            {"app_id": 2, "name": "B", "description": "menu bar thing"},
        ]
    )
    res = buildability.tag_untagged(db, FakeAnthropic("integration"), cap=10)
    assert res == {"seen": 2, "tagged": 2}
    assert all(u["complexity_class"] == "integration" for u in db.updates)
    assert all("complexity_at" in u for u in db.updates)


def test_tag_untagged_skips_uncoercible():
    db = FakeDB([{"app_id": 1, "name": "A", "description": "x"}])
    res = buildability.tag_untagged(db, FakeAnthropic("???"), cap=10)
    assert res == {"seen": 1, "tagged": 0}
    assert db.updates == []
