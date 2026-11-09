"""Korean lunar-to-solar conversion adapter."""

from datetime import date

from korean_lunar_calendar import KoreanLunarCalendar


def lunar_to_solar(
    year: int,
    month: int,
    day: int,
    intercalation: bool = False,
) -> date:
    """Convert a Korean lunar date to Gregorian date.

    Raises ValueError for unsupported or invalid lunar dates, including
    impossible leap-month requests.
    """

    calendar = KoreanLunarCalendar()
    if not calendar.setLunarDate(year, month, day, intercalation):
        raise ValueError(
            "invalid or unsupported Korean lunar date: "
            f"{year:04d}-{month:02d}-{day:02d}, "
            f"intercalation={intercalation}"
        )

    return date(
        calendar.solarYear,
        calendar.solarMonth,
        calendar.solarDay,
    )
