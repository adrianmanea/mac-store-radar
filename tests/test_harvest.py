"""Catalog-harvest tests (seed auto-generation) — pure prefix extraction."""

from __future__ import annotations

from radar.pipeline.discover import prefixes_from_names


def test_frequent_words_become_mac_prefixes():
    names = [
        "Clipboard Manager Pro",
        "Clipboard History",
        "Best Clipboard Tool",
        "Duplicate File Finder",
        "Duplicate Photo Cleaner",
    ]
    out = prefixes_from_names(names, top_words=5, top_bigrams=0)
    assert "clipboard mac" in out
    assert "duplicate mac" in out
    # generic/marketing words filtered
    assert "best mac" not in out
    assert "tool mac" not in out


def test_bigrams_captured():
    names = ["Android File Transfer", "Android File Transfer Tool", "Quick File Transfer"]
    out = prefixes_from_names(names, top_words=0, top_bigrams=5)
    assert "file transfer mac" in out


def test_stopwords_and_mac_tokens_dropped():
    names = ["Best Mac Cleaner", "Your Mac Tool", "MacBook Helper"]
    out = prefixes_from_names(names, top_words=10, top_bigrams=0)
    # 'mac', 'macbook', 'your', 'best', 'tool' all filtered; 'cleaner'/'helper' kept
    assert "cleaner mac" in out
    assert "helper mac" in out
    assert not any(p.startswith(("mac ", "your ", "best ", "tool ")) for p in out)


def test_dedup_and_empty():
    assert prefixes_from_names([]) == []
    out = prefixes_from_names(["Calendar", "Calendar", "Calendar"], top_bigrams=0)
    assert out.count("calendar mac") == 1
