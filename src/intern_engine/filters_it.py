"""Orlando-first entry-level IT opportunities and internships."""
from __future__ import annotations

import re

from . import filters_secnet as legacy

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
    r"|computer systems technician)\b", re.I,
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
    # Generic engineer/admin/analyst titles are not evidence of entry-level fit.
    return bool(is_relevant(title) and not SENIOR.search(title)
                and (is_internship(title) or ENTRY.search(title)
                     or SUPPORT.search(title) or FOUNDATION.search(title)
                     or re.search(r"\b(?:data cent(?:er|re)|network|noc) technician\b", title, re.I)))


FIT_VERSION = 5
_EXPERIENCE = re.compile(
    r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s*(?:\+|(?:-|–|to)\s*\d{1,2}\+?)?\s*years?"
    r"(?:['’]s?)?\s+(?:(?:of|in|with)\s+)?(?:[\w/-]+\s+){0,8}"
    r"(?:experience|technical support|support engineering|it support"
    r"|desktop support|customer support|customer service|networking"
    r"|help desk|troubleshooting)\b", re.I)
_WORD_NUMBERS = dict(zip('one two three four five six seven eight nine ten'.split(), range(1, 11), strict=True))


def assess_fit(title: str, description: str | None, location: str = "") -> str:
    """Require positive junior evidence; block experienced and unpaid postings.

    Unknown descriptions remain unverified, rather than silently claiming fit.
    Mandatory two-year requirements and 3+ years preferred are excluded.
    A two-year preference can be considered for a first IT job.
    """
    from .sponsorship import strip_html
    if not is_opportunity(title):
        return "rejected"
    text = strip_html(description or "")
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
    if location_group(location, title) == "remote":
        for match in re.finditer(
                r"\b(?:ability to|must|required to|expected to)\s+(?:work|be|report)"
                r"[^.]{0,30}\bon[ -]?site\b[^.]{0,100}", text, re.I):
            if location_group(match.group()) != "local":
                return "rejected"
    for match in _EXPERIENCE.finditer(text):
        value = match.group(1).lower()
        years = int(value) if value.isdigit() else _WORD_NUMBERS[value]
        if years >= 2:
            # Two years preferred can be a plausible first-job stretch;
            # an explicit two-year minimum or any 3+ year requirement cannot.
            left = max(text.rfind(".", 0, match.start()),
                       text.rfind(";", 0, match.start()))
            ends = [i for i in (text.find(".", match.end()),
                                text.find(";", match.end())) if i >= 0]
            clause = text[left + 1:min(ends) if ends else len(text)]
            preferred = bool(re.search(r"\b(?:preferred|nice to have|a plus|ideally)\b", clause, re.I))
            mandatory = bool(re.search(r"\b(?:required|minimum|at least|must have|need to have)\b", clause, re.I))
            if years == 2 and preferred and not mandatory:
                continue
            return "rejected"
    if is_internship(title) and not re.search(
            r"\bpaid\b|\$\s*\d|\b(?:USD|hourly rate|hourly wage)\b", text, re.I):
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
