"""Who this list is for, written as code.

The reader holds Network+ and Security+, has retail / customer-service
experience, is studying Computer Science at UCF, and has NO professional IT
experience. So a role belongs here when it is

  1. an entry path into IT (help desk, desktop support, IT technician, junior
     network / systems / operations work, or a paid IT internship), and
  2. not senior, and
  3. somewhere they can work (near Kissimmee, or remote and open to Florida),
     and
  4. not gated by a hard requirement they cannot meet — judged from the
     posting's own text, not from its title.

Step 4 is the one that needs care. "2 years of experience preferred" and
"2 years of experience required" are different sentences, and treating them
the same either hides real beginner jobs or lists jobs that will reject the
application. `assess()` reads the description in segments, tracks whether it
is inside a required or a preferred section, and only lets REQUIRED years of
IT experience exclude a role.

Every rejection carries a reason, and the pipeline logs them, so the rules can
be audited against what they threw away.
"""

from __future__ import annotations

import html as _html
import re

from . import filters, geo

# Bump when a rule change should re-read every stored posting.
VERSION = 5

LOCAL = "Local"
NEARBY = "Nearby"
REMOTE = "Remote"
SECTIONS = (LOCAL, NEARBY, REMOTE)

FIT_BEGINNER = "beginner"      # nothing in the posting requires IT experience
FIT_STRETCH = "stretch"        # ~1 year required, or a requirement that may flex
FIT_UNVERIFIED = "unverified"  # we could not read the posting's text


# --------------------------------------------------------------------------
# 1. Title: is this an entry path into IT at all?
# --------------------------------------------------------------------------
_I = re.IGNORECASE

_ROLE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Help Desk / Service Desk", re.compile(
        r"\b(help\s?desk|service\s?desk|support\s?desk|desk\s+technician|"
        r"it\s+service\s+cent(?:er|re)|technology\s+service\s+cent(?:er|re))\b", _I)),
    ("Desktop / End-User Support", re.compile(
        r"\b(desktop\s+(?:support|technician|engineer|analyst|administrator|services?|specialist)|"
        r"desk-?side|end[\s-]user\s+(?:support|computing|services?|technician|technology|"
        r"experience|specialist|analyst)|client\s+(?:technology|technical)\s+"
        r"(?:support|technician|specialist|analyst)|workstation\s+(?:support|technician)|"
        r"pc\s+(?:technician|support|tech|specialist))\b", _I)),
    ("Network / NOC", re.compile(
        r"\b(noc|network\s+operations|network\s+(?:technician|support|administrator|admin|"
        r"analyst|specialist|engineer|intern|associate|operator|tech)|"
        r"telecom(?:munications?)?\s+(?:technician|analyst|specialist))\b", _I)),
    ("Systems / Infrastructure", re.compile(
        r"\b(systems?\s+(?:administrator|admin|support|technician|operator)|sys\s?admin|"
        r"infrastructure\s+(?:technician|support|analyst|specialist|intern|associate|operations)|"
        r"data\s?cent(?:er|re)\s+(?:services?\s+)?"
        r"(?:technician|operator|operations|tech|associate|intern)|"
        r"server\s+(?:technician|support)|cloud\s+(?:support|operations)\s+"
        r"(?:associate|technician|engineer|analyst|intern|specialist)|"
        r"(?:windows|linux|active\s+directory|microsoft\s*365|m365|o365|office\s*365)\s+"
        r"(?:administrator|support|technician))\b", _I)),
    ("Security (entry)", re.compile(
        r"\b(soc\s+analyst|security\s+operations\s+(?:cent(?:er|re)\s+)?analyst|"
        r"(?:cyber\s?security|information\s+security|cyber|it\s+security|infosec|"
        r"network\s+security)\s+(?:intern|internship|analyst|technician|associate|"
        r"apprentice|trainee|specialist|co-?op))\b", _I)),
    ("IT Operations", re.compile(
        r"\b(it\s+operations|it\s+ops|it\s+asset|technology\s+operations|"
        r"information\s+technology\s+operations|computer\s+operator|"
        r"(?:it|information\s+technology|information\s+systems|technology)\s+"
        r"(?:intern|internship|co-?op|apprentice|trainee))\b", _I)),
    ("IT Support / Technician", re.compile(
        r"\b(it\s+support|i\.t\.\s+support|information\s+technology\s+(?:support|technician|"
        r"specialist|assistant|associate|analyst|coordinator|aide)|"
        r"information\s+systems\s+(?:technician|support|specialist|assistant)|"
        r"technical\s+support|tech\s+support|"
        r"computer\s+(?:support|technician|repair|specialist|tech|lab\s+(?:assistant|technician))|"
        r"technology\s+(?:support|technician|specialist|assistant|associate|aide|"
        r"installation\s+specialist|services?\s+(?:technician|specialist))|"
        r"it\s+(?:technician|tech|specialist|assistant|associate|analyst|coordinator|"
        r"administrator|admin|generalist|professional|field\s+(?:technician|support)|"
        r"services?\s+(?:technician|specialist|analyst|associate)|helpdesk|customer\s+support)|"
        r"field\s+support\s+technician|desktop\s+analyst|"
        r"(?:hardware|device|deployment|imaging|break[\s/-]?fix)\s+technician|"
        r"user\s+support\s+(?:specialist|technician|analyst)|geek\s+squad)\b", _I)),
]

