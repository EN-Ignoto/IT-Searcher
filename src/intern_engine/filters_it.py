"""Orlando-first entry-level IT opportunities and internships."""
from __future__ import annotations

import re

from . import filters_secnet as legacy

SEARCH_TERMS = ("support", "technician", "administrator", "network", "information technology")

BUCKETS = ["Orlando area", "Remote — Florida / US"]
ENTRY_LEVEL = BUCKETS[0]
INTERNSHIPS = BUCKETS[0]
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|supervisor|director|head|vp|vice president|architect|intermediate|mid[ -]level|journeyman|expert|sme|ii|iii|iv|[2-9]|tier[ -]?[2-9]|level[ -]?[2-9])\b", re.I)
ENTRY = re.compile(r"\b(entry[ -]level|junior|jr|associate|trainee|graduate|new grad|early career|(?:administrator|engineer|technician|analyst) (?:i|1)|level[ -]?(?:1|i)|tier[ -]?(?:1|i))\b", re.I)
# Specific first-job operations paths; do not admit generic infrastructure roles.
FOUNDATION = re.compile(
    r"\b(?:it operations (?:specialist|technician|associate)"
    r"|it asset (?:analyst|technician|coordinator|specialist)"
    r"|computer support (?:specialist|technician)"
    r"|technology support (?:specialist|technician)"
    r"|computer systems technician|desktop technician"
    r"|(?:it|information technology) assistant)\b", re.I,
)
SUPPORT = re.compile(r"\b(help[ -]?desk|service desk|desktop support|it support|computer technician|pc technician|it technician|it specialist|technical support|end[ -]user|field support|support technician|support specialist)\b", re.I)
IT = re.compile(r"\b(information technology|it|help[ -]?desk|service desk|desktop|sysadmin|systems? administrat\w*|network|networking|noc|data cent(?:er|re)|cloud|infrastructure|linux|windows|technical support|computer support|technology support|computer technician|pc technician|end[ -]user|devops|site reliability|cyber\w*|infosec|soc analyst|information security)\b", re.I)
EXCLUDE = re.compile(r"\b(sales|presales|pre-sales|marketing|recruit\w*|mechanical|aerospace|electrical|embedded|firmware|software|civil|manufacturing|landscape|construction|financial|data scien\w*|data engineer(?:ing)?|machine learning|provider network|social network|security guard|physical security|loss prevention|hvac|commissioning|facilities|electrician|plumbing|phlebotomist|product owner|product management|product manager|project coordinator|diagnostic\w*|reporter|scrum master|product line|clinical|veterinary|medical device|skillbridge|erp implementation)\b", re.I)
CITIES = re.compile(r"\b(orlando|winter park|winter garden|lake mary|sanford|kissimmee|poinciana|davenport|haines city|hunters creek|dr[.]? phillips|buenaventura lakes|four corners|altamonte springs|maitland|apopka|oviedo|longwood|casselberry|lake buena vista|celebration|ocoee|windermere|winter springs|st[.]? cloud|clermont|tavares|mount dora)\b", re.I)
FL = re.compile(r"\b(fl|florida)\b", re.I)
OTHER_STATE = re.compile(r",\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b")
REMOTE_STATE = re.compile(
    r"\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b"
    r"|\b(?:Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming)\b"
)
REMOTE = re.compile(r"\b(remote|work from home|anywhere)\b", re.I)
US = re.compile(r"\b(united states|usa|u\.s\.|us|nationwide)\b", re.I)


def is_relevant(title: str) -> bool:
    return bool(title and IT.search(title) and not EXCLUDE.search(title)
                and not legacy.NON_TECH_RE.search(title)
                and not legacy.FALSE_NETWORK_RE.search(title))


def is_internship(title: str) -> bool:
    return legacy.is_internship(title)


def is_opportunity(title: str) -> bool:
    # These consulting/migration positions are outside the first-job operations scope.
    if re.search(r"\b(?:cloud migration engineer|it advisory consultant|implementation consultant)\b",
                 title, re.I) and not is_internship(title):
        return False
    # Generic engineer/admin/analyst titles are not evidence of entry-level fit.
    if re.search(r"\bsupport engineer\b", title, re.I) and not (ENTRY.search(title) or is_internship(title)):
        return False
    return bool(is_relevant(title) and not SENIOR.search(title)
                and (is_internship(title) or ENTRY.search(title)
                     or SUPPORT.search(title) or FOUNDATION.search(title)
                     or re.search(r"\b(?:data cent(?:er|re)|network|noc) technician\b", title, re.I)))


