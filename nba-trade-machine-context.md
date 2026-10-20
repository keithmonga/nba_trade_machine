# NBA Trade Machine: Project Context File

> **For the assistant reading this:** This file is the full context for an ongoing project. The user will attach it to a new chat and name a part to work on (for example "I want to work on loader.py" or "help me with the CSV files"). Read the whole file first, then jump to the relevant section. Follow the "Working Style" rules in Section 1 exactly. Check Section 12 (Status Tracker) to see what is already done.

---

## Table of Contents

1. Who the user is and how to work with them
2. Project goal and scope
3. Key design decisions (and why)
4. CBA rules to implement (2026-27 season)
5. Environment setup (PyCharm)
6. Folder and file structure
7. CSV data spec
8. Module specs (file by file)
9. Hand-calculated test cases
10. Build order (phases)
11. Known traps and pitfalls
12. Status tracker
13. Open questions / things to verify
14. Sources

---

## 1. Who the user is and how to work with them

**User:** Keith, Computer Science undergrad at Western University (Ontario). Big NBA / Toronto Raptors fan. Interested in finance and fintech careers.

**Why this project exists:** It describes a project on his resume ("NBA Trade Machine Application"). He is rebuilding it himself from scratch so he fully understands and can defend every part of it.

**Original resume description (reference only):**
- Built a trade-simulation tool in Python with a multi-screen UI flow for selecting teams, constructing trades, and validating outcomes. Implemented automated CBA-style salary matching validation (e.g., "within 125%" rule) with clear pass/fail messaging and post-trade roster recomputation to visualize team changes.
- Designed a data ingestion + normalization pipeline using pandas to load roster/salary CSVs, sanitize currency formats, and attach structured salary metadata to UI selections.

> Note: The "within 125%" rule in that bullet is outdated (old CBA). The rebuild uses the current CBA rules in Section 4. Consider updating the resume bullet wording once the rebuild is done.

### Working Style rules (follow these)

| Rule | What it means in practice |
|---|---|
| **He writes the code himself** | Default to guidance, explanations, skeletons, hints, and pseudocode. Do NOT hand over full finished implementations unless he explicitly asks. If he's stuck, give the smallest hint that unblocks him first. |
| **Simple terminology** | Explain concepts plainly. Define jargon (venv, package, dataclass, etc.) the first time it comes up. |
| **Stress-test, don't validate** | Look for the weakest point in his idea or code before affirming anything. Lead with what's wrong or missing. No empty praise ("great", "brilliant"). |
| **Direct and concise** | No warm-up sentences. If something won't work, say so in the first sentence. |
| **No em dashes** | Never use em dashes in any output. Use colons, commas, or parentheses. |
| **Structured output** | He likes headers, numbered steps, tables, code snippets, and pseudocode. |
| **Raptors flavor is fine** | TOR is one of the two starter teams. Basketball references are welcome where natural, never forced. |

---

## 2. Project goal and scope

**Goal:** A Python trade-simulation tool. The user picks teams, picks players each team sends, and the tool says whether the trade is legal under NBA salary rules (pass/fail with a clear reason), then shows both rosters after the trade.

**Current phase:** Trade logic and rules ONLY. No user interface yet.

**Data plan:** One CSV per NBA team. Start with **two teams**, build and test all the trade logic with them, then fill in CSVs for the remaining 28 teams.