# Titles that name a support job without saying it is an IT one. Kept only
# when the posting's own text is clearly about IT (see `it_signal`).
_WEAK_ROLE_RE = re.compile(
    r"\b(support\s+(?:technician|analyst|specialist|engineer)|"
    r"field\s+(?:service\s+)?technician|service\s+technician|"
    r"technical\s+(?:specialist|analyst|associate)|"
    r"application\s+support|systems?\s+(?:analyst|specialist)|"
    r"operations\s+(?:technician|analyst)|technology\s+(?:analyst|coordinator))\b", _I)
# Words that mark a "weak" title as some other trade's support job.
_WEAK_OTHER_RE = re.compile(
    r"\b(building\s+automation|automation|controls?|turbine|wealth|banking|"
    r"pharmac\w+|call[\s-]cent(?:er|re)|flight|simulat\w+|avionics|fire|hvac)\b", _I)

_INTERN_RE = re.compile(
    r"\b(intern|interns|internship|co-?op|apprentice(?:ship)?)\b", _I)
_INTERN_IT_RE = re.compile(
    r"\b(it|i\.t\.|information\s+technology|information\s+systems|technology|"
    r"cyber\w*|infosec|security\s+(?:analyst|engineering|operations)|network\w*|"
    r"infrastructure|systems?\s+administrat\w*|cloud|help\s?desk|service\s+desk|"
    r"desktop|end\s+user|data\s?cent(?:er|re)|telecom\w*|digital\s+workplace|"
    r"enterprise\s+(?:technology|systems)|identity|iam|grc|soc|devops|sre)\b", _I)

_SENIOR_RE = re.compile(
    r"\b(senior|sr|lead|principal|manager|mgr|director|supervisor|chief|vp|"
    r"vice\s+president|architect|head\s+of|team\s+lead|expert|advanced|"
    r"staff\s+(?:\w+\s+){0,2}(?:engineer|analyst|administrator|technician|architect|"
    r"specialist)|"
    r"(?:level|tier|lvl|grade)\s*[-:]?\s*(?:[3-9]|iii|iv|v)|[lt][3-9])\b", _I)
_MID_RE = re.compile(
    r"\b(intermediate|mid[\s-]?level|journeyman|experienced|"
    r"(?:level|tier|lvl|grade)\s*[-:]?\s*(?:2|ii)|[lt]2)\b", _I)
_JUNIOR_RE = re.compile(
    r"\b(junior|jr|entry[\s-]?level|trainee|apprentice|assistant|aide|"
    r"(?:level|tier|lvl|grade)\s*[-:]?\s*(?:1|i)|[lt]1)\b", _I)
# A standalone level marker: "Technician II", "Analyst 2", "Tech I/II/III".
_LEVEL_TOKEN_RE = re.compile(r"(?<![\w.$#])(III|II|IV|I|[1-5])(?![\w.%])")
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}

# Not IT, whatever else the title says.
_NOT_IT_RE = re.compile(
    r"\b(sales|account\s+(?:executive|manager)|marketing|recruit\w*|nurs\w+|clinical|"
    r"medical|pharmac\w+|patient|dental|veterinar\w+|surgical|behavior\w*|radiolog\w+|"
    r"phlebotom\w+|laborator\w+|lab\s+(?:technician|support|assistant)|hvac|maintenance|"
    r"mechanic\w*|automotive|electrician|plumb\w+|custodia\w+|housekeep\w+|driver|"
    r"warehouse|cashier|teller|accountant|accounting|payroll|legal|paralegal|attorney|"
    r"teacher|instructional|professor|faculty|coach|chef|cook|bartender|"
    r"security\s+(?:officer|guard)|loss\s+prevention|firefighter|police|corrections|"
    r"quality\s+assurance|qa|software\s+(?:engineer\w*|develop\w+)|developer|programmer|"
    r"data\s+(?:scien\w+|engineer\w*|analy\w+|entry)|machine\s+learning|"
    r"(?:product|project|program)\s+manag\w+|business\s+analyst|scrum|ux|ui|graphic|"
    r"civil|mechanical|electrical|aerospace|manufactur\w+|avionics|aircraft|biomed\w*|"
    r"ultrasound|x-ray|mri|sonograph\w+|respiratory|therap\w+|claims|underwrit\w+|loan|"
    r"mortgage|real\s+estate|insurance|fire\s+alarm|irrigation|instrumentation|"
    r"hris|workday|sap|salesforce|oracle|erp|gis|bi|business\s+intelligence|"
    r"finance|financial|audit\w*|tax|supply\s+chain|logistics|merchandis\w+|"
    r"human\s+resources|hr|chemical|environmental|construction|animal|food|"
    r"property|adjuster|billing|collections|front\s+desk|receptionist|dispatch\w*)\b", _I)
