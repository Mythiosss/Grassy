"""Sunrise, sunset and daylight length from latitude and longitude. Pure maths, no internet.

This is the NOAA solar calculator algorithm (accurate to about a minute away from the poles).
It is what lets the nudge say "golden hour is 17:21-17:51" on a trail with no signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import acos, asin, cos, degrees, radians, sin, tan


@dataclass(frozen=True)
class Place:
    lat: float  # degrees north
    lon: float  # degrees east
    tz: float  # hours from UTC, e.g. 7 for Jakarta, 5.5 for India


@dataclass(frozen=True)
class SunTimes:
    sunrise: float | None  # minutes after local midnight; None in polar day/night
    sunset: float | None
    daylight_min: float  # 0 in polar night, 1440 in midnight sun


def sun_times(d: date, place: Place) -> SunTimes:
    jd = d.toordinal() + 1721424.5 + 0.5 - place.tz / 24  # Julian day at local noon
    t = (jd - 2451545.0) / 36525.0

    mean_long = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    mean_anom = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    ecc = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    m = radians(mean_anom)
    eq_centre = (
        sin(m) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + sin(2 * m) * (0.019993 - 0.000101 * t)
        + sin(3 * m) * 0.000289
    )
    true_long = mean_long + eq_centre
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * sin(radians(omega))
    mean_obliq = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    obliq = mean_obliq + 0.00256 * cos(radians(omega))
    decl = asin(sin(radians(obliq)) * sin(radians(app_long)))

    y = tan(radians(obliq / 2)) ** 2
    l0 = radians(mean_long)
    eq_time = 4 * degrees(
        y * sin(2 * l0)
        - 2 * ecc * sin(m)
        + 4 * ecc * y * sin(m) * cos(2 * l0)
        - 0.5 * y * y * sin(4 * l0)
        - 1.25 * ecc * ecc * sin(2 * m)
    )

    lat = radians(place.lat)
    cos_ha = cos(radians(90.833)) / (cos(lat) * cos(decl)) - tan(lat) * tan(decl)
    if cos_ha > 1:  # sun never rises
        return SunTimes(None, None, 0.0)
    if cos_ha < -1:  # sun never sets
        return SunTimes(None, None, 1440.0)
    ha = degrees(acos(cos_ha))

    solar_noon = 720 - 4 * place.lon - eq_time + place.tz * 60
    return SunTimes(solar_noon - 4 * ha, solar_noon + 4 * ha, 8 * ha)


def daylight_hours(d: date, place: Place) -> float:
    return sun_times(d, place).daylight_min / 60


def hhmm(minutes: float) -> str:
    minutes = int(round(minutes)) % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
