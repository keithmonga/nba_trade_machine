from pathlib import Path

import pandas as pd

from trade_machine.models import Player, Team

# Every team CSV must have exactly these headers, in this order.
EXPECTED_COLUMNS = ["player_id", "name", "position", "age", "salary"]


# ---------------------------------------------------------------------------
# Cleaning helpers
# ---------------------------------------------------------------------------

def clean_salary(value) -> int:
    """Turn a salary in any common format into whole dollars (int).

    Accepts:  45000000   45000000.0   "45000000"   "$45,000,000"   " $45,000,000 "
    Rejects:  blanks, NaN, negatives, non-whole amounts (45000000.50), junk text.
    """
    # bool is a subclass of int in Python, so True would sneak through as 1.
    if isinstance(value, bool):
        raise ValueError(f"invalid salary: {value!r}")

    if isinstance(value, int):
        number = value

    elif isinstance(value, float):
        if pd.isna(value) or not value.is_integer():
            raise ValueError(f"invalid salary: {value!r}")
        number = int(value)

    elif isinstance(value, str):
        text = value.strip().replace("$", "").replace(",", "").replace(" ", "")
        if text == "":
            raise ValueError("salary is blank")
        # Allow a trailing ".0" / ".00" (e.g. exported from Excel), nothing else.
        if "." in text:
            whole, _, cents = text.partition(".")
            if cents.strip("0") != "":
                raise ValueError(f"salary must be whole dollars: {value!r}")
            text = whole
        if not text.isdigit():
            raise ValueError(f"invalid salary: {value!r}")
        number = int(text)

    else:
        raise ValueError(f"invalid salary: {value!r}")

    if number < 0:
        raise ValueError(f"salary cannot be negative: {value!r}")
    return number


def clean_int(value, column: str) -> int:
    """Turn a plain whole-number cell (player_id, age) into an int."""
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError(f"invalid {column}: {value!r}")
    return int(text)


def clean_text(value, column: str) -> str:
    """Strip whitespace from a text cell and reject blanks."""
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        raise ValueError(f"{column} is blank")
    return text


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_team(path) -> Team:
    """Load one team CSV and return a Team. Team abbr comes from the filename."""
    path = Path(path)
    abbr = path.stem.upper()

    # dtype=str: read every cell as raw text so pandas never guesses a type
    # (no surprise floats). We convert each column ourselves below.
    # utf-8-sig: strips the invisible BOM character Excel puts at the start
    # of the file, which would otherwise turn "player_id" into "﻿player_id".
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)

    columns = [c.strip() for c in df.columns]
    if columns != EXPECTED_COLUMNS:
        raise ValueError(
            f"{path.name}: headers {columns} do not match expected {EXPECTED_COLUMNS}"
        )
    df.columns = columns

    players = []
    seen_ids = set()
    for row_num, row in enumerate(df.itertuples(index=False), start=2):  # row 1 = header
        try:
            player = Player(
                player_id=clean_int(row.player_id, "player_id"),
                name=clean_text(row.name, "name"),
                position=clean_text(row.position, "position").upper(),
                age=clean_int(row.age, "age"),
                salary=clean_salary(row.salary),
            )
        except ValueError as err:
            raise ValueError(f"{path.name} row {row_num}: {err}") from err

        if player.player_id in seen_ids:
            raise ValueError(f"{path.name} row {row_num}: duplicate player_id {player.player_id}")
        seen_ids.add(player.player_id)
        players.append(player)

    return Team(abbr=abbr, players=players)


def load_all_teams(folder) -> dict[str, Team]:
    """Load every .csv in `folder`. Returns {abbr: Team}.
    Checks that player_id is unique across ALL teams, not just within one file."""
    folder = Path(folder)
    csv_files = sorted(folder.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"no .csv files found in {folder}")

    teams: dict[str, Team] = {}
    id_owner: dict[int, str] = {}  # player_id -> team abbr that already has it

    for csv_path in csv_files:
        team = load_team(csv_path)
        for p in team.players:
            if p.player_id in id_owner:
                raise ValueError(
                    f"player_id {p.player_id} appears in both "
                    f"{id_owner[p.player_id]} and {team.abbr}"
                )
            id_owner[p.player_id] = team.abbr
        teams[team.abbr] = team

    return teams