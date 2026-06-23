"""Keyword-noise filter tests (M9.9)."""

from __future__ import annotations

from radar.pipeline.discover import is_noisy


def test_clean_keywords_pass():
    for kw in ["clipboard manager mac", "android file transfer mac", "video converter mac"]:
        assert not is_noisy(kw)


def test_question_phrasings_rejected():
    for kw in [
        "how to transfer from samsung to mac",
        "where is iphone backup on macbook air",
        "is whatsapp available on mac",
    ]:
        assert is_noisy(kw)


def test_web_community_tokens_rejected():
    assert is_noisy("window manager mac reddit")
    assert is_noisy("notion vs obsidian mac")
    assert is_noisy("screen recorder mac tutorial")


def test_foreign_completions_rejected():
    assert is_noisy("video converter mac kostenlos")  # German
    assert is_noisy("convertisseur pdf mac gratuit")  # French
    assert is_noisy("escáner mac")  # non-ascii


def test_overlong_rejected():
    assert is_noisy("how do i move all my files from my old android to a new mac")


def test_empty_rejected():
    assert is_noisy("")
    assert is_noisy("   ")