FIT_VERSION = 7
_EXPERIENCE = re.compile(
    r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s*(?:\+|(?:-|–|to)\s*\d{1,2}\+?)?\s*years?"
    r"(?:['’]s?)?\s+(?:(?:of|in|with)\s+)?(?:[\w/,&-]+\s+){0,12}"
    r"(?:experience|technical support|support engineering|it support"
    r"|desktop support|customer support|customer service|networking"
    r"|help desk|troubleshooting)\b", re.I)
_WORD_NUMBERS = dict(zip('one two three four five six seven eight nine ten'.split(), range(1, 11), strict=True))


def assess_fit(title: str, description: str | None, location: str = "") -> str:
    """Require positive junior evidence; block experienced and unpaid postings.

    Unknown descriptions remain unverified, rather than silently claiming fit.
    Required professional IT experience and 3+ years preferred are excluded.
    A two-year preference can be considered for a first IT job.
    """
    from .sponsorship import strip_html
    if not is_opportunity(title):
        return "rejected"
    text = strip_html(description or "")
    # An existing clearance is a hard barrier for a first civilian IT job.
    # Eligibility to obtain one is different and remains in scope.
    for match in re.finditer(
            r"\b(?:active|current|maintained)\b[^.;]{0,60}"
            r"\b(?:secret|ts/sci|top secret)\b[^.;]{0,60}\bclearance\b"
            r"|\bclearance\s+required\s*:\s*(?:active|current)\b",
            text, re.I):
        context = text[max(0, match.start() - 25):match.end() + 35]
        if re.search(r"\b(?:preferred|a plus|not required|no active|no current)\b", context, re.I):
            continue
        return "rejected"
    # Government and education job descriptions commonly spell out numbers
    # as "two (2) years". Normalize those before enforcing experience gates.
    # Treat "two (2) years" exactly like "2 years", never as no requirement.
    text = re.sub(
        r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s*\(\s*(\d{1,2})\s*\)(?=\s+years?\b)",
        lambda match: match.group(1),
        text,
        flags=re.I,
    )
    # Benefits such as volunteer days or unpaid leave do not make a job unpaid.
    if re.search(r"\bvolunteer\b", title, re.I) or re.search(
            r"\b(?:unpaid\s+(?:internship|position|role|opportunity)"
            r"|(?:internship|position|role)\s+(?:is|will be)\s+unpaid"
            r"|without compensation"
            r"|volunteer\s+(?:[\w-]+\s+){0,3}(?:opportunity|position|role|internship))\b",
            title + " " + text, re.I):
        return "rejected"
    # A current undergraduate does not yet meet a completed bachelor's
    # requirement. Preserve student/pursuing wording and preferred degrees.
    for match in re.finditer(
            r"[^.]{0,60}\b(?:bachelor\w*|master\w*)(?:['’]s)?[^.]{0,200}\brequired\b",
            text, re.I):
        if not re.search(r"\b(?:pursuing|enrolled|student|toward|preferred)\b", match.group(), re.I):
            return "rejected"
    # A qualification heading can make a completed degree mandatory without
    # repeating the word "required" after the degree (TruBridge's live format).
    for match in re.finditer(
            r"\b(?:minimum requirements|minimum qualifications|basic qualifications"
            r"|required qualifications|what you will need)\b[^.]{0,180}"
            r"\bbachelor\w*(?:['’]s)?[^.]{0,160}", text, re.I):
        if not re.search(r"\b(?:pursuing|enrolled|student|toward|towards|preferred)\b",
                         match.group(), re.I):
            return "rejected"
    # Some experienced escalation roles state no numeric years at all.
    # Require explicit specialist evidence rather than treating every mention
    # of experience (including retail or coursework) as professional IT tenure.
    if re.search(
            r"\bproven experience\s+(?:supporting|administering|implementing)\s+"
            r"(?:enterprise resource planning|erp systems|complex saas platforms)\b",
            text, re.I):
        return "rejected"
    if location_group(location, title) == "remote":
        for match in re.finditer(
                r"\b(?:ability to|must|required to|expected to)\s+(?:work|be|report)"
                r"[^.]{0,30}\bon[ -]?site\b[^.]{0,100}", text, re.I):
            if location_group(match.group()) != "local":
                return "rejected"
    # Normalize written ranges and preserve comma-separated skill lists:
    # "Three to five years of infrastructure engineering, systems administration,
    # cloud engineering, or migration experience" is an experienced requirement.
    text = re.sub(
        r"\b(" + "|".join(_WORD_NUMBERS) + r")\b",
        lambda match: str(_WORD_NUMBERS[match.group().lower()]), text, flags=re.I,
    )
    for match in _EXPERIENCE.finditer(text):
        value = match.group(1).lower()
        years = int(value) if value.isdigit() else _WORD_NUMBERS[value]
        if years >= 1:
            # A range beginning at two years is not a two-year preference:
            # "2 - 5+ years" is an experienced role even if another section
            # later says "nice to have". Never lower its upper bound to 2.
            upper = re.search(r"(?:-|–|to)\s*(\d{1,2})", match.group(), re.I)
            if upper and int(upper.group(1)) > 2:
                return "rejected"
            # Two years preferred can be a plausible first-job stretch;
            # an explicit two-year minimum or any 3+ year requirement cannot.
            left = max(text.rfind(".", 0, match.start()),
                       text.rfind(";", 0, match.start()))
            ends = [i for i in (text.find(".", match.end()),
                                text.find(";", match.end())) if i >= 0]

            # Limit preference language to the immediate requirement.
            # A distant "NICE TO HAVE" header cannot turn mandatory years
            # elsewhere in a flattened description into a preference.
            clause_end = min(ends) if ends else len(text)
            nearby = text[max(left + 1, match.start() - 35):min(clause_end, match.end() + 80)]
            preferred = bool(re.search(r"\b(?:preferred|nice to have|a plus|ideally)\b", nearby, re.I))
            mandatory = bool(re.search(r"\b(?:required|minimum|at least|must have|need to have)\b", nearby, re.I))
            if years <= 2 and preferred and not mandatory:
                continue
            return "rejected"
    if is_internship(title) and not re.search(
            r"\$\s*\d|\b\d[\d,.]*\s*(?:USD|dollars?\s+(?:per|an)\s+hour)\b"
            r"|\bpaid[,\s]+(?:(?:remote|full[ -]time|part[ -]time|summer|winter"
            r"|spring|fall|\d+[ -]week)[,\s]+){0,5}(?:internship|intern|position|role)\b"
            r"|\b(?:internship|position|role)\s+(?:is|will be)\s+(?:a\s+)?paid\b",
            text, re.I):
        return "unverified"
    return "eligible" if text.strip() else "unverified"