**Out of scope for now:**
- UI (comes after logic is solid and tested)
- Draft picks, cash in trades, sign-and-trades
- Non-simultaneous trades (trade exceptions / TPEs)
- Trade kickers, non-guaranteed salary rules, recently-signed player restrictions
- Three-team (or more) trades (design so this is possible later, but don't build it yet)

**Tech stack:** Python 3.12 or 3.13, PyCharm, pandas (loading CSVs only), pytest (testing), Git.

---

## 3. Key design decisions (and why)

| # | Decision | Reason |
|---|---|---|
| D1 | Build trade logic before UI | Logic can be tested with one command (pytest). Debugging through UI screens is slow and hides bugs. |
| D2 | One CSV per team | User's choice. Easier to fill in by hand. Requires identical headers in every file (loader must check this). |
| D3 | pandas only in `loader.py` | pandas is good at reading/cleaning files. Trade logic uses plain Python objects (dataclasses), which are easier to read and test. |
| D4 | Salaries stored as whole-number dollars (int) | Floats cause rounding errors. The $250K cushion in the rules means precision matters. `45000000` not `"$45,000,000"` and not `45.0`. |
| D5 | Never write trade results back to the CSVs | CSVs are the source of truth. Load once, simulate in memory, return NEW Team objects. Originals stay untouched. |
| D6 | All cap numbers live in one place (`cba_rules.py` constants) | Numbers change every season. Updating should be a one-file edit. |
| D7 | Every rule gets tests with hand-calculated numbers BEFORE the code | Catches math mistakes. Test cases are in Section 9. |
| D8 | Pick one team below the first apron and one above it | Two similar teams would leave half the rule branches untested. |
| D9 | Use `player_id` as the unique key | Names have typos and duplicates. |
| D10 | Validation returns pass/fail PLUS a human-readable reason | Matches resume ("clear pass/fail messaging") and makes debugging easier. |

---

## 4. CBA rules to implement (2026-27 season)

### 4.1 League numbers (confirmed, effective July 1, 2026)

| Threshold | Amount | Python constant |
|---|---|---|
| Salary cap | $164,961,000 | `SALARY_CAP = 164_961_000` |
| Luxury tax level | $200,428,000 | `TAX_LEVEL = 200_428_000` |
| First apron | $209,015,000 | `FIRST_APRON = 209_015_000` |
| Second apron | $221,686,000 | `SECOND_APRON = 221_686_000` |
| Minimum team salary | $148,465,000 | `MIN_TEAM_SALARY = 148_465_000` |
| Matching cushion | $250,000 | `CUSHION = 250_000` |

### 4.2 Salary-matching brackets (NOT confirmed for 2026-27)

The brackets below are the **2023-24 base values**. They grow with the cap every season. The exact 2026-27 values were not confirmed. Use these as placeholders and update once verified (Hoops Rumors / Spotrac / CBA Article VII).

| Constant | 2023-24 base value | Meaning |
|---|---|---|
| `LOWER_BRACKET` | $7,500,000 | Top of the "200%" bracket |
| `MIDDLE_ADD` | $7,500,000 | Flat amount added in the middle bracket |
| `UPPER_BRACKET` | $29,000,000 | Start of the "125%" bracket |

### 4.3 The rules, in plain English

Definitions:
- **Outgoing salary:** total salary of players a team sends away in the trade.
- **Incoming salary:** total salary of players a team receives.
- **Post-trade payroll:** team payroll after the trade = payroll before − outgoing + incoming.
- **Aggregation:** combining 2 or more outgoing players' salaries to match incoming salary.

**Rule R0: Taking back less (or equal) always passes matching.**
If incoming ≤ outgoing, salary matching passes for that team. (Aggregation rule R3 can still fail it.)

**Rule R1: Teams that end BELOW the first apron (incoming > outgoing).**
Max incoming salary depends on how much they send out:

| Outgoing salary | Max incoming |
|---|---|
| Up to $7.5M | 200% of outgoing + $250K |
| $7.5M to $29M | outgoing + $7.5M |
| Above $29M | 125% of outgoing + $250K |

These three brackets collapse into **one formula**:

```
max_incoming = max(
    1.25 * outgoing + CUSHION,
    min(2.00 * outgoing + CUSHION, outgoing + MIDDLE_ADD)
)
```

Use integer math in the real code (see Section 11, trap T3).

**Rule R2: Teams above the first apron can take back at most 100% of outgoing.**
Equivalent hard-cap framing (easier to code): **if a team takes back more than it sends out, its post-trade payroll must be ≤ FIRST_APRON.** If it would end above the first apron, it can only take back ≤ 100% of outgoing.

**Rule R3: Aggregation hard-caps a team at the second apron.**
If a team sends out 2+ players in the trade, its post-trade payroll must be ≤ SECOND_APRON. (Second-apron teams cannot aggregate.)

**Rule R4 (later): Roster size.** After the trade, each team must have ≤ 15 standard contracts. (Two-way contracts don't count. Minimum roster rules can be ignored for now.)

**Rule R5 (much later): Teams under the cap** can absorb salary into cap room instead of matching. Nearly every team is over the cap, so this is a separate, low-priority code path.

### 4.4 Validation logic for ONE team (pseudocode)

```
def check_team(team, outgoing_players, incoming_players):
    out = sum(salaries of outgoing_players)
    inc = sum(salaries of incoming_players)
    post = team.payroll() - out + inc
    reasons = []

    # R3: aggregation
    if len(outgoing_players) >= 2 and post > SECOND_APRON:
        reasons.append("aggregating salaries would put team over the second apron")

    # R0 / R1 / R2: matching
    if inc > out:
        if post > FIRST_APRON:
            reasons.append("over first apron: can take back at most 100% of outgoing")
        elif inc > max_incoming(out):
            reasons.append(f"incoming {inc} exceeds max allowed {max_incoming(out)}")

    return (len(reasons) == 0, reasons)
```

A trade is valid only if `check_team` passes for **both** teams.

---

## 5. Environment setup (PyCharm)

1. Install **Python 3.12 or 3.13** from python.org. On Windows, tick "Add Python to PATH".
2. PyCharm → **New Project** → name `nba-trade-machine` → interpreter type **Project venv**.
   - *venv = a private box of libraries for this one project.*
3. Terminal tab (bottom of PyCharm):
   ```
   pip install pandas pytest
   pip freeze > requirements.txt
   ```
4. Settings → Tools → Python Integrated Tools → **Default test runner: pytest**.
5. VCS menu → **Enable Version Control Integration → Git**. Commit after every working rule.
6. Create `.gitignore` containing:
   ```
   .venv/
   .idea/
   __pycache__/
   .pytest_cache/
   ```

To create the `trade_machine` folder: right-click project → New → **Python Package** (not Directory). *A package is a folder with an `__init__.py` file, which lets files import each other.*

---

## 6. Folder and file structure

```
nba-trade-machine/
├── data/
│   └── teams/
│       ├── TOR.csv
│       └── XXX.csv          (second team: one ABOVE the first apron, TBD)
├── trade_machine/
│   ├── __init__.py          (empty)
│   ├── cba_rules.py         (constants + matching math)
│   ├── models.py            (Player and Team dataclasses)
│   ├── loader.py            (CSV → Team objects, salary cleaning)
│   └── trade.py             (validate_trade, execute_trade)
├── tests/
│   ├── test_cba_rules.py
│   ├── test_loader.py
│   └── test_trade.py
├── main.py                  (scratch file for trying things out)
├── requirements.txt
└── .gitignore
```

**Dependency direction (who imports whom):**
```
main.py ──► loader.py ──► models.py
        ──► trade.py  ──► cba_rules.py
                      ──► models.py
```
`cba_rules.py` and `models.py` import nothing from the project. Keep it that way so they stay easy to test.

**Second team choice:** As of July 1, 2026, reports listed Denver, Oklahoma City, and Orlando above the first apron. Payrolls change, so verify on Spotrac before picking.

---

## 7. CSV data spec

**File naming:** `data/teams/<ABBR>.csv` using the 3-letter team abbreviation in caps (TOR, OKC, DEN, ...). The team abbreviation comes from the filename, not a column.

**Columns (exact names, exact order, every file):**

| Column | Type | Example | Notes |
|---|---|---|---|
| `player_id` | int | `1` | Unique across ALL teams, not just within one file. Simplest: number players sequentially league-wide, or use a source ID (e.g. Basketball-Reference slug, but then type is str). Decide once. |
| `name` | str | `Player A` | Display only. |
| `position` | str | `G` | G / F / C or PG/SG/SF/PF/C. Pick one style. |
| `salary` | int | `45000000` | 2026-27 cap hit in whole dollars. No `$`, no commas, no decimals. |
| `contract_end` | int | `2029` | Season the contract ends (ending year). Not used by rules yet. |

**Example file:**
```
player_id,name,position,salary,contract_end
1,Player A,G,45000000,2029
2,Player B,F,12500000,2027
3,Player C,C,2440000,2026
```

**Possible later columns** (don't add until a rule needs them): `contract_type` (standard / two_way), `is_guaranteed`, `trade_kicker_pct`, `signed_date`.

**Data entry rules:**
- Payroll total of a team's CSV should match Spotrac's team salary. If it doesn't, find out why before writing trade logic (missing players, dead money, cap holds).
- Dead money / waived players: Spotrac includes them in team salary. Decide how to handle (option: a row with `position` = `DEAD` that counts toward payroll but can't be traded). Open question, see Section 13.

---

## 8. Module specs (file by file)

### 8.1 `cba_rules.py`

**Job:** Hold all league numbers and pure math functions. No file reading, no Team objects.

```python
# cba_rules.py

SALARY_CAP      = 164_961_000
TAX_LEVEL       = 200_428_000
FIRST_APRON     = 209_015_000
SECOND_APRON    = 221_686_000
MIN_TEAM_SALARY = 148_465_000
CUSHION         = 250_000

# PLACEHOLDERS (2023-24 base values). Verify 2026-27 numbers.
LOWER_BRACKET = 7_500_000
MIDDLE_ADD    = 7_500_000
UPPER_BRACKET = 29_000_000

MAX_ROSTER = 15


def max_incoming(outgoing: int) -> int:
    """Max salary a below-first-apron team can take back for `outgoing` dollars.
    TODO: implement the one-line formula from Section 4.3 using integer math."""
    ...
```

### 8.2 `models.py`

**Job:** Define what a Player and a Team are.

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Player:
    player_id: int
    name: str
    position: str
    salary: int
    contract_end: int

@dataclass
class Team:
    abbr: str
    players: list[Player] = field(default_factory=list)

    def payroll(self) -> int:
        """TODO: sum of all player salaries."""
        ...

    def get_player(self, player_id: int) -> Player:
        """TODO: find player by id, raise ValueError if not on this team."""
        ...
```

*dataclass = a shortcut for writing a class that mostly just holds data. `frozen=True` means a Player can't be changed after creation, which prevents accidental edits during a trade.*

### 8.3 `loader.py`

**Job:** Read CSVs with pandas, clean them, return Team objects.

Functions to write:

| Function | Input | Output | Notes |
|---|---|---|---|
| `clean_salary(value)` | `"$45,000,000"`, `"45000000"`, `45000000` | `45000000` (int) | Strip `$`, commas, spaces. Raise error on junk. This is the "sanitize currency formats" part of the resume. |
| `load_team(path)` | path to one CSV | `Team` | Check headers match `EXPECTED_COLUMNS` exactly, raise a clear error if not. Team abbr from filename. |
| `load_all_teams(folder)` | `data/teams/` | `dict[str, Team]` keyed by abbr | Loop over every `.csv`. Check `player_id` is unique across all teams. |

```python
EXPECTED_COLUMNS = ["player_id", "name", "position", "salary", "contract_end"]
```

First milestone: `main.py` loads TOR, prints each player and the total payroll. Compare total to Spotrac.

### 8.4 `trade.py`

**Job:** Check if a trade is legal and produce post-trade rosters.

```python
from dataclasses import dataclass

@dataclass
class TradeResult:
    valid: bool
    reasons: list[str]        # empty if valid; one entry per failed rule, prefixed with team abbr

def check_team(team, outgoing_ids, incoming_players) -> list[str]:
    """Return a list of failure reasons for ONE team (empty list = pass).
    Logic in Section 4.4."""

def validate_trade(team_a, team_b, a_sends: list[int], b_sends: list[int]) -> TradeResult:
    """a_sends / b_sends are lists of player_ids.
    1. Confirm every id is actually on the sending team.
    2. Confirm no empty side (each team must send at least one player for now).
    3. check_team for both teams.
    4. Combine reasons, prefix each with team abbr, e.g. 'TOR: incoming $31.2M exceeds max $28.4M'."""

def execute_trade(team_a, team_b, a_sends, b_sends) -> tuple[Team, Team]:
    """Return NEW Team objects with players swapped. Do not modify team_a / team_b.
    Should only be called after validate_trade passes (or raise if invalid)."""
```

**Message formatting:** Show money as `$31.2M` in messages (write a small `fmt_money(int) -> str` helper), but keep all math in whole dollars.

### 8.5 `main.py`

Scratch file. Load teams, build a sample trade, print the result and both new payrolls. Not tested, not important. Delete or replace when the UI is built.

---

## 9. Hand-calculated test cases

Uses placeholder brackets (Section 4.2). If bracket values change, recompute these.

### 9.1 `max_incoming(outgoing)` (team ends below first apron)

| Test | Outgoing | 125%+250K | 200%+250K | Out + 7.5M | Result |
|---|---|---|---|---|---|
| Small salary | 5,000,000 | 6,500,000 | 10,250,000 | 12,500,000 | **10,250,000** |
| Middle salary | 20,000,000 | 25,250,000 | 40,250,000 | 27,500,000 | **27,500,000** |
| Big salary | 40,000,000 | 50,250,000 | 80,250,000 | 47,500,000 | **50,250,000** |
| Upper boundary | 29,000,000 | 36,500,000 | 58,250,000 | 36,500,000 | **36,500,000** (both formulas agree) |
| Lower boundary | 7,500,000 | 9,625,000 | 15,250,000 | 15,000,000 | **15,000,000** with the min/max formula. **Verify:** some sources say 200%+250K applies "up to $7.5M", which would give 15,250,000. See Section 13. |

### 9.2 `check_team` scenarios

Use fake teams in tests (build Team objects directly in the test file, don't depend on real CSVs).

| # | Setup | Expected |
|---|---|---|
| T1 | Team payroll 180M. Sends one 20M player, receives 27M. Post = 187M (< first apron). Max = 27.5M. | PASS |
| T2 | Same as T1 but receives 28M. | FAIL: exceeds max 27.5M |
| T3 | Team payroll 205M. Sends 20M, receives 25M. Post = 210M (> first apron 209.015M). | FAIL: over first apron, 100% limit |
| T4 | Team payroll 215M. Sends 20M, receives 20M. Post = 215M. | PASS (100% is allowed) |
| T5 | Team payroll 215M. Sends two players (10M + 10M), receives 19M. Post = 214M (< second apron). | PASS |
| T6 | Team payroll 220M. Sends two players (10M + 10M), receives 19M. Post = 219M... still < 221.686M. | PASS |
| T7 | Team payroll 225M. Sends two players (10M + 10M), receives 19M. Post = 224M (> second apron). | FAIL: aggregation over second apron |
| T8 | Team payroll 160M. Sends 30M, receives 10M (taking back less). | PASS (R0) |

### 9.3 `validate_trade` / `execute_trade` scenarios

| # | Scenario | Expected |
|---|---|---|
| V1 | Both teams pass `check_team` | `valid=True`, `reasons=[]` |
| V2 | One team fails | `valid=False`, reason prefixed with that team's abbr |
| V3 | Both fail | Two reasons, one per team |
| V4 | `a_sends` contains a player not on team A | Raises error (or invalid with clear reason; pick one and be consistent) |
| V5 | After `execute_trade`, original team objects unchanged | `team_a.payroll()` same as before |
| V6 | After `execute_trade`, new payrolls = old − out + in | Exact match |
| V7 | Player count conserved | Total players across both teams same before and after |

---

## 10. Build order (phases)

| Phase | Work | Done when |
|---|---|---|
| **P0** | Setup: PyCharm project, venv, pandas + pytest installed, Git on, folders created | `pytest` runs (even with 0 tests) |
| **P1** | CSVs for TOR + second team | Each CSV payroll ≈ Spotrac team salary |
| **P2** | `models.py` (Player, Team, payroll) | Can build a Team by hand and print payroll |
| **P3** | `loader.py` (clean_salary, load_team, load_all_teams) + tests | `main.py` prints both rosters and payrolls |
| **P4** | `cba_rules.py` constants + `max_incoming` + tests from 9.1 | All 9.1 tests pass |
| **P5** | `trade.py` `check_team` (R0, R1, R2) + tests T1 to T4, T8 | Tests pass |
| **P6** | Add R3 (aggregation) + tests T5 to T7 | Tests pass |
| **P7** | `validate_trade` + `execute_trade` + tests V1 to V7 | Tests pass; a real TOR trade runs in `main.py` |
| **P8** | R4 roster size limit | Tests pass |
| **P9** | Fill in remaining 28 team CSVs | `load_all_teams` loads 30 teams, unique IDs |
| **P10** | UI (framework TBD: Tkinter, PySide/PyQt, Streamlit, etc.) | Multi-screen flow: pick teams → build trade → see result |
| **Later** | R5 cap-room trades, 3-team trades, trade kickers, non-guaranteed salary, TPEs | As needed |

**Rule:** Git commit after each phase (or each passing rule).

---

## 11. Known traps and pitfalls

| # | Trap | Fix |
|---|---|---|
| T1 | Writing trade results back to CSVs | Don't. Return new Team objects. |
| T2 | Mismatched headers across 30 CSVs | Loader checks headers against `EXPECTED_COLUMNS`, fails loudly. |
| T3 | Float math (`1.25 * 29_000_000` is fine, but other values can produce `.0000001` errors) | Use integer math: `outgoing * 125 // 100` and `outgoing * 2`. |
| T4 | Using pre-trade payroll to decide apron status | Apron checks use POST-trade payroll. |
| T5 | Testing only with real CSV data | Unit tests build fake Teams in code, so tests don't break when real salaries are updated. |
| T6 | Two test teams in the same cap situation | One below first apron, one above. |
| T7 | Hardcoding numbers inside functions | All thresholds come from `cba_rules.py` constants. |
| T8 | Mutating lists while looping (removing players from a list you're iterating) | Build new lists instead. |
| T9 | pandas reading `salary` as float or string | Clean with `clean_salary`, then cast to `int`. Check `dtype`. |
| T10 | Duplicate `player_id` across teams | `load_all_teams` checks uniqueness. |
| T11 | Payroll not matching Spotrac (dead money, waived players) | Decide on dead money handling (Section 13) before trade logic. |

---

## 12. Status tracker

> **User: update this table as you go, then re-attach the file in new chats.**

| Phase | Status | Notes |
|---|---|---|
| P0 Setup | Not started | |
| P1 CSVs (2 teams) | Not started | Second team: TBD |
| P2 models.py | Not started | |
| P3 loader.py | Not started | |
| P4 cba_rules.py | Not started | Bracket values unverified |
| P5 check_team (R0-R2) | Not started | |
| P6 Aggregation (R3) | Not started | |
| P7 validate/execute | Not started | |
| P8 Roster size (R4) | Not started | |
| P9 All 30 CSVs | Not started | |
| P10 UI | Not started | Framework not chosen |

**Last updated:** October 18, 2026 (file created)

---

## 13. Open questions / things to verify

1. **2026-27 matching bracket values** (`LOWER_BRACKET`, `MIDDLE_ADD`, `UPPER_BRACKET`). Currently using 2023-24 base values ($7.5M / $7.5M / $29M). Look up current figures.
2. **Exact boundary behaviour at the lower bracket** (outgoing = exactly $7.5M: 15.0M or 15.25M?). Check CBA Article VII Section 8 or Hoops Rumors' Traded Player Exception glossary.
3. **Second team pick:** which team is above the first apron right now (verify on Spotrac).
4. **Dead money / waived players:** include as non-tradable rows so payroll matches Spotrac, or ignore?
5. **player_id scheme:** sequential ints league-wide vs a source ID string.
6. **Invalid player in a trade (V4):** raise an exception or return invalid with a reason?
7. **Should a team be allowed to send zero players** (pure salary dump into another team)? Currently: no, both sides must send at least one player.
8. **UI framework** for P10 (decide later).

---

## 14. Sources

- NBA 2026-27 cap figures: https://inplaymagazine.com/nba-sets-salary-cap-for-2026-27-season/
- Teams above first apron (July 2026): https://www.gmanetwork.com/news/sports/basketball/993311/nba-salary-cap-2026/story/
- Traded Player Exception / matching brackets: https://www.hoopsrumors.com/page/999
- What over-apron teams can't do: https://hoopsrumors.com/2024/12/what-each-nba-team-can-cant-do-on-the-trade-market.html
- Hard caps from aggregation / taking back >100%: https://cantstopcappin.beehiiv.com/p/decoding-the-trade-market
- Team payrolls for checking CSVs: https://www.spotrac.com/nba/cap/
