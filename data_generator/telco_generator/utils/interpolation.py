"""
Trajectory interpolation between annual anchor points.
"""


def interpolate_yearly(
    annual_values: dict[int, float],
    year: int,
    month: int,
) -> float:
    """
    Linearly interpolate a monthly value between annual anchors.

    annual_values keys are years, values are year-end totals.
    Returns the interpolated value for the requested year/month.

    For January-December within a year, smoothly transitions from the
    previous year's anchor toward the current year's anchor.
    """
    if year not in annual_values:
        # Use nearest available year.
        years = sorted(annual_values.keys())
        if year < years[0]:
            return annual_values[years[0]]
        if year > years[-1]:
            return annual_values[years[-1]]
        # Interpolate between bracketing years.
        for i, anchor_year in enumerate(years[:-1]):
            if anchor_year <= year <= years[i + 1]:
                progress = (year - anchor_year) / (years[i + 1] - anchor_year)
                return annual_values[anchor_year] + progress * (
                    annual_values[years[i + 1]] - annual_values[anchor_year]
                )
        return annual_values[years[-1]]

    # Within a known year: interpolate from previous year's end to this year's end.
    prev_year = year - 1
    if prev_year not in annual_values:
        return annual_values[year]

    prev_value = annual_values[prev_year]
    curr_value = annual_values[year]
    monthly_progress = month / 12.0
    return prev_value + monthly_progress * (curr_value - prev_value)


def interpolate_yearly_dict(
    annual_dicts: dict[int, dict[str, float]],
    year: int,
    month: int,
    key: str,
) -> float:
    """
    Interpolate a specific key from yearly dictionaries.

    Used for things like INTERNET_TECH_SHARES where each year holds a dict
    of {2G: ..., 3G: ..., 4G: ...} values.
    """
    flat_values = {y: d[key] for y, d in annual_dicts.items() if key in d}
    return interpolate_yearly(flat_values, year, month)