# The one place a "not IT" word is fine: "Customer Support" next to a real IT
# role word is still technical support.
_CUSTOMER_FACING_RE = re.compile(
    r"\b(customer|representative|agent|advisor|product\s+support|client\s+support)\b", _I)

_TITLE_CLEARANCE_RE = re.compile(
    r"\b(top\s+secret|ts/sci|ts\s*/\s*sci|secret\s+clearance|security\s+clearance|"
    r"(?:active|current)\s+(?:secret|clearance)|polygraph|cleared)\b", _I)
_EXPERIENCED_TITLE_RE = re.compile(
    r"\b(engineer|administrator|admin|sysadmin|sys\s+admin)\b", _I)
_PAST_TERM_RE = re.compile(r"\b(spring|summer|fall|autumn|winter)\s*'?(20\d\d|\d\d)\b", _I)


def title_level(title: str) -> int:
    """1 = entry, 2 = mid ("II"), 3 = senior. Lowest level a title offers wins:
    "Technician I/II/III" hires at I."""
    if not title:
        return 1
    if _SENIOR_RE.search(title):
        return 3
    tokens = [
        _ROMAN.get(tok, int(tok) if tok.isdigit() else 9)
        for tok in _LEVEL_TOKEN_RE.findall(title)
    ]
    if tokens:
        lowest = min(tokens)
        if lowest >= 3:
            return 3
        if lowest == 2:
            return 1 if _JUNIOR_RE.search(title) else 2
        return 1
    if _JUNIOR_RE.search(title):
        return 1
    return 2 if _MID_RE.search(title) else 1


def is_internship(title: str) -> bool:
    return bool(title and _INTERN_RE.search(title))


def categorize(title: str) -> str | None:
    """The first role family the title names, or None if it names none."""
    if not title:
        return None
    for name, pattern in _ROLE_PATTERNS:
        if pattern.search(title):
            if name == "IT Support / Technician" and _CUSTOMER_FACING_RE.search(title):
                return "Technical Support (customer-facing)"
            return name
    if is_internship(title) and _INTERN_IT_RE.search(title):
        return "IT Operations"
    return None


def title_verdict(title: str) -> tuple[str, str | None]:
    """('keep' | 'weak' | 'reject', category-or-reason).

    'weak' means the title could be IT but doesn't say so; the caller must
    confirm from the description (`it_signal`) before listing it.
    """
    if not title or not title.strip():
        return "reject", "no-title"
    category = categorize(title)
    if category is None:
        if _WEAK_ROLE_RE.search(title) and not _NOT_IT_RE.search(title) \
                and not _WEAK_OTHER_RE.search(title):
            if title_level(title) >= 3:
                return "reject", "senior-title"
            return "weak", "IT Support / Technician"
        return "reject", "not-it-role"
    # A real IT role word outranks most "not IT" words ("IT Support - Clinical
    # Systems" is still IT support), but not an outright different profession.
    hard_other = re.search(
        r"\b(sales|nurs\w+|software\s+(?:engineer\w*|develop\w+)|developer|"
        r"data\s+(?:scien\w+|engineer\w*)|recruit\w*|account\s+executive|"
        r"security\s+(?:officer|guard)|(?:product|project|program)\s+manag\w+|"
        r"pharmac\w+|call[\s-]cent(?:er|re)|building\s+automation|"
        r"utilit\w+|water|wastewater|broadcast\w*|teaching\s+assistant|instructor|"
        r"tutor|salesforce|finops)\b",
        title, _I)
    if hard_other:
        return "reject", "not-it-role"
    if title_level(title) >= 3:
        return "reject", "senior-title"
    if _TITLE_CLEARANCE_RE.search(title):
        # A clearance named in the title is one the hire must already hold.
        return "reject", "active-clearance-required"
    if is_internship(title) and _past_term(title):
        return "reject", "past-term"
    return "keep", category


def _past_term(title: str, today: tuple[int, int] | None = None) -> bool:
    """True when the title names a term that has already started and ended."""
    from datetime import UTC, datetime
    if today is None:
        now = datetime.now(UTC)
        today = (now.year, now.month)
    end_month = {"spring": 5, "summer": 8, "fall": 12, "autumn": 12, "winter": 3}
    found = _PAST_TERM_RE.findall(title)
    if not found:
        return False
    for term, year in found:
        yr = int(year) if len(year) == 4 else 2000 + int(year)
        if (yr, end_month[term.lower()]) >= today:
            return False
    return True


# --------------------------------------------------------------------------
# 2. Description: what does the posting actually require?
# --------------------------------------------------------------------------
_BLOCK_TAG_RE = re.compile(r"<\s*(?:br|/p|/li|/h[1-6]|/div|/tr|/ul|/ol|li|p|h[1-6])\b[^>]*>", _I)
_TAG_RE = re.compile(r"<[^>]+>")


