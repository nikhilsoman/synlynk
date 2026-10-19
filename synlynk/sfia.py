"""Open SFIA 8/9 Taxonomy Classifier Module for Synlynk.

Provides standard SFIA professional discipline codes, category metadata, and a deterministic
task classifier mapping prompts, issue titles, commit messages, and descriptions into
skills disciplines across software engineering, creative multimedia, audio/video, VR,
and business operations.
"""

from __future__ import annotations

import re
from typing import Tuple

# Canonical SFIA 8/9 Taxonomy dictionary for Synlynk
SFIA_TAXONOMY: dict[str, dict[str, str]] = {
    "PROG": {
        "name": "Software Development",
        "domain": "Development & Implementation",
        "description": "Designing, building, refactoring, and verifying software components, algorithms, and systems.",
    },
    "TEST": {
        "name": "Testing",
        "domain": "Development & Implementation",
        "description": "Constructing test suites, automated test execution, QA verification, regression analysis, and assertion contracts.",
    },
    "REQM": {
        "name": "Requirements Definition and Management",
        "domain": "Strategy & Architecture",
        "description": "Defining user stories, specifications, architectural design documents, acceptance criteria, and system constraints.",
    },
    "DBDS": {
        "name": "Database Design",
        "domain": "Development & Implementation",
        "description": "Data modeling, schema migrations, table relationships, indexing, query optimization, and storage engines.",
    },
    "VISU": {
        "name": "Visual Design",
        "domain": "Development & Implementation",
        "description": "User interface design, CSS layouts, styling, components, responsive templates, and design systems.",
    },
    "ANIM": {
        "name": "Animation Development",
        "domain": "Creative & Content Operations",
        "description": "2D/3D skeletal animation, keyframe curves, transition effects, particle dynamics, and motion scripting.",
    },
    "GRAP": {
        "name": "Graphic Design",
        "domain": "Creative & Content Operations",
        "description": "Vector illustration, SVG assets, iconography, typography, infographics, and promotional imagery.",
    },
    "MUDI": {
        "name": "Multimedia Design",
        "domain": "Creative & Content Operations",
        "description": "Video production, montage editing, audio-visual sync, streaming pipelines, and rich media assets.",
    },
    "SNDD": {
        "name": "Sound Design & Audio Scripting",
        "domain": "Creative & Content Operations",
        "description": "Audio composition, Foley sound effects, synthetic waveforms, voice synthesis, and audio DSP scripting.",
    },
    "ICDV": {
        "name": "Interactive & VR/AR Development",
        "domain": "Creative & Content Operations",
        "description": "Spatial computing, WebXR, stereoscopic scenes, 3D world interaction, and haptic / immersive engines.",
    },
    "BUSA": {
        "name": "Business Analysis",
        "domain": "Business Operations & Strategy",
        "description": "Evaluating business processes, operational metrics, stakeholder workflows, and feasibility economics.",
    },
    "MKTG": {
        "name": "Marketing & Positioning",
        "domain": "Business Operations & Strategy",
        "description": "Go-to-market strategy, product positioning, launch announcements, press releases, and developer outreach.",
    },
    "COMM": {
        "name": "Communications & Technical Writing",
        "domain": "Business Operations & Strategy",
        "description": "Documentation, user guides, runbooks, release notes, tutorials, and technical retrospectives.",
    },
    "PROD": {
        "name": "Product Management",
        "domain": "Business Operations & Strategy",
        "description": "Roadmap planning, sprint backlog grooming, KPI setting, feature prioritization, and launch milestones.",
    },
    "UNAN": {
        "name": "Unclassified / General Operations",
        "domain": "General",
        "description": "Unclassified, ad-hoc, or cross-cutting operational tasks.",
    },
}

