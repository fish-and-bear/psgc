"""Distance calculations between geographic coordinates."""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0


def haversine(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate the great-circle distance between two points (km).

    Uses the Haversine formula. Accurate to within ~0.5% for
    most practical purposes.
    """
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def vincenty(
    lat1: float, lon1: float, lat2: float, lon2: float,
    max_iterations: int = 200, tolerance: float = 1e-12,
) -> float:
    """Calculate geodesic distance using Vincenty's formula (km).

    More accurate than Haversine (~0.5mm precision on WGS84 ellipsoid)
    but slower. Falls back to Haversine on convergence failure.
    """
    a = 6378.137  # semi-major axis (km)
    f = 1 / 298.257223563  # flattening
    b = a * (1 - f)

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    L = math.radians(lon2 - lon1)

    U1 = math.atan((1 - f) * math.tan(phi1))
    U2 = math.atan((1 - f) * math.tan(phi2))

    sin_U1, cos_U1 = math.sin(U1), math.cos(U1)
    sin_U2, cos_U2 = math.sin(U2), math.cos(U2)

    lam = L
    for _ in range(max_iterations):
        sin_lam, cos_lam = math.sin(lam), math.cos(lam)
        sin_sigma = math.sqrt(
            (cos_U2 * sin_lam) ** 2
            + (cos_U1 * sin_U2 - sin_U1 * cos_U2 * cos_lam) ** 2
        )
        if sin_sigma == 0:
            return 0.0

        cos_sigma = sin_U1 * sin_U2 + cos_U1 * cos_U2 * cos_lam
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos_U1 * cos_U2 * sin_lam / sin_sigma
        cos2_alpha = 1 - sin_alpha ** 2
        cos_2sigma_m = (
            cos_sigma - 2 * sin_U1 * sin_U2 / cos2_alpha
            if cos2_alpha != 0
            else 0
        )
        C = f / 16 * cos2_alpha * (4 + f * (4 - 3 * cos2_alpha))
        lam_prev = lam
        lam = L + (1 - C) * f * sin_alpha * (
            sigma
            + C * sin_sigma * (cos_2sigma_m + C * cos_sigma * (-1 + 2 * cos_2sigma_m ** 2))
        )
        if abs(lam - lam_prev) < tolerance:
            break
    else:
        return haversine(lat1, lon1, lat2, lon2)

    u2 = cos2_alpha * (a ** 2 - b ** 2) / b ** 2
    A_coeff = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B_coeff = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    delta_sigma = B_coeff * sin_sigma * (
        cos_2sigma_m
        + B_coeff
        / 4
        * (
            cos_sigma * (-1 + 2 * cos_2sigma_m ** 2)
            - B_coeff
            / 6
            * cos_2sigma_m
            * (-3 + 4 * sin_sigma ** 2)
            * (-3 + 4 * cos_2sigma_m ** 2)
        )
    )
    return b * A_coeff * (sigma - delta_sigma)
