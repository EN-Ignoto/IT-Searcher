"""United States location recognition.

All that remains of the original engine's filter module: `filters_it` uses the
state tables and `is_united_states` to decide whether a remote role is open to
a Florida resident.
"""

from __future__ import annotations

import re

_US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia",
]
_CA_PROVINCES = [
    "ontario", "quebec", "british columbia", "alberta", "manitoba",
    "saskatchewan", "nova scotia", "new brunswick", "newfoundland", "labrador",
    "prince edward island", "yukon", "northwest territories", "nunavut",
]
_US_CODES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC", "US", "USA",
]
_CA_CODES = ["ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"]

# US country tokens. These MUST be matched as whole tokens, never as substrings:
# "usa" hides inside Lausanne, Jerusalem, Busan, Sausalito and dozens of other
# real ATS locations, and a substring test made every one of them read as the
# US. The lookarounds (rather than \b) are what let "U.S." keep its periods.
_US_COUNTRY_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    r"united\s+states(?:\s+of\s+america)?"
    r"|u\.\s?s\.?\s?a\.?"
    r"|u\.\s?s\.?"
    r"|usa"
    r"|america"
    r")(?![a-z0-9])",
    re.IGNORECASE,
)
# "Latin America" / "South America" must not read as the US ("america" token).
_AMERICA_NOT_US_RE = re.compile(r"\b(?:south|latin|central)\s+america")

# Countries that appear in ATS location strings and must never read as US, even
# when a state-code lookalike sits next to them ("IN - Bangalore, India" is not
# Indiana). An explicit US token still wins for multi-country strings.
# NOTE on omissions: "georgia" is a US state as well as a country, and
# "england" hides inside "New England" — both are handled below rather than
# listed here, so a US location never loses to a name collision.
_NON_US_COUNTRIES = (
    "india", "united kingdom", "great britain", "scotland", "wales",
    "northern ireland", "ireland", "germany", "france", "poland",
    "netherlands", "spain", "italy", "portugal", "romania", "hungary",
    "bulgaria", "croatia", "serbia", "slovenia", "bosnia", "albania",
    "montenegro", "macedonia", "ukraine", "belarus", "russia", "moldova",
    "lithuania", "latvia", "estonia", "luxembourg", "iceland", "cyprus",
    "malta", "czech", "slovakia", "sweden", "switzerland", "belgium",
    "austria", "denmark", "norway", "finland", "greece", "turkey", "israel",
    "united arab emirates", "saudi arabia", "qatar", "kuwait", "bahrain",
    "oman", "jordan", "lebanon", "iraq", "iran", "afghanistan", "egypt",
    "morocco", "tunisia", "algeria", "nigeria", "ghana", "senegal",
    "ethiopia", "kenya", "tanzania", "uganda", "zimbabwe", "botswana",
    "namibia", "south africa", "brazil", "mexico", "argentina", "colombia",
    "chile", "peru", "bolivia", "paraguay", "uruguay", "venezuela",
    "ecuador", "panama", "costa rica", "guatemala", "honduras", "nicaragua",
    "el salvador", "belize", "dominican republic", "jamaica", "trinidad",
    "japan", "china", "singapore", "korea", "taiwan", "hong kong", "macau",
    "philippines", "indonesia", "vietnam", "thailand", "cambodia",
    "myanmar", "malaysia", "pakistan", "bangladesh", "sri lanka", "nepal",
    "mongolia", "kazakhstan", "uzbekistan", "azerbaijan", "armenia",
    "australia", "new zealand", "fiji",
)
_NON_US_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _NON_US_COUNTRIES) + r")\b"
    # "England" is a foreign country only when it isn't "New England".
    r"|(?<!new\s)\bengland\b"
)

_US_NAME_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _US_STATES) + r")\b", re.IGNORECASE
)
_CA_NAME_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _CA_PROVINCES) + r")\b", re.IGNORECASE
)
# case-sensitive; (?!-) avoids matching country-style prefixes like "DE-Berlin"
# (Germany) as the US state code DE (Delaware).
_US_CODE_RE = re.compile(r"\b(" + "|".join(_US_CODES) + r")\b(?!-)")
_CA_CODE_RE = re.compile(r"\b(" + "|".join(_CA_CODES) + r")\b(?!-)")

