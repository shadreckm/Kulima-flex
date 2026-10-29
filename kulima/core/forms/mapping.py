"""Assessment Mapping Layer (Phase 1) + entity awareness (Phase 6).

Two jobs, both deterministic and both free of LLM calls:

1. Map a raw provider payload (Forms API answer map, or a Sheet row) onto
   ``CollectedAnswer`` records with a readable question title. Titles come from
   the instrument's own schema, so nothing is paraphrased.

2. Give each entity type a *different* collection contract. An NGO's form
   answers "who did this reach and did services arrive", a tourism SME's form
   answers "what did visitors experience", a startup's form answers "does
   anyone pay for this". The evidence layer downstream is identical; only the
   mapping, the respondent vocabulary and the honesty caveat differ.

Nothing here re-derives the entity profile after a run starts: ``classify_entity``
feeds document filenames and matched terms into the corpus, and a filename
containing "survey" can flip a declared type. The connection therefore stores
the entity type it was created for and uses it as a label only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .models import CollectedAnswer, EvidenceClass, FormQuestion

# ── Respondent identity ──────────────────────────────────────────────────────
# Ordered: first match wins. Matched against question *titles* and answers, so
# a form that asks "Which ministry do you work with?" lands as Government.
RESPONDENT_TYPE_ORDER: tuple[str, ...] = (
    "Beneficiary / community member",
    "Programme participant",
    "Customer",
    "Visitor / tourist",
    "Community leader",
    "Local government officer",
    "Partner organisation",
    "Government officer",
    "Staff member",
    "Implementing partner",
    "Farmer / producer",
    "Supplier",
    "Unidentified respondent",
)

_RESPONDENT_NEEDLES: dict[str, tuple[str, ...]] = {
    "Beneficiary / community member": ("beneficiar", "community member", "household", "resident", "farmers like me", "you received"),
    "Programme participant": ("participant", "enrolled", "trained", "cohort", "program member"),
    "Customer": ("customer", "client", "buyer", "payer", "purchased", "subscri"),
    "Visitor / tourist": ("visitor", "tourist", "guest", "traveler", "traveller", "safari", "lodge stay"),
    "Community leader": ("village head", "community leader", "chief", "elders", "councillor", "ward"),
    "Local government officer": ("ward officer", "district officer", "local authority", "county", "municipal"),
    "Partner organisation": ("partner", "ngo partner", "implementing partner", "consortium"),
    "Government officer": ("ministry", "government official", "civil servant", "regulator", "agency staff"),
    "Staff member": ("staff", "employee", "your role at the organisation", "you work"),
    "Implementing partner": ("implementing", "sub-grantee", "sub recipient", "donor"),
    "Farmer / producer": ("farmer", "producer", "cooperative member", "aggregator"),
    "Supplier": ("supplier", "vendor", "distributor", "agent"),
    "Unidentified respondent": (),
}

# Question titles that identify a respondent. Used for the respondent_ref field
# only — the value itself is never copied into the evidence digest.
_IDENTIFIER_TITLE_PATTERNS = (
    "phone", "msisdn", "tel ", "email", "e-mail", "respondent id", "response id",
    "national id", "id number", "name of respondent", "full name", "gps", "village id",
)

_ANSWER_TYPE_KEYS: dict[str, str] = {
    "textQuestion": "text",
    "paragraphTextQuestion": "long text",
    "choiceQuestion": "single choice",
    "dropdownQuestion": "dropdown",
    "checkboxQuestion": "multi choice",
    "linearScaleQuestion": "linear scale",
    "gridQuestion": "grid",
    "dateQuestion": "date",
    "timeQuestion": "time",
    "datetimeQuestion": "date & time",
    "ratingQuestion": "rating",
    "fileUploadQuestion": "file",
}


@dataclass(frozen=True)
class EntityCollectionContract:
    """How one entity type is allowed to use a collection channel."""

    entity_type: str
    label: str
    default_evidence_class: str
    purpose: str
    respondent_types: tuple[str, ...]
    required_blocks: tuple[str, ...]
    signal_domains: tuple[str, ...]
    #: Responses below this count are not directional for this entity type.
    minimum_responses: int
    #: What the channel can never establish for this entity (shown verbatim).
    honesty_caveat: str
    report_sections: tuple[str, ...] = field(default_factory=tuple)


_CONTRACTS: dict[str, EntityCollectionContract] = {
    "ngo": EntityCollectionContract(
        entity_type="ngo",
        label="NGO / non-profit",
        default_evidence_class=EvidenceClass.COMMUNITY.value,
        purpose="Verify reach, service quality and monitoring claims against what beneficiaries themselves report.",
        respondent_types=("Beneficiary / community member", "Community leader", "Staff member", "Partner organisation"),
        required_blocks=("Reach (who responded, where)", "Service quality and access barriers", "Grievance and feedback route", "Verification consent"),
        signal_domains=("Institutional Capacity", "Programme Performance", "Community Reach", "Funding Sustainability", "Monitoring Quality"),
        minimum_responses=30,
        honesty_caveat="A form you distributed cannot verify your own financials, governance or audit position. Those stay with documents.",
        report_sections=("Institutional Capacity Review", "Programme Performance Review", "Outcome Tracking"),
    ),
    "development_program": EntityCollectionContract(
        entity_type="development_program",
        label="Development programme",
        default_evidence_class=EvidenceClass.COMMUNITY.value,
        purpose="Measure delivery against the results framework and capture beneficiary-level experience across sites.",
        respondent_types=("Programme participant", "Beneficiary / community member", "Implementing partner", "Government officer"),
        required_blocks=("Site / district identifier", "Indicator experience questions", "Delivery timing", "Do no harm / consent"),
        signal_domains=("Programme Performance", "Institutional Capacity", "Community Reach", "Funding Sustainability", "Monitoring Quality"),
        minimum_responses=30,
        honesty_caveat="Self-reported delivery data corroborates a results framework; it does not replace baseline or endline measurement.",
        report_sections=("Programme Performance Review", "Delivery Coverage", "Outcome Tracking"),
    ),
    "government_program": EntityCollectionContract(
        entity_type="government_program",
        label="Government programme",
        default_evidence_class=EvidenceClass.OPERATIONAL.value,
        purpose="Test citizen experience of a public service and where delivery capacity breaks down.",
        respondent_types=("Beneficiary / community member", "Local government officer", "Government officer", "Supplier"),
        required_blocks=("Service touched", "Wait time / cost to access", "Officer conduct", "Redress channel"),
        signal_domains=("Governance", "Policy Alignment", "Delivery Capacity", "Public Value"),
        minimum_responses=50,
        honesty_caveat="Representativeness matters more here than volume: an unweighted citizen sample cannot evidence programme-wide performance.",
        report_sections=("Public Value Review", "Delivery Capacity Review", "Outcome Tracking"),
    ),
    "tourism_sme": EntityCollectionContract(
        entity_type="tourism_sme",
        label="Tourism SME",
        default_evidence_class=EvidenceClass.SURVEY.value,
        purpose="Capture visitor experience, community impact and destination readiness from the people who paid.",
        respondent_types=("Visitor / tourist", "Community leader", "Supplier", "Staff member"),
        required_blocks=("Trip type and origin", "Experience quality", "Local spending and employment", "Season and climate exposure"),
        signal_domains=("Tourism Signals", "Climate Signals", "Community Signals", "Destination Readiness", "Visitor Economy Signals"),
        minimum_responses=20,
        honesty_caveat="Visitor satisfaction is demand-side evidence. Occupancy, revenue and licence position must come from documents.",
        report_sections=("Destination Readiness Review", "Visitor Economy Review", "Community Signal Review"),
    ),
    "startup": EntityCollectionContract(
        entity_type="startup",
        label="Startup / venture",
        default_evidence_class=EvidenceClass.SURVEY.value,
        purpose="Test whether customers recognise the problem, pay for the solution, and stay.",
        respondent_types=("Customer", "Programme participant", "Supplier", "Partner organisation"),
        required_blocks=("Who they are / company size", "Problem and current workaround", "Willingness and evidence of payment", "Retention or renewal intent"),
        signal_domains=("Founder Risk", "Market Readiness", "Revenue Potential", "Investment Readiness"),
        minimum_responses=40,
        honesty_caveat="Stated intent is not traction. Revenue, unit economics and cap table claims stay with financial statements and filings.",
        report_sections=("Market Readiness Review", "Revenue Potential Review", "Outcome Tracking"),
    ),
}

_DEFAULT_CONTRACT = _CONTRACTS["ngo"]

#: Types not listed above still collect; they inherit the NGO-shaped contract
#: with a neutral label so the UI never shows a blank guidance block.
_ALIAS_LABELS = {
    "foundation": "Foundation",
    "cooperative": "Cooperative",
    "social_enterprise": "Social enterprise",
    "farmer_organization": "Farmer organization",
    "research_institution": "Research institution",
    "accelerator": "Accelerator",
}


def collection_contract(entity_type: str | None) -> EntityCollectionContract:
    """Resolve the per-entity contract; unknown types fall back without failing."""
    key = str(entity_type or "").strip().lower()
    base = _CONTRACTS.get(key, _DEFAULT_CONTRACT)
    if key in _ALIAS_LABELS and base.entity_type != key:
        from dataclasses import replace

        base = replace(base, entity_type=key, label=_ALIAS_LABELS[key])
    return base


def entity_guidance(entity_type: str | None) -> dict[str, Any]:
    """API/UI payload: how this workspace's entity should use the channel."""
    c = collection_contract(entity_type)
    return {
        "entityType": c.entity_type,
        "entityLabel": c.label,
        "purpose": c.purpose,
        "defaultEvidenceClass": c.default_evidence_class,
        "respondentTypes": list(c.respondent_types),
        "requiredBlocks": list(c.required_blocks),
        "signalDomains": list(c.signal_domains),
        "minimumResponses": c.minimum_responses,
        "honestyCaveat": c.honesty_caveat,
        "reportSections": list(c.report_sections),
    }