def to_text(description: str | None) -> str:
    """HTML or plain text -> text that KEEPS line structure.

    Section headers ("Preferred Qualifications") are how postings separate
    what is required from what is nice to have, so flattening the markup to
    one line — fine for keyword matching — throws away the signal this module
    depends on.
    """
    if not description:
        return ""
    text = _BLOCK_TAG_RE.sub("\n", description)
    text = _TAG_RE.sub(" ", text)
    text = _html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUM = r"(\d{1,2}(?:\.\d)?|one|two|three|four|five|six|seven|eight|nine|ten)"
_YEARS_RE = re.compile(
    _NUM + r"\s*(?:\(\s*\d{1,2}\s*\)\s*)?(\+|plus|or\s+more)?\s*"
    r"(?:(?:-|–|—|to)\s*" + _NUM + r"\s*(?:\(\s*\d{1,2}\s*\)\s*)?\+?\s*)?"
    r"(years?|yrs?|months?)\b(?!\s+(?:old|of\s+age))", _I)
_EXPERIENCE_WORD_RE = re.compile(r"\bexperienc\w*|\bbackground\s+in\b|\bworking\s+in\b", _I)

_PREF_HDR_RE = re.compile(
    r"prefer|desired|desirable|nice[\s-]to[\s-]have|bonus|\bplus(?:es)?\b|"
    r"additional\s+(?:qualifications|skills)|ideal\s+candidate|would\s+be\s+(?:nice|great)|"
    r"not\s+required|stand\s+out|extra\s+credit", _I)
_REQ_HDR_RE = re.compile(
    r"required|requirements?|minimum|basic\s+qualifications|must[\s-]haves?|"
    r"what\s+you(?:'ll|\s+will)?\s+(?:need|bring)|qualifications|essential|"
    r"who\s+you\s+are|education\s+and\s+experience", _I)
_OTHER_HDR_RE = re.compile(
    r"responsibilit|duties|what\s+you(?:'ll|\s+will)\s+do|about\s+(?:us|the)|benefits|"
    r"compensation|overview|summary|description|why\s+", _I)

_PREF_INLINE_RE = re.compile(
    r"\bprefer\w*|\bdesired\b|\bdesirable\b|\ba\s+plus\b|\bis\s+a\s+plus\b|"
    r"\bnice\s+to\s+have\b|\bideally\b|\bbonus\b|\bhelpful\b|\badvantage\w*|"
    r"\bnot\s+required\b|\bbut\s+not\s+necessary\b|\bwould\s+be\s+(?:nice|great|beneficial)", _I)
_REQ_INLINE_RE = re.compile(
    r"\brequired?\b|\brequires\b|\bmust\s+have\b|\bminimum\b|\bat\s+least\b|\bmandatory\b", _I)
_SUBSTITUTE_RE = re.compile(
    r"\bor\s+equivalent\b|\bequivalent\s+(?:combination|experience|education|training)|"
    r"\bin\s+lieu\s+of\b|\bsubstitut\w+|\bor\s+(?:an?\s+)?(?:relevant\s+|related\s+)?"
    r"(?:education|certifications?|degree|training|coursework|associate|bachelor|"
    r"technical\s+school|vocational|military)|\bcombination\s+of\s+education", _I)
_NOT_IT_EXPERIENCE_RE = re.compile(
    r"customer[\s-]service|retail|hospitality|call[\s-]cent(?:er|re)|client[\s-]facing|"
    r"customer[\s-]facing|guest\s+service|general\s+work|work\s+experience\b", _I)
_IT_EXPERIENCE_RE = re.compile(
    r"\bit\b|information\s+technology|help\s?desk|service\s+desk|technical|desktop|"
    r"network|system|computer|troubleshoot|support|infrastructure|security|related|"
    r"relevant|similar|professional|industry|hands[\s-]on|administrat|engineer", _I)
_NOT_EXPERIENCE_CONTEXT_RE = re.compile(
    r"\bwithin\s+\d|\bfor\s+(?:over|more\s+than|nearly|almost)\b|\byears?\s+ago\b|"
    r"\bin\s+business\b|\bserving\b|\bhistory\b|\bwarranty\b|\bcontract\b|\bprobation", _I)

_NO_EXPERIENCE_RE = re.compile(
    r"no\s+(?:prior\s+|previous\s+|professional\s+)?experience\s+(?:is\s+)?"
    r"(?:required|necessary|needed)|entry[\s-]level|will\s+train|training\s+(?:is\s+)?provided|"
    r"recent\s+graduates?|new\s+grad|early[\s-]career|0\s*(?:-|–|to)\s*[12]\s+years?", _I)
_UNPAID_RE = re.compile(
    r"\bunpaid\b|\bnon[\s-]?paid\b|\bvolunteer\s+(?:position|internship|role)\b|"
    r"for\s+(?:academic\s+)?credit\s+only|\bwithout\s+(?:pay|compensation)\b|"
    r"this\s+is\s+(?:a|an)\s+unpaid", _I)
