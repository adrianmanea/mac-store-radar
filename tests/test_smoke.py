"""M0 smoke tests — scaffold imports, weights spec loads, CLI parses (no live run)."""

from __future__ import annotations

import pytest

from radar import __version__
from radar.__main__ import build_parser
from radar.scoring.weights import load_weights


def test_version_string():
    assert __version__ == "0.1.0"


def test_weights_spec_loads_and_has_required_sections():
    w = load_weights()
    for section in ("gates", "demand", "competition", "gap", "monetization", "buildability"):
        assert section in w, f"weights.json missing {section!r}"
    assert w["version"] == "0.1.0"


def test_cli_version_flag_exits_zero():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0


def test_cli_parses_seed_and_limit():
    args = build_parser().parse_args(["--seed", "a mac", "b mac", "--limit", "10"])
    assert args.seed == ["a mac", "b mac"]
    assert args.limit == 10


def test_cli_bare_seed_flag_is_empty_list():
    # `--seed` with no values -> [] (run layer expands to the default calibration set)
    args = build_parser().parse_args(["--seed"])
    assert args.seed == []