# ── Schema discovery & answer mapping ────────────────────────────────────────

def questions_from_metadata(form: Mapping[str, Any]) -> list[FormQuestion]:
    """Build the instrument schema from a Forms API ``Form`` resource.

    Both ``items[].itemId`` and ``items[].questionId`` are recorded as lookup
    keys: the responses endpoint keys its answer map by question id, and the
    field returned for an item id depends on the API version.
    """
    questions: list[FormQuestion] = []
    # The Forms API returns ``items`` at the top of the Form resource and keeps
    # only titles/info under ``info``. Accept a nested ``info.items`` shape too,
    # but never let it shadow the real one (that silently returned nothing).
    items = form.get("items")
    if not items:
        info = form.get("info")
        items = info.get("items") if isinstance(info, Mapping) else None
    for item in items or []:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("title") or "").strip()
        qtype = "text"
        options: list[str] = []
        # The Forms API puts the question-type block on the item itself; older
        # and proxied shapes nest it under "question". Accept either.
        holders = [item]
        nested = item.get("question")
        if isinstance(nested, Mapping):
            holders.append(nested)
        for key, readable in _ANSWER_TYPE_KEYS.items():
            block: Any = None
            for holder in holders:
                if key in holder:
                    block = holder.get(key) or {}
                    break
            if not isinstance(block, Mapping):
                continue
            qtype = readable
            opts = block.get("options")
            for opt in opts or []:
                if isinstance(opt, Mapping) and opt.get("value"):
                    options.append(str(opt["value"]))
            break
        required = False
        for holder in holders:
            if "required" in holder:
                required = bool(holder.get("required"))
                break
        keys = [str(item.get("questionId") or ""), str(item.get("itemId") or "")]
        for k in [x for x in keys if x]:
            if any(q.key == k for q in questions):
                continue
            questions.append(
                FormQuestion(
                    key=k,
                    title=title or f"Question {k}",
                    question_type=qtype,
                    required=required,
                    options=options,
                )
            )
    return questions


