import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
import anthropic
from PIL import Image
from urllib.parse import quote_plus, urljoin
from fpdf import FPDF
from email.message import EmailMessage
import smtplib
import urllib.request
import base64
import io
import os
import json
import time
import re
import tempfile
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Executive Intelligence Suite",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

CACHE_DIR = ".audit_cache"
TTL_SECONDS = 2 * 24 * 3600  # 48 hours
MAX_LOGO_BYTES = 5 * 1024 * 1024  # 5 MB
os.makedirs(CACHE_DIR, exist_ok=True)

BUSINESS_MODELS = [
    "B2C / DTC",
    "B2B / B2B SaaS",
    "Hybrid / B2B2C",
]

NO_LATEX_CURRENCY_RULE = (
    "CURRENCY & FORMATTING RULE: Never wrap numbers or currency values in LaTeX dollar delimiters like $250K$ or $3,00,000/mo$. "
    "Write plain text such as USD 250K, INR 3,00,000/mo, or GBP 1,000."
)


def _sanitize_display_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    # Strip accidental LaTeX math delimiters around currency/numbers like $250K$ or $3,00,000$
    cleaned = re.sub(r"\$([^$\n]{1,60})\$", r"\1", cleaned)
    # Normalize unicode arrows/dashes cleanly while preserving readability
    cleaned = cleaned.replace("\u2192", "->")
    return cleaned


def _score_tier_rgb(score_str: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    digits = re.sub(r"[^\d]", "", str(score_str or ""))
    val = int(digits) if digits else 65
    if val < 50:
        return (254, 226, 226), (153, 27, 27)   # Soft Red fill, dark red text
    if val < 70:
        return (254, 243, 199), (146, 64, 14)   # Soft Amber fill, dark amber text
    return (209, 250, 229), (6, 95, 70)        # Soft Emerald fill, dark green text


def _score_tier_css(score_str: str) -> str:
    digits = re.sub(r"[^\d]", "", str(score_str or ""))
    val = int(digits) if digits else 65
    if val < 50:
        return "score-low"
    if val < 70:
        return "score-mid"
    return "score-high"


def _get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            val = st.secrets[key]
            if val is not None:
                return str(val).strip()
    except Exception:
        pass
    return os.getenv(key, default).strip()


def _get_gcp_credentials():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            if info:
                return Credentials.from_service_account_info(info, scopes=scopes)
    except Exception:
        pass

    fallback_file = "gserviceaccount.json"
    if os.path.exists(fallback_file):
        return Credentials.from_service_account_file(fallback_file, scopes=scopes)
    return None


GEMINI_KEY = _get_secret("GEMINI_API_KEY")
CLAUDE_KEY = _get_secret("ANTHROPIC_API_KEY")
GMAIL_SENDER = _get_secret("GMAIL_SENDER")
GMAIL_APP_PASSWORD = _get_secret("GMAIL_APP_PASSWORD").replace(" ", "")
GSHEET_ID = _get_secret("GSHEET_ID")
BACKEND_FORCE_REFRESH = _get_secret("FORCE_REFRESH", "false").lower() in ("1", "true", "yes")
GENERATE_IMAGES_DEFAULT = _get_secret("GENERATE_IMAGES", "true").lower() in ("1", "true", "yes")


# -----------------------------------------------------------------------------
# LEAD LOGGING (GOOGLE SHEETS) & PDF EMAIL DELIVERY (GMAIL SMTP)
# -----------------------------------------------------------------------------
def _is_valid_email(email: str) -> bool:
    cleaned = (email or "").strip()
    return re.match(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$", cleaned) is not None


def _log_lead_to_sheet(email: str, company: str, country: str = "", biz_model: str = "") -> tuple[bool, str]:
    if not GSHEET_ID:
        return False, "GSHEET_ID is not configured in Streamlit Secrets."
    creds = _get_gcp_credentials()
    if creds is None:
        return False, "Google service account credentials ([gcp_service_account]) are missing from Streamlit Secrets."
    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GSHEET_ID)
        ws = sh.get_worksheet(0)
        ws.append_row([
            email.strip(),
            company.strip(),
            (country or "Global").strip(),
            (biz_model or "B2C / DTC").strip(),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ])
        return True, "Saved"
    except Exception as e:
        return False, f"Google Sheets error: {e}"


def _send_pdf_via_gmail_smtp(
    recipient_email: str,
    company: str,
    country: str,
    pdf_bytes: bytes,
    filename: str,
) -> tuple[bool, str]:
    if not GMAIL_SENDER:
        return False, "GMAIL_SENDER is not configured in Streamlit Secrets."
    if not GMAIL_APP_PASSWORD:
        return False, "GMAIL_APP_PASSWORD is not configured in Streamlit Secrets."

    geo_label = f" - {country}" if country else ""
    msg = EmailMessage()
    msg["From"] = f"Executive Intelligence Suite <{GMAIL_SENDER}>"
    msg["To"] = recipient_email.strip()
    msg["Subject"] = f"Your PDF report for {company}{geo_label}"
    msg.set_content(
        f"Hello,\n\n"
        f"Here is the PDF report you requested for {company}{geo_label}.\n\n"
        f"If you do not see it in your primary inbox within a minute, please check your "
        f"Spam or Promotions folder and mark the message as Not spam.\n\n"
        f"Regards,\nSoumya Ranjan Nayak"
    )
    msg.add_alternative(
        f"<p>Hello,</p>"
        f"<p>Here is the PDF report you requested for <strong>{company}{geo_label}</strong>.</p>"
        f"<p>If it does not appear in your primary inbox within a minute, please check your "
        f"<strong>Spam</strong> or <strong>Promotions</strong> folder and mark it as "
        f"<strong>Not spam</strong>.</p>"
        f"<p>Regards,<br/>Soumya Ranjan Nayak</p>",
        subtype="html",
    )
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True, "Sent"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail SMTP authentication failed. Verify GMAIL_SENDER and your 16-character Google App Password."
    except Exception as e:
        return False, f"Gmail SMTP error: {e}"


# -----------------------------------------------------------------------------
# COUNTRY CODE HELPER FOR AD TRANSPARENCY LINKS
# -----------------------------------------------------------------------------
COUNTRY_REGION_MAP = {
    "united states": "US",
    "usa": "US",
    "us": "US",
    "india": "IN",
    "brazil": "BR",
    "brasil": "BR",
    "united kingdom": "GB",
    "uk": "GB",
    "germany": "DE",
    "france": "FR",
    "canada": "CA",
    "australia": "AU",
    "japan": "JP",
    "mexico": "MX",
    "spain": "ES",
    "italy": "IT",
    "netherlands": "NL",
    "singapore": "SG",
    "uae": "AE",
    "united arab emirates": "AE",
}


def resolve_region_code(country: str) -> str:
    cleaned = (country or "").strip().lower()
    if not cleaned:
        return "ALL"
    if cleaned in COUNTRY_REGION_MAP:
        return COUNTRY_REGION_MAP[cleaned]
    if len(cleaned) == 2 and cleaned.isalpha():
        return cleaned.upper()
    return "ALL"


# -----------------------------------------------------------------------------
# BUSINESS MODEL CONTEXT & MODULE ADAPTATION RULES
# -----------------------------------------------------------------------------
def _model_guidance(biz_model: str) -> dict:
    model = biz_model if biz_model in BUSINESS_MODELS else "B2C / DTC"
    if model == "B2B / B2B SaaS":
        return {
            "label": "B2B / B2B SaaS",
            "cro_pillar": "3. Landing Page, Demo/Trial & Pipeline CRO",
            "checkout_pillar": "4. Lead Routing, Sales Handoff & Buying-Committee Friction",
            "pricing_summary_label": "Current Monetization & Packaging Strategy",
            "pricing_p1": "1. Core Plan, Seat/Usage Tier & ACV Positioning",
            "pricing_p2": "2. Free Trial, Freemium & Implementation Fee Architecture",
            "pricing_p3": "3. Expansion, NRR & Multi-Year Renewal Monetization",
            "pricing_p4": "4. Enterprise Tier, Add-On Module & Services Mix",
            "social_p1": "1. Pipeline Velocity, Demo/SQL & Post-Signup Sentiment",
            "social_p2": "2. Category Authority, Security/ROI & Product Trust",
            "social_p3": "3. G2 / Capterra / Peer Review & Forum Parity",
            "social_p4": "4. Executive / Founder Advocacy & Customer Proof",
            "prompt_context": (
                "BUSINESS MODEL: Pure B2B / B2B SaaS. Focus on ICP precision, buying committees "
                "(economic buyer, technical evaluator, end user, procurement), high-intent search vs. demand creation, "
                "LinkedIn + Google Search mix, demo/trial-to-SQL conversion, speed-to-lead, ACV/seat/usage tiers, "
                "CAC payback/NRR, G2/Capterra reviews, and executive/founder thought leadership. Avoid retail cart/COD/AOV jargon."
            ),
        }
    if model == "Hybrid / B2B2C":
        return {
            "label": "Hybrid / B2B2C",
            "cro_pillar": "3. Multi-Path Funnel & Partner/Direct CRO",
            "checkout_pillar": "4. Order/Quote Routing, Partner Handoff & Fulfillment Friction",
            "pricing_summary_label": "Current Dual-Channel & Partner Pricing Strategy",
            "pricing_p1": "1. Direct vs. Partner / Channel Price Alignment",
            "pricing_p2": "2. Freight, Installation/Onboarding & Threshold Architecture",
            "pricing_p3": "3. Repeat Replenishment, Attach & Lifecycle Retention",
            "pricing_p4": "4. High-Margin Bundles, Add-Ons & Commercial Program Mix",
            "social_p1": "1. End-User & Partner Fulfillment / Handoff Sentiment",
            "social_p2": "2. Technical / Product Reliability & Brand Trust",
            "social_p3": "3. Consumer Review & B2B/Partner Reputation Parity",
            "social_p4": "4. Community Advocacy, Partner Co-Marketing & Earned Proof",
            "prompt_context": (
                "BUSINESS MODEL: Hybrid / B2B2C (serves both end consumers/prosumers and business/partner/channel buyers). "
                "Explicitly address both sides of the motion—direct conversion/checkout/CRO AND commercial/partner/installer "
                "or multi-stakeholder demand—plus channel conflict, margin/attach economics, and two-sided trust."
            ),
        }
    return {
        "label": "B2C / DTC",
        "cro_pillar": "3. Landing Page & Product-to-Cart CRO",
        "checkout_pillar": "4. Checkout, Booking & Post-Click Friction",
        "pricing_summary_label": "Current Pricing Strategy",
        "pricing_p1": "1. Core SKU & Marketplace Price Positioning",
        "pricing_p2": "2. Shipping, Fee & Basket Threshold Architecture",
        "pricing_p3": "3. Subscription & Repeat-Cohort Monetization",
        "pricing_p4": "4. Private-Label & High-Margin Service Mix",
        "social_p1": "1. Fulfillment & Post-Purchase Sentiment",
        "social_p2": "2. Clinical & Product Trust Authority",
        "social_p3": "3. Review Ecosystem Parity",
        "social_p4": "4. Community Advocacy & Earned Momentum",
        "prompt_context": (
            "BUSINESS MODEL: B2C / DTC. Focus on consumer purchase intent, AOV, cart/checkout conversion, "
            "shipping/COD/fee friction, repeat replenishment/subscriptions, private-label/bundle margin, "
            "consumer reviews, and creator/social engagement."
        ),
    }


# -----------------------------------------------------------------------------
# UNIFIED TYPOGRAPHY, APPLE PILL BUTTONS & CLICKABLE BENTO CSS
# -----------------------------------------------------------------------------
st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="collapsedControl"] {
    display: none !important;
}

:root {
    --font-ui: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", Arial, sans-serif;
    --fs-hero: 3.3rem;
    --fs-h2: 1.45rem;
    --fs-h3: 1.15rem;
    --fs-body: 0.95rem;
    --apple-blue: #0071E3;
    --apple-blue-hover: #0077ED;
}

html, body, .stApp, .stMarkdown, p, li, label, input, div, table, th, td {
    font-family: var(--font-ui) !important;
    font-size: var(--fs-body);
    color: #1D1D1F;
}

[data-testid="stIconMaterial"],
.material-symbols-rounded,
.material-symbols-outlined {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined", sans-serif !important;
}

.stApp {
    background-color: #FBFBFD !important;
}

.block-container {
    max-width: 1080px !important;
    padding-top: 3.5rem !important;
    padding-bottom: 4rem !important;
}

h1.suite-title, div.suite-title, .suite-title {
    font-size: var(--fs-hero) !important;
    font-weight: 700 !important;
    letter-spacing: -0.03em !important;
    line-height: 1.12 !important;
    color: #1D1D1F !important;
    margin: 0 0 0.5rem 0 !important;
}

h2 {
    font-size: var(--fs-h2) !important;
    font-weight: 600 !important;
    letter-spacing: -0.015em !important;
    line-height: 1.25 !important;
    color: #1D1D1F !important;
    margin: 0.5rem 0 0.35rem 0 !important;
}

h3 {
    font-size: var(--fs-h3) !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    line-height: 1.3 !important;
    color: #1D1D1F !important;
    margin: 0.25rem 0 0.25rem 0 !important;
}

.suite-subtitle {
    font-size: 1.06rem !important;
    color: #6E6E73 !important;
    margin: 0 0 1.25rem 0 !important;
    line-height: 1.5 !important;
    max-width: 820px;
}

.preset-strip-label {
    font-size: var(--fs-body) !important;
    font-weight: 500 !important;
    color: #6E6E73 !important;
    padding-top: 0.3rem !important;
}

.model-detect-banner {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 14px;
    padding: 0.85rem 1.1rem;
    margin: 0.75rem 0 0.6rem 0;
}

.status-panel {
    background-color: #FFFFFF;
    border: 1px solid #E5E5EA;
    border-radius: 14px;
    padding: 0.85rem 1.1rem;
    margin: 0.8rem 0 0.45rem 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
}

.status-step-label {
    font-weight: 600 !important;
    color: #1D1D1F !important;
}

.status-pct-pill {
    font-weight: 600 !important;
    color: var(--apple-blue) !important;
    background-color: #EEF6FF;
    padding: 0.14rem 0.65rem;
    border-radius: 999px;
    white-space: nowrap;
}

div[data-testid="stProgress"] > div > div > div > div {
    background-color: var(--apple-blue) !important;
}

/* Uniform clickable Bento cards with invisible full-surface click trigger */
.bento-card {
    background-color: #FFFFFF;
    border: 1.5px solid #E5E5EA;
    border-radius: 16px;
    padding: 1.05rem 1.1rem;
    height: 148px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: border-color 0.12s ease, box-shadow 0.12s ease, background-color 0.12s ease;
}

.bento-card-selected {
    background-color: #F4F9FF;
    border: 1.8px solid var(--apple-blue);
    box-shadow: 0 6px 16px rgba(0, 113, 227, 0.12);
}

.bento-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.4rem;
}

.bento-pillar {
    font-size: var(--fs-body) !important;
    font-weight: 700 !important;
    color: #1D1D1F !important;
    line-height: 1.25 !important;
}

.bento-score {
    font-size: var(--fs-body) !important;
    font-weight: 600 !important;
    color: var(--apple-blue) !important;
    background-color: #EEF6FF;
    padding: 0.12rem 0.55rem;
    border-radius: 999px;
    white-space: nowrap;
}

.bento-score.score-low {
    background-color: #FEE2E2 !important;
    color: #991B1B !important;
}

.bento-score.score-mid {
    background-color: #FEF3C7 !important;
    color: #92400E !important;
}

.bento-score.score-high {
    background-color: #D1FAE5 !important;
    color: #065F46 !important;
}

.bento-oneliner {
    font-size: var(--fs-body) !important;
    color: #424245 !important;
    line-height: 1.4 !important;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

div[data-testid="stElementContainer"]:has(.bento-card) {
    margin-bottom: 0 !important;
}

div[data-testid="stElementContainer"]:has(.bento-card) + div[data-testid="stElementContainer"] {
    margin-top: -148px !important;
    height: 148px !important;
    position: relative !important;
    z-index: 4 !important;
}

div[data-testid="stElementContainer"]:has(.bento-card) + div[data-testid="stElementContainer"] div[data-testid="stButton"],
div[data-testid="stElementContainer"]:has(.bento-card) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button {
    width: 100% !important;
    height: 148px !important;
    min-height: 148px !important;
    opacity: 0 !important;
    cursor: pointer !important;
    border-radius: 16px !important;
    margin: 0 !important;
    padding: 0 !important;
}

div[data-testid="stTextInput"] input {
    background-color: #FFFFFF !important;
    border: 1px solid #D2D2D7 !important;
    border-radius: 10px !important;
    padding: 0.65rem 0.95rem !important;
    font-size: var(--fs-body) !important;
    color: #1D1D1F !important;
}

div[data-testid="stButton"] > button,
div[data-testid="stButton"] > button p,
div[data-testid="stFormSubmitButton"] > button,
div[data-testid="stFormSubmitButton"] > button p {
    font-family: var(--font-ui) !important;
    font-weight: 500 !important;
    font-size: var(--fs-body) !important;
    color: #FFFFFF !important;
}

div[data-testid="stButton"] > button,
div[data-testid="stFormSubmitButton"] > button {
    border-radius: 999px !important;
    padding: 0.45rem 1.2rem !important;
    background-color: var(--apple-blue) !important;
    border: 1.5px solid var(--apple-blue) !important;
    transition: background-color 0.12s ease, border-color 0.12s ease !important;
}

div[data-testid="stButton"] > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    background-color: var(--apple-blue-hover) !important;
    border-color: var(--apple-blue-hover) !important;
    color: #FFFFFF !important;
}

