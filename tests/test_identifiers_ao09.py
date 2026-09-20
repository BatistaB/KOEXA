"""Tests for aoryzae_atlas.identifiers.ao09 (spec section 12)."""
from __future__ import annotations

from aoryzae_atlas.identifiers.ao09 import find_ao09_ids, find_non_ao09_tokens


def test_find_ao09_ids_single():
    assert find_ao09_ids("AO090103000076") == ["AO090103000076"]


def test_find_ao09_ids_multiple_slash_separated():
    text = "prtT prtR AO090003001211/AO090003001212"
    assert find_ao09_ids(text) == ["AO090003001211", "AO090003001212"]


def test_find_ao09_ids_ignores_ao07_prefix():
    # AO07... is a different, non-canonical FungiDB namespace (GeneAliases.txt).
    assert find_ao09_ids("AO070280000026") == []


def test_find_ao09_ids_none_or_empty():
    assert find_ao09_ids(None) == []
    assert find_ao09_ids("") == []


def test_find_ao09_ids_dedup_preserves_order():
    assert find_ao09_ids("AO090003001212 AO090003001211 AO090003001212") == [
        "AO090003001212",
        "AO090003001211",
    ]


def test_find_non_ao09_tokens():
    text = "prtT prtR AO090003001211/AO090003001212"
    assert find_non_ao09_tokens(text) == ["prtT", "prtR"]


def test_find_non_ao09_tokens_none():
    assert find_non_ao09_tokens(None) == []