def schema_hash(questions: Sequence[FormQuestion]) -> str:
    """Stable fingerprint of the instrument (design: schema drift is visible)."""
    import hashlib

    parts = "|".join(f"{q.title}::{q.question_type}::{len(q.options)}" for q in questions)
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:16]


def title_for_key(questions: Sequence[FormQuestion], key: str) -> str:
    for q in questions:
        if q.key == str(key):
            return q.title
    return f"Question {key}"


def _flatten_value(answer_block: Any) -> tuple[str, str]:
    """Extract (value, type) from one Forms API answer object."""
    if not isinstance(answer_block, Mapping):
        return str(answer_block or ""), "text"
    if "questionTitle" in answer_block and not answer_block.get("textAnswers"):
        # Some payload shapes only carry the title; nothing to record.
        return "", str(answer_block.get("type") or "text")
    text = answer_block.get("textAnswers") or {}
    if isinstance(text, Mapping):
        values = [str(v.get("value") or "") for v in (text.get("answers") or []) if isinstance(v, Mapping)]
        joined = "; ".join(v for v in values if v)
        if joined:
            return joined, "text"
    for key, label in (
        ("multipleChoiceAnswer", "single choice"),
        ("checkboxAnswer", "multi choice"),
        ("dropdownAnswer", "dropdown"),
        ("linearScaleAnswer", "linear scale"),
        ("ratingAnswer", "rating"),
        ("dateAnswer", "date"),
        ("timeAnswer", "time"),
        ("datetimeAnswer", "date & time"),
    ):
        block = answer_block.get(key)
        if isinstance(block, Mapping):
            if "value" in block:
                return str(block["value"]), label
            if "values" in block:
                return "; ".join(str(v) for v in (block.get("values") or [])), label
            if "date" in block:
                return str(block.get("date")), label
            if "hours" in block:
                return f"{block.get('hours')}:{str(block.get('minutes', 0)).zfill(2)}", label
    grid = answer_block.get("gridAnswer")
    if isinstance(grid, Mapping):
        rows = grid.get("rows") or []
        parts = []
        for row in rows:
            if isinstance(row, Mapping):
                parts.append(f"{row.get('rowQuestionTitle', '')}={'; '.join(str(v) for v in ((row.get('multipleChoiceAnswer') or {}).get('value'),) if v)}")
        return " | ".join(p for p in parts if p), "grid"
    return "", "text"