_LOCATION_PART_RE = re.compile(r"[,;|]+")
_LOCATION_OPTION_RE = re.compile(r"[;|]+")
_GEORGIA_COUNTRY_CITIES = {
    "tbilisi", "batumi", "kutaisi", "rustavi", "gori", "zugdidi",
}


def _location_parts(location: str) -> list[str]:
    return [part.strip() for part in _LOCATION_PART_RE.split(location) if part.strip()]


def _structured_signal(
    parts: list[str], names: list[str], codes: list[str]
) -> tuple[int, str, str] | None:
    """Rightmost state/province component as ``(index, kind, value)``."""
    by_length = sorted(names, key=len, reverse=True)
    for index in range(len(parts) - 1, -1, -1):
        low = parts[index].lower().strip()
        for name in by_length:
            if re.fullmatch(
                rf"{re.escape(name)}(?:\s+(?:[-–—(]).*)?", low, re.IGNORECASE
            ) or re.search(
                rf"(?:^|\s[-–—]\s){re.escape(name)}$", low, re.IGNORECASE
            ):
                return index, "name", name
        for code in codes:
            # A structured component accepts lowercase ("Austin, tx"), but a
            # country-style prefix such as "DE-Berlin" deliberately does not.
            if re.fullmatch(
                rf"{re.escape(code)}(?:\s+(?:[-–—(]).*)?", parts[index], re.IGNORECASE
            ):
                return index, "code", code
    return None


def _matching_part_indexes(parts: list[str], pattern: re.Pattern) -> list[int]:
    return [index for index, part in enumerate(parts) if pattern.search(part.lower())]


def is_united_states(location: str) -> bool:
    if not location:
        return False
    # Several connectors preserve every advertised location by joining
    # alternatives with semicolons.  Evaluate each option independently:
    # otherwise a foreign country in the last option can veto a valid US
    # option (and reversing the employer's list changes the answer).
    options = [part.strip() for part in _LOCATION_OPTION_RE.split(location)
               if part.strip()]
    if len(options) > 1:
        return any(is_united_states(option) for option in options)
    low = location.lower()
    stripped = _AMERICA_NOT_US_RE.sub(" ", low)
    if _US_COUNTRY_RE.search(stripped):
        return True
    parts = _location_parts(location)
    us_signal = _structured_signal(parts, _US_STATES, _US_CODES)
    ca_signal = _structured_signal(parts, _CA_PROVINCES, _CA_CODES)
    foreign_indexes = _matching_part_indexes(parts, _NON_US_RE)
    canada_indexes = [
        index for index, part in enumerate(parts)
        if re.search(r"\bcanada\b", part, re.IGNORECASE)
    ]

    if us_signal:
        index, kind, value = us_signal
        # A named country to the right is an actual country qualifier:
        # "IN - Bangalore, India" and "CA - Sydney, Australia" are foreign.
        if any(country_index > index for country_index in foreign_indexes):
            return False
        if any(country_index > index for country_index in canada_indexes):
            return False
        if value == "georgia" and any(
            city in parts[0].lower() for city in _GEORGIA_COUNTRY_CITIES
        ):
            return False
        if kind == "code" and (ca_signal or canada_indexes):
            # "Milton, Ontario, CA" is Canada; a province outranks the
            # California-looking suffix. A full state name remains decisive,
            # so "Ontario, California" stays correctly American.
            # Ontario, California is commonly abbreviated "Ontario, CA".
            # It is a two-component US city/state location; the Canadian form
            # carries another city/province component ("Milton, Ontario, CA")
            # or an explicit Canada qualifier.
            if (
                value == "CA" and len(parts) == 2
                and parts[0].strip().casefold() == "ontario"
                and not canada_indexes
            ):
                return True
            return False
        return True

    if foreign_indexes:
        return False
    if _US_NAME_RE.search(low):
        return True
    if re.search(r"\b(?:canada|canadian)\b", low) or _CA_NAME_RE.search(low):
        return False
    if _US_CODE_RE.search(location):
        return True
    return False