# Rule weights for deterministic classification
# Each pattern associates a regex with a target SFIA code and a confidence contribution
_CLASSIFICATION_RULES: list[tuple[re.Pattern, str, float]] = [
    # Testing & Verification (high priority patterns)
    (re.compile(r"\b(test|tests|pytest|unittest|testbed|mock|fixture|assertions|regression|qa\b|coverage|pr check|repro|audit|lint)\b", re.IGNORECASE), "TEST", 0.85),
    (re.compile(r"\b(verify|verification|validat|assert|reproduce)\b", re.IGNORECASE), "TEST", 0.65),

    # Database Design
    (re.compile(r"\b(database|sql|sqlite|postgres|postgresql|mysql|schema|migration|table|index|query|orm|foreign key)\b", re.IGNORECASE), "DBDS", 0.85),

    # Sound Design & Audio
    (re.compile(r"\b(audio|sound|soundtrack|sound effect|foley|dsp|synthesizer|waveform|speech|music|compose|acoustic)\b", re.IGNORECASE), "SNDD", 0.90),

    # Animation
    (re.compile(r"\b(animation|animate|keyframe|skeletal|tween|motion|easing|rigging|particle)\b", re.IGNORECASE), "ANIM", 0.90),

    # Multimedia (Video / Rich Media)
    (re.compile(r"\b(video|multimedia|montage|trailer|audiovisual|subtitles|transcode|stream)\b", re.IGNORECASE), "MUDI", 0.85),

    # Interactive / VR / AR
    (re.compile(r"\b(vr\b|ar\b|xr\b|webxr|stereoscopic|spatial|metaverse|haptic|immersive|three\.js|webgl)\b", re.IGNORECASE), "ICDV", 0.85),

    # Graphic & Visual Design
    (re.compile(r"\b(svg|vector|icon|icons|illustration|infographic|typography|font)\b", re.IGNORECASE), "GRAP", 0.85),
    (re.compile(r"\b(css|styling|theme|dark mode|glassmorphic|glassmorphism|layout|tailwind|html|ui\b|frontend|template|dialog|modal|website|landing page)\b", re.IGNORECASE), "VISU", 0.80),

    # Requirements, Architecture & Specifications
    (re.compile(r"\b(spec|specs|specification|architecture|architect|design doc|rfc\b|acceptance criteria|requirements?|system design|brainstorm|spike|poc\b|benchmark|benchmarks)\b", re.IGNORECASE), "REQM", 0.85),

    # Marketing & Positioning
    (re.compile(r"\b(marketing|press release|social media|pitch|positioning|gtm\b|campaign|outreach|launch post)\b", re.IGNORECASE), "MKTG", 0.85),

    # Communications & Docs
    (re.compile(r"\b(docs|documentation|readme|guide|runbook|retrospective|tutorial|handbook)\b", re.IGNORECASE), "COMM", 0.80),

    # Product Management
    (re.compile(r"\b(product|roadmap|milestone|backlog|epic|kpi|okr|prioritiz|sprint goal|release|version|bump|changelog)\b", re.IGNORECASE), "PROD", 0.85),

    # Business Analysis
    (re.compile(r"\b(business analysis|feasibility|stakeholder|roi\b|cost benefit|workflow analysis)\b", re.IGNORECASE), "BUSA", 0.80),

    # Core Software Programming / Development
    (re.compile(r"\b(fix|bug|refactor|implement|code|coding|function|class|method|algorithm|concurrency|thread|async|mutex|race condition|parse|parser|compiler|cli\b|backend|api\b|endpoint|module|subsystem|dispatch|migrate|remediation)\b", re.IGNORECASE), "PROG", 0.75),
    (re.compile(r"\b(feat|fix|chore|refactor|perf|build|ci)[:(]|\b(def|async def|class|import)\b", re.IGNORECASE), "PROG", 0.70),
]


def is_valid_sfia_code(code: str) -> bool:
    """Return True if code is a known SFIA discipline in the taxonomy."""
    return code in SFIA_TAXONOMY


def get_sfia_name(code: str) -> str:
    """Return the human-readable discipline name for a given SFIA code."""
    entry = SFIA_TAXONOMY.get(code)
    if entry:
        return entry["name"]
    return SFIA_TAXONOMY["UNAN"]["name"]


def get_sfia_domain(code: str) -> str:
    """Return the high-level category domain for a given SFIA code."""
    entry = SFIA_TAXONOMY.get(code)
    if entry:
        return entry["domain"]
    return SFIA_TAXONOMY["UNAN"]["domain"]


def classify_task_sfia(text: str) -> Tuple[str, str, float]:
    """Classify a task description, prompt, or title into an SFIA 8/9 code.

    Returns:
        tuple[str, str, float]: (sfia_code, domain_name, confidence_score)
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return "UNAN", SFIA_TAXONOMY["UNAN"]["domain"], 0.0

    scores: dict[str, float] = {}

    for pattern, code, weight in _CLASSIFICATION_RULES:
        matches = pattern.findall(clean_text)
        if matches:
            # Score scales logarithmically with match frequency
            count = len(matches)
            score = weight * min(1.0 + 0.15 * (count - 1), 1.5)
            scores[code] = scores.get(code, 0.0) + score

    if not scores:
        return "UNAN", SFIA_TAXONOMY["UNAN"]["domain"], 0.2

    # Select discipline with highest aggregated score
    best_code = max(scores, key=lambda c: scores[c])
    raw_score = scores[best_code]
    confidence = min(round(raw_score / 1.5, 2), 0.98)
    if confidence < 0.35:
        confidence = 0.35

    domain = get_sfia_domain(best_code)
    return best_code, domain, confidence