_GRAD_ONLY_RE = re.compile(
    r"(?:pursuing|enrolled\s+in|working\s+toward)\s+(?:a\s+|an\s+)?"
    r"(?:master'?s?|mba|ph\.?d|doctoral|graduate)\s+(?:degree|program|student)|"
    r"\b(?:master'?s?|ph\.?d|graduate)\s+(?:student|candidate)s?\s+only", _I)
_CLEARANCE_HAVE_RE = re.compile(
    r"(?:active|current|existing|must\s+(?:have|possess|hold|maintain)|requires?(?:\s+an?)?|"
    r"with\s+an?)\s+(?:[\w/]+\s+){0,4}?(?:secret|top\s+secret|ts/sci|"
    r"security\s+clearance|public\s+trust)", _I)
_CLEARANCE_OBTAIN_RE = re.compile(
    r"(?:ability|able|eligible|eligibility)\s+to\s+(?:obtain|receive|get|acquire)|"
    r"must\s+be\s+able\s+to\s+obtain|obtain\s+and\s+maintain|prior\s+to\s+start", _I)
_DEGREE_RE = re.compile(r"\bbachelor'?s?\b|\bb\.?[sa]\.?\s+(?:degree|in)\b|\b4[\s-]year\s+degree", _I)
_DEGREE_SOFT_RE = re.compile(
    r"prefer|desired|pursuing|enrolled|working\s+toward|candidate\s+for|or\s+equivalent|"
    r"equivalent|in\s+lieu|or\s+(?:related\s+|relevant\s+)?experience|associate|"
    r"high\s+school|\bged\b|a\s+plus|or\s+certif", _I)

_IT_SIGNAL_RE = re.compile(
    r"active\s+directory|windows\s+1[01]|windows|office\s*365|microsoft\s*365|\bo365\b|"
    r"help\s?desk|service\s+desk|ticket(?:ing|s)?|servicenow|troubleshoot\w*|"
    r"hardware|software|laptops?|desktops?|printers?|networks?|\bvpn\b|\btcp/ip\b|\bdns\b|"
    r"\bdhcp\b|imaging|\bitil\b|comptia|\ba\+|network\+|security\+|end\s+users?|"
    r"workstations?|peripherals|operating\s+systems?|information\s+technology|\bmdm\b|"
    r"intune|\bsccm\b|password\s+resets?|remote\s+support", _I)

# Words match in any case; the abbreviations only in capitals ("PT", not "pt").
_PART_TIME_RE = re.compile(
    r"(?i:\bpart[\s-]?time\b|\bstudent\s+(?:assistant|worker|employee)\b|"
    r"\bwork[\s-]study\b)|\bPT\b|\bOPS\b")
_FULL_TIME_RE = re.compile(r"(?i:\bfull[\s-]?time\b)|\bFT\b")
_TEMP_RE = re.compile(r"\b(temporary|temp|contract|seasonal|per\s+diem|on[\s-]call)\b", _I)
_TYPE_STATEMENT_RE = re.compile(
    r"(?:employment\s+type|job\s+type|position\s+type|time\s+type|schedule|status|"
    r"this\s+(?:is\s+an?|position\s+is(?:\s+an?)?))\s*[:\-]?\s*[^.\n]{0,30}?"
    r"\b(part[\s-]?time|full[\s-]?time|temporary|contract|seasonal|per\s+diem)\b", _I)
_HOURS_RE = re.compile(r"\b(1\d|2\d)\s*(?:-|–|to)?\s*(?:\d{2}\s*)?hours?\s+(?:per|a|/)\s*week", _I)
_SHIFT_RE = re.compile(
    r"\b(night|overnight|graveyard|3rd|third|2nd|second|evening|weekend|rotating|swing)\s+"
    r"shifts?\b|\b24\s?[x/]\s?7\b|\bon[\s-]call\s+rotation", _I)
_CERT_MATCH_RE = re.compile(r"security\+|network\+|sec\+|net\+", _I)


def it_signal(text: str) -> int:
    """How many DISTINCT IT-support terms the posting text uses."""
    return len({m.group(0).lower() for m in _IT_SIGNAL_RE.finditer(text or "")})


def _num(value: str) -> float:
    return float(_NUM_WORDS.get(value.lower(), value)) if not value[0].isdigit() \
        else float(value)


def _segments(text: str) -> list[str]:
    out: list[str] = []
    for line in text.split("\n"):
        # Split sentences, but not on the dot in "5.5" or "e.g."
        for part in re.split(r"(?<=[a-z\)])[.;]\s+(?=[A-Z])", line):
            part = part.strip(" \t•·-*–—")
            if part:
                out.append(part)
    return out


def _header_mode(segment: str) -> str | None:
    """'pref' / 'req' / 'other' when the segment is a section header."""
    if len(segment) > 70 or _YEARS_RE.search(segment):
        return None
    looks_like_header = segment.endswith(":") or len(segment.split()) <= 6
    if not looks_like_header:
        return None
    if _PREF_HDR_RE.search(segment):
        return "pref"
    if _REQ_HDR_RE.search(segment):
        return "req"
    if _OTHER_HDR_RE.search(segment):
        return "other"
    return None