div[data-testid="stDownloadButton"] > button,
div[data-testid="stDownloadButton"] > button p,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button p,
div[data-testid="stElementContainer"]:has(.collapse-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button,
div[data-testid="stElementContainer"]:has(.collapse-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button p {
    font-family: var(--font-ui) !important;
    font-weight: 500 !important;
    font-size: var(--fs-body) !important;
    color: var(--apple-blue) !important;
}

div[data-testid="stDownloadButton"] > button,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button,
div[data-testid="stElementContainer"]:has(.collapse-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button {
    background-color: transparent !important;
    border: 1.5px solid var(--apple-blue) !important;
    border-radius: 999px !important;
    padding: 0.45rem 1.2rem !important;
    transition: background-color 0.12s ease, color 0.12s ease !important;
}

div[data-testid="stDownloadButton"] > button:hover,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button:hover,
div[data-testid="stElementContainer"]:has(.collapse-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button:hover {
    background-color: rgba(0, 113, 227, 0.06) !important;
    border-color: var(--apple-blue-hover) !important;
    color: var(--apple-blue-hover) !important;
}

details[data-testid="stExpander"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E5E5EA !important;
    border-radius: 14px !important;
    margin-top: 0.75rem !important;
}

details[data-testid="stExpander"] summary {
    display: flex !important;
    align-items: center !important;
    gap: 0.45rem !important;
}

details[data-testid="stExpander"] summary p {
    font-family: var(--font-ui) !important;
    font-size: var(--fs-body) !important;
    font-weight: 600 !important;
    color: #1D1D1F !important;
    margin: 0 !important;
}

table {
    width: 100% !important;
    border-collapse: collapse !important;
    margin: 0.75rem 0 1.1rem 0 !important;
}

th, td {
    font-size: var(--fs-body) !important;
    padding: 0.6rem 0.8rem !important;
    border-bottom: 1px solid #E5E5EA !important;
    color: #1D1D1F !important;
    vertical-align: top !important;
}

th {
    background-color: #F5F5F7 !important;
    font-weight: 600 !important;
    text-align: left !important;
    border-bottom: 1px solid #D2D2D7 !important;
}

.gov-note {
    font-size: var(--fs-body) !important;
    color: #6E6E73 !important;
    margin-top: 0.75rem !important;
    padding-top: 0.5rem !important;
    border-top: 1px solid #EFEFF4 !important;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# MODULE METADATA & CURATED SHOWCASES
# -----------------------------------------------------------------------------
MODULE_ORDER = ["seo", "paid", "pricing", "creative", "social"]

MODULE_LABELS = {
    "seo": "SEO, AEO & GEO",
    "paid": "Paid Search & CRO",
    "pricing": "Pricing & Unit Economics",
    "creative": "Ad Creative Studio",
    "social": "Social & Brand Triage",
}

MODULE_FULL_TITLES = {
    "seo": "Organic Search Intelligence: SEO, AEO & GEO",
    "paid": "Paid Acquisition, Pipeline & Funnel CRO",
    "pricing": "Pricing Architecture & Unit Economics",
    "creative": "Ad Creative Studio & Next-Gen Hooks",
    "social": "Brand Reputation, Social Listening & Creator Partnerships",
}

MODULE_DEEP_TITLES = {
    "seo": "Deep Dive: AI Prompt Visibility Matrix & Execution Plan",
    "paid": "Deep Dive: Paid Architecture Fixes & Experiment Backlog",
    "pricing": "Deep Dive: Tier Optimization Playbook & Impact Matrix",
    "creative": "Deep Dive: Creative Rationale & A/B Testing Matrix",
    "social": "Deep Dive: Rapid Triage Plan, Escalation SLAs & Top 10 Creators",
}

MODULE_GOV = {
    "seo": "Diagnostic signals are synthesized via live search and URL context; verify exact counts and schema before distribution.",
    "paid": "Benchmarks reflect observable storefront/site signals and unit-economics heuristics; validate against live ad-account and CRM telemetry.",
    "pricing": "Pricing signals reflect website and search observations; model contribution margin, ACV/payback, or freight rates against internal financials.",
    "creative": "Ad copy follows platform character caps; visual concepts are prototypes for creative direction and testing.",
    "social": "Sentiment signals and creator/authority suggestions are grounded via search; verify current metrics and escalation SLAs before outreach.",
}


def _sample_item(content: str, engine: str = "Curated Snapshot (US)"):
    return {"ok": True, "content": content, "engine": engine, "from_cache": True, "age": "curated US", "error": None}


def build_sample_showcase(brand_key: str) -> dict:
    if brand_key == "enphase":
        return {
            "company": "Enphase Energy",
            "country": "United States",
            "biz_model": "Hybrid / B2B2C",
            "official_url": "https://enphase.com",
            "is_showcase": True,
            "hooks": {
                "seo": ("67", "Add US net-metering (NEM 3.0) & backup Q&As to win US AI answer blocks."),
                "paid": ("63", "Separate US homeowner vs. installer funnels and simplify mobile quote steps."),
                "pricing": ("64", "Bundle IQ8 + IQ Battery + smart load tiers to lift US storage attach and margin."),
                "creative": ("71", "Lead with US grid-outage resilience and bill control over raw spec sheets."),
                "social": ("68", "Tighten US installer callback SLAs and PTO milestone updates to protect trust."),
            },
            "brand_logo": {"ok": False, "bytes": None, "source": None, "from_cache": False},
            "brand_intel": (
                "- **Visual Design Language:** Crisp white surfaces, electric blue and emerald accents, clean technical cards, and bright US residential photography.\n"
                "- **Paid Social & Ad Patterns:** US homeowner energy independence stories, outage protection hooks, and certified installer co-marketing.\n"
                "- **Search & Demand Messaging:** US microinverter reliability, battery storage readiness, and certified installer discovery.\n"
                "- **Core Audience & Trust Triggers:** US homeowners and certified solar installers anchored by reliability and Enlighten app monitoring.\n\n"
                "| Channel / Format | Current Baseline Pattern | Creative Fatigue / Gap | Next-Gen Hook Angle |\n"
                "| --- | --- | --- | --- |\n"
                "| Paid Social & Video | US hardware & solar overview ads | Spec-heavy copy under-indexes on outage peace of mind | 4s blackout-to-backup US homeowner hook |\n"
                "| Search & Demand Gen | Broad US solar & microinverter terms | Blended homeowner vs. installer intent | Segmented US savings & certified installer proof |\n"
                "| Web & Lead Funnels | Multi-step US sizing & quote handoff | Drop-off prior to local US quote request | Quick bill-offset & battery-readiness check |"
            ),
            "e1": _sample_item(
                "| Search Pillar | Score /100 | Observable Diagnostic Signal (US) | Primary Gap |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Technical & Programmatic SEO | 72 | Strong US product/solution depth and state/city pages | Faceted comparison indexation & page speed hygiene |\n"
                "| 2. AEO | 66 | Solid technical definitions; room for concise US answer blocks | Direct Q&A blocks for NEM 3.0 / utility tariffs & battery sizing |\n"
                "| 3. GEO | 64 | High US brand awareness; mixed share in homeowner TCO prompts | Clear US lifecycle & storage TCO citation assets |\n"
                "| 4. Entity & Local Schema | 69 | Clear Organization & Product graph; state/installer variance | Consistent local/service schema & US regional proof |\n"
                "| 5. Off-Site Consensus & Digital PR | 65 | Active US homeowner forums and solar press coverage | Structured US review & installer proof aggregation |\n\n"
                "- Build US comparison hubs for microinverter vs. string inverter reliability and payback.\n"
                "- Add concise FAQ blocks on US battery backup sizing and utility tariff shifts.\n"
                "- Strengthen US state/regional homeowner proof and installer directory pages.\n"
                "- Publish clear guides on US whole-home energy management and EV charging.\n"
                "---DEEP_DIVE---\n"
                "| High-Intent US Buyer Prompt | Current AI Winner | Enphase US Vulnerability | Asset Needed to Win |\n"
                "| --- | --- | --- | --- |\n"
                "| Best home solar microinverter & battery setup US | US solar review aggregators | Technical specs outweigh plain-English US outcomes | Side-by-side US reliability & backup guide |\n"
                "| How much does solar + battery backup save in US | US utility & solar calculators | State utility tariff rules vary across US states | US payback & tariff-impact explainer |\n"
                "| Reliable solar installer near me US | US directories & local listings | Lead handoff friction between brand & US partner | Verified US installer checklist & proof hub |\n"
                "| Microinverter vs string inverter maintenance US | US owner forums | Scattered anecdotal comparisons | Transparent lifecycle & warranty table |\n\n"
                "### US Execution Plan\n"
                "- **[AEO] Problem -> Fix:** Technical copy buries direct US answers -> Add concise answer-first blocks on sizing and FAQ pages.\n"
                "- **[GEO] Problem -> Fix:** Forums shape US TCO answers -> Publish clear reliability and lifecycle TCO comparisons.\n"
                "- **[Schema] Problem -> Fix:** Uneven markup across US regional templates -> Standardize Product, FAQPage, and Organization schema.\n"
                "- **[SEO] Problem -> Fix:** Thin US state pages compete on broad terms -> Add localized US case studies and utility context.\n"
                "- **[Off-Site] Problem -> Fix:** Positive Enlighten stories stay scattered -> Syndicate verified US homeowner stories and proof."
            ),
            "e_paid": _sample_item(
                "| Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal (US) | Primary Leakage |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Non-Brand Search & Demand/PMax Efficiency | 65 | Strong US demand capture alongside broad hardware queries | Broad non-brand clicks before readiness check |\n"
                "| 2. Paid Social Acquisition & Creative Fatigue | 61 | Clear visual assets; repeated hardware framing | US prospecting over-indexes on specs vs. outage/bill hooks |\n"
                "| 3. Multi-Path Funnel & Partner/Direct CRO | 62 | Multi-step path to qualified US lead/quote | Friction before US homeowners see tailored system fit |\n"
                "| 4. Order/Quote Routing, Partner Handoff & Fulfillment Friction | 64 | US partner routing in place; follow-up speed varies | Delayed US installer contact erodes lead conversion |\n\n"
                "- Separate US homeowner lead-gen from installer-focused campaigns.\n"
                "- Lead US social hooks with outage protection and monthly bill control.\n"
                "- Use 3 quick qualification inputs before US quote capture.\n"
                "- Track qualified-lead-to-proposal rate alongside form fills.\n"
                "---DEEP_DIVE---\n"
                "### US Paid & Funnel Fixes\n"
                "- **[Search/PMax] Problem -> Fix:** Blended brand and non-brand signals blur US efficiency -> Separate brand defense from storage/solar capture.\n"
                "- **[Paid Social] Problem -> Fix:** Hardware creatives fatigue US homeowners -> Test outage-resilience and bill-predictability hooks.\n"
                "- **[Landing Page] Problem -> Fix:** Long forms hurt US mobile completion -> Show quick system fit estimates before contact capture.\n"
                "- **[Post-Click] Problem -> Fix:** Slow US partner handoffs lose high-intent leads -> Enforce instant confirmation and SLA-tracked routing.\n\n"
                "### US Experiment Backlog\n"
                "| Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |\n"
                "| --- | --- | --- | --- |\n"
                "| 3-step solar + battery estimator on US mobile LPs | Qualified Lead CVR | Cost per Qualified Lead (USD) | +15-22% mobile form completion |\n"
                "| Outage/backup hook vs. hardware hook on US Meta/YouTube | Thumbstop & CTR | Lead Quality Score | +18-25% engaged click rate |\n"
                "| Instant next-step timeline after US quote submission | Proposal Booking Rate | Installer SLA Breach Rate | +10-16% speed-to-contact lift |\n"
                "| Dedicated US storage/backup search ad groups | Storage Lead Share | Blended Non-Brand CPA (USD) | +12-18% higher-AOV inquiry mix |"
            ),
            "e2": _sample_item(
                "**Current Dual-Channel & Partner Pricing Strategy:** In the US, Enphase pairs premium IQ8 microinverter and IQ Battery hardware pricing with multi-tier US installer commercial programs, volume incentives, and ongoing monitoring/energy-management value.\n\n"
                "| Pricing & Economics Pillar | Score /100 | Observable US Pricing Signal | Margin / LTV Leakage |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Direct vs. Partner / Channel Price Alignment | 68 | Premium US hardware anchored by reliability & warranty | Price pressure from lower-cost US string/hybrid options |\n"
                "| 2. Freight, Installation/Onboarding & Threshold Architecture | 62 | US commercial/installer logistics and regional fulfillment | Freight/handling drag on smaller or split US orders |\n"
                "| 3. Repeat Replenishment, Attach & Lifecycle Retention | 63 | Ongoing monitoring and energy-management value | Under-monetized post-install upgrade touchpoints |\n"
                "| 4. High-Margin Bundles, Add-Ons & Commercial Program Mix | 64 | Integrated microinverter, battery & smart energy stack | Attach-rate gap between solar core and US storage add-ons |\n\n"
                "- Bundle US microinverters, battery storage, and smart controls into clear tiers.\n"
                "- Weight US installer volume rebates toward multi-product attach.\n"
                "- Standardize transparent US commercial/freight terms across order tiers.\n"
                "- Create clear post-install paths for US battery and EV expansion.\n"
                "---DEEP_DIVE---\n"
                "### US Tier Optimization & Margin Plan\n"
                "- **[Package Tiers] Problem -> Fix:** A la carte US quotes obscure total value -> Offer Good/Better/Best solar + storage + control tiers.\n"
                "- **[Partner Tiers] Problem -> Fix:** Flat volume discounts miss US attach incentives -> Tie higher rebates to battery and smart-panel attach.\n"
                "- **[Freight/Fees] Problem -> Fix:** Split US order sizes add logistics overhead -> Incentivize consolidated batch ordering thresholds.\n"
                "- **[Expansion LTV] Problem -> Fix:** Post-install engagement slows after US setup -> Surface timely storage/EV expansion offers via milestones.\n\n"
                "### US Unit Economics & Pricing Impact Matrix\n"
                "| Pricing Lever | Target US Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| Solar + Battery Tiered Bundles | US residential buyers | Clear package tiers with backup options | +200-280 bps blended GM | Keep entry solar option for budget buyers |\n"
                "| Attach-Weighted Partner Tiers | US certified installers | Higher rebates on bundled storage/EMS | +12-18% US storage attach rate | Protect installer margin on competitive bids |\n"
                "| Consolidated Batch Ordering | US regional partners/orders | Threshold-based fulfillment terms | -100-140 bps freight drag | Avoid order barriers on small pilots |\n"
                "| Post-Install Expansion Offers | US Enlighten app users | Milestone-triggered storage/EV upgrades | +15-22% expansion LTV | Keep prompts helpful, never intrusive |"
            ),
            "e3": _sample_item(
                "1. **Search / High-Intent Ad Pack (US)**\n"
                "- Headline 1: Smart Solar & Battery Systems\n"
                "- Headline 2: Reliable Power When Grid Drops\n"
                "- Headline 3: Connect With Certified US Pros\n"
                "- Description 1: Protect your US home with reliable solar and battery storage. Get a tailored plan.\n"
                "- Description 2: Monitor energy in real time and cut grid reliance. Request a home assessment.\n\n"
                "2. **Primary Paid Social Ad (US)**\n"
                "- Primary Text: Keep lights, Wi-Fi, and essentials running smoothly with smart US solar + battery storage.\n"
                "- Headline: Smart Solar + Backup Made Simple\n"
                "- CTA: Learn More\n\n"
                "3. **4-Second Video Hook (US)**\n"
                "- Visual Scene: US home lights stay on while street goes dark; homeowner checks phone app.\n"
                "- Voiceover/Text Overlay: Outage outside. Power inside. (6 words)\n"
                "---DEEP_DIVE---\n"
                "### US Creative Rationale\n"
                "- **[Paid Social/Video] Problem -> Fix:** Spec-heavy visuals feel distant to US homeowners -> Lead with blackout protection and app clarity in 4 seconds.\n"
                "- **[Search RSA] Problem -> Fix:** Broad headlines dilute US intent -> Pair clear backup/savings outcomes with assessment CTAs.\n"
                "- **[Funnel Match] Problem -> Fix:** Ad-to-page messaging gap -> Carry backup and savings framing directly onto the US landing hero.\n\n"
                "### US Creative A/B Testing Matrix\n"
                "| Ad Variant | Hook / Angle | Target US Persona | Primary KPI |\n"
                "| --- | --- | --- | --- |\n"
                "| Variant A (Outage Hook) | Seamless backup during US grid dips | Outage-prone US homeowners | Qualified Lead CVR |\n"
                "| Variant B (Bill Control) | Predictable energy & self-use | High-bill / EV US homeowners | Cost per Qualified Lead (USD) |\n"
                "| Variant C (App Telemetry) | Real-time visibility & control | Tech-forward US homeowners | Thumbstop & LP CTR |\n"
                "| Variant D (Installer Trust) | Certified local US execution & warranty | First-time US solar buyers | Proposal Completion Rate |"
            ),
            "e4": _sample_item(
                "**Current Brand Sentiment Archetype:** In the US, Enphase earns strong engineering trust and Enlighten app loyalty among homeowners, while reputation risks center on installer execution speed and support follow-through.\n\n"
                "| Reputation & Listening Pillar | Score /100 | Observable US Social / Review Signal | Primary Trust Risk |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. End-User & Partner Fulfillment / Handoff Sentiment | 66 | US setup timelines depend on local installers | US partner delays reflecting on brand |\n"
                "| 2. Technical / Product Reliability & Brand Trust | 74 | Strong US reliability and monitoring UX feedback | Isolated RMA/firmware threads |\n"
                "| 3. Consumer Review & B2B/Partner Reputation Parity | 65 | High product affinity vs. mixed local US reviews | State-level sentiment uneven across channels |\n"
                "| 4. Community Advocacy, Partner Co-Marketing & Earned Proof | 69 | Active US owner discussions sharing performance | Unanswered forum threads lingering |\n\n"
                "| Polarity | US Platform & Context | Representative Customer Feedback | Core Theme |\n"
                "| --- | --- | --- | --- |\n"
                "| Positive | US Solar Owner Forums | Per-panel monitoring makes spotting any issue quick and reliable. | App & Telemetry Value |\n"
                "| Positive | US Homeowner Reviews | System runs steadily with clear daily generation visibility. | Hardware Reliability |\n"
                "| Positive | US Community Threads | Battery backup kept essentials running through an outage. | Backup Peace of Mind |\n"
                "| Negative | US Installer / Review Threads | Waited too long for local installer callback after inquiry. | Installer Speed-to-Lead |\n"
                "| Negative | US Support / Forum Threads | Needed multiple follow-ups to close commissioning check. | Support Resolution SLA |\n"
                "| Negative | US Regional Discussions | Utility export/tariff rules felt unclear during initial pitch. | Expectation Clarity |\n\n"
                "---DEEP_DIVE---\n"
                "### US Rapid Triage Plan\n"
                "- **[Installer SLA] Problem -> Fix:** Slow US partner callbacks hurt perception -> Tighten routing SLAs and escalate stalled leads quickly.\n"
                "- **[Forum Triage] Problem -> Fix:** Open US technical threads shape research -> Assign dedicated technical specialists with clear escalations.\n"
                "- **[Expectations] Problem -> Fix:** US permitting/utility steps surprise buyers -> Share clear milestone timelines upfront.\n"
                "- **[Advocacy] Problem -> Fix:** Satisfied US owners post less often -> Prompt completed installs to share verified stories.\n\n"
                "### US Social Listening & Escalation SLA Matrix\n"
                "| Listening Cluster & US Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |\n"
                "| --- | --- | --- | --- |\n"
                "| Outage / Fault Mentions (US) | System fault or backup claims | High (<2h triage) | US Technical Support + Field Ops check |\n"
                "| Installer Delay Complaints (US) | Slow install or callback threads | Medium (<24h response) | US Partner Ops + CX escalates |\n"
                "| App & Monitoring Questions (US) | Setup, login, or telemetry queries | Low-Med (<12h response) | Digital Care shares guided fix |\n"
                "| Creator & Press Mentions (US) | Reviews, comparisons, or policy posts | Medium (<24h response) | US Brand/Comms logs & responds |\n\n"
                "### Top 10 US Influencers & YouTube Channels for Brand Collaboration\n"
                "| Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| 1 | Undecided with Matt Ferrell | YouTube | US clean energy & home tech | Deep dive on microinverters, storage & resilience |\n"
                "| 2 | US Home Solar & DIY Channels | YouTube | US solar homeowners & builders | Real-world performance & monitoring walkthrough |\n"
                "| 3 | US Engineering & Grid Creators | YouTube | US grid & energy transition viewers | Explaining distributed energy & backup design |\n"
                "| 4 | US Smart Home & EV Creators | YouTube & Instagram | US EV + home energy owners | Whole-home solar + EV charging daily routine |\n"
                "| 5 | US Personal Finance & Home Creators | YouTube & Instagram | ROI-focused US homeowners | US utility bill & payback math breakdown |\n"
                "| 6 | US Sustainable Living Creators | YouTube | Eco-minded US home upgraders | Home efficiency & backup readiness tour |\n"
                "| 7 | US Real Estate & Reno Creators | Instagram & YouTube | US home renovators/builders | Planning solar-ready roofs & smart panels |\n"
                "| 8 | US Energy Policy Commentators | YouTube & LinkedIn | US tariff & policy watchers | How US tariff/NEM shifts affect solar + storage |\n"
                "| 9 | US Consumer Tech Reviewers | YouTube | US smart-device & app reviewers | Hands-on review of monitoring UX & alerts |\n"
                "| 10 | US Local Homeowner Advocates | Instagram & YouTube | US community builders | Authentic post-install neighborhood walkthrough |"
            ),
        }

    if brand_key == "chargebee":
        return {
            "company": "Chargebee",
            "country": "United States",
            "biz_model": "B2B / B2B SaaS",
            "official_url": "https://www.chargebee.com",
            "is_showcase": True,
            "hooks": {
                "seo": ("70", "Expand comparison/migration hubs & AI answers for subscription billing & rev-rec."),
                "paid": ("64", "Separate high-intent billing search from demo/trial retargeting and cut form steps."),
                "pricing": ("66", "Clarify usage/volume tier jumps, implementation packaging & expansion paths."),
                "creative": ("72", "Test CFO/RevOps billing-pain hooks & compliance proof over generic SaaS claims."),
                "social": ("69", "Keep G2/peer review momentum high and tighten enterprise onboarding SLAs."),
            },
            "brand_logo": {"ok": False, "bytes": None, "source": None, "from_cache": False},
            "brand_intel": (
                "- **Visual Design Language:** Clean light surfaces, vibrant orange and deep slate accents, crisp SaaS UI cards, and structured workflow diagrams.\n"
                "- **Paid Social & Ad Patterns:** LinkedIn thought-leadership and revenue-ops pain callouts paired with product UI and ROI proof.\n"
                "- **Search & Demand Messaging:** Subscription billing, recurring revenue, usage-based pricing, and demo/trial conversion CTAs.\n"
                "- **Core Audience & Trust Triggers:** Finance, RevOps, and growth leaders anchored by SOC2/compliance trust, integrations, and customer proof.\n\n"
                "| Channel / Format | Current Baseline Pattern | Creative Fatigue / Gap | Next-Gen Hook Angle |\n"
                "| --- | --- | --- | --- |\n"
                "| LinkedIn Sponsored & Video | Broad billing & subscription platform ads | Generic SaaS value claims blend in feeds | Finance/RevOps bottleneck & migration proof hook |\n"
                "| High-Intent Search | Subscription billing & rev-rec keywords | Competitor/migration intent needs tighter framing | Side-by-side billing & rev-rec readiness hook |\n"
                "| Demo & Trial Funnels | Multi-field qualification & demo booking | Friction before buyers see tailored tier fit | Fast interactive billing-fit & ROI preview |"
            ),
            "e1": _sample_item(
                "| Search Pillar | Score /100 | Observable Diagnostic Signal (US) | Primary Gap |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Technical & Programmatic SEO | 73 | Strong product, integration, and billing guide architecture | Comparison/alternative landing depth & crawl hygiene |\n"
                "| 2. AEO | 69 | Solid billing & rev-rec definitions; structured Q&A upside | Concise answer blocks for billing, proration & rev-rec queries |\n"
                "| 3. GEO | 67 | Known category name; mixed share in vendor shortlist prompts | Clear TCO & migration citation assets for AI answers |\n"
                "| 4. Entity & Local Schema | 71 | Clear Organization & SoftwareApplication graph | Consistent integration, review & FAQ structured data |\n"
                "| 5. Off-Site Consensus & Digital PR | 69 | Active B2B review presence and finance/SaaS coverage | Consistent peer proof across buyer shortlists |\n\n"
                "- Build dedicated comparison and migration guides for high-intent B2B buyers.\n"
                "- Add concise answer blocks on usage billing, dunning, and revenue recognition.\n"
                "- Strengthen integration pages for ERP, CRM, and payment stack buyers.\n"
                "- Publish clear benchmarks on subscription churn, billing recovery, and NRR.\n"
                "---DEEP_DIVE---\n"
                "| High-Intent B2B Buyer Prompt | Current AI Winner | Chargebee Vulnerability | Asset Needed to Win |\n"
                "| --- | --- | --- | --- |\n"
                "| Best subscription billing software for SaaS US | B2B review directories & blogs | Broad billing claims vs. specific stack fit | Clear SaaS billing & rev-rec comparison matrix |\n"
                "| Usage-based billing vs seat-based pricing tools | SaaS pricing blogs & guides | Technical nuances split across articles | Practical hybrid/usage billing playbook |\n"
                "| Stripe Billing alternatives for growing SaaS | Comparison listicles & forums | Generic category framing on migration intent | Migration checklist & TCO breakdown |\n"
                "| Revenue recognition software for B2B finance | Finance/ERP roundups | Finance buyer proof needs sharper prominence | CFO/Controller rev-rec & audit readiness guide |\n\n"
                "### US Execution Plan\n"
                "- **[AEO] Problem -> Fix:** Long guides bury direct answers -> Add concise answer-first blocks on billing & rev-rec pages.\n"
                "- **[GEO] Problem -> Fix:** Roundups shape AI shortlists -> Publish objective comparison and migration benchmark assets.\n"
                "- **[Schema] Problem -> Fix:** Uneven markup across resource templates -> Standardize SoftwareApplication, FAQPage & Organization schema.\n"
                "- **[SEO] Problem -> Fix:** High-intent alternative queries split across posts -> Consolidate comparison hubs with clear next steps.\n"
                "- **[Off-Site] Problem -> Fix:** Customer proof sits in silos -> Pair verified case studies with transparent implementation stories."
            ),
            "e_paid": _sample_item(
                "| Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal (US) | Primary Leakage |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Non-Brand Search & Demand/PMax Efficiency | 66 | Strong intent capture on core billing & SaaS queries | Broad non-brand clicks before scale/ICP check |\n"
                "| 2. Paid Social Acquisition & Creative Fatigue | 62 | Active LinkedIn & paid social demand programs | Repeated platform framing across buying roles |\n"
                "| 3. Landing Page, Demo/Trial & Pipeline CRO | 63 | Demo and trial paths serve different deal sizes | Qualification friction before showing value |\n"
                "| 4. Lead Routing, Sales Handoff & Buying-Committee Friction | 65 | Multi-stakeholder B2B evaluation cycle | Slow handoff or missing multi-thread assets |\n\n"
                "- Separate high-intent BOF search from top-of-funnel demand campaigns.\n"
                "- Tailor paid social creatives to CFO, RevOps, and product leaders.\n"
                "- Streamline demo/trial forms and offer self-guided fit previews.\n"
                "- Track pipeline/SQL conversion and speed-to-lead, not raw leads.\n"
                "---DEEP_DIVE---\n"
                "### US Paid & Funnel Fixes\n"
                "- **[Search] Problem -> Fix:** Broad non-brand terms bring lower-fit inquiries -> Tighten intent segmentation and ICP qualification cues.\n"
                "- **[Paid Social] Problem -> Fix:** Generic B2B ads fatigue senior buyers -> Segment hooks by finance, RevOps, and growth personas.\n"
                "- **[Funnel CRO] Problem -> Fix:** Heavy forms slow high-intent visitors -> Test progressive fields and instant calendar/trial flow.\n"
                "- **[Sales Handoff] Problem -> Fix:** Buying committees need multi-role proof -> Provide shareable ROI and security briefs post-signup.\n\n"
                "### US Experiment Backlog\n"
                "| Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |\n"
                "| --- | --- | --- | --- |\n"
                "| Progressive form + instant fit summary on demo LP | Demo-to-SQL CVR | Cost per Qualified SQL (USD) | +14-20% qualified pipeline lift |\n"
                "| Persona-specific LinkedIn hooks (CFO vs. RevOps) | Engaged CTR & SQL Rate | LinkedIn CPL (USD) | +16-24% persona click & reply lift |\n"
                "| Dedicated comparison/migration search ad groups | High-Intent Demo Share | Blended Non-Brand CAC Payback | +12-18% higher-ACV demo mix |\n"
                "| Post-demo buyer enablement kit (ROI + security) | Stage-1 to Closed-Won Rate | Sales Cycle Length | +8-14% committee conversion lift |"
            ),
            "e2": _sample_item(
                "**Current Monetization & Packaging Strategy:** Chargebee pairs tiered subscription/revenue-management packaging with volume/usage scaling, add-on modules, and enterprise/commercial expansion paths.\n\n"
                "| Pricing & Economics Pillar | Score /100 | Observable Pricing Signal | Margin / LTV Leakage |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Core Plan, Seat/Usage Tier & ACV Positioning | 68 | Clear tier progression for growing to enterprise SaaS | Over-jump complexity at usage/volume inflection points |\n"
                "| 2. Free Trial, Freemium & Implementation Fee Architecture | 63 | Guided evaluation and structured onboarding | Implementation friction on mid-market upgrades |\n"
                "| 3. Expansion, NRR & Multi-Year Renewal Monetization | 67 | Strong natural expansion with billing volume growth | Uncaptured add-on attach during renewals |\n"
                "| 4. Enterprise Tier, Add-On Module & Services Mix | 66 | Advanced rev-rec, billing & analytics capabilities | Packaging overlap across adjacent modules |\n\n"
                "- Make tier transitions and usage thresholds transparent for buyers.\n"
                "- Offer clear starter vs. guided onboarding paths by deal size.\n"
                "- Tie expansion packaging to billing volume and module attach.\n"
                "- Align sales discounting guardrails with net dollar retention.\n"
                "---DEEP_DIVE---\n"
                "### US Tier Optimization & Margin Plan\n"
                "- **[Tier Structure] Problem -> Fix:** Usage/volume jumps can feel opaque -> Clarify threshold math and predictable overage/tier steps.\n"
                "- **[Onboarding/Fees] Problem -> Fix:** Setup effort slows mid-market adoption -> Package transparent implementation tiers with clear ROI.\n"
                "- **[Expansion/NRR] Problem -> Fix:** Add-on value surfaces late in cycle -> Introduce high-attach modules at clear growth milestones.\n"
                "- **[Discounting] Problem -> Fix:** Ad-hoc concessions trim net realization -> Anchor discounts to multi-year terms or add-on attach.\n\n"
                "### US Unit Economics & Pricing Impact Matrix\n"
                "| Pricing Lever | Target Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| Transparent Tier & Overage Guardrails | Scaling SaaS accounts | Clearer volume bands & predictable steps | +10-16% expansion conversion | Prevent surprise bill shock at renewal |\n"
                "| Tiered Implementation Packages | Mid-market & upmarket buyers | Fixed-scope onboarding & migration options | +150-240 bps net realization | Keep low-friction entry for self-serve/SMB |\n"
                "| Module Attach Bundles at Renewal | Existing subscribers | Bundled rev-rec/retention add-ons | +12-20% NRR / expansion LTV | Gate add-ons to clear workflow triggers |\n"
                "| Multi-Year Term Incentives | Annual/enterprise renewals | Discount tied to multi-year or add-on commit | -8-14% annual churn risk | Protect list price integrity on 1-yr deals |"
            ),
            "e3": _sample_item(
                "1. **Search / High-Intent Ad Pack (US)**\n"
                "- Headline 1: Subscription Billing & Rev-Rec\n"
                "- Headline 2: Scale Recurring & Usage Revenue\n"
                "- Headline 3: Book a Tailored SaaS Demo\n"
                "- Description 1: Automate recurring billing, usage tiers, and revenue recognition as you scale. Book a demo.\n"
                "- Description 2: Built for finance and growth teams managing complex subscriptions. See how it works.\n\n"
                "2. **Primary Paid Social Ad (US)**\n"
                "- Primary Text: Stop duct-taping billing spreadsheets and manual invoices as revenue scales. See modern SaaS billing.\n"
                "- Headline: Billing Built to Scale With You\n"
                "- CTA: Book a Demo\n\n"
                "3. **4-Second Video Hook (US)**\n"
                "- Visual Scene: Finance lead closes messy billing sheet; clean automated revenue workflow appears.\n"
                "- Voiceover/Text Overlay: Outgrow billing bottlenecks before they stall growth. (7 words)\n"
                "---DEEP_DIVE---\n"
                "### US Creative Rationale\n"
                "- **[Paid Social/Video] Problem -> Fix:** Abstract SaaS visuals blend together -> Lead with a concrete finance/RevOps workflow shift in 4 seconds.\n"
                "- **[Search RSA] Problem -> Fix:** Broad headlines miss high-intent buyers -> Pair billing/rev-rec outcomes with clear demo CTAs.\n"
                "- **[Funnel Match] Problem -> Fix:** Ad-to-page message drift -> Carry the exact billing/scale promise onto the landing hero.\n\n"
                "### US Creative A/B Testing Matrix\n"
                "| Ad Variant | Hook / Angle | Target Persona | Primary KPI |\n"
                "| --- | --- | --- | --- |\n"
                "| Variant A (Rev-Rec & Close) | Faster month-end & audit readiness | CFO / Finance leaders | Qualified SQL Rate |\n"
                "| Variant B (Pricing Agility) | Launching usage/hybrid plans fast | RevOps / Product / Growth | Demo-to-SQL CVR |\n"
                "| Variant C (Migration Ease) | Switching billing stacks smoothly | VP Eng / Billing leads | Cost per Qualified SQL (USD) |\n"
                "| Variant D (Customer Proof) | Real SaaS scaling & retention metrics | Buying committee / Execs | Pipeline Opportunity Value |"
            ),
            "e4": _sample_item(
                "**Current Brand Sentiment Archetype:** In the US, Chargebee holds strong category recognition for subscription billing and SaaS revenue workflows, while buyer scrutiny focuses on implementation effort, edge-case flexibility, and support responsiveness.\n\n"
                "| Reputation & Listening Pillar | Score /100 | Observable US Social / Review Signal | Primary Trust Risk |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Pipeline Velocity, Demo/SQL & Post-Signup Sentiment | 67 | Active B2B evaluation and onboarding feedback | Implementation complexity slowing time-to-value |\n"
                "| 2. Category Authority, Security/ROI & Product Trust | 73 | Strong billing/rev-rec credibility and enterprise trust | Edge-case workflow questions in complex setups |\n"
                "| 3. G2 / Capterra / Peer Review & Forum Parity | 68 | Solid B2B review footprint with mixed setup notes | Setup/support nuance in peer review threads |\n"
                "| 4. Executive / Founder Advocacy & Customer Proof | 67 | Credible SaaS growth & monetization stories | Need more role-specific CFO/RevOps proof |\n\n"
                "| Polarity | US Platform & Context | Representative Customer Feedback | Core Theme |\n"
                "| --- | --- | --- | --- |\n"
                "| Positive | B2B Software Reviews | Handles recurring plans, proration, and upgrades cleanly once configured. | Core Billing Capability |\n"
                "| Positive | Customer Case Studies | Helped streamline subscription workflows while scaling recurring revenue. | Scalability & Workflows |\n"
                "| Positive | Peer Discussions | Helpful integrations across billing, payments, and revenue tools. | Stack Ecosystem |\n"
                "| Negative | B2B Review Threads | Initial setup and custom configuration took longer than expected. | Implementation Effort |\n"
                "| Negative | User / Forum Feedback | Edge-case billing rules needed extra workarounds or specialist help. | Edge-Case Flexibility |\n"
                "| Negative | Support / Account Threads | Escalating complex billing tickets took multiple touchpoints. | Technical Support SLA |\n\n"
                "---DEEP_DIVE---\n"
                "### US Rapid Triage Plan\n"
                "- **[Time-to-Value] Problem -> Fix:** Setup friction hurts early sentiment -> Set clearer onboarding milestones and templates upfront.\n"
                "- **[Review Parity] Problem -> Fix:** Setup/edge-case notes appear in reviews -> Address common configuration questions proactively in docs/FAQs.\n"
                "- **[Support SLA] Problem -> Fix:** Complex billing tickets stall deals/renewals -> Route technical billing escalations to senior specialists fast.\n"
                "- **[Executive Proof] Problem -> Fix:** Buyers want peer validation -> Publish concise CFO and RevOps ROI stories by segment.\n\n"
                "### US Social Listening & Escalation SLA Matrix\n"
                "| Listening Cluster & US Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |\n"
                "| --- | --- | --- | --- |\n"
                "| Production Billing / Outage Issue | Live billing/webhook failure mentions | High (<1h triage) | Engineering + Escalation Support resolve |\n"
                "| Implementation / Migration Friction | Setup delay or migration complaints | Medium (<12h response) | Solutions / Onboarding Lead intervenes |\n"
                "| G2 / Capterra / Peer Threads | Comparison or setup/support reviews | Medium (<24h response) | Customer Advocacy + Product Marketing respond |\n"
                "| Executive & Community Mentions | SaaS pricing, rev-rec, or brand posts | Low-Med (<24h response) | Brand / Thought Leadership engages |\n\n"
                "### Top 10 US Influencers & Channels for B2B Collaboration\n"
                "| Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| 1 | SaaS Metrics & Monetization Newsletters | Newsletter & LinkedIn | SaaS founders, CFOs & GTM leaders | Benchmarks on NRR, usage pricing & expansion |\n"
                "| 2 | RevOps & Revenue Architecture Communities | LinkedIn & Podcasts | RevOps & GTM ops practitioners | Designing clean lead-to-billing-to-rev-rec handoffs |\n"
                "| 3 | B2B CFO & SaaS Finance Creators | LinkedIn & YouTube | CFOs, VPs Finance & controllers | Audit-ready rev-rec & subscription margin playbooks |\n"
                "| 4 | B2B SaaS Growth & PLG Podcasts | YouTube & Podcasts | SaaS growth & product leaders | Hybrid PLG + sales-assisted monetization models |\n"
                "| 5 | Fintech & Payments Infrastructure Analysts | LinkedIn & Newsletters | Payments & commerce decision-makers | Global payment methods, retries & recovery rates |\n"
                "| 6 | B2B Demand Gen & Paid Media Educators | LinkedIn | B2B marketers & demand leaders | High-intent SaaS capture vs. pipeline quality |\n"
                "| 7 | Enterprise Software Review & Buying Guides | Web & LinkedIn | Software buyers & evaluators | Transparent billing & subscription buyer checklist |\n"
                "| 8 | Startup Scaling & Founder Operators | LinkedIn & YouTube | Seed to Series C SaaS founders | Avoiding billing debt before scaling ARR |\n"
                "| 9 | Cloud & API Architecture Creators | YouTube & LinkedIn | Technical evaluators & architects | Webhooks, billing APIs & usage metering patterns |\n"
                "| 10 | B2B Customer Success & Retention Leaders | LinkedIn & Webinars | CS & renewals leaders | Reducing involuntary churn & driving expansion |"
            ),
        }

    return {
        "company": "Supertails",
        "country": "India",
        "biz_model": "B2C / DTC",
        "official_url": "https://supertails.com",
        "is_showcase": True,
        "hooks": {
            "seo": ("68", "Clean faceted filter bloat and build vet nutrition guides to win AI answers."),
            "paid": ("61", "Exclude brand terms from PMax, tier by margin, and simplify checkout fees."),
            "pricing": ("62", "Gate top promos behind private-label or higher baskets and weight-tier shipping."),
            "creative": ("74", "Pair vet-curated care bundles and 4s hooks with verified brand logo guardrails."),
            "social": ("65", "Audit failed delivery call/GPS logs and streamline cancellation & refund flows."),
        },
        "brand_logo": {"ok": False, "bytes": None, "source": None, "from_cache": False},
        "brand_intel": (
            "- **Visual Design Language:** Warm orange and deep navy accents, rounded cards, friendly sans-serif typography, and candid pet photography.\n"
            "- **Paid Social & Ad Patterns:** Dynamic SKU carousels, creator reels, situational hooks, and express delivery or offer badges.\n"
            "- **Search & Demand Messaging:** Pet store headlines, vet care access, fast delivery cues, and direct shop CTAs.\n"
            "- **Core Audience & Trust Triggers:** Urban Indian pet parents anchored by certified vets, community scale, and verified reviews.\n\n"
            "| Channel / Format | Current Baseline Pattern | Creative Fatigue / Gap | Next-Gen Hook Angle |\n"
            "| --- | --- | --- | --- |\n"
            "| Meta Feed & Carousels | Generic SKU/discount cards | Commodity fatigue vs. quick-commerce | Vet-curated breed & life-stage bundles |\n"
            "| Reels & Short Video | Standard pet/offer clips | Over-used discount framing over vet trust | 4s split-screen vet check & care hook |\n"
            "| Search & Shopping | Broad pet food & delivery terms | High CPC overlap with marketplaces | Bundle + vet care value hooks |"
        ),
        "e1": _sample_item(
            "| Search Pillar | Score /100 | Observable Diagnostic Signal | Primary Gap |\n"
            "| --- | --- | --- | --- |\n"
            "| 1. Technical & Programmatic SEO | 69 | Broad catalog and vet-content footprint | Faceted filter crawl bloat & out-of-stock indexation |\n"
            "| 2. AEO | 67 | Strong pet health topics; structured Q&A upside | Concise answer blocks for breed, diet & care queries |\n"
            "| 3. GEO | 65 | Recognizable brand; mixed LLM recommendation share | Comparison & authority assets for AI shopping prompts |\n"
            "| 4. Entity & Local Schema | 70 | Clinic presence across key cities | Unified Organization, Vet/Clinic & Product schema |\n"
            "| 5. Off-Site Consensus & Digital PR | 66 | Active Reddit communities and review profiles | Balancing delivery complaints with vet/care proof |\n\n"
            "- Prune low-value faceted URLs and handle out-of-stock SKUs cleanly.\n"
            "- Add structured vet-backed Q&A blocks for AI Overviews and snippets.\n"
            "- Build breed and life-stage nutrition guides that LLMs cite.\n"
            "- Keep local clinic schema and listings consistent across active cities.\n"
            "---DEEP_DIVE---\n"
            "| High-Intent Buyer Prompt | Current AI Winner | Supertails Vulnerability | Asset Needed to Win |\n"
            "| --- | --- | --- | --- |\n"
            "| Best vet-recommended dog food in India | Review blogs & Reddit | Generic listicles outrank brand guides | Vet-authored ingredient & life-stage matrix |\n"
            "| Online vet consultation India for pet skin issue | Telehealth & forums | Symptom-to-consult path not always first | Structured symptom-triage & consult guide |\n"
            "| Fast pet food delivery near me | Quick-commerce apps | Perceived slower on small instant baskets | City delivery + care bundle pages |\n"
            "| Best puppy/kitten starter essentials | Marketplaces & blogs | Fragmented category discovery | Life-stage checklist & bundle hub |\n\n"
            "### Execution Plan\n"
            "- **[SEO] Problem -> Fix:** Filter combinations dilute crawl budget -> Canonicalize and noindex low-utility sort/filter URLs.\n"
            "- **[AEO] Problem -> Fix:** Long articles delay direct answers -> Add concise answer blocks at top of key guides.\n"
            "- **[GEO] Problem -> Fix:** LLMs lean on Reddit/blogs for picks -> Publish clear nutrition comparisons and clinical FAQs.\n"
            "- **[Schema] Problem -> Fix:** Partial markup across templates -> Enforce valid Product, Offer, MedicalClinic & FAQ schema.\n"
            "- **[Off-Site] Problem -> Fix:** Delivery threads skew perception -> Pair fast CX fixes with verified care stories."
        ),
        "e_paid": _sample_item(
            "| Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal | Primary Leakage |\n"
            "| --- | --- | --- | --- |\n"
            "| 1. Non-Brand Search & Demand/PMax Efficiency | 60 | PMax and Search capture brand & category demand | Brand overlap & low-margin staple bidding |\n"
            "| 2. Paid Social Acquisition & Creative Fatigue | 62 | Active Meta prospecting and retention ads | Low-AOV trial orders & overlapping retargeting |\n"
            "| 3. Landing Page & Product-to-Cart CRO | 59 | Mobile web and app serve distinct journeys | Mobile web conversion lag & missing unit cues |\n"
            "| 4. Checkout, Booking & Post-Click Friction | 63 | Express checkout plus fee/COD mechanics | Fee/COD friction & delivery SLA uncertainty |\n\n"
            "- Exclude brand terms from non-brand PMax and tier by margin.\n"
            "- Exclude recent repeaters from aggressive retargeting.\n"
            "- Show clear per-kg/unit cues and guided pack selectors.\n"
            "- Simplify checkout fees, COD prompts, and delivery ETAs.\n"
            "---DEEP_DIVE---\n"
            "### Paid & Funnel Fixes\n"
            "- **[PMax] Problem -> Fix:** Blended PMax mixes brand and margin tiers -> Separate brand exclusions and segment by margin.\n"
            "- **[Paid Social] Problem -> Fix:** Retargeting overlaps recent buyers & low-AOV trials -> Exclude active repeaters and optimize for LTV.\n"
            "- **[PDP CRO] Problem -> Fix:** Pack math slows mobile add-to-cart -> Surface unit pricing and 1-tap pack/bundle choices.\n"
            "- **[Checkout] Problem -> Fix:** Fees and COD drop-offs stall completion -> Streamline fee framing, prepaid nudges & ETAs.\n\n"
            "### Experiment Backlog\n"
            "| Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |\n"
            "| --- | --- | --- | --- |\n"
            "| Split PMax by margin tier with brand exclusions | Contribution Margin ROAS | New-to-Brand Share | +15-22% margin-adjusted return |\n"
            "| Exclude recent repeaters from Meta retargeting | Prospecting / Blended ROAS | Paid Social CAC | -12-18% wasted retargeting spend |\n"
            "| Add unit-price badges & bundle selector on PDP | Mobile Add-to-Cart & CVR | Page Load / LCP | +12-20% mobile conversion lift |\n"
            "| Streamline checkout fee & COD/prepaid prompt | Checkout-to-Paid CVR | Gross Margin & RTO % | +5-9% checkout completion lift |"
        ),
        "e2": _sample_item(
            "**Current Pricing Strategy:** Supertails combines competitive marketplace-aligned pricing on staple pet foods with free-shipping thresholds, checkout/COD fee mechanics, and growing private-label and vet-service monetization.\n\n"
            "| Pricing & Economics Pillar | Score /100 | Observable Pricing Signal | Margin / LTV Leakage |\n"
            "| --- | --- | --- | --- |\n"
            "| 1. Core SKU & Marketplace Price Positioning | 63 | Competitive discounting on 3P staples vs. q-commerce | Margin compression on commodity food SKUs |\n"
            "| 2. Shipping, Fee & Basket Threshold Architecture | 59 | Free-shipping MOV paired with platform/COD fees | Heavy-bag freight subsidy & small-order friction |\n"
            "| 3. Subscription & Repeat-Cohort Monetization | 61 | Repeat replenishment across food & essentials | One-off buying instead of recurring cadence |\n"
            "| 4. Private-Label & High-Margin Service Mix | 65 | Owned brands and vet consults carry higher margin | Owned-brand & service attach still modest share |\n\n"
            "- Gate steep promo discounts behind private-label or higher-AOV carts.\n"
            "- Align shipping thresholds with parcel weight and local zones.\n"
            "- Differentiate subscription savings across staples vs. owned brands.\n"
            "- Connect vet consultations smoothly into care/nutrition carts.\n"
            "---DEEP_DIVE---\n"
            "### Tier Optimization & Margin Plan\n"
            "- **[Promo Gating] Problem -> Fix:** Broad discounts erode staple margin -> Gate top promos behind owned-brand or basket thresholds.\n"
            "- **[Shipping/Fees] Problem -> Fix:** Flat thresholds strain heavy or small orders -> Calibrate MOV by weight/zone and keep fees clear.\n"
            "- **[Subscriptions] Problem -> Fix:** Flat auto-ship discounts trim 3P margin -> Tier repeat perks higher on owned brands & bundles.\n"
            "- **[Vet-to-Cart] Problem -> Fix:** Vet consults and carts sit too apart -> Streamline post-consult care/nutrition basket flow.\n\n"
            "### Unit Economics & Pricing Impact Matrix\n"
            "| Pricing Lever | Target Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| Promo & Basket Gating | Deal-seeking staple buyers | Require owned-brand mix or higher AOV for promos | +200-300 bps blended GM | Keep welcome offer for first-time trial |\n"
            "| Weight/Zone Shipping MOV | Heavy-bag & small-cart buyers | Dynamic threshold & zone-aware fulfillment | -120-160 bps freight drag | Offer multi-pack value to lift AOV cleanly |\n"
            "| Tiered Auto-Ship | Repeat food/treat buyers | Higher recurring perks on owned brands & bundles | +20-30% repeat order LTV | Allow easy pause/skip to prevent churn |\n"
            "| Consult-to-Care Bundle | Vet consultation users | Post-consult tailored care/supplement cart | +15-22% consult-to-order rate | Keep clinical advice unbiased & trusted |"
        ),
        "e3": _sample_item(
            "1. **Search / High-Intent Ad Pack**\n"
            "- Headline 1: Vet-Curated Pet Care & Food\n"
            "- Headline 2: Fast Delivery & Vet Support\n"
            "- Headline 3: Trusted By Indian Pet Parents\n"
            "- Description 1: Shop authentic pet food, treats, and vet-backed essentials with fast delivery.\n"
            "- Description 2: Get expert vet guidance and easy repeat orders for pets every day.\n\n"
            "2. **Primary Paid Social Ad**\n"
            "- Primary Text: Upgrade daily pet routines with vet-curated nutrition and care bundles.\n"
            "- Headline: Vet-Curated Care Bundles\n"
            "- CTA: Shop Now\n\n"
            "3. **4-Second Video Hook**\n"
            "- Visual Scene: Pet parent checks ingredient label at home; cut to vet-approved bundle.\n"
            "- Voiceover/Text Overlay: Know what goes in their bowl. (6 words)\n"
            "---DEEP_DIVE---\n"
            "### Creative Rationale\n"
            "- **[Paid Social/Video] Problem -> Fix:** Generic discount banners blend into feeds -> Lead with ingredient trust and life-stage fit in 4 seconds.\n"
            "- **[Search RSA] Problem -> Fix:** Repetitive promo copy misses care buyers -> Pair fast delivery with vet authority and proof.\n"
            "- **[Visual Guardrail] Problem -> Fix:** Logo drift hurts brand polish -> Preserve official brand logo and cap overlay badges.\n\n"
            "### Creative A/B Testing Matrix\n"
            "| Ad Variant | Hook / Angle | Target Persona | Primary KPI |\n"
            "| --- | --- | --- | --- |\n"
            "| Variant A (Vet Trust) | Vet-curated nutrition & care | Health-focused pet parents | First-Order Contribution ROAS |\n"
            "| Variant B (Speed/Restock) | Fast restock when running low | Busy urban pet parents | Mobile Add-to-Cart & CVR |\n"
            "| Variant C (Life-Stage Kit) | Puppy/kitten/senior starter bundle | New & transitioning owners | Average Order Value (AOV) |\n"
            "| Variant D (UGC Story) | Real pet parent & vet tip reel | Social/video scrollers | Thumbstop Rate & CTR |"
        ),
        "e4": _sample_item(
            "**Current Brand Sentiment Archetype:** Supertails earns strong goodwill for Fear Free vet care and local speed, while delivery exceptions, cancellation/refund friction, and review gaps drive complaints.\n\n"
            "| Reputation & Listening Pillar | Score /100 | Observable Social / Review Signal | Primary Trust Risk |\n"
            "| --- | --- | --- | --- |\n"
            "| 1. Fulfillment & Post-Purchase Sentiment | 58 | Complaints around missed delivery attempts & cancellations | Courier/SLA failures hurting repeat trust |\n"
            "| 2. Clinical & Product Trust Authority | 74 | Positive feedback on Fear Free vets & product sourcing | Isolated service/escalation disputes |\n"
            "| 3. Review Ecosystem Parity | 62 | Strong site claims vs. mixed public review/forum threads | Rating/sentiment gap across platforms |\n"
            "| 4. Community Advocacy & Earned Momentum | 66 | Loyal pet-parent community and growth milestones | Unresolved threads amplifying complaints |\n\n"
            "| Polarity | Platform & Context | Representative Customer Feedback | Core Theme |\n"
            "| --- | --- | --- | --- |\n"
            "| Positive | Local Clinic Reviews | Calm, gentle vet team explained care clearly without rushing. | Fear Free Vet Care |\n"
            "| Positive | Pet Parent Forums | Genuine branded food and quick arrival on local stock. | Product & Local Speed |\n"
            "| Positive | Customer Stories | Helpful guidance choosing diet/care for a new pet. | Care Guidance |\n"
            "| Negative | Community / Forum Threads | Marked attempted delivery without a real call or visit. | Fake Delivery Attempt |\n"
            "| Negative | Review / App Feedback | Hard to cancel or get prompt refund updates on delayed orders. | Cancellation & Refund UX |\n"
            "| Negative | Support Escalations | Automated replies loop before reaching a human agent. | Support Escalation Gap |\n\n"
            "---DEEP_DIVE---\n"
            "### Rapid Triage Plan\n"
            "- **[Logistics Triage] Problem -> Fix:** Fake delivery attempts spark angry posts -> Audit courier call/GPS logs and resolve fast.\n"
            "- **[Self-Serve UX] Problem -> Fix:** Slow cancellation/refunds fuel escalations -> Add clear cancellation flows and faster refund SLAs.\n"
            "- **[Human Escalation] Problem -> Fix:** Bot loops frustrate urgent orders -> Route stalled orders and care issues to live agents.\n"
            "- **[Trust Amplification] Problem -> Fix:** Negative threads overshadow care wins -> Spotlight verified vet care and real stories.\n\n"
            "### Social Listening & Escalation SLA Matrix\n"
            "| Listening Cluster & Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |\n"
            "| --- | --- | --- | --- |\n"
            "| Delivery Failure / Fake Attempt | 'Attempted delivery', 'no call', overdue | High (<1h triage) | Logistics & CX verify and resolve |\n"
            "| Clinical / Vet Escalation | Care complaint or clinic dispute | High (<2h triage) | Clinical Quality / Clinic Lead follows up |\n"
            "| Refund & Cancellation Friction | Refund delay or cancellation issue | Medium (<12h response) | Billing/CX resolves and updates status |\n"
            "| Creator & Community Buzz | Product reviews, adoption stories, mentions | Medium (<24h response) | Brand/Community team engages |\n\n"
            "### Top 10 Influencers & YouTube Channels for Brand Collaboration\n"
            "| Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 1 | Indian Pet Care & Dog Training YouTubers | YouTube | Indian dog parents seeking diet & training | Vet-backed nutrition & feeding routine |\n"
            "| 2 | Indie Dog & Rescue Creators | Instagram & YouTube | Indian pet & indie adoption audience | Indie/rescue care starter kit story |\n"
            "| 3 | Veterinarian & Pet Health Educators | YouTube & Instagram | Credibility-first pet health viewers | Vet Q&A on skin, coat & digestion |\n"
            "| 4 | Cat Parent & Feline Lifestyle Creators | Instagram & YouTube | Urban cat owners | Cat nutrition, litter & enrichment picks |\n"
            "| 5 | Puppy Parenting & First-Time Channels | YouTube | New pet parents buying starter kits | First 90 days puppy checklist & vet prep |\n"
            "| 6 | Pet Product & Unboxing Reviewers | YouTube Shorts & Reels | Value & comparison buyers | Honest breakdown of food, treats & gear |\n"
            "| 7 | Bengaluru / Metro Pet Community Creators | Instagram | High-density urban pet hubs | Local pet routines & fast care access |\n"
            "| 8 | Pet Wellness & Grooming Creators | Instagram & YouTube | Skin/coat & seasonal care seekers | Coat & skin care across seasons |\n"
            "| 9 | Multi-Pet Household Vloggers | YouTube | High-frequency repeat buyers | Managing multi-pet monthly replenishment |\n"
            "| 10 | Pet Behavior & Enrichment Creators | Instagram & YouTube | Millennial/Gen-Z pet parents | Enrichment + balanced treat pairing |"
        ),
    }


# -----------------------------------------------------------------------------
# GEO + BUSINESS MODEL AWARE CACHE HELPERS (48-HOUR TTL)
# -----------------------------------------------------------------------------
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_") or "default"


def _model_slug(biz_model: str) -> str:
    return _slug(biz_model or "b2c_dtc")


def _scope_prefix(company: str, country: str = "", biz_model: str = "B2C / DTC") -> str:
    geo_part = _slug(country) if (country or "").strip() else "global"
    return f"{_slug(company)}__{geo_part}__{_model_slug(biz_model)}"


def _meta_path(company: str, element_key: str, country: str = "", biz_model: str = "B2C / DTC") -> str:
    return os.path.join(CACHE_DIR, f"{_scope_prefix(company, country, biz_model)}__{_slug(element_key)}.json")


def _asset_path(company: str, element_key: str, ext: str, country: str = "", biz_model: str = "B2C / DTC") -> str:
    return os.path.join(CACHE_DIR, f"{_scope_prefix(company, country, biz_model)}__{_slug(element_key)}.{ext}")


def load_cached_element(company: str, element_key: str, asset_ext: str | None = None, country: str = "", biz_model: str = "B2C / DTC"):
    if BACKEND_FORCE_REFRESH:
        return None
    meta_file = _meta_path(company, element_key, country=country, biz_model=biz_model)
    if not os.path.exists(meta_file):
        return None
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        saved_at = float(meta.get("saved_at", 0))
        if (time.time() - saved_at) > TTL_SECONDS:
            return None
        if asset_ext:
            asset_file = _asset_path(company, element_key, asset_ext, country=country, biz_model=biz_model)
            if not os.path.exists(asset_file):
                return None
            with open(asset_file, "rb") as af:
                meta["bytes"] = af.read()
        return meta
    except Exception:
        return None


def save_cached_element(company: str, element_key: str, payload: dict, raw_bytes: bytes | None = None, asset_ext: str | None = None, country: str = "", biz_model: str = "B2C / DTC"):
    meta_file = _meta_path(company, element_key, country=country, biz_model=biz_model)
    record = dict(payload)
    record["saved_at"] = time.time()
    if asset_ext and raw_bytes is not None:
        asset_file = _asset_path(company, element_key, asset_ext, country=country, biz_model=biz_model)
        with open(asset_file, "wb") as af:
            af.write(raw_bytes)
        record["asset_ext"] = asset_ext
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(record, f)


def format_age(saved_at: float) -> str:
    hours = max(0.0, (time.time() - saved_at) / 3600.0)
    if hours < 1:
        mins = max(1, int(hours * 60))
        return f"{mins}m ago"
    return f"{hours:.1f}h ago"


# -----------------------------------------------------------------------------
# MODEL CALLERS, AUTO-CLASSIFICATION & LOGO EXTRACTION
# -----------------------------------------------------------------------------
def call_gemini(prompt: str, use_search: bool = False, use_url_context: bool = False):
    if not GEMINI_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in backend secrets.")
    client = genai.Client(api_key=GEMINI_KEY)
    tools = []
    if use_search:
        tools.append({"google_search": {}})
    if use_url_context:
        tools.append({"url_context": {}})
    config = types.GenerateContentConfig(tools=tools if tools else None)

    last_err = None
    for model_id in ["gemini-4-hydrogen", "gemini-3.8-flash"]:
        try:
            res = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=config,
            )
            if not res or not res.text:
                raise RuntimeError(f"Empty response from {model_id}")
            cleaned = _sanitize_display_text(res.text)
            mode_tag = "Search + URL Context" if (use_search and use_url_context) else ("Search" if use_search else "Direct")
            return cleaned, f"Gemini ({model_id} • {mode_tag})"
        except Exception as e:
            if use_url_context:
                try:
                    fallback_tools = [{"google_search": {}}] if use_search else None
                    res = client.models.generate_content(
                        model=model_id,
                        contents=prompt,
                        config=types.GenerateContentConfig(tools=fallback_tools),
                    )
                    if res and res.text:
                        return _sanitize_display_text(res.text), f"Gemini ({model_id} • Search)"
                except Exception as inner_e:
                    last_err = inner_e
            else:
                last_err = e
    raise last_err


def call_claude(prompt: str, use_search: bool = False):
    if not CLAUDE_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not configured in backend secrets.")
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    kwargs = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1800,
        "messages": [{"role": "user", "content": prompt}],
    }
    if use_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    msg = client.messages.create(**kwargs)
    text_parts = [block.text for block in msg.content if getattr(block, "type", "") == "text" and getattr(block, "text", "")]
    text = _sanitize_display_text("\n".join(text_parts).strip())
    if not text:
        raise RuntimeError("Empty response from Claude.")
    mode_tag = "Web Search" if use_search else "Direct"
    return text, f"Claude (Sonnet 4.6 • {mode_tag})"


def route_agent(prompt: str, preferred: str = "gemini", use_search: bool = False, use_url_context: bool = False):
    order = ["gemini", "claude"] if preferred == "gemini" else ["claude", "gemini"]
    errors = []
    for provider in order:
        try:
            if provider == "gemini" and GEMINI_KEY:
                return call_gemini(prompt, use_search=use_search, use_url_context=use_url_context)
            elif provider == "claude" and CLAUDE_KEY:
                return call_claude(prompt, use_search=use_search)
        except Exception as e:
            errors.append(f"{provider.upper()}: {e}")
    raise RuntimeError(" | ".join(errors) if errors else "No API key configured.")


def get_or_resolve_official_url(company: str, country: str = "") -> str:
    cached = load_cached_element(company, "official_url_v1", country=country, biz_model="shared")
    if cached and cached.get("url"):
        return cached["url"]
    default_url = f"https://{_slug(company)}.com"
    if not GEMINI_KEY:
        return default_url
    geo_hint = f" specifically for the {country.strip()} market" if (country or "").strip() else ""
    try:
        domain_raw, _ = call_gemini(
            f"Return ONLY the canonical official website URL (e.g., https://supertails.com) for {company}{geo_hint}. No markdown, no extra words.",
            use_search=True,
        )
        match = re.search(r"https?://[^\s\"'<>]+", domain_raw.strip())
        resolved = match.group(0).rstrip(".,)/") if match else default_url
        save_cached_element(company, "official_url_v1", {"url": resolved}, country=country, biz_model="shared")
        return resolved
    except Exception:
        return default_url


def detect_business_model_from_site(company: str, official_url: str, country: str = "") -> dict:
    geo_part = _slug(country) if (country or "").strip() else "global"
    cache_key = f"biz_model_detect_v1__{geo_part}"
    cached = load_cached_element(company, cache_key, country=country, biz_model="shared")
    if cached and cached.get("detected_model"):
        return cached

    geo_note = f" in {country.strip()}" if (country or "").strip() else ""
    prompt = f"""
    Analyze the website and commercial offering of {company} ({official_url}){geo_note}.
    Classify the business model into EXACTLY one of these three options:
    - B2C / DTC
    - B2B / B2B SaaS
    - Hybrid / B2B2C

    Rules:
    - Choose "B2B / B2B SaaS" if the primary offering is B2B software, SaaS, enterprise tooling, APIs, or B2B services sold to businesses/teams.
    - Choose "B2C / DTC" if the primary offering is direct-to-consumer or retail products/services sold to individual consumers.
    - Choose "Hybrid / B2B2C" if the brand meaningfully serves both end consumers/retailers and B2B/enterprise/channel/partner buyers.

    {NO_LATEX_CURRENCY_RULE}

    Respond ONLY in this exact two-line format (no emojis):
    MODEL: <B2C / DTC | B2B / B2B SaaS | Hybrid / B2B2C>
    REASON: <1 concise sentence under 22 words citing website/offering signals>
    """
    try:
        raw, _ = route_agent(prompt, preferred="gemini", use_search=True, use_url_context=True)
        raw = _sanitize_display_text(raw)
        model_match = re.search(r"MODEL:\s*(B2C\s*/\s*DTC|B2B\s*/\s*B2B\s*SaaS|Hybrid\s*/\s*B2B2C)", raw, re.IGNORECASE)
        reason_match = re.search(r"REASON:\s*(.+)", raw, re.IGNORECASE)

        detected = "B2C / DTC"
        if model_match:
            norm = re.sub(r"\s+", " ", model_match.group(1).strip()).lower()
            if "saas" in norm or "b2b / b2b" in norm:
                detected = "B2B / B2B SaaS"
            elif "hybrid" in norm or "b2b2c" in norm:
                detected = "Hybrid / B2B2C"
            else:
                detected = "B2C / DTC"

        reason = reason_match.group(1).strip() if reason_match else f"Classified from {official_url} positioning and commercial signals."
        payload = {"detected_model": detected, "reason": reason}
        save_cached_element(company, cache_key, payload, country=country, biz_model="shared")
        return payload
    except Exception:
        return {
            "detected_model": "B2C / DTC",
            "reason": f"Defaulted to B2C / DTC for {official_url}; toggle above if needed.",
        }


def _download_valid_raster_image(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
                "Accept": "image/png,image/jpeg,image/webp,image/*,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "svg" in ctype or url.lower().split("?")[0].endswith(".svg"):
                return None
            data = resp.read()
        if len(data) > MAX_LOGO_BYTES:
            return None
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        w, h = img.size
        if w < 48 or h < 24:
            return None
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def get_or_fetch_brand_logo(company: str, base_url: str, country: str = ""):
    cached = load_cached_element(company, "brand_logo_v1", asset_ext="png", country=country, biz_model="shared")
    if cached:
        return {"ok": True, "bytes": cached["bytes"], "source": cached.get("source", f"Official Site ({base_url})"), "from_cache": True}

    try:
        req = urllib.request.Request(
            base_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        candidate_urls = []
        for img_tag in re.findall(r"<img\b[^>]*>", html, flags=re.IGNORECASE):
            if "logo" in img_tag.lower():
                src_m = re.search(r'\bsrc=["\']([^"\']+)["\']', img_tag, flags=re.IGNORECASE)
                if src_m:
                    candidate_urls.append(urljoin(base_url, src_m.group(1)))

        for link_tag in re.findall(r"<link\b[^>]*>", html, flags=re.IGNORECASE):
            if any(k in link_tag.lower() for k in ["apple-touch-icon", "icon"]):
                href_m = re.search(r'\bhref=["\']([^"\']+)["\']', link_tag, flags=re.IGNORECASE)
                if href_m:
                    candidate_urls.append(urljoin(base_url, href_m.group(1)))

        candidate_urls.extend([
            urljoin(base_url, "/apple-touch-icon.png"),
            urljoin(base_url, "/logo.png"),
        ])

        seen = set()
        for c_url in candidate_urls:
            if c_url in seen:
                continue
            seen.add(c_url)
            png_bytes = _download_valid_raster_image(c_url)
            if png_bytes:
                source_label = f"Official Site ({base_url})"
                save_cached_element(company, "brand_logo_v1", {"source": source_label}, raw_bytes=png_bytes, asset_ext="png", country=country, biz_model="shared")
                return {"ok": True, "bytes": png_bytes, "source": source_label, "from_cache": False}
    except Exception:
        pass

    return {"ok": False, "bytes": None, "source": None, "from_cache": False}


def get_or_generate_text_element(company: str, element_key: str, prompt: str, preferred: str = "gemini", use_search: bool = False, use_url_context: bool = False, country: str = "", biz_model: str = "B2C / DTC"):
    cached = load_cached_element(company, element_key, country=country, biz_model=biz_model)
    if cached:
        return {
            "ok": True,
            "content": _sanitize_display_text(cached["content"]),
            "engine": cached["engine"],
            "from_cache": True,
            "age": format_age(cached["saved_at"]),
            "error": None,
        }
    try:
        content, engine = route_agent(prompt, preferred=preferred, use_search=use_search, use_url_context=use_url_context)
        content = _sanitize_display_text(content)
        save_cached_element(company, element_key, {"content": content, "engine": engine}, country=country, biz_model=biz_model)
        return {
            "ok": True,
            "content": content,
            "engine": engine,
            "from_cache": False,
            "age": "just now",
            "error": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "content": None,
            "engine": "Unavailable",
            "from_cache": False,
            "age": None,
            "error": str(e),
        }


def get_or_generate_brand_intel(company: str, official_url: str, country: str = "", biz_model: str = "B2C / DTC"):
    cached = load_cached_element(company, "brand_ad_intel_v5", country=country, biz_model=biz_model)
    if cached:
        return _sanitize_display_text(cached["content"])
    m_ctx = _model_guidance(biz_model)
    geo_clause = f"STRICTLY SCOPED TO {country.strip().upper()} ONLY (use local currency, local regulations, and {country.strip()} market context; ignore other countries)." if (country or "").strip() else "Cover primary active commercial markets."
    prompt = f"""
    Act as VP of Brand & Performance Creative auditing {company} (official website: {official_url}) across its web experience, Meta Ad Library, LinkedIn/Google Ads Transparency Center, and search presence.
    {m_ctx["prompt_context"]}
    {geo_clause}
    {NO_LATEX_CURRENCY_RULE}
    STRICT FORMATTING (DO NOT USE ANY EMOJIS):
    - Output EXACTLY these 4 concise bullet points (max 18 words per bullet):
      - **Visual Design Language:** [Exact primary/secondary brand colors, card/UI styling, typography mood, and photography/product UI style]
      - **Paid Social & Ad Patterns:** [Dominant visual hooks, proof/offer badges, and creative formats seen in their ads]
      - **Search & Demand Messaging:** [Primary headline angles, value props, and CTA patterns in search/demand ads]
      - **Core Audience & Trust Triggers:** [Target buyer/persona setting and key credibility signals/social proof used]
    - Immediately follow with a compact 3-row **Creative Baseline & Opportunity Matrix** table:
      | Channel / Format | Current Baseline Pattern | Creative Fatigue / Gap | Next-Gen Hook Angle |
    """
    res = get_or_generate_text_element(company, "brand_ad_intel_v5", prompt, preferred="gemini", use_search=True, use_url_context=True, country=country, biz_model=biz_model)
    return _sanitize_display_text(res["content"]) if res["ok"] else f"Authentic brand design language for {company}."


def get_or_generate_image_element(company: str, element_key: str, prompt: str, aspect_ratio: str = "1:1", logo_bytes: bytes | None = None, country: str = "", biz_model: str = "B2C / DTC"):
    cached = load_cached_element(company, element_key, asset_ext="png", country=country, biz_model=biz_model)
    if cached:
        return {
            "ok": True,
            "bytes": cached["bytes"],
            "from_cache": True,
            "age": format_age(cached["saved_at"]),
            "error": None,
        }
    try:
        if not GEMINI_KEY:
            raise ValueError("GEMINI_API_KEY required for image generation.")
        client = genai.Client(api_key=GEMINI_KEY)

        if logo_bytes:
            logo_pil = Image.open(io.BytesIO(logo_bytes))
            logo_rule = (
                "BRAND LOGO GUARDRAIL: The attached reference image is the official brand logo. "
                "Place this exact logo cleanly in the top-left corner without altering, redrawing, recoloring, or distorting its icon or typography."
            )
            model_contents = [logo_pil, f"{prompt} {logo_rule}"]
        else:
            logo_rule = (
                "BRAND LOGO GUARDRAIL: Do NOT invent, draw, or render any brand logo, wordmark, or company name text anywhere in the image. "
                "Leave a clean unobstructed top-left corner safe zone for manual brand logo placement."
            )
            model_contents = f"{prompt} {logo_rule}"

        response = client.models.generate_content(
            model="gemini-3.1-flash-image",
            contents=model_contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                img = Image.open(io.BytesIO(part.inline_data.data))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                raw_png = buf.getvalue()
                save_cached_element(company, element_key, {}, raw_bytes=raw_png, asset_ext="png", country=country, biz_model=biz_model)
                return {
                    "ok": True,
                    "bytes": raw_png,
                    "from_cache": False,
                    "age": "just now",
                    "error": None,
                }
        raise RuntimeError("No image bytes returned by model.")
    except Exception as e:
        return {
            "ok": False,
            "bytes": None,
            "from_cache": False,
            "age": None,
            "error": str(e),
        }


def extract_composite_score(markdown_text: str, fallback: int = 65) -> int:
    scores = []
    for line in (markdown_text or "").splitlines():
        if line.strip().startswith("|") and not line.strip().startswith("| Search Pillar") and not line.strip().startswith("| Paid & Funnel") and not line.strip().startswith("| Pricing & Economics") and not line.strip().startswith("| Reputation & Listening"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 2:
                m = re.match(r"^(\d{1,3})$", cols[1])
                if m:
                    val = int(m.group(1))
                    if 0 <= val <= 100:
                        scores.append(val)
    return round(sum(scores) / len(scores)) if scores else fallback


# -----------------------------------------------------------------------------
# BRAND COLOR EXTRACTOR, PILLAR CHART & EXECUTIVE SUMMARY + APPENDIX PDF BUILDER
# -----------------------------------------------------------------------------
def _extract_brand_rgb(logo_bytes: bytes | None) -> tuple[int, int, int]:
    default_rgb = (0, 113, 227)
    if not logo_bytes:
        return default_rgb
    try:
        img = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        img.thumbnail((64, 64))
        color_counts: dict[tuple[int, int, int], int] = {}
        for r, g, b, a in img.getdata():
            if a < 140:
                continue
            if (r > 235 and g > 235 and b > 235) or (r < 25 and g < 25 and b < 25):
                continue
            bucket = (round(r / 16) * 16, round(g / 16) * 16, round(b / 16) * 16)
            color_counts[bucket] = color_counts.get(bucket, 0) + 1
        if not color_counts:
            return default_rgb
        best = max(color_counts.items(), key=lambda kv: kv[1])[0]
        return (min(210, best[0]), min(210, best[1]), min(210, best[2]))
    except Exception:
        return default_rgb


def _render_pillar_score_chart_png(hooks: dict, brand_rgb: tuple[int, int, int]) -> bytes | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        labels = [
            "Social & Brand",
            "Creative Studio",
            "Pricing & Econ",
            "Paid & CRO",
            "SEO / AEO / GEO",
        ]
        ordered_keys = ["social", "creative", "pricing", "paid", "seo"]
        scores = []
        bar_colors = []
        for k in ordered_keys:
            raw_sc = hooks.get(k, ("65", ""))[0]
            try:
                val = max(0, min(100, int(re.sub(r"[^\d]", "", str(raw_sc)) or "65")))
            except ValueError:
                val = 65
            scores.append(val)
            if val < 50:
                bar_colors.append("#DC2626")
            elif val < 70:
                bar_colors.append("#D97706")
            else:
                bar_colors.append("#059669")

        fig, ax = plt.subplots(figsize=(7.6, 2.55), dpi=180)
        fig.patch.set_facecolor("#FFFFFF")
        ax.set_facecolor("#FAFBFD")

        y_pos = list(range(len(labels)))
        bars = ax.barh(y_pos, scores, height=0.56, color=bar_colors, edgecolor="none")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=9, fontweight="bold", color="#1D1D1F")
        ax.set_xlim(0, 108)
        ax.xaxis.grid(True, linestyle="--", alpha=0.45, color="#CBD5E1")
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#CBD5E1")
        ax.spines["bottom"].set_color("#CBD5E1")
        ax.tick_params(axis="x", labelsize=8, colors="#475569")

        r, g, b = brand_rgb
        hex_accent = f"#{r:02x}{g:02x}{b:02x}"
        ax.set_title("5-Pillar Readiness Scores (Red <50  |  Amber 50-69  |  Green 70+)", fontsize=9.5, fontweight="bold", color=hex_accent, loc="left", pad=8)

        for bar, val in zip(bars, scores):
            ax.text(val + 1.8, bar.get_y() + bar.get_height() / 2, f"{val}/100", va="center", ha="left", fontsize=8.5, fontweight="bold", color="#1E293B")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="PNG", dpi=180)
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        return None


def _clean_pdf_text(text: str) -> str:
    if not text:
        return ""
    text = _sanitize_display_text(text)
    replacements = {
        "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "-", "\u2026": "...",
        "\u2192": "->", "\u20b9": "INR ", "\u00a0": " ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    return text.encode("latin-1", "ignore").decode("latin-1").strip()


def _infer_col_widths(headers: list[str], usable_w: float) -> tuple[float, ...]:
    n = len(headers)
    if n == 0:
        return ()
    weights = []
    for h in headers:
        hl = h.lower()
        if any(k in hl for k in ["score", "rank", "polarity", "severity"]):
            weights.append(1.15)
        elif any(k in hl for k in ["pillar", "lever", "variant", "platform", "stakeholder", "cluster", "channel", "module"]):
            weights.append(2.2)
        elif any(k in hl for k in ["metric", "kpi", "cohort", "persona"]):
            weights.append(2.0)
        else:
            weights.append(3.4)
    total = sum(weights)
    return tuple(round((w / total) * usable_w, 2) for w in weights)


class ExecutivePDF(FPDF):
    def __init__(self, company_name: str, country_label: str = "", biz_model: str = "", brand_rgb: tuple[int, int, int] = (0, 113, 227)):
        super().__init__()
        self.company_name = _clean_pdf_text(company_name)
        self.country_label = _clean_pdf_text(country_label)
        self.biz_model = _clean_pdf_text(biz_model)
        self.brand_rgb = brand_rgb

    def header(self):
        if self.page_no() == 1:
            return
        r, g, b = self.brand_rgb
        self.set_fill_color(r, g, b)
        self.rect(0, 0, self.w, 3, style="F")
        self.set_y(6)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(110, 110, 115)
        geo_tag = f"  |  {self.country_label.upper()}" if self.country_label else ""
        model_tag = f"  |  {self.biz_model}" if self.biz_model else ""
        self.cell(0, 6, _clean_pdf_text(f"EXECUTIVE INTELLIGENCE BRIEF  |  {self.company_name.upper()}{geo_tag}{model_tag}"), align="L")
        self.ln(9)

    def footer(self):
        self.set_y(-13)
        self.set_draw_color(225, 225, 230)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font("Helvetica", "", 8)
        self.set_text_color(130, 130, 135)
        self.cell(0, 8, _clean_pdf_text(f"Prepared by Soumya Ranjan Nayak   |   Executive Summary & Appendix   |   Page {self.page_no()}"), align="C")

    def section_banner(self, num_label: str, title: str, score_str: str | None = None):
        if self.get_y() > self.h - 45:
            self.add_page()
        self.ln(4)
        r, g, b = self.brand_rgb
        y0 = self.get_y()
        self.set_fill_color(246, 247, 250)
        self.rect(self.l_margin, y0, self.w - self.l_margin - self.r_margin, 11, style="F")
        self.set_fill_color(r, g, b)
        self.rect(self.l_margin, y0, 2.5, 11, style="F")

        self.set_xy(self.l_margin + 5, y0 + 2)
        self.set_font("Helvetica", "B", 11.5)
        self.set_text_color(29, 29, 31)
        header_txt = f"{num_label}. {title}" if num_label else title
        if score_str:
            header_txt += f"   [{score_str}/100]"
        self.cell(0, 7, _clean_pdf_text(header_txt))
        self.set_y(y0 + 14)

    def sub_heading(self, title: str):
        if self.get_y() > self.h - 32:
            self.add_page()
        self.ln(2)
        r, g, b = self.brand_rgb
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(r, g, b)
        self.cell(0, 6, _clean_pdf_text(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def render_table(self, table_rows: list[list[str]]):
        if not table_rows:
            return
        col_count = max(len(r) for r in table_rows)
        normalized = [r + [""] * (col_count - len(r)) for r in table_rows]
        usable_w = self.w - self.l_margin - self.r_margin
        col_widths = _infer_col_widths(normalized[0], usable_w)

        score_col_indices = {
            idx for idx, h in enumerate(normalized[0])
            if "score" in h.lower()
        }

        r, g, b = self.brand_rgb
        self.set_font("Helvetica", "", 8.2)
        self.set_draw_color(218, 220, 226)

        with self.table(
            col_widths=col_widths,
            text_align="LEFT",
            line_height=4.4,
            padding=(2.2, 2.5, 2.2, 2.5),
            borders_layout="HORIZONTAL_LINES",
            first_row_as_headings=True,
            repeat_headings=1,
        ) as tbl:
            for row_idx, row_data in enumerate(normalized):
                row = tbl.row()
                for c_idx, cell_val in enumerate(row_data):
                    clean_val = _clean_pdf_text(cell_val)
                    if row_idx == 0:
                        self.set_font("Helvetica", "B", 8.3)
                        self.set_text_color(255, 255, 255)
                        self.set_fill_color(r, g, b)
                    elif c_idx in score_col_indices and re.search(r"\d+", clean_val):
                        bg_rgb, fg_rgb = _score_tier_rgb(clean_val)
                        self.set_font("Helvetica", "B", 8.2)
                        self.set_fill_color(*bg_rgb)
                        self.set_text_color(*fg_rgb)
                    else:
                        self.set_font("Helvetica", "", 8.1)
                        self.set_text_color(38, 38, 42)
                        if row_idx % 2 == 0:
                            self.set_fill_color(248, 249, 252)
                        else:
                            self.set_fill_color(255, 255, 255)
                    row.cell(clean_val)
        self.ln(3)

    def render_callout_bullet(self, raw_bullet: str):
        cleaned = _clean_pdf_text(raw_bullet)
        if self.get_y() > self.h - 26:
            self.add_page()
        r, g, b = self.brand_rgb
        x0 = self.l_margin
        y0 = self.get_y()
        self.set_fill_color(r, g, b)
        self.rect(x0 + 1.5, y0 + 1.8, 1.5, 1.5, style="F")
        self.set_xy(x0 + 5, y0)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(34, 34, 38)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 5, 4.8, cleaned)
        self.ln(1.2)

    def render_problem_fix_card(self, raw_line: str):
        cleaned = _clean_pdf_text(raw_line)
        if self.get_y() > self.h - 32:
            self.add_page()
        r, g, b = self.brand_rgb
        x0 = self.l_margin
        y0 = self.get_y()
        w_box = self.w - self.l_margin - self.r_margin

        if "->" in cleaned and ":" in cleaned:
            head, body = cleaned.split(":", 1)
            self.set_font("Helvetica", "B", 8.8)
            self.set_text_color(r, g, b)
            self.set_x(x0 + 3)
            self.multi_cell(w_box - 4, 4.6, head.strip())
            self.set_font("Helvetica", "", 8.6)
            self.set_text_color(44, 44, 48)
            self.set_x(x0 + 3)
            self.multi_cell(w_box - 4, 4.5, body.strip())
        else:
            self.set_font("Helvetica", "", 8.6)
            self.set_text_color(44, 44, 48)
            self.set_x(x0 + 3)
            self.multi_cell(w_box - 4, 4.5, cleaned)

        y1 = self.get_y()
        self.set_draw_color(r, g, b)
        self.set_line_width(0.6)
        self.line(x0 + 1, y0 + 0.5, x0 + 1, y1 - 0.5)
        self.set_line_width(0.2)
        self.ln(2.2)

    def render_markdown_block(self, md_text: str):
        parts = (md_text or "").split("---DEEP_DIVE---")
        for p_idx, part in enumerate(parts):
            if p_idx == 1 and part.strip():
                self.sub_heading("Strategic Deep Dive & Action Playbook")
            lines = part.splitlines()
            table_rows: list[list[str]] = []

            for raw_line in lines:
                line = raw_line.strip()
                if not line:
                    if table_rows:
                        self.render_table(table_rows)
                        table_rows = []
                    continue

                if line.startswith("|") and line.endswith("|"):
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    if all(set(c) <= set("-: ") for c in cells):
                        continue
                    table_rows.append(cells)
                    continue

                if table_rows:
                    self.render_table(table_rows)
                    table_rows = []

                if line.startswith("#"):
                    self.sub_heading(line.lstrip("#").strip())
                elif line.startswith("- ") or line.startswith("* "):
                    item_txt = line[2:].strip()
                    if "Problem -> Fix" in item_txt or "Problem → Fix" in item_txt:
                        self.render_problem_fix_card(item_txt)
                    else:
                        self.render_callout_bullet(item_txt)
                else:
                    self.set_font("Helvetica", "", 9.2)
                    self.set_text_color(44, 44, 48)
                    self.multi_cell(0, 4.9, _clean_pdf_text(line))
                    self.ln(1.5)

            if table_rows:
                self.render_table(table_rows)


def build_executive_pdf(audit_data: dict) -> bytes:
    company = audit_data.get("company", "Brand")
    country_lbl = audit_data.get("country", "")
    biz_model = audit_data.get("biz_model", "B2C / DTC")
    official_url = audit_data.get("official_url", "")
    hooks = audit_data.get("hooks") or {}
    bl = audit_data.get("brand_logo") or {}
    logo_bytes = bl.get("bytes") if bl.get("ok") else None

    brand_rgb = _extract_brand_rgb(logo_bytes)
    r, g, b = brand_rgb

    pdf = ExecutivePDF(company, country_label=country_lbl, biz_model=biz_model, brand_rgb=brand_rgb)
    pdf.set_margins(14, 14, 14)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    # SECTION 1 OF PDF: EXECUTIVE SUMMARY
    pdf.set_fill_color(r, g, b)
    pdf.rect(0, 0, pdf.w, 6, style="F")

    temp_files = []
    try:
        y_top = 14
        x_cursor = pdf.l_margin
        if logo_bytes:
            tmp_logo = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp_logo.write(logo_bytes)
            tmp_logo.close()
            temp_files.append(tmp_logo.name)
            pdf.set_fill_color(242, 243, 247)
            pdf.rect(x_cursor, y_top, 26, 14, style="F")
            pdf.image(tmp_logo.name, x=x_cursor + 2, y=y_top + 2, h=10)
            x_cursor += 30

        pdf.set_xy(x_cursor, y_top)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(29, 29, 31)
        pdf.cell(0, 9, _clean_pdf_text(company), new_x="LMARGIN", new_y="NEXT")

        pdf.set_x(x_cursor)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(100, 100, 108)
        geo_part = f"Market: {country_lbl}" if country_lbl else "Market: Global"
        meta_line = f"{official_url}  |  {biz_model}  |  {geo_part}  |  {datetime.now().strftime('%B %d, %Y')}"
        pdf.cell(0, 6, _clean_pdf_text(meta_line), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        pdf.section_banner("", "Executive Summary: 5-Pillar Scorecard")

        score_rows = [["Diagnostic Pillar", "Score /100", "Primary Strategic Priority"]]
        module_meta = [
            ("seo", "Organic Search (SEO, AEO & GEO)"),
            ("paid", "Paid Search & Funnel CRO"),
            ("pricing", "Pricing & Unit Economics"),
            ("creative", "Ad Creative Studio"),
            ("social", "Social & Brand Triage"),
        ]
        for m_key, m_title in module_meta:
            sc_val, one_liner = hooks.get(m_key, ("65", "See appendix for full diagnostics."))
            score_rows.append([m_title, f"{sc_val} / 100", one_liner])
        pdf.render_table(score_rows)

        chart_png = _render_pillar_score_chart_png(hooks, brand_rgb)
        if chart_png:
            tmp_chart = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp_chart.write(chart_png)
            tmp_chart.close()
            temp_files.append(tmp_chart.name)
            if pdf.get_y() + 56 > pdf.h - 18:
                pdf.add_page()
            pdf.image(tmp_chart.name, x=pdf.l_margin, y=pdf.get_y(), w=pdf.w - pdf.l_margin - pdf.r_margin)
            pdf.ln(58)

        pdf.sub_heading("Key Executive Priorities")
        for m_key, m_title in module_meta:
            sc_val, one_liner = hooks.get(m_key, ("65", ""))
            if one_liner:
                pdf.render_callout_bullet(f"{m_title} ({sc_val}/100): {one_liner}")

        # SECTION 2 OF PDF: APPENDIX (DETAILED MODULES & CREATIVES)
        pdf.add_page()
        pdf.section_banner("APPENDIX", "Detailed Module Diagnostics, Playbooks & Creatives")

        sections = [
            ("A.1", "SEO, AEO & GEO", "seo", audit_data.get("e1")),
            ("A.2", "Paid Search & Funnel CRO", "paid", audit_data.get("e_paid")),
            ("A.3", "Pricing & Unit Economics", "pricing", audit_data.get("e2")),
            ("A.4", "Ad Creative Studio", "creative", audit_data.get("e3")),
            ("A.5", "Social & Brand Triage", "social", audit_data.get("e4")),
        ]
        for num_lbl, sec_title, m_key, item in sections:
            if item and item.get("ok"):
                sc_val = hooks.get(m_key, ("", ""))[0]
                pdf.section_banner(num_lbl, sec_title, score_str=sc_val)
                pdf.render_markdown_block(item["content"])

        images_to_embed = [
            ("Paid Social Creative (1:1)", audit_data.get("img_meta"), 88),
            ("Display / Demand Banner (16:9)", audit_data.get("img_banner"), 142),
            ("4-Second Video Hook Keyframe (16:9)", audit_data.get("img_hook_frame"), 142),
        ]
        valid_imgs = [(lbl, it, w) for lbl, it, w in images_to_embed if it and it.get("ok") and it.get("bytes")]
        if valid_imgs:
            pdf.add_page()
            pdf.section_banner("A.6", "Generated Brand Creative Prototypes")
            for lbl, it, w in valid_imgs:
                if pdf.get_y() > 195:
                    pdf.add_page()
                pdf.sub_heading(lbl)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                tmp.write(it["bytes"])
                tmp.close()
                temp_files.append(tmp.name)
                y_img = pdf.get_y()
                pdf.image(tmp.name, x=pdf.l_margin, y=y_img, w=w)
                pdf.set_y(pdf.get_y() + (w * 0.58 if w > 100 else w) + 6)
    finally:
        for p in temp_files:
            if os.path.exists(p):
                os.remove(p)

    raw_out = pdf.output()
    return bytes(raw_out) if isinstance(raw_out, (bytes, bytearray)) else raw_out.encode("latin-1")


def get_cached_pdf_bytes(audit_data: dict) -> bytes:
    cache_map = st.session_state.setdefault("pdf_cache_v3", {})
    key = f"{_scope_prefix(audit_data.get('company', 'brand'), audit_data.get('country', ''), audit_data.get('biz_model', 'B2C / DTC'))}__{audit_data.get('is_showcase', False)}"
    if key not in cache_map:
        cache_map[key] = build_executive_pdf(audit_data)
    return cache_map[key]


# -----------------------------------------------------------------------------
# STEP 1 (MODEL DETECTION) & STEP 2 (MODEL-AWARE LIVE AUDIT ORCHESTRATOR)
# -----------------------------------------------------------------------------
def run_step1_detection(company: str, country: str = "") -> dict:
    clean_country = (country or "").strip()
    official_url = get_or_resolve_official_url(company, country=clean_country)
    detected = detect_business_model_from_site(company, official_url, country=clean_country)
    return {
        "company": company,
        "country": clean_country,
        "official_url": official_url,
        "detected_model": detected.get("detected_model", "B2C / DTC"),
        "reason": detected.get("reason", ""),
    }


def run_live_audit(company: str, country: str = "", biz_model: str = "B2C / DTC", pre_resolved_url: str | None = None):
    clean_country = (country or "").strip()
    clean_model = biz_model if biz_model in BUSINESS_MODELS else "B2C / DTC"
    m_ctx = _model_guidance(clean_model)

    geo_rule = (
        f"GEOGRAPHIC SCOPE MANDATE: Limit ALL analysis, search queries, buyer prompts, pricing/currency figures, regulations, ad hooks, customer reviews, and creator/authority recommendations strictly to {clean_country.upper()}. Do not blend in other countries."
        if clean_country
        else "GEOGRAPHIC SCOPE MANDATE: Analyze the brand across its primary active commercial markets."
    )
    model_rule = f"BUSINESS MODEL MANDATE: {m_ctx['prompt_context']}"

    progress_slot = st.empty()
    bar_slot = st.empty()

    def update_status(pct: int, stage_title: str):
        progress_slot.markdown(f"""
        <div class="status-panel">
            <span class="status-step-label">{stage_title}</span>
            <span class="status-pct-pill">{pct}%</span>
        </div>
        """, unsafe_allow_html=True)
        bar_slot.progress(min(100, max(0, pct)))

    try:
        update_status(10, f"Resolving domain & brand mark ({clean_model})...")
        official_url = pre_resolved_url or get_or_resolve_official_url(company, country=clean_country)
        brand_logo = get_or_fetch_brand_logo(company, official_url, country=clean_country)

        update_status(22, "Mapping brand design language & ad baseline...")
        brand_dna_text = get_or_generate_brand_intel(company, official_url, country=clean_country, biz_model=clean_model)

        p1 = f"""
        Act as Principal SEO, AEO, and GEO Architect auditing {company} ({official_url}).
        {model_rule}
        {geo_rule}
        {NO_LATEX_CURRENCY_RULE}
        STRICT FORMATTING:
        - Start with:
          | Search Pillar | Score /100 | Observable Diagnostic Signal | Primary Gap |
          Rows: 1. Technical & Programmatic SEO, 2. AEO, 3. GEO, 4. Entity & Local Schema, 5. Off-Site Consensus & Digital PR. Use integer-only scores.
        - Follow with 4 short bullets (max 16 words each).
        - End with '---DEEP_DIVE---' followed by an AI Prompt Visibility Matrix table and 5 bullets formatted as `- **[Area] Problem -> Fix:** [Diagnosis] -> [Action]`.
        """
        p_paid = f"""
        Act as VP of Performance Marketing & Conversion auditing {company} ({official_url}).
        {model_rule}
        {geo_rule}
        {NO_LATEX_CURRENCY_RULE}
        STRICT FORMATTING:
        - Start with:
          | Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal | Primary Leakage |
          Rows: 1. Non-Brand Search & Demand/PMax Efficiency, 2. Paid Social Acquisition & Creative Fatigue, {m_ctx["cro_pillar"]}, {m_ctx["checkout_pillar"]}. Use integer-only scores.
        - Follow with 4 short bullets (max 16 words each).
        - End with '---DEEP_DIVE---' followed by 4 bullets (`- **[Area] Problem -> Fix:** ...`) and a 4-row experiment backlog table (`| Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |`).
        """
        p2 = f"""
        Act as VP of Pricing & Commercial Strategy auditing {company} ({official_url}).
        {model_rule}
        {geo_rule}
        {NO_LATEX_CURRENCY_RULE}
        STRICT FORMATTING:
        - Line 1: **{m_ctx["pricing_summary_label"]}:** [1 concise sentence].
        - Follow with:
          | Pricing & Economics Pillar | Score /100 | Observable Pricing Signal | Margin / LTV Leakage |
          Rows: {m_ctx["pricing_p1"]}, {m_ctx["pricing_p2"]}, {m_ctx["pricing_p3"]}, {m_ctx["pricing_p4"]}. Use integer-only scores.
        - Follow with 4 short bullets (max 16 words each).
        - End with '---DEEP_DIVE---' followed by 4 bullets (`- **[Lever] Problem -> Fix:** ...`) and a 4-row impact table (`| Pricing Lever | Target Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |`).
        """
        p3 = f"""
        Act as VP of Performance Creative for {company}. Brand baseline: {brand_dna_text}
        {model_rule}
        {geo_rule}
        {NO_LATEX_CURRENCY_RULE}
        STRICT FORMATTING (NO EMOJIS):
        - Output 1. Search / High-Intent Ad Pack (3 headlines <=30 chars + 2 descriptions <=90 chars), 2. Primary Paid Social Ad (Primary Text <=110 chars, Headline <=35 chars, CTA tailored to {clean_model}), 3. 4-Second Video Hook (Scene + <=12-word hook).
        - End with '---DEEP_DIVE---' followed by 3 bullets (`- **[Channel] Problem -> Fix:** ...`) and a 4-row A/B testing table (`| Ad Variant | Hook / Angle | Target Persona | Primary KPI |`).
        """
        p4 = f"""
        Act as VP of Brand Reputation, Social Listening & Creator/Authority Partnerships auditing {company} ({official_url}).
        {model_rule}
        {geo_rule}
        {NO_LATEX_CURRENCY_RULE}
        STRICT FORMATTING (NO EMOJIS):
        - Line 1: **Current Brand Sentiment Archetype:** [1 concise sentence].
        - Follow with:
          | Reputation & Listening Pillar | Score /100 | Observable Social / Review Signal | Primary Trust Risk |
          Rows: {m_ctx["social_p1"]}, {m_ctx["social_p2"]}, {m_ctx["social_p3"]}, {m_ctx["social_p4"]}. Use integer-only scores.
        - Follow with a 6-row table (3 Positive, 3 Negative): `| Polarity | Platform & Context | Representative Customer Feedback | Core Theme |`.
        - End with '---DEEP_DIVE---' followed by 4 bullets (`- **[Area] Problem -> Fix:** ...`), a 4-row SLA table (`| Listening Cluster & Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |`), and a 10-row creator/thought-leader table (`| Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |`).
        """

        update_status(35, "Running SEO, AEO & GEO search module...")
        e1 = get_or_generate_text_element(company, "agent1_seo_aeo_geo_v5", p1, preferred="gemini", use_search=True, use_url_context=True, country=clean_country, biz_model=clean_model)

        update_status(48, "Running Paid Search & Funnel CRO module...")
        e_paid = get_or_generate_text_element(company, "agent2_paid_cro_v4", p_paid, preferred="gemini", use_search=True, use_url_context=True, country=clean_country, biz_model=clean_model)

        update_status(60, "Running Pricing & Unit Economics module...")
        e2 = get_or_generate_text_element(company, "agent2_pricing_v4", p2, preferred="gemini", use_search=True, use_url_context=True, country=clean_country, biz_model=clean_model)

        update_status(72, "Generating ad copy & creative angles...")
        e3 = get_or_generate_text_element(company, "agent3_creative_v4", p3, preferred="gemini", country=clean_country, biz_model=clean_model)

        update_status(84, "Auditing social sentiment & creator/authority roster...")
        e4 = get_or_generate_text_element(company, "agent4_social_v4", p4, preferred="gemini", use_search=True, use_url_context=True, country=clean_country, biz_model=clean_model)

        img_meta = img_banner = img_hook_frame = None
        if GENERATE_IMAGES_DEFAULT:
            update_status(92, "Rendering brand-aligned ad mockups...")
            logo_bytes = brand_logo["bytes"] if brand_logo["ok"] else None
            geo_img_note = f" Market context: {clean_country}." if clean_country else ""
            model_img_note = f" Business model context: {clean_model}."
            img_meta = get_or_generate_image_element(company, "meta_ad_1x1_v5", f"Clean 1:1 paid social ad for {company}.{geo_img_note}{model_img_note} {brand_dna_text} Max 2 clean UI elements.", "1:1", logo_bytes, country=clean_country, biz_model=clean_model)
            img_banner = get_or_generate_image_element(company, "banner_ad_16x9_v5", f"Clean 16:9 display banner for {company}.{geo_img_note}{model_img_note} {brand_dna_text} Max 2 clean UI elements.", "16:9", logo_bytes, country=clean_country, biz_model=clean_model)
            img_hook_frame = get_or_generate_image_element(company, "video_hook_frame_16x9_v5", f"Clean 16:9 4-second video hook opening frame for {company}.{geo_img_note}{model_img_note} {brand_dna_text} Max 2 clean UI overlays.", "16:9", logo_bytes, country=clean_country, biz_model=clean_model)

        update_status(100, "Audit complete.")
    finally:
        progress_slot.empty()
        bar_slot.empty()

    s_seo = extract_composite_score(e1.get("content", ""), 68)
    s_paid = extract_composite_score(e_paid.get("content", ""), 61)
    s_pri = extract_composite_score(e2.get("content", ""), 62)
    s_soc = extract_composite_score(e4.get("content", ""), 65)

    geo_suffix = f" in {clean_country}" if clean_country else ""
    if clean_model == "B2B / B2B SaaS":
        hooks = {
            "seo": (str(s_seo), f"Capture BOF comparison/alternative searches & AI answers for {company}{geo_suffix}."),
            "paid": (str(s_paid), f"Tighten demo/SQL conversion & buying-committee funnel flow for {company}{geo_suffix}."),
            "pricing": (str(s_pri), f"Align seat/usage/ACV tiers, trial-to-paid & expansion levers for {company}{geo_suffix}."),
            "creative": ("72", f"Test persona-led ROI & workflow hooks with brand logo guardrails for {company}{geo_suffix}."),
            "social": (str(s_soc), f"Strengthen G2/peer proof, executive voice & support SLAs for {company}{geo_suffix}."),
        }
    elif clean_model == "Hybrid / B2B2C":
        hooks = {
            "seo": (str(s_seo), f"Align direct & B2B/partner search/AI visibility for {company}{geo_suffix}."),
            "paid": (str(s_paid), f"Segment direct vs. partner/commercial funnels & CRO for {company}{geo_suffix}."),
            "pricing": (str(s_pri), f"Balance direct vs. partner margins, bundles & attach for {company}{geo_suffix}."),
            "creative": ("72", f"Test dual-audience proof hooks with brand logo guardrails for {company}{geo_suffix}."),
            "social": (str(s_soc), f"Close end-user & partner SLA gaps and scale proof for {company}{geo_suffix}."),
        }
    else:
        hooks = {
            "seo": (str(s_seo), f"Fix crawl/schema gaps and target high-intent search & AI answers for {company}{geo_suffix}."),
            "paid": (str(s_paid), f"Isolate brand vs. non-brand spend and cut funnel drop-offs for {company}{geo_suffix}."),
            "pricing": (str(s_pri), f"Gate promos, tune shipping thresholds, and lift high-margin mix for {company}{geo_suffix}."),
            "creative": ("72", f"Test high-contrast hooks and compliant ad copy with logo guardrails for {company}{geo_suffix}."),
            "social": (str(s_soc), f"Resolve top fulfillment/service friction and activate creators for {company}{geo_suffix}."),
        }

    return {
        "company": company,
        "country": clean_country,
        "biz_model": clean_model,
        "official_url": official_url,
        "is_showcase": False,
        "hooks": hooks,
        "brand_logo": brand_logo,
        "brand_intel": brand_dna_text,
        "e1": e1,
        "e_paid": e_paid,
        "e2": e2,
        "e3": e3,
        "e4": e4,
        "img_meta": img_meta,
        "img_banner": img_banner,
        "img_hook_frame": img_hook_frame,
    }


# -----------------------------------------------------------------------------
# HEADER, TWO-STEP LIVE AUDIT FLOW & SAMPLE PRESET ROW
# -----------------------------------------------------------------------------
st.markdown("""
<div class="suite-title">Executive Intelligence Suite.</div>
<p class="suite-subtitle">
    Structured diagnostics across Organic Search (SEO/AEO/GEO), Paid Acquisition & CRO, Pricing Economics, Brand Creative, and Reputation Triage.
</p>
""", unsafe_allow_html=True)

if "selected_bento_v5" not in st.session_state:
    st.session_state["selected_bento_v5"] = None

if "scroll_to_detail_nonce" not in st.session_state:
    st.session_state["scroll_to_detail_nonce"] = 0

if "last_audit_v5" not in st.session_state:
    st.session_state["last_audit_v5"] = build_sample_showcase("supertails")

if "delivered_email_v1" not in st.session_state:
    st.session_state["delivered_email_v1"] = None

if "pending_model_step" not in st.session_state:
    st.session_state["pending_model_step"] = None

if "biz_model_selector_v1" not in st.session_state:
    st.session_state["biz_model_selector_v1"] = "B2C / DTC"


def _on_tile_click(m_key: str):
    if st.session_state.get("selected_bento_v5") == m_key:
        st.session_state["selected_bento_v5"] = None
        st.session_state["scroll_to_detail_nonce"] = 0
    else:
        st.session_state["selected_bento_v5"] = m_key
        st.session_state["scroll_to_detail_nonce"] = time.time_ns()


def _on_collapse_click():
    st.session_state["selected_bento_v5"] = None
    st.session_state["scroll_to_detail_nonce"] = 0


# Step 1 Input Row: Brand Input + Optional Country / Geo Filter + Detect Model
c_in, c_geo, c_detect = st.columns([2.35, 1.3, 1.35], vertical_alignment="center")
with c_in:
    target_company = st.text_input(
        "Target Company",
        placeholder="Brand name (e.g., Enphase Energy, Chargebee, Zepto)",
        label_visibility="collapsed",
    )
with c_geo:
    target_country = st.text_input(
        "Target Country",
        placeholder="Country/Geo (e.g., United States, India)",
        label_visibility="collapsed",
    )
with c_detect:
    if st.button("Detect Business Model", use_container_width=True):
        if not GEMINI_KEY and not CLAUDE_KEY:
            st.error("Backend API key is not configured in Streamlit Secrets.")
        elif not target_company.strip():
            st.warning("Enter a company name first.")
        else:
            with st.spinner("Inspecting website & detecting business model..."):
                step1_res = run_step1_detection(target_company.strip(), target_country.strip())
            st.session_state["pending_model_step"] = step1_res
            detected_choice = step1_res.get("detected_model", "B2C / DTC")
            if detected_choice in BUSINESS_MODELS:
                st.session_state["biz_model_selector_v1"] = detected_choice
            st.rerun()

# Step 2 Confirmation / Override Bar (appears once Step 1 detects the model)
pending_step = st.session_state.get("pending_model_step")
if isinstance(pending_step, dict) and pending_step.get("company"):
    st.markdown(f"""
    <div class="model-detect-banner">
        <strong>Step 2 — Confirm or Override Business Model for {_sanitize_display_text(pending_step['company'])}</strong>
        <span style="color:#6E6E73;"> ({pending_step.get('official_url', '')})</span><br/>
        <span style="color:#424245;">Auto-detected: <strong>{pending_step.get('detected_model', 'B2C / DTC')}</strong> — {_sanitize_display_text(pending_step.get('reason', ''))}</span>
    </div>
    """, unsafe_allow_html=True)

    m_sel_col, m_run_col = st.columns([3.3, 1.5], vertical_alignment="center")
    with m_sel_col:
        chosen_model = st.radio(
            "Select Business Model",
            options=BUSINESS_MODELS,
            key="biz_model_selector_v1",
            horizontal=True,
            label_visibility="collapsed",
        )
    with m_run_col:
        if st.button("Run Full Audit", key="run_full_audit_step2", use_container_width=True):
            st.session_state["last_audit_v5"] = run_live_audit(
                company=pending_step["company"],
                country=pending_step.get("country", ""),
                biz_model=chosen_model,
                pre_resolved_url=pending_step.get("official_url"),
            )
            st.session_state["selected_bento_v5"] = None
            st.session_state["scroll_to_detail_nonce"] = 0
            st.session_state["delivered_email_v1"] = None
            st.rerun()

# Sample Presets Row (Apple secondary outline pill buttons with explicit business models)
st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
p_lbl, p_b1, p_b2, p_b3 = st.columns([2.05, 0.98, 0.98, 0.99], vertical_alignment="center")
with p_lbl:
    st.markdown(
        '<div class="preset-strip-label">Samples — Supertails (B2C/DTC) • Enphase US (Hybrid) • Chargebee (B2B SaaS):</div>',
        unsafe_allow_html=True,
    )
with p_b1:
    st.markdown('<span class="sample-btn-hook" style="display:none;"></span>', unsafe_allow_html=True)
    if st.button("Supertails • B2C", key="preset_supertails", use_container_width=True):
        st.session_state["last_audit_v5"] = build_sample_showcase("supertails")
        st.session_state["pending_model_step"] = None
        st.session_state["selected_bento_v5"] = None
        st.session_state["scroll_to_detail_nonce"] = 0
        st.session_state["delivered_email_v1"] = None
        st.rerun()
with p_b2:
    st.markdown('<span class="sample-btn-hook" style="display:none;"></span>', unsafe_allow_html=True)
    if st.button("Enphase US • Hybrid", key="preset_enphase_us", use_container_width=True):
        st.session_state["last_audit_v5"] = build_sample_showcase("enphase")
        st.session_state["pending_model_step"] = None
        st.session_state["selected_bento_v5"] = None
        st.session_state["scroll_to_detail_nonce"] = 0
        st.session_state["delivered_email_v1"] = None
        st.rerun()
with p_b3:
    st.markdown('<span class="sample-btn-hook" style="display:none;"></span>', unsafe_allow_html=True)
    if st.button("Chargebee • SaaS", key="preset_chargebee_saas", use_container_width=True):
        st.session_state["last_audit_v5"] = build_sample_showcase("chargebee")
        st.session_state["pending_model_step"] = None
        st.session_state["selected_bento_v5"] = None
        st.session_state["scroll_to_detail_nonce"] = 0
        st.session_state["delivered_email_v1"] = None
        st.rerun()

# -----------------------------------------------------------------------------
# COMPANY HEADER & EMAIL PDF DELIVERY + INSTANT DOWNLOAD UNLOCK
# -----------------------------------------------------------------------------
audit = st.session_state.get("last_audit_v5") or build_sample_showcase("supertails")
company = audit.get("company", "Supertails")
country_val = audit.get("country", "")
biz_model_val = audit.get("biz_model", "B2C / DTC")
official_url = audit.get("official_url", "")
hooks = audit.get("hooks") or {}
file_geo_slug = f"_{_slug(country_val)}" if country_val else ""
pdf_filename = f"{_slug(company)}{file_geo_slug}_{_model_slug(biz_model_val)}_executive_brief.pdf"
current_report_key = f"{_scope_prefix(company, country_val, biz_model_val)}__{audit.get('is_showcase', False)}"

st.markdown("---")
h_left, h_right = st.columns([2.7, 2.1], vertical_alignment="top")
with h_left:
    logo_img_html = ""
    bl = audit.get("brand_logo") or {}
    if bl.get("ok") and bl.get("bytes"):
        b64 = base64.b64encode(bl["bytes"]).decode("utf-8")
        logo_img_html = f'<img src="data:image/png;base64,{b64}" style="height:28px;width:auto;margin-right:10px;vertical-align:middle;" />'
    geo_badge = f"  •  Geo: {country_val}" if country_val else "  •  Geo: Global"
    mode_badge = "Sample Preset" if audit.get("is_showcase") else "Live Audit"
    st.markdown(f"<h2>{logo_img_html}{_sanitize_display_text(company)}</h2>", unsafe_allow_html=True)
    st.caption(f"{official_url}  •  {biz_model_val}  •  {mode_badge}{geo_badge}")

with h_right:
    delivered_info = st.session_state.get("delivered_email_v1")
    already_sent_for_this_report = (
        isinstance(delivered_info, dict)
        and delivered_info.get("report_key") == current_report_key
        and bool(delivered_info.get("email"))
    )

    if already_sent_for_this_report:
        st.success(f"Sent to {delivered_info['email']}")
        st.caption("Don't see it? Check Spam or Promotions and mark Not spam.")
        st.download_button(
            label="Download PDF",
            data=get_cached_pdf_bytes(audit),
            file_name=pdf_filename,
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        with st.form(key="email_pdf_form", clear_on_submit=False):
            recipient_email = st.text_input(
                "Email PDF Report",
                placeholder="Enter email to receive PDF",
                label_visibility="collapsed",
            )
            send_clicked = st.form_submit_button("Email PDF", use_container_width=True)

            if send_clicked:
                cleaned_email = (recipient_email or "").strip()
                if not _is_valid_email(cleaned_email):
                    st.warning("Please enter a valid email address.")
                else:
                    pdf_bytes = get_cached_pdf_bytes(audit)
                    sent_ok, send_msg = _send_pdf_via_gmail_smtp(
                        recipient_email=cleaned_email,
                        company=company,
                        country=country_val,
                        pdf_bytes=pdf_bytes,
                        filename=pdf_filename,
                    )
                    if not sent_ok:
                        st.error(f"Could not send email: {send_msg}")
                    else:
                        logged_ok, log_msg = _log_lead_to_sheet(cleaned_email, company, country_val, biz_model_val)
                        if not logged_ok:
                            st.warning(f"PDF sent to {cleaned_email}, but sheet logging had a note: {log_msg}")
                        st.session_state["delivered_email_v1"] = {
                            "report_key": current_report_key,
                            "email": cleaned_email,
                        }
                        st.rerun()

# -----------------------------------------------------------------------------
# 5 PURELY CLICKABLE UNIFORM BENTO TILES (COLOR-CODED SCORE TIERS)
# -----------------------------------------------------------------------------
selected_bento = st.session_state.get("selected_bento_v5")


def render_uniform_bento_row(keys: list[str]):
    cols = st.columns(len(keys))
    for i, m_key in enumerate(keys):
        with cols[i]:
            h_pair = hooks.get(m_key, ("65", "Click tile to view module diagnostics."))
            sc_val = str(h_pair[0]) if len(h_pair) > 0 else "65"
            one_line = _sanitize_display_text(str(h_pair[1])) if len(h_pair) > 1 else ""
            is_sel = (selected_bento == m_key)
            card_cls = "bento-card bento-card-selected" if is_sel else "bento-card"
            tier_cls = _score_tier_css(sc_val)
            st.markdown(f"""
            <div class="{card_cls}">
                <div class="bento-header">
                    <span class="bento-pillar">{MODULE_LABELS[m_key]}</span>
                    <span class="bento-score {tier_cls}">{sc_val}/100</span>
                </div>
                <div class="bento-oneliner">{one_line}</div>
            </div>
            """, unsafe_allow_html=True)
            st.button(
                MODULE_LABELS[m_key],
                key=f"bento_tile_trigger_{m_key}",
                on_click=_on_tile_click,
                args=(m_key,),
            )


render_uniform_bento_row(["seo", "paid", "pricing"])
st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
render_uniform_bento_row(["creative", "social"])

# -----------------------------------------------------------------------------
# DETAIL SECTION (WITH AUTO-SCROLL & FAST COLLAPSE DETAILS ACTION)
# -----------------------------------------------------------------------------
key_lookup = {
    "seo": "e1",
    "paid": "e_paid",
    "pricing": "e2",
    "creative": "e3",
    "social": "e4",
}

if selected_bento in key_lookup:
    st.markdown('<div id="detail-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown("---")

    scroll_nonce = st.session_state.get("scroll_to_detail_nonce", 0)
    if scroll_nonce:
        components.html(f"""
        <script>
        (function() {{
            const _n = {int(scroll_nonce)};
            const doc = window.parent && window.parent.document ? window.parent.document : document;
            const target = doc.getElementById("detail-section-anchor");
            if (target) {{
                target.scrollIntoView({{ behavior: "smooth", block: "start" }});
            }}
        }})();
        </script>
        """, height=0)
        st.session_state["scroll_to_detail_nonce"] = 0

    item = audit.get(key_lookup[selected_bento])
    sel_score = hooks.get(selected_bento, ("65", ""))[0]

    d_left, d_right = st.columns([3.6, 1.2], vertical_alignment="center")
    with d_left:
        st.markdown(f"### {MODULE_FULL_TITLES[selected_bento]} ({sel_score}/100)")
    with d_right:
        st.markdown('<span class="collapse-btn-hook" style="display:none;"></span>', unsafe_allow_html=True)
        st.button("Collapse Details", key="collapse_detail_btn", on_click=_on_collapse_click, use_container_width=True)

    if not item or not item.get("ok"):
        st.error(item.get("error", "Module unavailable.") if item else "Module unavailable.")
    else:
        st.caption(f"{item.get('engine', '')}  •  {biz_model_val}  •  {item.get('age', '')}")

        if selected_bento == "creative" and audit.get("brand_intel"):
            st.markdown("### Brand Design Language & Creative Baseline")
            st.markdown(_sanitize_display_text(audit["brand_intel"]))
            q = quote_plus(company)
            reg = resolve_region_code(country_val)
            meta_country_param = f"&country={reg}" if reg != "ALL" else ""
            google_region_param = f"®ion={reg}" if reg != "ALL" else ""
            st.markdown(
                f"[Meta Ad Library ↗](https://www.facebook.com/ads/library/?active_status=active&ad_type=all{meta_country_param}&q={q}&search_type=keyword_unordered)  •  "
                f"[Google Ads Transparency ↗](https://adstransparency.google.com/?domain={q}{google_region_param})"
            )
            st.markdown("### Next-Gen Ad Copy & Hooks")

        clean_content = _sanitize_display_text(item["content"])
        parts = clean_content.split("---DEEP_DIVE---")
        st.markdown(parts[0].strip())
        if len(parts) > 1 and parts[1].strip():
            with st.expander(MODULE_DEEP_TITLES[selected_bento], expanded=False):
                st.markdown(parts[1].strip())

        if selected_bento == "creative" and GENERATE_IMAGES_DEFAULT:
            imgs = [
                ("Paid Social Ad (1:1)", audit.get("img_meta")),
                ("Display Banner (16:9)", audit.get("img_banner")),
                ("4-Second Video Hook Keyframe (16:9)", audit.get("img_hook_frame")),
            ]
            ready_imgs = [(lbl, im) for lbl, im in imgs if im and im.get("ok") and im.get("bytes")]
            if ready_imgs:
                st.markdown("---")
                st.markdown("### Generated Visual Creatives")
                for lbl, im in ready_imgs:
                    st.markdown(f"**{lbl}**")
                    st.image(im["bytes"], use_container_width=True)

        st.markdown(f'<div class="gov-note">{MODULE_GOV[selected_bento]}</div>', unsafe_allow_html=True)
