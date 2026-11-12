"""Where a posting is, relative to home (Kissimmee, FL).

Three outcomes, and the difference matters to the reader:

  - a distance in miles  -> the job is somewhere we can place on the map
  - None                 -> we could not place it (NOT the same as "far away")

Coordinates come from one of two places. The NLx feed publishes a latitude and
longitude per job, which is exact. Everything else publishes a text location
("Orlando, FL (Main Campus)"), which is matched against a fixed table of
Central Florida places. The table is deliberately closed: a place we don't
list yields None, and the pipeline then treats the role as not-local instead
of guessing.
"""

from __future__ import annotations

import math
import re

# Kissimmee City Hall. Every distance on the site is measured from here.
HOME_NAME = "Kissimmee, FL"
HOME = (28.2920, -81.4076)

# Central Florida places within roughly 60 miles of Kissimmee.
PLACES: dict[str, tuple[float, float]] = {
    "kissimmee": (28.2920, -81.4076),
    "orlando": (28.5384, -81.3789),
    "st. cloud": (28.2489, -81.2812),
    "saint cloud": (28.2489, -81.2812),
    "st cloud": (28.2489, -81.2812),
    "celebration": (28.3253, -81.5331),
    "poinciana": (28.1403, -81.4584),
    "lake buena vista": (28.3936, -81.5387),
    "bay lake": (28.3886, -81.5659),
    "buenaventura lakes": (28.3358, -81.3531),
    "hunters creek": (28.3606, -81.4223),
    "hunter's creek": (28.3606, -81.4223),
    "meadow woods": (28.3856, -81.3665),
    "lake nona": (28.3772, -81.2459),
    "narcoossee": (28.3306, -81.2362),
    "harmony": (28.1906, -81.1453),
    "intercession city": (28.2628, -81.5079),
    "campbell": (28.2589, -81.4565),
    "loughman": (28.2420, -81.5667),
    "reunion": (28.2767, -81.5926),
    "championsgate": (28.2611, -81.6236),
    "champions gate": (28.2611, -81.6236),
    "four corners": (28.3329, -81.6474),
    "davenport": (28.1614, -81.6017),
    "haines city": (28.1142, -81.6179),
    "winter park": (28.6000, -81.3392),
    "maitland": (28.6278, -81.3631),
    "eatonville": (28.6147, -81.3856),
    "altamonte springs": (28.6611, -81.3656),
    "casselberry": (28.6778, -81.3278),
    "fern park": (28.6492, -81.3512),
    "longwood": (28.7031, -81.3384),
    "lake mary": (28.7589, -81.3178),
    "heathrow": (28.7636, -81.3723),
    "sanford": (28.8003, -81.2731),
    "oviedo": (28.6700, -81.2081),
    "winter springs": (28.6989, -81.3081),
    "chuluota": (28.6419, -81.1234),
    "geneva": (28.7397, -81.1151),
    "apopka": (28.6934, -81.5322),
    "wekiwa springs": (28.6986, -81.4256),
    "forest city": (28.6672, -81.4431),
    "lockhart": (28.6194, -81.4426),
    "pine hills": (28.5578, -81.4534),
    "ocoee": (28.5692, -81.5440),
    "winter garden": (28.5653, -81.5862),
    "oakland": (28.5550, -81.6331),
    "gotha": (28.5278, -81.5231),
    "windermere": (28.4956, -81.5348),
    "horizon west": (28.4336, -81.6226),
    "dr. phillips": (28.4494, -81.4923),
    "doctor phillips": (28.4494, -81.4923),
    "dr phillips": (28.4494, -81.4923),
    "williamsburg": (28.4070, -81.4420),
    "oak ridge": (28.4711, -81.4245),
    "taft": (28.4297, -81.3651),
    "southchase": (28.3931, -81.3834),
    "sky lake": (28.4572, -81.3915),
    "pine castle": (28.4717, -81.3678),
    "belle isle": (28.4583, -81.3592),
    "edgewood": (28.4861, -81.3723),
    "conway": (28.5028, -81.3306),
    "azalea park": (28.5411, -81.3006),
    "goldenrod": (28.6103, -81.2887),
    "union park": (28.5656, -81.2356),
    "alafaya": (28.5641, -81.2114),
    "avalon park": (28.5136, -81.1487),
    "bithlo": (28.5547, -81.1064),
    "christmas": (28.5364, -81.0178),
    "clermont": (28.5494, -81.7729),
    "minneola": (28.5744, -81.7462),
    "montverde": (28.6003, -81.6740),
    "groveland": (28.5580, -81.8512),
    "mount dora": (28.8025, -81.6445),
    "tavares": (28.8042, -81.7256),
    "eustis": (28.8528, -81.6853),
    "leesburg": (28.8108, -81.8779),
    "sorrento": (28.8078, -81.5648),
    "zellwood": (28.7311, -81.6012),
    "debary": (28.8831, -81.3087),
    "deltona": (28.9005, -81.2637),
    "orange city": (28.9489, -81.2987),
    "deland": (29.0283, -81.3031),
    "lake alfred": (28.0920, -81.7234),
    "auburndale": (28.0653, -81.7887),
    "winter haven": (28.0222, -81.7329),
    "lake wales": (27.9014, -81.5859),
    "polk city": (28.1825, -81.8240),
    "lakeland": (28.0395, -81.9498),
    "bartow": (27.8964, -81.8431),
    "plant city": (28.0186, -82.1129),
    "titusville": (28.6122, -80.8076),
    "cocoa": (28.3861, -80.7420),
    "rockledge": (28.3164, -80.7270),
    "merritt island": (28.3581, -80.6895),
    "cape canaveral": (28.4058, -80.6048),
    "kennedy space center": (28.5729, -80.6490),
    "viera": (28.2550, -80.7350),
    "melbourne": (28.0836, -80.6081),
    "palm bay": (28.0345, -80.5887),
    # County names, placed at their seats. Public employers often publish only
    # the county ("Osceola County, FL").
    "osceola county": (28.2920, -81.4076),
    "orange county": (28.5384, -81.3789),
    "seminole county": (28.8003, -81.2731),
    "lake county": (28.8042, -81.7256),
    "polk county": (27.8964, -81.8431),
}

