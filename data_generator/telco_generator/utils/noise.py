"""
Noise injection utilities for realistic data variation.
"""

import numpy as np


def lognormal_noise(rng: np.random.Generator, sigma: float = 0.05) -> float:
    """
    Return a lognormal noise factor centered at 1.0.

    sigma controls variance. 0.05 = ~5% typical variation.
    Use as: noisy_value = base_value * lognormal_noise(rng)
    """
    return float(rng.lognormal(mean=0.0, sigma=sigma))


def normal_noise(rng: np.random.Generator, sigma: float = 0.02) -> float:
    """
    Return a normal noise factor centered at 1.0, clamped to >= 0.5.

    Used for symmetric, bounded variation (e.g., ratios, percentages).
    """
    factor = float(rng.normal(loc=1.0, scale=sigma))
    return max(factor, 0.5)


def seasonal_factor(month: int, amplitude: float = 0.05) -> float:
    """
    Return a seasonal multiplier based on month of year.

    Models the December peak (holidays, diaspora calls) and August dip.
    Returns a factor near 1.0 with sinusoidal variation.
    """
    # December (month 12) peaks, June (month 6) dips.
    phase = (month - 6) / 6  # -1 in June, +1 in December
    return 1.0 + amplitude * np.cos((1 - phase) * np.pi)


def occasional_anomaly(
    rng: np.random.Generator,
    base_value: float,
    anomaly_rate: float = 0.02,
    severity: float = 0.3,
) -> tuple[float, bool]:
    """
    Occasionally inject a significant outlier.

    Returns (value, is_anomaly). When triggered, value is reduced by `severity`
    fraction (e.g., 0.3 = 30% drop), simulating an outage or measurement issue.
    """
    if rng.random() < anomaly_rate:
        return base_value * (1.0 - severity * rng.random()), True
    return base_value, False