def experience_findings(text: str) -> dict:
    """Every stated amount of experience, split into required vs preferred.

    Returns {"required": [(years, substitutable, snippet)],
             "preferred": [(years, snippet)], "non_it": [(years, snippet)]}.
    `years` is the LOWER bound of what was written: "1-3 years" asks for one.
    """
    required: list[tuple[float, bool, str]] = []
    preferred: list[tuple[float, str]] = []
    non_it: list[tuple[float, str]] = []
    mode = "req"   # text before any header is read as the employer's ask
    segments = _segments(text)
    for index, segment in enumerate(segments):
        header = _header_mode(segment)
        if header:
            mode = "pref" if header == "pref" else "req"
            continue
        if not _EXPERIENCE_WORD_RE.search(segment):
            continue
        matches = list(_YEARS_RE.finditer(segment))
        if not matches:
            continue
        if _NOT_EXPERIENCE_CONTEXT_RE.search(segment) and not _REQ_INLINE_RE.search(segment):
            continue
        amounts = []
        for m in matches:
            low = _num(m.group(1))
            if m.group(4).lower().startswith("month"):
                low = low / 12.0
            before = segment[max(0, m.start() - 14):m.start()].lower()
            if re.search(r"up\s+to|less\s+than|under|fewer\s+than|0\s*(?:-|–|to)\s*$", before):
                low = 0.0
            amounts.append(low)
        snippet = segment[:180]
        inline_pref = bool(_PREF_INLINE_RE.search(segment))
        # "preferred but not required" is a preference; don't let the word
        # "required" inside the negation read as a requirement.
        inline_req = bool(_REQ_INLINE_RE.search(
            re.sub(r"\b(?:but\s+)?not\s+(?:a\s+)?require\w*", " ", segment, flags=_I)))
        nxt = segments[index + 1] if index + 1 < len(segments) else ""
        substitutable = bool(_SUBSTITUTE_RE.search(segment)) or (
            len(nxt) < 200 and bool(re.search(
                r"equivalent\s+combination|in\s+lieu\s+of|substitut", nxt, _I)))
        if inline_pref and inline_req and len(amounts) > 1:
            # "2 years required, 4 preferred": the smaller is the requirement.
            required.append((min(amounts), substitutable, snippet))
            preferred.append((max(amounts), snippet))
            continue
        is_pref = inline_pref if (inline_pref or inline_req) else mode == "pref"
        if inline_pref and inline_req:
            is_pref = False
        low = min(amounts)
        if is_pref:
            preferred.append((low, snippet))
        elif _NOT_IT_EXPERIENCE_RE.search(segment) and not re.search(
                r"\bit\b|information\s+technology|help\s?desk|technical\s+support|desktop|"
                r"network|system", segment, _I):
            non_it.append((low, snippet))
        else:
            required.append((low, substitutable, snippet))
    return {"required": required, "preferred": preferred, "non_it": non_it}


def _fmt_years(years: float) -> str:
    if years < 1:
        return f"{round(years * 12)} months"
    return f"{years:g} year" + ("" if years == 1 else "s")


def employment_type(title: str, text: str, hint: str | None = None) -> str:
    """Internship / Part-time / Full-time / Temporary / Not stated."""
    if is_internship(title):
        return "Internship"
    for source in (title or "", hint or ""):
        if _PART_TIME_RE.search(source):
            return "Part-time"
        if _FULL_TIME_RE.search(source):
            return "Full-time"
        if _TEMP_RE.search(source):
            return "Temporary / contract"
    statement = _TYPE_STATEMENT_RE.search(text or "")
    if statement:
        word = statement.group(1).lower().replace("-", " ").replace("  ", " ")
        if word.startswith("part"):
            return "Part-time"
        if word.startswith("full"):
            return "Full-time"
        return "Temporary / contract"
    if _HOURS_RE.search(text or ""):
        return "Part-time"
    return "Not stated"


