import pytest

from trade_machine.cba_rules import FIRST_APRON, SECOND_APRON
from trade_machine.models import Player, Team
from trade_machine.trade import (
    TradeResult,
    check_team,
    execute_trade,
    fmt_money,
    validate_trade,
)

M = 1_000_000


# --- Helpers to build fake data -----------------------------------------------------

def p(player_id: int, salary: int) -> Player:
    return Player(player_id=player_id, name=f"Player {player_id}", position="G", age=25, salary=salary)


def make_team(abbr: str, payroll: int, tradeable: list[Player], first_filler_id: int,
              roster_size: int = 13) -> Team:
    """Team containing `tradeable` players plus filler players so that the
    total payroll is exactly `payroll` and the roster has `roster_size` players."""
    remaining = payroll - sum(x.salary for x in tradeable)
    n_fillers = roster_size - len(tradeable)
    assert remaining >= 0 and n_fillers >= 1
    fillers = [p(first_filler_id + i, remaining // n_fillers) for i in range(n_fillers)]
    # Put any leftover dollars on the first filler so the total is exact.
    fillers[0] = p(first_filler_id, remaining // n_fillers + remaining % n_fillers)
    team = Team(abbr=abbr, players=tradeable + fillers)
    assert team.payroll() == payroll
    return team


# --- fmt_money --------------------------------------------------------------------------

@pytest.mark.parametrize("amount, expected", [
    (50_300_000, "$50.3M"),
    (29_096_000, "$29.096M"),
    (27_500_000, "$27.5M"),
    (209_015_000, "$209.015M"),
    (20_000_000, "$20M"),
    (750_000, "$750,000"),
    (0, "$0"),
    (-5_000_000, "-$5M"),
])
def test_fmt_money(amount, expected):
    assert fmt_money(amount) == expected


# --- check_team: matching (R0, R1, R2) -----------------------------------------------

def test_T1_below_apron_within_max_passes():
    team = make_team("AAA", 180 * M, [p(1, 20 * M)], 100)
    assert check_team(team, [p(1, 20 * M)], [p(2, 27 * M)]) == []


def test_T2_below_apron_over_max_fails():
    # Max for 20M outgoing is 29,096,000. 29.2M is $104,000 over.
    team = make_team("AAA", 180 * M, [p(1, 20 * M)], 100)
    reasons = check_team(team, [p(1, 20 * M)], [p(2, 29_200_000)])
    assert len(reasons) == 1
    assert "exceeds max $29.096M" in reasons[0]
    assert "over by $104,000" in reasons[0]


def test_R1_exact_max_passes_and_one_dollar_over_fails():
    team = make_team("AAA", 180 * M, [p(1, 20 * M)], 100)
    assert check_team(team, [p(1, 20 * M)], [p(2, 29_096_000)]) == []
    assert len(check_team(team, [p(1, 20 * M)], [p(2, 29_096_001)])) == 1


def test_T3_ends_over_first_apron_taking_back_more_fails():
    # Post = 205 - 20 + 25 = 210M > 209.015M. 25M would pass R1, so this proves R2.
    team = make_team("AAA", 205 * M, [p(1, 20 * M)], 100)
    reasons = check_team(team, [p(1, 20 * M)], [p(2, 25 * M)])
    assert len(reasons) == 1
    assert "over the first apron" in reasons[0]


def test_R2_ending_exactly_at_first_apron_passes():
    payroll = FIRST_APRON - 5 * M          # post = payroll - 20M + 25M = FIRST_APRON
    team = make_team("AAA", payroll, [p(1, 20 * M)], 100)
    assert check_team(team, [p(1, 20 * M)], [p(2, 25 * M)]) == []


def test_R2_one_dollar_over_first_apron_fails():
    payroll = FIRST_APRON - 5 * M + 1
    team = make_team("AAA", payroll, [p(1, 20 * M)], 100)
    assert len(check_team(team, [p(1, 20 * M)], [p(2, 25 * M)])) == 1


def test_T4_over_apron_equal_salary_passes():
    team = make_team("AAA", 215 * M, [p(1, 20 * M)], 100)
    assert check_team(team, [p(1, 20 * M)], [p(2, 20 * M)]) == []


def test_over_apron_one_dollar_more_fails():
    team = make_team("AAA", 215 * M, [p(1, 20 * M)], 100)
    assert len(check_team(team, [p(1, 20 * M)], [p(2, 20 * M + 1)])) == 1


def test_T8_taking_back_less_passes():
    team = make_team("AAA", 160 * M, [p(1, 30 * M)], 100)
    assert check_team(team, [p(1, 30 * M)], [p(2, 10 * M)]) == []


# --- check_team: aggregation (R3) -------------------------------------------------------

def test_T5_aggregation_below_second_apron_passes():
    out = [p(1, 10 * M), p(2, 10 * M)]
    team = make_team("AAA", 215 * M, out, 100)
    assert check_team(team, out, [p(3, 19 * M)]) == []


def test_T6_aggregation_just_below_second_apron_passes():
    out = [p(1, 10 * M), p(2, 10 * M)]
    team = make_team("AAA", 220 * M, out, 100)
    assert check_team(team, out, [p(3, 19 * M)]) == []


def test_T7_aggregation_over_second_apron_fails():
    out = [p(1, 10 * M), p(2, 10 * M)]
    team = make_team("AAA", 225 * M, out, 100)
    reasons = check_team(team, out, [p(3, 19 * M)])
    assert len(reasons) == 1                    # only R3: taking back less, so matching passes
    assert "second apron" in reasons[0]


def test_aggregation_ending_exactly_at_second_apron_passes():
    out = [p(1, 10 * M), p(2, 10 * M)]
    team = make_team("AAA", SECOND_APRON + 1 * M, out, 100)   # post = +1M - 20M + 19M
    assert check_team(team, out, [p(3, 19 * M)]) == []


def test_single_player_over_second_apron_is_not_aggregation():
    team = make_team("AAA", 230 * M, [p(1, 20 * M)], 100)
    assert check_team(team, [p(1, 20 * M)], [p(2, 19 * M)]) == []


def test_R2_and_R3_can_both_fail():
    out = [p(1, 10 * M), p(2, 10 * M)]
    team = make_team("AAA", 220 * M, out, 100)     # post = 225M
    reasons = check_team(team, out, [p(3, 25 * M)])
    assert len(reasons) == 2


# --- check_team: roster size (R4) ---------------------------------------------------------

def test_R4_two_for_one_into_full_roster_fails():
    team = make_team("AAA", 150 * M, [p(1, 10 * M)], 100, roster_size=15)
    reasons = check_team(team, [p(1, 10 * M)], [p(2, 5 * M), p(3, 5 * M)])
    assert len(reasons) == 1
    assert "16 players" in reasons[0]


def test_R4_ending_at_exactly_15_passes():
    team = make_team("AAA", 150 * M, [p(1, 10 * M)], 100, roster_size=14)
    assert check_team(team, [p(1, 10 * M)], [p(2, 5 * M), p(3, 5 * M)]) == []


# --- validate_trade -------------------------------------------------------------------------

@pytest.fixture
def two_teams():
    """TOR-like team below the first apron, OKC-like team above it."""
    tor = make_team("TOR", 180 * M, [p(1, 20 * M), p(2, 8 * M), p(3, 2 * M)], 100)
    okc = make_team("OKC", 215 * M, [p(51, 27 * M), p(52, 20 * M)], 200)
    return tor, okc


def test_V1_both_pass(two_teams):
    tor, okc = two_teams
    # TOR: out 20M, in 20M. OKC: out 20M, in 20M.
    assert validate_trade(tor, okc, [1], [52]) == TradeResult(True, [])


def test_V2_one_team_fails_prefixed(two_teams):
    tor, okc = two_teams
    # TOR: out 28M, in 27M -> passes.
    # OKC: out 27M, in 28M, ends at 216M (over first apron) -> FAIL (R2).
    result = validate_trade(tor, okc, [1, 2], [51])
    assert result.valid is False
    assert len(result.reasons) == 1
    assert result.reasons[0].startswith("OKC: ")


def test_V3_both_fail():
    # TOR: out 5M, in 20M, max 10.25M -> FAIL (R1).
    # OKC: full 15-man roster, sends 1 and gets 2 -> 16 players -> FAIL (R4).
    tor = make_team("TOR", 180 * M, [p(1, 3 * M), p(2, 2 * M)], 100)
    okc = make_team("OKC", 215 * M, [p(51, 20 * M)], 200, roster_size=15)
    result = validate_trade(tor, okc, [1, 2], [51])
    assert result.valid is False
    assert len(result.reasons) == 2
    assert result.reasons[0].startswith("TOR: ")
    assert result.reasons[1].startswith("OKC: ")


def test_V4_player_not_on_team(two_teams):
    tor, okc = two_teams
    result = validate_trade(tor, okc, [51], [52])     # 51 is on OKC, not TOR
    assert result.valid is False
    assert result.reasons == ["TOR: player id 51 is not on TOR"]


def test_empty_side_is_invalid(two_teams):
    tor, okc = two_teams
    result = validate_trade(tor, okc, [1], [])
    assert result.reasons == ["OKC: must send at least one player"]


def test_duplicate_id_is_invalid(two_teams):
    tor, okc = two_teams
    result = validate_trade(tor, okc, [1, 1], [52])
    assert result.reasons == ["TOR: player id 1 is listed more than once"]


@pytest.mark.parametrize("bad_id", ["1", 1.0, None, True])
def test_non_int_id_is_invalid(two_teams, bad_id):
    tor, okc = two_teams
    result = validate_trade(tor, okc, [bad_id], [52])
    assert result.valid is False
    assert "not a whole number" in result.reasons[0]


def test_ids_not_a_list_is_invalid(two_teams):
    tor, okc = two_teams
    result = validate_trade(tor, okc, 1, [52])
    assert result.valid is False


def test_same_team_both_sides(two_teams):
    tor, _ = two_teams
    result = validate_trade(tor, tor, [1], [2])
    assert result.valid is False


# --- execute_trade ---------------------------------------------------------------------------

def test_V5_originals_unchanged(two_teams):
    tor, okc = two_teams
    tor_before, okc_before = tor.payroll(), okc.payroll()
    tor_players, okc_players = list(tor.players), list(okc.players)
    execute_trade(tor, okc, [1], [52])
    assert tor.payroll() == tor_before and okc.payroll() == okc_before
    assert tor.players == tor_players and okc.players == okc_players



def test_V6_V7_payroll_and_player_count(two_teams):
    tor, okc = two_teams
    new_tor, new_okc = execute_trade(tor, okc, [1], [51])     # TOR out 20M in 27M; OKC out 27M in 20M
    assert new_tor.payroll() == tor.payroll() - 20 * M + 27 * M
    assert new_okc.payroll() == okc.payroll() - 27 * M + 20 * M
    assert len(new_tor.players) + len(new_okc.players) == len(tor.players) + len(okc.players)
    assert new_tor.payroll() + new_okc.payroll() == tor.payroll() + okc.payroll()


def test_players_moved_to_correct_teams(two_teams):
    tor, okc = two_teams
    new_tor, new_okc = execute_trade(tor, okc, [1], [51])
    tor_ids = {x.player_id for x in new_tor.players}
    okc_ids = {x.player_id for x in new_okc.players}
    assert 51 in tor_ids and 1 not in tor_ids
    assert 1 in okc_ids and 51 not in okc_ids
    assert new_tor.abbr == "TOR" and new_okc.abbr == "OKC"


def test_execute_invalid_trade_raises(two_teams):
    tor, okc = two_teams
    with pytest.raises(ValueError, match="invalid trade"):
        execute_trade(tor, okc, [3], [51])   # TOR out 2M, in 27M