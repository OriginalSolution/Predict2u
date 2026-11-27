"""None-safe slip dates and ordering.

Combined inbox legs (and some Verzzify copies) carry a kickoff and no date.
Sorting those slips with a raw None date or grade raises
TypeError: '<' not supported between instances of 'NoneType' and 'str'.
"""


def ymd(value):
    """YYYY-MM-DD prefix, or None when the value is missing or not a date."""
    if isinstance(value, str) and len(value) >= 10 and value[4:5] == "-":
        return value[:10]
    return None


def leg_date(leg, fallback):
    """Date from the leg, else the kickoff/ko calendar day, else fallback (today)."""
    if not isinstance(leg, dict):
        return fallback
    return ymd(leg.get("date")) or ymd(leg.get("kickoff")) or ymd(leg.get("ko")) or fallback


def stamp_leg(leg, fallback):
    """Write a real date onto the leg. Returns that date."""
    day = leg_date(leg, fallback)
    if isinstance(leg, dict):
        leg["date"] = day
    return day


def slip_sort_key(slip, risk_ord):
    """Order by date, risk, grade, then rating. Missing fields stay comparable."""
    date = ymd(slip.get("date")) or "9999-99-99"
    grade = slip.get("grade")
    if not isinstance(grade, str) or not grade:
        grade = "Z"
    try:
        rating = float(slip.get("rating"))
    except (TypeError, ValueError):
        rating = 0.0
    return (date, risk_ord(slip), grade, -rating)