def assess(title: str, description: str | None, *, level: int | None = None,
           weak_title: bool = False, employment_hint: str | None = None) -> dict:
    """Read one posting and decide whether a beginner can realistically apply.

    Returns a dict with:
      verdict        "keep" | "reject"
      reason         why it was rejected (None when kept)
      fit            beginner | stretch | unverified
      experience     short, human label of what the posting says
      evidence       the posting's own sentence behind that label (may be "")
      employment     Internship | Part-time | Full-time | Temporary / contract | Not stated
      notes          list of short flags worth seeing before applying
    """
    level = title_level(title) if level is None else level
    intern = is_internship(title)
    text = to_text(description)
    notes: list[str] = []
    out = {
        "verdict": "keep", "reason": None, "fit": FIT_BEGINNER,
        "experience": "", "evidence": "", "notes": notes,
        "employment": employment_type(title, text, employment_hint),
    }

    def reject(reason: str, evidence: str = "") -> dict:
        out.update(verdict="reject", reason=reason, evidence=evidence[:180])
        return out

    if not text or len(text) < 120:
        if weak_title:
            return reject("unconfirmed-it-role")
        if level >= 2:
            return reject("level-2-unverifiable")
        out.update(fit=FIT_UNVERIFIED,
                   experience="Posting text unavailable — check requirements")
        return out

    if weak_title and it_signal(text) < 4:
        return reject("not-it-role")

    unpaid = _UNPAID_RE.search(text)
    if unpaid and (intern or "intern" in text.lower()[:4000]):
        return reject("unpaid", text[max(0, unpaid.start() - 60):unpaid.end() + 40])
    if intern:
        grad = _GRAD_ONLY_RE.search(text)
        if grad and not re.search(r"bachelor|undergraduate", text, _I):
            return reject("graduate-students-only", grad.group(0))

    for m in _CLEARANCE_HAVE_RE.finditer(text):
        window = text[max(0, m.start() - 90):m.end() + 90]
        if _CLEARANCE_OBTAIN_RE.search(window) or _PREF_INLINE_RE.search(window):
            if "Clearance must be obtainable" not in notes:
                notes.append("Clearance must be obtainable")
            continue
        return reject("active-clearance-required", window.strip())
    if not notes and re.search(
            r"obtain[^.\n]{0,60}clearance|clearance[^.\n]{0,40}obtain", text, _I):
        notes.append("Clearance must be obtainable")

    found = experience_findings(text)
    required = found["required"]
    if required:
        years_list = [y for y, _s, _t in required]
        # A posting that describes several levels ("I: 1 year, II: 3 years")
        # hires at the lowest one.
        multi_level = len(_LEVEL_TOKEN_RE.findall(title or "")) > 1
        years = min(years_list) if multi_level else max(years_list)
        idx = years_list.index(years)
        _y, substitutable, snippet = required[idx]
        if years >= 3 or (years >= 2 and not substitutable):
            return reject(f"requires-{_fmt_years(years).replace(' ', '-')}-experience", snippet)
        if years >= 2:
            out.update(fit=FIT_STRETCH, evidence=snippet,
                       experience=f"{_fmt_years(years)} required — education/certs may substitute")
        elif years > 0:
            out.update(fit=FIT_STRETCH, evidence=snippet,
                       experience=f"{_fmt_years(years)} required"
                       + (" — or equivalent" if substitutable else ""))
        else:
            out.update(experience="0+ years — open to no experience", evidence=snippet)
    if not out["experience"]:
        explicit = _NO_EXPERIENCE_RE.search(text)
        if found["preferred"]:
            years, snippet = min(found["preferred"])
            out.update(experience=f"None required — {_fmt_years(years)} preferred",
                       evidence=snippet)
        elif explicit:
            out.update(experience="Entry-level / no experience required",
                       evidence=text[max(0, explicit.start() - 60):explicit.end() + 60].strip())
        elif intern:
            out.update(experience="Internship — no experience requirement stated")
        else:
            out.update(experience="No years of experience stated")
        if level >= 2:
            out["fit"] = FIT_STRETCH
            notes.append("Level II title")
        elif not intern and not explicit and _EXPERIENCED_TITLE_RE.search(title or "") \
                and not _JUNIOR_RE.search(title or "") \
                and not re.search(r"\bassociate\b", title or "", _I):
            # Silence is not an invitation: an "engineer" or "administrator"
            # posting that states no years still usually expects some.
            out["fit"] = FIT_STRETCH
            notes.append("No experience stated, but this title usually expects some")
    if found["non_it"] and max(found["non_it"])[0] > 0:
        years, _snippet = max(found["non_it"])
        notes.append(f"Asks {_fmt_years(years)} customer-service-type experience")

    if not intern:
        for segment in _segments(text):
            if not _DEGREE_RE.search(segment) or len(segment) > 400:
                continue
            if _DEGREE_SOFT_RE.search(segment):
                continue
            if re.search(r"\brequired\b|\bmust\s+have\b|\bminimum\b", segment, _I):
                return reject("bachelors-degree-required", segment)
            if "Bachelor's degree listed" not in notes:
                notes.append("Bachelor's degree listed")
                if out["fit"] == FIT_BEGINNER:
                    out["fit"] = FIT_STRETCH

    if _CERT_MATCH_RE.search(text):
        notes.append("Mentions Security+/Network+")
    shift = _SHIFT_RE.search(text)
    if shift:
        notes.append("Shift work mentioned: " + shift.group(0).lower())
    return out


# --------------------------------------------------------------------------
# 3. Location: near Kissimmee, or remote and open to Florida?
# --------------------------------------------------------------------------
_REMOTE_WORD_RE = re.compile(
    r"\b(remote|virtual|work\s+from\s+home|wfh|telecommut\w*|teleworker?|anywhere|"
    r"home[\s-]based)\b", _I)
# In a TITLE only unambiguous words count: "Azure Virtual Desktop" is a product.
_REMOTE_TITLE_RE = re.compile(
    r"\b(remote|work\s+from\s+home|wfh|telecommut\w*|home[\s-]based)\b", _I)