def location_group(location: str, title: str = "") -> str | None:
    """Nearby city names, not a claimed GPS radius. Remote needs US/FL evidence."""
    text = location or ""
    if CITIES.search(text) and (FL.search(text) or not OTHER_STATE.search(text)):
        return "local"
    if REMOTE.search(text + " " + title):
        if FL.search(text):
            return "remote"
        if US.search(text) and not REMOTE_STATE.search(text):
            return "remote"
    return None


def is_stretch(title: str) -> bool:
    return not bool(is_internship(title) or ENTRY.search(title) or SUPPORT.search(title))


def bucket(title: str, location: str) -> str | None:
    group = location_group(location, title)
    if not group or not is_opportunity(title):
        return None
    return BUCKETS[0] if group == "local" else BUCKETS[1]


def categorize(title: str) -> str:
    if SUPPORT.search(title) or FOUNDATION.search(title):
        return "IT Support / Ops"
    if legacy.SECURITY_RE.search(title):
        return "Security / IT"
    if re.search(r"\b(network|networking|noc)\b", title, re.I):
        return "Network / Telecom"
    if re.search(r"\b(cloud|aws|azure|gcp)\b", title, re.I):
        return "Cloud Platform"
    if re.search(r"\b(systems?|server|infrastructure|sysadmin|data cent(?:er|re))\b", title, re.I):
        return "Systems & Cloud Infra"
    return "IT Support / Ops"


def tracks_of(title: str) -> tuple[str, ...]:
    return ("network",)
