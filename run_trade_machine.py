"""run_trade_machine.py

Terminal front end for the trade_machine package. No rules live here:
this file only reads input, prints rosters, and asks trade.py for a verdict.

Put this file in the project root (next to main.py, not inside trade_machine/).
Run it with:  python run_trade_machine.py
or right-click it in PyCharm -> Run.
"""

from pathlib import Path

from trade_machine.cba_rules import FIRST_APRON, SECOND_APRON
from trade_machine.loader import load_all_teams
from trade_machine.models import Team
from trade_machine.trade import execute_trade, fmt_money, validate_trade

TEAMS_DIR = Path(__file__).parent / "data" / "teams"


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def ask_team(prompt: str, teams: dict[str, Team], taken: str | None = None) -> Team:
    """Keep asking until the user types a team abbr that has a CSV."""
    options = ", ".join(sorted(teams))
    while True:
        abbr = input(f"{prompt} ({options}): ").strip().upper()
        if abbr not in teams:
            print(f"  '{abbr}' is not a team with a CSV in data/teams. Try again.")
        elif abbr == taken:
            print("  A team can't trade with itself. Pick a different team.")
        else:
            return teams[abbr]


def ask_player_ids(team: Team) -> list[int]:
    """Read comma-separated player_ids for one side of the trade.

    Only catches typos (text that isn't a number, or an id that isn't on
    this roster) so the user can retype. Everything else, like an empty side
    or a repeated id, goes to validate_trade so your rules decide it.
    """
    on_roster = {p.player_id for p in team.players}
    while True:
        raw = input(f"\nPlayer IDs {team.abbr} sends (comma-separated, e.g. 3,7): ").strip()
        tokens = [t.strip() for t in raw.split(",") if t.strip()]

        not_numbers = [t for t in tokens if not t.isdigit()]
        if not_numbers:
            print(f"  Not a player_id: {', '.join(not_numbers)}. Use numbers only.")
            continue

        ids = [int(t) for t in tokens]
        not_here = [str(i) for i in ids if i not in on_roster]
        if not_here:
            print(f"  Not on the {team.abbr} roster: {', '.join(not_here)}. Try again.")
            continue

        return ids


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def apron_status(payroll: int) -> str:
    if payroll > SECOND_APRON:
        return "over 2nd apron"
    if payroll > FIRST_APRON:
        return "over 1st apron"
    return "below 1st apron"


def print_roster(team: Team) -> None:
    line = "-" * 52
    print(f"\n{team.abbr} ROSTER")
    print(f"{'player_id':<11}{'name':<27}{'salary':>14}")
    print(line)
    for p in sorted(team.players, key=lambda p: p.player_id):
        print(f"{p.player_id:<11}{p.name:<27}{p.salary:>14,}")
    print(line)
    print(f"{'':<11}{'Payroll':<27}{team.payroll():>14,}")
    print(f"{'':<11}{'Status':<27}{apron_status(team.payroll()):>14}")


def print_proposal(team1: Team, ids1: list[int], team2: Team, ids2: list[int]) -> None:
    def side(team: Team, ids: list[int]) -> str:
        players = [team.get_player(i) for i in dict.fromkeys(ids)]  # dedupe for display only
        if not players:
            return "nobody"
        names = ", ".join(p.name for p in players)
        return f"{names} ({fmt_money(sum(p.salary for p in players))})"

    print("\nPROPOSED TRADE")
    print(f"  {team1.abbr} sends: {side(team1, ids1)}")
    print(f"  {team2.abbr} sends: {side(team2, ids2)}")


def print_payroll_change(before: Team, after: Team) -> None:
    print(f"  {before.abbr}: {fmt_money(before.payroll())} -> {fmt_money(after.payroll())} "
          f"({apron_status(after.payroll())}), {len(after.players)} players")


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def run_one_trade(teams: dict[str, Team]) -> None:
    team1 = ask_team("Enter team 1", teams)
    team2 = ask_team("Enter team 2", teams, taken=team1.abbr)

    print_roster(team1)
    print_roster(team2)

    ids1 = ask_player_ids(team1)
    ids2 = ask_player_ids(team2)
    print_proposal(team1, ids1, team2, ids2)

    result = validate_trade(team1, team2, ids1, ids2)

    print()
    if result.valid:
        print("Trade Successful")
        new1, new2 = execute_trade(team1, team2, ids1, ids2)
        print_payroll_change(team1, new1)
        print_payroll_change(team2, new2)
    else:
        print("Trade Invalid")
        for reason in result.reasons:
            print(f"  - {reason}")


def main() -> None:
    try:
        teams = load_all_teams(TEAMS_DIR)
    except (FileNotFoundError, ValueError) as err:
        print(f"Could not load team data: {err}")
        return

    if len(teams) < 2:
        print(f"Need at least two team CSVs in {TEAMS_DIR}, found {len(teams)}.")
        return

    print("=== NBA TRADE MACHINE (2026-27 rules) ===")
    try:
        while True:
            # Every trade starts from the CSV rosters. A successful trade is
            # not saved, so rosters reset each time.
            run_one_trade(teams)
            if input("\nTry another trade? (y/n): ").strip().lower() != "y":
                break
            print()
    except (KeyboardInterrupt, EOFError):
        print()
    print("Trade Machine Shutdown")


if __name__ == "__main__":
    main()