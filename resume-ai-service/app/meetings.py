"""Catalog of built-in demo meetings addressable through stable API IDs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.vtt import duration_seconds, parse_vtt, transcript_from_captions

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

@dataclass(frozen=True)
class Meeting:
    id: str
    title: str
    description: str
    filename: str
    meeting_date: str

MEETINGS: dict[str, Meeting] = {
    "product-planning": Meeting(
        id="product-planning",
        title="Weekly Product Planning",
        description="Onboarding experiment, billing migration risk, and action owners.",
        filename="product-planning.vtt",
        meeting_date="2026-08-10",
    ),
    "customer-feedback": Meeting(
        id="customer-feedback",
        title="Education Customer Feedback Review",
        description="Interview findings, September release priorities, and follow-ups.",
        filename="customer-feedback.vtt",
        meeting_date="2026-08-11",
    ),
    "citi-fx-eur-attempt-1": Meeting(
        id="citi-fx-eur-attempt-1",
        title="CITI-FX EUR/USD Block — First Attempt",
        description="CITI-FX tries to reach the desk about a 250m EUR/USD fix order; unanswered, message left.",
        filename="citi-fx-eur-attempt-1.vtt",
        meeting_date="2026-08-22",
    ),
    "nomura-jgb-anomaly": Meeting(
        id="nomura-jgb-anomaly",
        title="NOMURA-RT JGB 10y Anomaly",
        description="Off-market bid on 10y JGB flagged as a pricing anomaly, second line requested before trading.",
        filename="nomura-jgb-anomaly.vtt",
        meeting_date="2026-08-22",
    ),
    "cpi-whisper-briefing": Meeting(
        id="cpi-whisper-briefing",
        title="CPI Whisper — Desk Briefing",
        description="Desk head instructs the desk to flatten 2s10s risk ahead of a CPI print running above consensus.",
        filename="cpi-whisper-briefing.vtt",
        meeting_date="2026-08-22",
    ),
    "citi-fx-eur-callback": Meeting(
        id="citi-fx-eur-callback",
        title="CITI-FX EUR/USD Block — Callback",
        description="Renata returns the call, confirms an axe, and agrees to work the block into the WM fix.",
        filename="citi-fx-eur-callback.vtt",
        meeting_date="2026-08-22",
    ),
    "jpm-cred-auto-basis-ask": Meeting(
        id="jpm-cred-auto-basis-ask",
        title="JPM-CRED Auto Issuer Basis — Ask",
        description="JPM-CRED asks for a two-way on the auto issuer basis trade, level due before tomorrow's open.",
        filename="jpm-cred-auto-basis-ask.vtt",
        meeting_date="2026-08-22",
    ),
    "nomura-jgb-confirm": Meeting(
        id="nomura-jgb-confirm",
        title="NOMURA-RT JGB 10y — Level Confirmed",
        description="Reference lines confirm the JGB anomaly is real; desk trades an initial clip on the bid.",
        filename="nomura-jgb-confirm.vtt",
        meeting_date="2026-08-22",
    ),
    "barc-swap-spread-colour": Meeting(
        id="barc-swap-spread-colour",
        title="BARC-RT Swap Spread Colour",
        description="Routine colour on 5y swap spreads widening on month-end positioning, no action needed.",
        filename="barc-swap-spread-colour.vtt",
        meeting_date="2026-08-22",
    ),
    "citi-fx-eur-escalation": Meeting(
        id="citi-fx-eur-escalation",
        title="CITI-FX EUR/USD Block — Escalation",
        description="Remaining block size split across two banks to reduce impact before the fix window closes.",
        filename="citi-fx-eur-escalation.vtt",
        meeting_date="2026-08-22",
    ),
    "hsbc-mxn-liquidity": Meeting(
        id="hsbc-mxn-liquidity",
        title="HSBC-EM MXN Liquidity Warning",
        description="MXN liquidity thinning ahead of a local holiday; no size quoted after 16:00.",
        filename="hsbc-mxn-liquidity.vtt",
        meeting_date="2026-08-22",
    ),
    "gs-fx-nzd-settlement": Meeting(
        id="gs-fx-nzd-settlement",
        title="GS-FX NZD Settlement Confirmation",
        description="Quick confirmation that yesterday's larger NZD trade settled correctly on both sides.",
        filename="gs-fx-nzd-settlement.vtt",
        meeting_date="2026-08-22",
    ),
    "cpi-aftermath-review": Meeting(
        id="cpi-aftermath-review",
        title="CPI Aftermath — Desk Review",
        description="Desk head and trader review how the flatten and client call volume played out after the print.",
        filename="cpi-aftermath-review.vtt",
        meeting_date="2026-08-23",
    ),
    "jpm-cred-auto-basis-confirm": Meeting(
        id="jpm-cred-auto-basis-confirm",
        title="JPM-CRED Auto Issuer Basis — Executed",
        description="Client confirms and executes the full 100m two-way on the auto issuer basis trade.",
        filename="jpm-cred-auto-basis-confirm.vtt",
        meeting_date="2026-08-23",
    ),
    "db-swaps-compression": Meeting(
        id="db-swaps-compression",
        title="DB-RT Swaps Compression Housekeeping",
        description="Confirmations from last week's compression run reconcile cleanly on both sides.",
        filename="db-swaps-compression.vtt",
        meeting_date="2026-08-23",
    ),
    "ubs-hoot-audio-check": Meeting(
        id="ubs-hoot-audio-check",
        title="UBS-RT Hoot Audio Check",
        description="Quick check that the JGB hoot line is audible again after a morning outage; no orders missed.",
        filename="ubs-hoot-audio-check.vtt",
        meeting_date="2026-08-23",
    ),
    "ms-cred-utility-levels": Meeting(
        id="ms-cred-utility-levels",
        title="MS-CRED Utility Levels",
        description="Indicative levels shared on two utility credit names, both inside current marks.",
        filename="ms-cred-utility-levels.vtt",
        meeting_date="2026-08-23",
    ),
    "citi-em-bond-inquiry": Meeting(
        id="citi-em-bond-inquiry",
        title="CITI-EM Local Bond Inquiry",
        description="Client interest in a 7y Brazil local bond; desk agrees to send an indicative two-way level.",
        filename="citi-em-bond-inquiry.vtt",
        meeting_date="2026-08-23",
    ),
    "socgen-fx-vol-nfp": Meeting(
        id="socgen-fx-vol-nfp",
        title="SOCGEN-RT FX Vol Ahead of NFP",
        description="FX implied volatility picking up ahead of payrolls; both desks keeping size lighter into the print.",
        filename="socgen-fx-vol-nfp.vtt",
        meeting_date="2026-08-23",
    ),
    "stanchart-asia-credit": Meeting(
        id="stanchart-asia-credit",
        title="STANCHART-EM Asia Credit Colour",
        description="Overnight Asia credit colour; one property developer name widened on headlines, largely noise.",
        filename="stanchart-asia-credit.vtt",
        meeting_date="2026-08-23",
    ),
    "rbc-cad-rates": Meeting(
        id="rbc-cad-rates",
        title="RBC-RT CAD Rates Positioning",
        description="Read on CAD rates positioning ahead of next week's central bank meeting; market fairly balanced.",
        filename="rbc-cad-rates.vtt",
        meeting_date="2026-08-23",
    ),
    "mizuho-jpy-intervention": Meeting(
        id="mizuho-jpy-intervention",
        title="MIZUHO-FX JPY Intervention Rumor",
        description="Unconfirmed intervention rumor on JPY; both desks keeping size conservative near the level.",
        filename="mizuho-jpy-intervention.vtt",
        meeting_date="2026-08-23",
    ),
}

def get_meeting(meeting_id: str) -> Meeting | None:
    return MEETINGS.get(meeting_id)

def load_meeting_transcript(meeting: Meeting) -> tuple[str, int]:
    captions = parse_vtt((SAMPLES_DIR / meeting.filename).read_text(encoding="utf-8"))
    return transcript_from_captions(captions), len(captions)

def meeting_participants(meeting: Meeting) -> list[str]:
    """Get unique speaker names in first-appearance order from VTT cue text."""
    captions = parse_vtt((SAMPLES_DIR / meeting.filename).read_text(encoding="utf-8"))
    names: list[str] = []
    for caption in captions:
        possible_name, separator, _ = caption.text.partition(":")
        name = possible_name.strip()
        if separator and name and name not in names:
            names.append(name)
    return names

def meeting_duration_seconds(meeting: Meeting) -> int:
    captions = parse_vtt((SAMPLES_DIR / meeting.filename).read_text(encoding="utf-8"))
    return duration_seconds(captions)