# Unambiguous enough to accept without a state: nobody else has a Kissimmee.
_BARE_OK = {"kissimmee", "orlando", "lake buena vista", "lake mary",
            "altamonte springs", "poinciana"}

_FL_RE = re.compile(r"(?:\bFL\b|\bFla\b\.?|\bflorida\b)", re.IGNORECASE)
_OTHER_STATE_AFTER = re.compile(
    r",\s*(?:A[LKZR]|C[AOT]|DE|GA|HI|I[DLNA]|K[SY]|LA|M[EDAINSOT]|N[EVHJMYCD]|"
    r"O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[TA]|W[AVIY]|DC)\b"
)

# Longest names first so "winter park" is tried before a shorter overlap and
# "orange city" before "orange county" never mis-pairs.
_ORDERED = sorted(PLACES, key=len, reverse=True)
_PLACE_RES = {
    name: re.compile(r"(?<![a-z])" + re.escape(name).replace(r"\ ", r"\s+") + r"(?![a-z])")
    for name in _ORDERED
}

_ZIP_PREFIXES = ("327", "328", "347", "338", "329")  # Central Florida ZIP3s


def miles_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in miles (haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def miles_from_home(point: tuple[float, float]) -> float:
    return round(miles_between(HOME, point), 1)


def parse_latlon(value) -> tuple[float, float] | None:
    """'28.52, -81.32' -> (28.52, -81.32); anything implausible -> None."""
    if not isinstance(value, str) or "," not in value:
        return None
    try:
        lat, lon = (float(part) for part in value.split(",", 1))
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None
    return lat, lon


def _option_distance(option: str) -> float | None:
    low = option.lower()
    has_fl = bool(_FL_RE.search(option))
    if not has_fl and _OTHER_STATE_AFTER.search(option):
        return None  # "Melbourne, VIC" / "Oakland, CA" / "Sanford, NC"
    for name in _ORDERED:
        if not _PLACE_RES[name].search(low):
            continue
        if has_fl or name in _BARE_OK:
            return miles_from_home(PLACES[name])
    return None


def local_distance(location: str | None) -> float | None:
    """Miles from Kissimmee for a text location, or None if we can't place it.

    A posting that lists several places ("Orlando, FL; Tampa, FL") is as close
    as its closest listed place: any one of them is somewhere you could work.
    """
    if not location:
        return None
    best: float | None = None
    for option in re.split(r"[;|/]|\band\b|\bor\b", location):
        option = option.strip()
        if not option:
            continue
        dist = _option_distance(option)
        if dist is not None and (best is None or dist < best):
            best = dist
    return best
