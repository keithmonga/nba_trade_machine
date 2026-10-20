"""trade.py

Checks whether a two-team trade is legal under the 2026-27 salary rules
and builds the post-trade rosters. Plain Python only (no pandas).

Rules implemented (see context file Section 4.3):
    R0  Taking back less than or equal to outgoing always passes matching.
    R1  Team ending at or below the first apron: incoming <= max_incoming(outgoing).
    R2  Team ending above the first apron: incoming <= outgoing (100%).
    R3  Team sending 2+ players (aggregating) must end at or below the second apron.
    R4  Team must end with <= MAX_ROSTER players.

Not implemented yet: R5 (cap room), draft picks, cash, trade kickers,
non-guaranteed salary, TPEs, 3-team trades.
"""

from dataclasses import dataclass, field

from trade_machine.cba_rules import (
    FIRST_APRON,
    MAX_ROSTER,
    SECOND_APRON,
    matching_bracket,
    max_incoming,
)
from trade_machine.models import Player, Team


@dataclass
class TradeResult:
    valid: bool
    reasons: list[str] = field(default_factory=list)  # empty if valid; each prefixed with team abbr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_money(amount: int) -> str:
    """50300000 -> '$50.3M', 29096000 -> '$29.096M', 750000 -> '$750,000'.
    Display only. All math stays in whole dollars."""
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount < 1_000_000:
        return f"{sign}${amount:,}"
    millions = f"{amount / 1_000_000:.3f}".rstrip("0").rstrip(".")
    return f"{sign}${millions}M"


def _total_salary(players: list[Player]) -> int:
    return sum(p.salary for p in players)


def _check_id_list(team: Team, ids) -> list[str]:
    """Problems with one side's list of player_ids (empty list = fine)."""
    if not isinstance(ids, (list, tuple)):
        return [f"player ids must be a list, got {type(ids).__name__}"]
    if len(ids) == 0:
        return ["must send at least one player"]

    problems = []
    on_roster = {p.player_id for p in team.players}
    seen = set()
    for pid in ids:
        if isinstance(pid, bool) or not isinstance(pid, int):
            problems.append(f"player id {pid!r} is not a whole number")
            continue
        if pid in seen:
            problems.append(f"player id {pid} is listed more than once")
        elif pid not in on_roster:
            problems.append(f"player id {pid} is not on {team.abbr}")
        seen.add(pid)
    return problems


# ---------------------------------------------------------------------------
# Rules for ONE team
# ---------------------------------------------------------------------------

def check_team(team: Team, outgoing: list[Player], incoming: list[Player]) -> list[str]:
    """Failure reasons for ONE team (empty list = this team passes).
    Reasons are NOT prefixed with the team abbr; validate_trade adds that."""
    out_total = _total_salary(outgoing)
    in_total = _total_salary(incoming)
    post_payroll = team.payroll() - out_total + in_total
    post_roster = len(team.players) - len(outgoing) + len(incoming)

    reasons = []

    # R3: aggregation hard-caps the team at the second apron.
    if len(outgoing) >= 2 and post_payroll > SECOND_APRON:
        reasons.append(
            f"sends {len(outgoing)} players (aggregation) but would end at "
            f"{fmt_money(post_payroll)}, over the second apron ({fmt_money(SECOND_APRON)})"
        )

    # R0 / R1 / R2: salary matching only matters when taking back more.
    if in_total > out_total:
        if post_payroll > FIRST_APRON:
            # R2
            reasons.append(
                f"would end at {fmt_money(post_payroll)}, over the first apron "
                f"({fmt_money(FIRST_APRON)}), so incoming ({fmt_money(in_total)}) "
                f"cannot exceed outgoing ({fmt_money(out_total)})"
            )
        else:
            # R1
            limit = max_incoming(out_total)
            if in_total > limit:
                reasons.append(
                    f"incoming {fmt_money(in_total)} exceeds max {fmt_money(limit)} "
                    f"for {fmt_money(out_total)} outgoing ({matching_bracket(out_total)} rule), "
                    f"over by ${in_total - limit:,}"
                )

    # R4: roster limit.
    if post_roster > MAX_ROSTER:
        reasons.append(f"would have {post_roster} players, over the {MAX_ROSTER}-man limit")

    return reasons


# ---------------------------------------------------------------------------
# Two-team trade
# ---------------------------------------------------------------------------

def validate_trade(team_a: Team, team_b: Team, a_sends: list[int], b_sends: list[int]) -> TradeResult:
    """Check a trade. a_sends / b_sends are lists of player_ids.
    Never raises for bad input: problems come back as reasons."""
    if team_a.abbr == team_b.abbr:
        return TradeResult(False, [f"{team_a.abbr}: a team cannot trade with itself"])

    # Step 1: input problems (bad ids, empty sides). Stop here if any,
    # because the salary math would be meaningless.
    reasons = [f"{team_a.abbr}: {r}" for r in _check_id_list(team_a, a_sends)]
    reasons += [f"{team_b.abbr}: {r}" for r in _check_id_list(team_b, b_sends)]
    if reasons:
        return TradeResult(False, reasons)

    a_out = [team_a.get_player(pid) for pid in a_sends]
    b_out = [team_b.get_player(pid) for pid in b_sends]

    # Step 2: rules for each team. A sends a_out and receives b_out, and vice versa.
    reasons = [f"{team_a.abbr}: {r}" for r in check_team(team_a, a_out, b_out)]
    reasons += [f"{team_b.abbr}: {r}" for r in check_team(team_b, b_out, a_out)]

    return TradeResult(valid=len(reasons) == 0, reasons=reasons)


def execute_trade(team_a: Team, team_b: Team, a_sends: list[int], b_sends: list[int]) -> tuple[Team, Team]:
    """Return NEW Team objects with players swapped. team_a and team_b are not changed.
    Raises ValueError if the trade is not valid."""
    result = validate_trade(team_a, team_b, a_sends, b_sends)
    if not result.valid:
        raise ValueError("invalid trade: " + "; ".join(result.reasons))

    a_ids, b_ids = set(a_sends), set(b_sends)
    a_out = [p for p in team_a.players if p.player_id in a_ids]
    b_out = [p for p in team_b.players if p.player_id in b_ids]

    # Build new lists instead of removing from the originals (trap T8).
    new_a = Team(abbr=team_a.abbr,
                 players=[p for p in team_a.players if p.player_id not in a_ids] + b_out)
    new_b = Team(abbr=team_b.abbr,
                 players=[p for p in team_b.players if p.player_id not in b_ids] + a_out)
    return new_a, new_b