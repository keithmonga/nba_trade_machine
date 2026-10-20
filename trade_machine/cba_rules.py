# ---------------------------------------------------------------------------
# 2026-27 league thresholds (whole dollars)
# ---------------------------------------------------------------------------

SALARY_CAP      = 164_961_000
TAX_LEVEL       = 200_428_000
FIRST_APRON     = 209_015_000
SECOND_APRON    = 221_686_000
MIN_TEAM_SALARY = 148_465_000

MAX_ROSTER = 15

# ---------------------------------------------------------------------------
# Salary matching (expanded traded player exception)
# ---------------------------------------------------------------------------

# Flat $250K added to the 200% and 125% formulas. Fixed in the CBA, does not grow.
CUSHION = 250_000

# Flat amount added in the middle bracket. Was $7.5M in 2023-24 and grows with
# the cap every season. 2026-27 value per Hoops Rumors.
MIDDLE_ADD = 9_096_000

# in max_incoming() cross, so they are derived here instead of typed in by hand.
# That way, changing MIDDLE_ADD can never leave the brackets out of sync.
#
#   Lower edge: 2x + CUSHION    = x + MIDDLE_ADD   ->  x = MIDDLE_ADD - CUSHION
#   Upper edge: 1.25x + CUSHION = x + MIDDLE_ADD   ->  x = 4 * (MIDDLE_ADD - CUSHION)
LOWER_BRACKET = MIDDLE_ADD - CUSHION            # 8,846,000 in 2026-27
UPPER_BRACKET = 4 * (MIDDLE_ADD - CUSHION)      # 35,384,000 in 2026-27


def _check_dollars(amount, label: str) -> None:
    """Raise if `amount` is not a non-negative whole-dollar int.
    Floats are rejected on purpose so rounding errors can't sneak in."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError(f"{label} must be an int in whole dollars, got {type(amount).__name__}: {amount!r}")
    if amount < 0:
        raise ValueError(f"{label} cannot be negative: {amount}")


def max_incoming(outgoing: int) -> int:
    _check_dollars(outgoing, "outgoing")

    two_hundred = outgoing * 2 + CUSHION
    flat_add = outgoing + MIDDLE_ADD
    one_twenty_five = outgoing * 5 // 4 + CUSHION

    return max(min(two_hundred, flat_add), one_twenty_five)


def matching_bracket(outgoing: int) -> str:
    _check_dollars(outgoing, "outgoing")
    if outgoing <= LOWER_BRACKET:
        return "200% + $250K"
    if outgoing <= UPPER_BRACKET:
        return f"outgoing + ${MIDDLE_ADD:,}"
    return "125% + $250K"