def _answer_pairs(payload: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    """Return (question key, answer block) pairs from either response shape.

    The Forms API v1 puts answers in ``answerSheet.answers`` as a *list*, each
    element carrying ``questionId`` plus one answer block. Older and proxied
    payloads key a *map* by question id. Both are accepted; nothing is guessed
    beyond those two documented shapes.
    """
    raw = payload.get("answers")
    if not isinstance(raw, (Mapping, list)):
        sheet = payload.get("answerSheet")
        raw = sheet.get("answers") if isinstance(sheet, Mapping) else None
    if isinstance(raw, Mapping):
        return [(str(key), block) for key, block in raw.items() if isinstance(block, Mapping)]
    pairs: list[tuple[str, Mapping[str, Any]]] = []
    for idx, entry in enumerate(raw or []):
        if not isinstance(entry, Mapping):
            continue
        key = str(entry.get("questionId") or entry.get("question_id") or f"answer_{idx}")
        block = entry.get("answer") if isinstance(entry.get("answer"), Mapping) else entry
        pairs.append((key, block))
    return pairs


def answers_from_form_response(
    payload: Mapping[str, Any],
    questions: Sequence[FormQuestion],
) -> list[CollectedAnswer]:
    """Normalise one Forms API response into ordered answers."""
    out: list[CollectedAnswer] = []
    order = {q.key: i for i, q in enumerate(questions)}
    pairs = _answer_pairs(payload)
    ranked = sorted(
        enumerate(pairs),
        key=lambda pair: (order.get(pair[1][0], len(order) + pair[0]), pair[0]),
    )
    for _idx, (key, block) in ranked:
        title = str(block.get("questionTitle") or "")
        if not title:
            title = title_for_key(questions, key)
        value, atype = _flatten_value(block)
        if not value and atype == "text":
            continue
        out.append(CollectedAnswer(question_key=key, question_title=title, value=value, answer_type=atype))
    return out


def answers_from_sheet_row(
    headers: Sequence[str],
    row: Sequence[str],
) -> list[CollectedAnswer]:
    """Normalise one linked-sheet response row (the Sheets connector path)."""
    out: list[CollectedAnswer] = []
    for i, header in enumerate(headers):
        title = str(header or "").strip()
        if not title:
            continue
        value = str(row[i]).strip() if i < len(row) and row[i] is not None else ""
        atype = "timestamp" if "timestamp" in title.lower() else ("text" if not value.replace(".", "", 1).isdigit() else "numeric")
        if not value:
            continue
        out.append(CollectedAnswer(question_key=title, question_title=title, value=value, answer_type=atype))
    return out


# ── Respondent identity + privacy ────────────────────────────────────────────

def _looks_identifier(title: str) -> bool:
    low = (title or "").lower()
    return any(p in low for p in _IDENTIFIER_TITLE_PATTERNS)


def detect_respondent_type(answers: Iterable[CollectedAnswer]) -> tuple[str, str]:
    """Return (respondent_type, respondent_ref).

    ``respondent_ref`` is a non-reversible local marker, never the raw contact
    value: personal data must not be copied into the evidence corpus, where it
    would be rendered in reports and read by the signals layer.
    """
    import hashlib

    haystack = " ".join(f"{a.question_title} {a.value}" for a in answers).lower()
    matched = "Unidentified respondent"
    for candidate in RESPONDENT_TYPE_ORDER:
        needles = _RESPONDENT_NEEDLES.get(candidate, ())
        if needles and any(n in haystack for n in needles):
            matched = candidate
            break
    ref = ""
    for a in answers:
        if _looks_identifier(a.question_title) and a.value:
            ref = "anon-" + hashlib.sha256(a.value.encode("utf-8")).hexdigest()[:10]
            break
    return matched, ref


def identifier_titles(answers: Iterable[CollectedAnswer]) -> list[str]:
    return [a.question_title for a in answers if _looks_identifier(a.question_title) and a.value]


_NUMERIC_TOKEN = re.compile(r"^\s*-?\d+(\.\d+)?\s*$")


def is_numeric(value: str) -> bool:
    return bool(_NUMERIC_TOKEN.match(value or ""))
