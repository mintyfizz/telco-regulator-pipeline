"""
Market trajectory parameters extracted from regulatory market reports (2020-2024).

These shape how metrics evolve year-over-year. The generator interpolates
monthly between annual anchor points and adds noise for realism.
"""

# National anchor values, year-end. Source: regulatory annual market reports.

MOBILE_TELEPHONY_SUBSCRIBERS_NATIONAL = {
    2020: 5_618_000,
    2021: 5_648_000,
    2022: 5_650_000,
    2023: 5_907_000,
    2024: 6_050_000,
}

MOBILE_INTERNET_SUBSCRIBERS_NATIONAL = {
    2020: 2_890_000,
    2021: 3_148_000,
    2022: 3_034_000,
    2023: 3_433_000,
    2024: 3_757_000,
}

# Internet subscribers by technology (2G/3G/4G) in thousands.
INTERNET_TECH_SHARES = {
    2020: {"2G": 0.343, "3G": 0.368, "4G": 0.287},
    2021: {"2G": 0.315, "3G": 0.371, "4G": 0.313},
    2022: {"2G": 0.264, "3G": 0.331, "4G": 0.405},
    2023: {"2G": 0.241, "3G": 0.315, "4G": 0.444},
    2024: {"2G": 0.243, "3G": 0.306, "4G": 0.450},
}

# Internet traffic shares by technology (volume, not subscribers).
INTERNET_TRAFFIC_SHARES = {
    2020: {"2G": 0.021, "3G": 0.461, "4G": 0.517},
    2021: {"2G": 0.016, "3G": 0.392, "4G": 0.592},
    2022: {"2G": 0.009, "3G": 0.354, "4G": 0.637},
    2023: {"2G": 0.005, "3G": 0.289, "4G": 0.706},
    2024: {"2G": 0.003, "3G": 0.244, "4G": 0.752},
}

# Total annual internet traffic in megabytes (millions).
TOTAL_INTERNET_TRAFFIC_MB = {
    2020: 24_385_000_000,  # 24.4 billion MB
    2021: 29_231_000_000,
    2022: 42_474_000_000,
    2023: 69_485_000_000,
    2024: 90_904_000_000,  # 90.9 billion MB
}

# Total annual mobile internet revenue (FCFA, millions).
TOTAL_INTERNET_REVENUE_XAF = {
    2020: 50_634_000_000,  # 50.6B FCFA
    2021: 55_818_000_000,
    2022: 51_285_000_000,
    2023: 56_823_000_000,
    2024: 63_569_000_000,  # 63.6B FCFA
}

# Weighted tariffs per MB by technology (FCFA/MB).
INTERNET_TARIFF_PER_MB = {
    2020: {"2G": 2.12, "3G": 2.09, "4G": 2.31},
    2021: {"2G": 1.91, "3G": 1.91, "4G": 2.89},
    2022: {"2G": 1.31, "3G": 1.21, "4G": 2.17},
    2023: {"2G": 0.86, "3G": 0.82, "4G": 1.99},
    2024: {"2G": 0.73, "3G": 0.70, "4G": 2.15},
}

# Total annual voice traffic (millions of minutes).
TOTAL_VOICE_TRAFFIC_OUTGOING = {
    2020: 4_040_000_000,
    2021: 4_698_000_000,
    2022: 5_199_000_000,
    2023: 5_823_000_000,
    2024: 6_102_000_000,
}

# Total annual SMS traffic (outgoing, millions).
TOTAL_SMS_TRAFFIC_OUTGOING = {
    2020: 4_932_000_000,
    2021: 5_274_000_000,
    2022: 5_422_000_000,
    2023: 5_505_000_000,
    2024: 4_643_000_000,  # SMS declining
}

# Voice tariff (FCFA/minute, weighted).
VOICE_TARIFF_OUTGOING = {
    2020: 29,
    2021: 25,
    2022: 21,
    2023: 19,
    2024: 18,
}

# Annual ARPU in FCFA per subscriber per month.
MOBILE_ARPU = {
    2020: 1_995,
    2021: 1_740,
    2022: 1_757,
    2023: 1_766,
    2024: 1_636,
}

# Months covered by the simulation.
SIMULATION_START_YEAR: int = 2020
SIMULATION_END_YEAR: int = 2024
SIMULATION_TOTAL_MONTHS: int = 60  # Jan 2020 through Dec 2024