_FOREIGN_RE = re.compile(
    r"\b(uk|u\.k\.|united\s+kingdom|england|ireland|canada|emea|europe\w*|apac|asia|"
    r"latam|latin\s+america|india|australia|new\s+zealand|germany|german|france|french|"
    r"spain|portugal|poland|netherlands|mexico|brazil|argentina|colombia|philippines|"
    r"japan|singapore|israel|dubai|uae|south\s+africa|nigeria|kenya|egypt|pakistan|"
    r"romania|ukraine|turkey|italy|sweden|denmark|norway|finland|switzerland)\b", _I)
# A remote job pinned to a part of the country Florida is not in.
_OTHER_REGION_RE = re.compile(
    r"\b(north\s?west\w*|south\s?west\w*|north\s?east\w*|mid[\s-]?west\w*|"
    r"west\s+coast|pacific|mountain|pst|mst)\b|-\s*west\b", _I)
# Work done at customers' sites is not remote work, whatever the location says.
_FIELD_WORK_RE = re.compile(r"\bfield\b|\bon[\s-]?site\b|\btravel(?:l?ing)?\b", _I)
_TITLE_PLACE_RE = re.compile(r"[-–—,(]\s*[A-Z][A-Za-z. ]+,\s*([A-Z]{2})\b")
_US_WIDE_RE = re.compile(
    r"\b(united\s+states|u\.s\.a?\.?|usa|us|nationwide|anywhere|north\s+america|"
    r"americas)\b", _I)
_FLORIDA_RE = re.compile(r"(?i:\bflorida\b)|\bFL\b")
_STATE_NAME_RE = re.compile(
    r"\b(" + "|".join(s for s in filters._US_STATES if s != "florida") + r")\b", _I)
# Hyphens are separators here: "Remote-LA" and "OH-Remote" name states.
_STATE_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(
        c for c in filters._US_CODES if c not in ("FL", "US", "USA")) + r")(?![A-Za-z0-9])")
_RESIDENCY_RE = re.compile(
    r"(?:must\s+(?:reside|live|be\s+located|be\s+based)|residents?\s+of|"
    r"(?:eligible|approved|following)\s+(?:states|locations)|"
    r"(?:hire|hiring|employ)\s+(?:only\s+)?in(?:\s+the\s+following)?(?:\s+states)?)"
    r"[^.\n]{0,400}", _I)


def remote_open_to_florida(location: str, title: str = "",
                           description_text: str = "") -> tuple[bool, str | None]:
    """(eligible, note). Only what the posting says: 'Remote - Texas' is not
    a job a Florida resident can take, 'Remote, United States' is."""
    loc = location or ""
    title = title or ""
    if not (_REMOTE_WORD_RE.search(loc) or _REMOTE_TITLE_RE.search(title)):
        return False, None
    if _FOREIGN_RE.search(loc) or _FOREIGN_RE.search(title):
        return False, None
    if _OTHER_REGION_RE.search(loc) or _OTHER_REGION_RE.search(title):
        return False, None
    if _FIELD_WORK_RE.search(title):
        return False, None
    named = _TITLE_PLACE_RE.search(title)
    if named and named.group(1) in filters._US_CODES:
        return False, None   # "Support Engineer - Utica, NY": the job is in Utica
    note = None
    options = [o.strip() for o in re.split(r"[;|]", loc) if o.strip()] or [loc]
    ok = False
    for option in options:
        residual = _REMOTE_WORD_RE.sub(" ", option)
        if _FLORIDA_RE.search(residual):
            ok = True
            break
        named_state = _STATE_NAME_RE.search(residual) or _STATE_CODE_RE.search(residual)
        if named_state:
            continue  # remote, but tied to another state
        if _US_WIDE_RE.search(residual):
            ok = True
            break
        if not re.search(r"[A-Za-z]{3,}", residual):
            ok = True  # a bare "Remote"
            note = "Remote region not stated"
            break
        if filters.is_united_states(option):
            ok = True
            break
    if not ok:
        return False, None
    for m in _RESIDENCY_RE.finditer(description_text or ""):
        chunk = m.group(0)
        states = len(_STATE_NAME_RE.findall(chunk)) + len(_STATE_CODE_RE.findall(chunk))
        if states >= 2 and not _FLORIDA_RE.search(chunk):
            return False, None
    return True, note


def place(location: str, title: str = "", description_text: str = "", *,
          latlon: tuple[float, float] | None = None,
          local_radius: float = 30.0, nearby_radius: float = 50.0,
          ) -> tuple[str | None, float | None, bool, str | None]:
    """(section, miles, is_remote, note). section None = outside the area."""
    miles = geo.miles_from_home(latlon) if latlon else geo.local_distance(location)
    is_remote, note = remote_open_to_florida(location, title, description_text)
    if miles is not None and miles <= local_radius:
        return LOCAL, miles, is_remote, note
    if miles is not None and miles <= nearby_radius:
        return NEARBY, miles, is_remote, note
    if is_remote:
        return REMOTE, None, True, note
    return None, miles, False, None
