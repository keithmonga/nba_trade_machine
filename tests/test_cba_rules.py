"""Tests for cba_rules.py. Every expected number was calculated by hand
with 2026-27 values: MIDDLE_ADD = 9,096,000, CUSHION = 250,000."""

import pytest

from trade_machine import cba_rules
from trade_machine.cba_rules import (
    CUSHION,
    LOWER_BRACKET,
    MIDDLE_ADD,
    UPPER_BRACKET,
    matching_bracket,
    max_incoming,
)


# --- Constants ---------------------------------------------------------------

def test_thresholds_in_order():
    assert (cba_rules.MIN_TEAM_SALARY < cba_rules.SALARY_CAP < cba_rules.TAX_LEVEL
            < cba_rules.FIRST_APRON < cba_rules.SECOND_APRON)


def test_all_money_constants_are_ints():
    for name in ["SALARY_CAP", "TAX_LEVEL", "FIRST_APRON", "SECOND_APRON",
                 "MIN_TEAM_SALARY", "CUSHION", "MIDDLE_ADD", "LOWER_BRACKET", "UPPER_BRACKET"]:
        assert type(getattr(cba_rules, name)) is int, name


def test_bracket_edges_derived_correctly():
    assert LOWER_BRACKET == 8_846_000
    assert UPPER_BRACKET == 35_384_000


# --- max_incoming: one case per bracket ----------------------------------------

@pytest.mark.parametrize("outgoing, expected", [
    (5_000_000, 10_250_000),     # 200% bracket: 10M + 250K
    (10_000_000, 19_096_000),    # middle: 10M + 9.096M (matches Hoops Rumors example)
    (20_000_000, 29_096_000),    # middle: 20M + 9.096M
    (40_000_000, 50_250_000),    # 125% bracket: 50M + 250K
    (50_300_000, 63_125_000),    # Kawhi: 62.875M + 250K
])
def test_max_incoming_each_bracket(outgoing, expected):
    assert max_incoming(outgoing) == expected


# --- max_incoming: edges ---------------------------------------------------------

def test_lower_edge_formulas_agree():
    # 2 * 8,846,000 + 250,000 == 8,846,000 + 9,096,000 == 17,942,000
    assert max_incoming(LOWER_BRACKET) == 17_942_000


def test_upper_edge_formulas_agree():
    # 35,384,000 * 1.25 + 250,000 == 35,384,000 + 9,096,000 == 44,480,000
    assert max_incoming(UPPER_BRACKET) == 44_480_000


def test_one_dollar_either_side_of_edges():
    assert max_incoming(LOWER_BRACKET - 1) == 17_941_998   # 200%: loses $2 per $1
    assert max_incoming(LOWER_BRACKET + 1) == 17_942_001   # middle: loses $1 per $1
    assert max_incoming(UPPER_BRACKET - 1) == 44_479_999   # middle
    assert max_incoming(UPPER_BRACKET + 1) == 44_480_001   # 125%: 1.25 floored


def test_zero_outgoing():
    assert max_incoming(0) == CUSHION


# --- max_incoming: integer math --------------------------------------------------

def test_returns_int():
    assert type(max_incoming(12_345_678)) is int


def test_125_percent_floors_correctly():
    # 40,000,001 * 1.25 = 50,000,001.25 -> 50,000,001 + 250,000
    assert max_incoming(40_000_001) == 50_250_001
    # 40,000,003 * 1.25 = 50,000,003.75 -> 50,000,003 + 250,000
    assert max_incoming(40_000_003) == 50_250_003


def test_never_decreases():
    # Sending out more salary must never shrink what you can take back.
    previous = max_incoming(0)
    for outgoing in range(0, 60_000_001, 37_331):
        current = max_incoming(outgoing)
        assert current >= previous, outgoing
        previous = current


def test_always_at_least_outgoing():
    for outgoing in [0, 1, 1_357_763, 8_846_000, 35_384_000, 60_000_000]:
        assert max_incoming(outgoing) > outgoing


def test_matches_float_formula_on_safe_values():
    # Values divisible by 4 make 1.25x exact in floats, so the two must match.
    for outgoing in range(0, 60_000_000, 1_000_004):
        assert outgoing % 4 == 0
        expected = max(min(2 * outgoing + CUSHION, outgoing + MIDDLE_ADD),
                       int(1.25 * outgoing) + CUSHION)
        assert max_incoming(outgoing) == expected


# --- max_incoming: bad input -----------------------------------------------------

@pytest.mark.parametrize("bad", [20_000_000.0, "20000000", None, True, False])
def test_rejects_non_int(bad):
    with pytest.raises(TypeError):
        max_incoming(bad)


def test_rejects_negative():
    with pytest.raises(ValueError):
        max_incoming(-1)


# --- matching_bracket --------------------------------------------------------------

def test_bracket_labels():
    assert matching_bracket(5_000_000) == "200% + $250K"
    assert matching_bracket(LOWER_BRACKET) == "200% + $250K"
    assert matching_bracket(LOWER_BRACKET + 1) == f"outgoing + ${MIDDLE_ADD:,}"
    assert matching_bracket(UPPER_BRACKET) == f"outgoing + ${MIDDLE_ADD:,}"
    assert matching_bracket(UPPER_BRACKET + 1) == "125% + $250K"