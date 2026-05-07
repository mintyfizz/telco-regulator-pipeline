"""
Congolese department reference data calibrated against the 2023 census reform.

Population shares drive geographic distribution of subscribers, traffic, and
QoS measurements. The North/South zone classification captures the historical
digital divide central to ARPCE policy concerns.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionProfile:
    """A Congolese administrative department."""

    region_code: str
    region_name: str
    region_capital: str
    population_2023: int
    area_km2: int
    density_per_km2: float
    zone: str  # North, South, Southeast, Southwest
    is_urban_concentration: bool


# 15 departments per the 2023 reform. Total population ~6.14M.
# Brazzaville and Pointe-Noire together hold 58% of population on 0.25% of land.
REGIONS: dict[str, RegionProfile] = {
    # North zone — 7 departments, sparsely populated
    "SAN": RegionProfile("SAN", "Sangha", "Ouésso", 209_701, 55_800, 3.80, "North", False),
    "LIK": RegionProfile("LIK", "Likouala", "Impfondo", 325_429, 61_993, 5.24, "North", False),
    "COB": RegionProfile("COB", "Congo-Oubangui", "Mossaka", 124_100, 25_536, 4.86, "North", False),
    "CUV": RegionProfile("CUV", "Cuvette", "Owando", 222_640, 26_765, 8.30, "North", False),
    "CUO": RegionProfile("CUO", "Cuvette-Ouest", "Ewo", 119_328, 26_600, 4.50, "North", False),
    "NKA": RegionProfile("NKA", "Nkéni-Alima", "Gamboma", 154_230, 17_406, 8.86, "North", False),
    "PLA": RegionProfile("PLA", "Plateaux", "Djambala", 129_191, 20_994, 6.15, "North", False),
    # Southeast zone — 3 departments, includes the capital
    "DJL": RegionProfile("DJL", "Djoué-Léfini", "Odziba", 174_761, 23_560, 7.41, "Southeast", False),
    "BZV": RegionProfile("BZV", "Brazzaville", "Brazzaville", 2_145_783, 588, 3649.29, "Southeast", True),
    "POO": RegionProfile("POO", "Pool", "Kinkala", 219_771, 10_395, 21.14, "Southeast", False),
    # South zone — 3 departments, agricultural belt
    "BOU": RegionProfile("BOU", "Bouenza", "Madingou", 363_850, 12_265, 29.67, "South", False),
    "LEK": RegionProfile("LEK", "Lékoumou", "Sibiti", 100_559, 20_950, 4.80, "South", False),
    "NIA": RegionProfile("NIA", "Niari", "Dolisie", 334_863, 25_942, 12.91, "South", False),
    # Southwest zone — 2 departments, includes economic capital
    "KOU": RegionProfile("KOU", "Kouilou", "Loango", 119_162, 13_103, 9.09, "Southwest", False),
    "PNR": RegionProfile("PNR", "Pointe-Noire", "Pointe-Noire", 1_398_812, 288, 4857.00, "Southwest", True),
}


TOTAL_POPULATION_2023: int = sum(r.population_2023 for r in REGIONS.values())


def get_population_weights() -> dict[str, float]:
    """
    Return each region's share of national population as a weight.

    Used to distribute national-level metrics geographically.
    Sum of all weights = 1.0.
    """
    return {
        code: profile.population_2023 / TOTAL_POPULATION_2023
        for code, profile in REGIONS.items()
    }


def get_regions_by_zone(zone: str) -> list[RegionProfile]:
    """Return all regions in a given zone."""
    return [r for r in REGIONS.values() if r.zone == zone]


def get_region(region_code: str) -> RegionProfile:
    """Look up a single region profile by code."""
    if region_code not in REGIONS:
        raise KeyError(f"Unknown region_code: {region_code}")
    return REGIONS[region_code]


def get_urban_regions() -> list[RegionProfile]:
    """Return only urban concentration regions (Brazzaville and Pointe-Noire)."""
    return [r for r in REGIONS.values() if r.is_urban_concentration]


def get_rural_regions() -> list[RegionProfile]:
    """Return all non-urban-concentration regions."""
    return [r for r in REGIONS.values() if not r.is_urban_concentration]