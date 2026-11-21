import streamlit as st
from google import genai
from google.genai import types
import anthropic
from PIL import Image
from urllib.parse import quote_plus, urljoin
from fpdf import FPDF
import urllib.request
import base64
import io
import os
import json
import time
import re
import tempfile
from datetime import datetime

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


def _get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            val = st.secrets[key]
            if val is not None:
                return str(val).strip()
    except Exception:
        pass
    return os.getenv(key, default).strip()


GEMINI_KEY = _get_secret("GEMINI_API_KEY")
CLAUDE_KEY = _get_secret("ANTHROPIC_API_KEY")
BACKEND_FORCE_REFRESH = _get_secret("FORCE_REFRESH", "false").lower() in ("1", "true", "yes")
GENERATE_IMAGES_DEFAULT = _get_secret("GENERATE_IMAGES", "true").lower() in ("1", "true", "yes")

# -----------------------------------------------------------------------------
# UNIFIED TYPOGRAPHY, APPLE PILL BUTTONS & UNIFORM BENTO CSS
# -----------------------------------------------------------------------------
st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="collapsedControl"] {
    display: none !important;
}

:root {
    --font-ui: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", Arial, sans-serif;
    --fs-hero: 2.65rem;
    --fs-h2: 1.45rem;
    --fs-h3: 1.15rem;
    --fs-body: 0.95rem;
    --apple-blue: #0071E3;
    --apple-blue-hover: #0077ED;
}

html, body, [class*="css"], .stApp, .stMarkdown, p, li, label, input, div, span, table, th, td {
    font-family: var(--font-ui) !important;
    font-size: var(--fs-body);
    color: #1D1D1F;
}

.stApp {
    background-color: #FBFBFD !important;
}

.block-container {
    max-width: 1080px !important;
    padding-top: 2.2rem !important;
    padding-bottom: 4rem !important;
}

h1.suite-title, .suite-title {
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

.suite-eyebrow {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    color: var(--apple-blue) !important;
    margin-bottom: 0.35rem !important;
}

.suite-subtitle {
    font-size: 1.05rem !important;
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

.bento-card {
    background-color: #FFFFFF;
    border: 1.5px solid #E5E5EA;
    border-radius: 16px;
    padding: 1rem 1.05rem;
    height: 148px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    margin-bottom: 0.45rem;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.bento-card-selected {
    background-color: #F4F9FF;
    border: 1.8px solid var(--apple-blue);
    box-shadow: 0 6px 16px rgba(0, 113, 227, 0.10);
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

.bento-oneliner {
    font-size: var(--fs-body) !important;
    color: #424245 !important;
    line-height: 1.38 !important;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

div[data-testid="stTextInput"] input {
    background-color: #FFFFFF !important;
    border: 1px solid #D2D2D7 !important;
    border-radius: 10px !important;
    padding: 0.65rem 0.95rem !important;
    font-size: var(--fs-body) !important;
    color: #1D1D1F !important;
}

/* Primary solid Apple pill buttons (Run Live Audit + Bento Inspect/Close) */
div[data-testid="stButton"] > button,
div[data-testid="stButton"] > button p,
div[data-testid="stButton"] > button span {
    font-family: var(--font-ui) !important;
    font-weight: 500 !important;
    font-size: var(--fs-body) !important;
    color: #FFFFFF !important;
}

div[data-testid="stButton"] > button {
    border-radius: 999px !important;
    padding: 0.45rem 1.2rem !important;
    background-color: var(--apple-blue) !important;
    border: 1.5px solid var(--apple-blue) !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
}

div[data-testid="stButton"] > button:hover {
    background-color: var(--apple-blue-hover) !important;
    border-color: var(--apple-blue-hover) !important;
    color: #FFFFFF !important;
}

/* Apple secondary pill outline style for Download PDF and Sample Preset buttons */
div[data-testid="stDownloadButton"] > button,
div[data-testid="stDownloadButton"] > button p,
div[data-testid="stDownloadButton"] > button span,
div:has(> div > .sample-btn-hook) + div[data-testid="stButton"] > button,
div:has(> div > .sample-btn-hook) + div[data-testid="stButton"] > button p,
div:has(> div > .sample-btn-hook) + div[data-testid="stButton"] > button span,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button p,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button span {
    font-family: var(--font-ui) !important;
    font-weight: 500 !important;
    font-size: var(--fs-body) !important;
    color: var(--apple-blue) !important;
}

div[data-testid="stDownloadButton"] > button,
div:has(> div > .sample-btn-hook) + div[data-testid="stButton"] > button,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button {
    background-color: transparent !important;
    border: 1.5px solid var(--apple-blue) !important;
    border-radius: 999px !important;
    padding: 0.45rem 1.2rem !important;
    transition: background-color 0.15s ease, color 0.15s ease !important;
}

div[data-testid="stDownloadButton"] > button:hover,
div:has(> div > .sample-btn-hook) + div[data-testid="stButton"] > button:hover,
div[data-testid="stElementContainer"]:has(.sample-btn-hook) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button:hover {
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

details[data-testid="stExpander"] summary,
details[data-testid="stExpander"] summary p,
details[data-testid="stExpander"] summary span {
    font-size: var(--fs-body) !important;
    font-weight: 600 !important;
    color: #1D1D1F !important;
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
    "paid": "Paid Acquisition, Shopping & Funnel CRO",
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
    "paid": "Benchmarks reflect observable storefront/ad signals and unit-economics heuristics; validate against live ad-account telemetry.",
    "pricing": "Pricing signals reflect storefront and search observations; model contribution margin against internal COGS and freight rates.",
    "creative": "Ad copy follows platform character caps; visual concepts are prototypes for creative direction and testing.",
    "social": "Sentiment signals and creator suggestions are grounded via search; verify current metrics and ticket taxonomy before outreach.",
}


def _sample_item(content: str, engine: str = "Curated Snapshot"):
    return {"ok": True, "content": content, "engine": engine, "from_cache": True, "age": "curated", "error": None}


def build_sample_showcase(brand_key: str) -> dict:
    if brand_key == "enphase":
        return {
            "company": "Enphase Energy",
            "official_url": "https://enphase.com",
            "is_showcase": True,
            "hooks": {
                "seo": ("67", "Add concise homeowner payback & outage Q&As to win AI answer blocks."),
                "paid": ("63", "Separate homeowner vs. installer funnels and simplify mobile quote steps."),
                "pricing": ("64", "Bundle solar, battery & smart load tiers to lift storage attach and margin."),
                "creative": ("71", "Lead with grid-outage resilience and home energy control over raw specs."),
                "social": ("68", "Tighten installer callback SLAs and milestone updates to protect trust."),
            },
            "brand_logo": {"ok": False, "bytes": None, "source": None, "from_cache": False},
            "brand_intel": (
                "- **Visual Design Language:** Crisp white surfaces, electric blue and emerald accents, clean technical cards, and bright home photography.\n"
                "- **Meta & Social Ad Patterns:** Homeowner energy independence stories, outage protection hooks, and installer co-marketing.\n"
                "- **Google Search & Shopping Messaging:** Microinverter reliability, battery storage readiness, and certified installer discovery.\n"
                "- **Core Audience & Trust Triggers:** Homeowners and certified solar installers anchored by reliability and app monitoring.\n\n"
                "| Channel / Format | Current Baseline Pattern | Creative Fatigue / Gap | Next-Gen Hook Angle |\n"
                "| --- | --- | --- | --- |\n"
                "| Paid Social & Video | Hardware & solar overview ads | Spec-heavy copy under-indexes on outage peace of mind | 4s blackout-to-backup homeowner hook |\n"
                "| Search & Demand Gen | Broad solar & microinverter terms | Blended homeowner vs. installer intent | Segmented savings & certified installer proof |\n"
                "| Web & Lead Funnels | Multi-step sizing & quote handoff | Drop-off prior to local quote request | Quick bill-offset & battery-readiness check |"
            ),
            "e1": _sample_item(
                "| Search Pillar | Score /100 | Observable Diagnostic Signal | Primary Gap |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Technical & Programmatic SEO | 72 | Strong product/solution depth and regional pages | Faceted comparison indexation & page speed hygiene |\n"
                "| 2. AEO | 66 | Solid technical definitions; room for concise answer blocks | Direct Q&A blocks for net metering & battery sizing |\n"
                "| 3. GEO | 64 | High brand awareness; mixed share in homeowner TCO prompts | Clear lifecycle & storage TCO citation assets |\n"
                "| 4. Entity & Local Schema | 69 | Clear Organization & Product graph; regional variance | Consistent local/service schema & regional proof |\n"
                "| 5. Off-Site Consensus & Digital PR | 65 | Active homeowner forums and press coverage | Structured review & installer proof aggregation |\n\n"
                "- Build comparison hubs for microinverter vs. string inverter reliability and payback.\n"
                "- Add concise FAQ blocks on battery backup sizing and utility tariff changes.\n"
                "- Strengthen regional homeowner proof and installer directory pages.\n"
                "- Publish clear guides on whole-home energy management and EV charging.\n"
                "---DEEP_DIVE---\n"
                "| High-Intent Buyer Prompt | Current AI Winner | Enphase Energy Vulnerability | Asset Needed to Win |\n"
                "| --- | --- | --- | --- |\n"
                "| Best home solar microinverter & battery setup | Solar review aggregators | Technical specs outweigh plain-English outcomes | Side-by-side reliability & backup guide |\n"
                "| How much does solar + battery backup save | Utility & solar calculators | Regional tariff rules vary across markets | Payback & tariff-impact explainer |\n"
                "| Reliable solar installer near me | Directories & local listings | Lead handoff friction between brand & partner | Verified installer checklist & proof hub |\n"
                "| Microinverter vs string inverter maintenance | Owner forums | Scattered anecdotal comparisons | Transparent lifecycle & warranty table |\n\n"
                "### Execution Plan\n"
                "- **[AEO] Problem -> Fix:** Technical copy buries direct answers -> Add concise answer-first blocks on sizing and FAQ pages.\n"
                "- **[GEO] Problem -> Fix:** Forums shape TCO answers -> Publish clear reliability and lifecycle TCO comparisons.\n"
                "- **[Schema] Problem -> Fix:** Uneven markup across regional templates -> Standardize Product, FAQPage, and Organization schema.\n"
                "- **[SEO] Problem -> Fix:** Thin regional pages compete on broad terms -> Add localized case studies and incentive context.\n"
                "- **[Off-Site] Problem -> Fix:** Positive app stories stay scattered -> Syndicate verified homeowner stories and proof."
            ),
            "e_paid": _sample_item(
                "| Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal | Primary Leakage |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Non-Brand Search & PMax Efficiency | 65 | Strong demand capture alongside broad hardware queries | Broad non-brand clicks before readiness check |\n"
                "| 2. Paid Social Acquisition & Creative Fatigue | 61 | Clear visual assets; repeated hardware framing | Prospecting over-indexes on specs vs. outage/bill hooks |\n"
                "| 3. Landing Page & Product-to-Cart CRO | 62 | Multi-step path to qualified lead/quote | Friction before homeowners see tailored system fit |\n"
                "| 4. Checkout, Booking & Post-Click Friction | 64 | Partner routing in place; follow-up speed varies | Delayed installer contact erodes lead conversion |\n\n"
                "- Separate homeowner lead-gen from installer-focused campaigns.\n"
                "- Lead social hooks with outage protection and monthly bill control.\n"
                "- Use 3 quick qualification inputs before quote capture.\n"
                "- Track qualified-lead-to-proposal rate alongside form fills.\n"
                "---DEEP_DIVE---\n"
                "### Paid & Funnel Fixes\n"
                "- **[Search/PMax] Problem -> Fix:** Blended brand and non-brand signals blur efficiency -> Separate brand defense from storage/solar capture.\n"
                "- **[Paid Social] Problem -> Fix:** Hardware creatives fatigue homeowners -> Test outage-resilience and bill-predictability hooks.\n"
                "- **[Landing Page] Problem -> Fix:** Long forms hurt mobile completion -> Show quick system fit estimates before contact capture.\n"
                "- **[Post-Click] Problem -> Fix:** Slow partner handoffs lose high-intent leads -> Enforce instant confirmation and SLA-tracked routing.\n\n"
                "### Experiment Backlog\n"
                "| Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |\n"
                "| --- | --- | --- | --- |\n"
                "| 3-step solar + battery estimator on mobile LPs | Qualified Lead CVR | Cost per Qualified Lead | +15-22% mobile form completion |\n"
                "| Outage/backup hook vs. hardware hook on Meta/YouTube | Thumbstop & CTR | Lead Quality Score | +18-25% engaged click rate |\n"
                "| Instant next-step timeline after quote submission | Proposal Booking Rate | Installer SLA Breach Rate | +10-16% speed-to-contact lift |\n"
                "| Dedicated storage/backup search ad groups | Storage Lead Share | Blended Non-Brand CPA | +12-18% higher-AOV inquiry mix |"
            ),
            "e2": _sample_item(
                "**Current Pricing Strategy:** Enphase pairs premium IQ microinverter and battery hardware pricing with multi-tier installer commercial programs, volume incentives, and ongoing monitoring/energy-management value.\n\n"
                "| Pricing & Economics Pillar | Score /100 | Observable Pricing Signal | Margin / LTV Leakage |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Core SKU & Marketplace Price Positioning | 68 | Premium hardware anchored by reliability & warranty | Price pressure from lower-cost string/hybrid options |\n"
                "| 2. Shipping, Fee & Basket Threshold Architecture | 62 | Commercial/installer logistics and regional fulfillment | Freight/handling drag on smaller or split orders |\n"
                "| 3. Subscription & Repeat-Cohort Monetization | 63 | Ongoing monitoring and energy-management value | Under-monetized post-install upgrade touchpoints |\n"
                "| 4. Private-Label & High-Margin Service Mix | 64 | Integrated microinverter, battery & smart energy stack | Attach-rate gap between solar core and storage add-ons |\n\n"
                "- Bundle microinverters, battery storage, and smart controls into clear tiers.\n"
                "- Weight installer volume rebates toward multi-product attach.\n"
                "- Standardize transparent commercial/freight terms across order tiers.\n"
                "- Create clear post-install paths for battery and EV expansion.\n"
                "---DEEP_DIVE---\n"
                "### Tier Optimization & Margin Plan\n"
                "- **[Package Tiers] Problem -> Fix:** A la carte quotes obscure total value -> Offer Good/Better/Best solar + storage + control tiers.\n"
                "- **[Partner Tiers] Problem -> Fix:** Flat volume discounts miss attach incentives -> Tie higher rebates to battery and smart-panel attach.\n"
                "- **[Freight/Fees] Problem -> Fix:** Split order sizes add logistics overhead -> Incentivize consolidated batch ordering thresholds.\n"
                "- **[Expansion LTV] Problem -> Fix:** Post-install engagement slows after setup -> Surface timely storage/EV expansion offers via milestones.\n\n"
                "### Unit Economics & Pricing Impact Matrix\n"
                "| Pricing Lever | Target Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| Solar + Battery Tiered Bundles | New residential buyers | Clear package tiers with backup options | +200-280 bps blended GM | Keep entry solar option for budget buyers |\n"
                "| Attach-Weighted Partner Tiers | Certified installers | Higher rebates on bundled storage/EMS | +12-18% storage attach rate | Protect installer margin on competitive bids |\n"
                "| Consolidated Batch Ordering | Regional partners/orders | Threshold-based fulfillment terms | -100-140 bps freight drag | Avoid order barriers on small pilots |\n"
                "| Post-Install Expansion Offers | Existing app users | Milestone-triggered storage/EV upgrades | +15-22% expansion LTV | Keep prompts helpful, never intrusive |"
            ),
            "e3": _sample_item(
                "1. **Google Search RSA Pack**\n"
                "- Headline 1: Smart Solar & Battery Systems\n"
                "- Headline 2: Reliable Power When Grid Drops\n"
                "- Headline 3: Connect With Certified Pros\n"
                "- Description 1: Protect your home with reliable solar and battery storage. Get a tailored plan.\n"
                "- Description 2: Monitor energy in real time and cut grid reliance. Request a home assessment.\n\n"
                "2. **Meta Feed Ad**\n"
                "- Primary Text: Keep lights, Wi-Fi, and essentials running smoothly with smart solar + battery storage.\n"
                "- Headline: Smart Solar + Backup Made Simple\n"
                "- CTA: Learn More\n\n"
                "3. **4-Second Video Hook**\n"
                "- Visual Scene: Home lights stay on while street goes dark; homeowner checks phone app.\n"
                "- Voiceover/Text Overlay: Outage outside. Power inside. (6 words)\n"
                "---DEEP_DIVE---\n"
                "### Creative Rationale\n"
                "- **[Meta/Video] Problem -> Fix:** Spec-heavy visuals feel distant to homeowners -> Lead with blackout protection and app clarity in 4 seconds.\n"
                "- **[Search RSA] Problem -> Fix:** Broad headlines dilute intent -> Pair clear backup/savings outcomes with assessment CTAs.\n"
                "- **[Funnel Match] Problem -> Fix:** Ad-to-page messaging gap -> Carry backup and savings framing directly onto the landing hero.\n\n"
                "### Creative A/B Testing Matrix\n"
                "| Ad Variant | Hook / Angle | Target Persona | Primary KPI |\n"
                "| --- | --- | --- | --- |\n"
                "| Variant A (Outage Hook) | Seamless backup during grid dips | Outage-prone homeowners | Qualified Lead CVR |\n"
                "| Variant B (Bill Control) | Predictable energy & self-use | High-bill / EV homeowners | Cost per Qualified Lead |\n"
                "| Variant C (App Telemetry) | Real-time visibility & control | Tech-forward homeowners | Thumbstop & LP CTR |\n"
                "| Variant D (Installer Trust) | Certified local execution & warranty | First-time solar buyers | Proposal Completion Rate |"
            ),
            "e4": _sample_item(
                "**Current Brand Sentiment Archetype:** Enphase earns strong engineering trust and app loyalty among homeowners, while reputation risks center on installer execution speed and support follow-through.\n\n"
                "| Reputation & Listening Pillar | Score /100 | Observable Social / Review Signal | Primary Trust Risk |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Fulfillment & Post-Purchase Sentiment | 66 | Setup timelines depend on local installers | Partner delays reflecting on brand |\n"
                "| 2. Clinical & Product Trust Authority | 74 | Strong reliability and monitoring UX feedback | Isolated RMA/firmware threads |\n"
                "| 3. Review Ecosystem Parity | 65 | High product affinity vs. mixed local reviews | Regional sentiment uneven across channels |\n"
                "| 4. Community Advocacy & Earned Momentum | 69 | Active owner discussions sharing performance | Unanswered forum threads lingering |\n\n"
                "| Polarity | Platform & Context | Representative Customer Feedback | Core Theme |\n"
                "| --- | --- | --- | --- |\n"
                "| Positive | Solar Owner Forums | Per-panel monitoring makes spotting any issue quick and reliable. | App & Telemetry Value |\n"
                "| Positive | Homeowner Reviews | System runs steadily with clear daily generation visibility. | Hardware Reliability |\n"
                "| Positive | Community Threads | Battery backup kept essentials running through an outage. | Backup Peace of Mind |\n"
                "| Negative | Installer / Review Threads | Waited too long for local installer callback after inquiry. | Installer Speed-to-Lead |\n"
                "| Negative | Support / Forum Threads | Needed multiple follow-ups to close commissioning check. | Support Resolution SLA |\n"
                "| Negative | Regional Discussions | Net-metering rules felt unclear during initial pitch. | Expectation Clarity |\n\n"
                "---DEEP_DIVE---\n"
                "### Rapid Triage Plan\n"
                "- **[Installer SLA] Problem -> Fix:** Slow partner callbacks hurt perception -> Tighten routing SLAs and escalate stalled leads quickly.\n"
                "- **[Forum Triage] Problem -> Fix:** Open technical threads shape research -> Assign dedicated technical specialists with clear escalations.\n"
                "- **[Expectations] Problem -> Fix:** Permitting/utility steps surprise buyers -> Share clear milestone timelines upfront.\n"
                "- **[Advocacy] Problem -> Fix:** Satisfied owners post less often -> Prompt completed installs to share verified stories.\n\n"
                "### Social Listening & Escalation SLA Matrix\n"
                "| Listening Cluster & Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |\n"
                "| --- | --- | --- | --- |\n"
                "| Outage / Fault Mentions | System fault or backup claims | High (<2h triage) | Technical Support + Field Ops check |\n"
                "| Installer Delay Complaints | Slow install or callback threads | Medium (<24h response) | Partner Ops + CX escalates |\n"
                "| App & Monitoring Questions | Setup, login, or telemetry queries | Low-Med (<12h response) | Digital Care shares guided fix |\n"
                "| Creator & Press Mentions | Reviews, comparisons, or policy posts | Medium (<24h response) | Brand/Comms logs & responds |\n\n"
                "### Top 10 Influencers & YouTube Channels for Brand Collaboration\n"
                "| Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| 1 | Undecided with Matt Ferrell | YouTube | Clean energy & home tech | Deep dive on microinverters, storage & resilience |\n"
                "| 2 | Home Solar & DIY Channels | YouTube | Solar homeowners & builders | Real-world performance & monitoring walkthrough |\n"
                "| 3 | Engineering & Grid Creators | YouTube | Grid & energy transition viewers | Explaining distributed energy & backup design |\n"
                "| 4 | Smart Home & EV Creators | YouTube & Instagram | EV + home energy owners | Whole-home solar + EV charging daily routine |\n"
                "| 5 | Personal Finance & Home Creators | YouTube & Instagram | ROI-focused homeowners | Utility bill & payback math breakdown |\n"
                "| 6 | Sustainable Living Creators | YouTube | Eco-minded home upgraders | Home efficiency & backup readiness tour |\n"
                "| 7 | Real Estate & Reno Creators | Instagram & YouTube | Home renovators/builders | Planning solar-ready roofs & smart panels |\n"
                "| 8 | Energy Policy Commentators | YouTube & LinkedIn | Tariff & policy watchers | How tariff shifts affect solar + storage |\n"
                "| 9 | Consumer Tech Reviewers | YouTube | Smart-device & app reviewers | Hands-on review of monitoring UX & alerts |\n"
                "| 10 | Local Homeowner Advocates | Instagram & YouTube | Regional community builders | Authentic post-install neighborhood walkthrough |"
            ),
        }

    return {
        "company": "Supertails",
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
            "- **Meta & Social Ad Patterns:** Dynamic SKU carousels, creator reels, situational hooks, and express delivery or offer badges.\n"
            "- **Google Search & Shopping Messaging:** Pet store headlines, vet care access, fast delivery cues, and direct shop CTAs.\n"
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
            "| 1. Non-Brand Search & PMax Efficiency | 60 | PMax and Search capture brand & category demand | Brand overlap & low-margin staple bidding |\n"
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
            "1. **Google Search RSA Pack**\n"
            "- Headline 1: Vet-Curated Pet Care & Food\n"
            "- Headline 2: Fast Delivery & Vet Support\n"
            "- Headline 3: Trusted By Indian Pet Parents\n"
            "- Description 1: Shop authentic pet food, treats, and vet-backed essentials with fast delivery.\n"
            "- Description 2: Get expert vet guidance and easy repeat orders for pets every day.\n\n"
            "2. **Meta Feed Ad**\n"
            "- Primary Text: Upgrade daily pet routines with vet-curated nutrition and care bundles.\n"
            "- Headline: Vet-Curated Care Bundles\n"
            "- CTA: Shop Now\n\n"
            "3. **4-Second Video Hook**\n"
            "- Visual Scene: Pet parent checks ingredient label at home; cut to vet-approved bundle.\n"
            "- Voiceover/Text Overlay: Know what goes in their bowl. (6 words)\n"
            "---DEEP_DIVE---\n"
            "### Creative Rationale\n"
            "- **[Meta/Video] Problem -> Fix:** Generic discount banners blend into feeds -> Lead with ingredient trust and life-stage fit in 4 seconds.\n"
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
# CACHE HELPERS (48-HOUR TTL)
# -----------------------------------------------------------------------------
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_") or "default"


def _meta_path(company: str, element_key: str) -> str:
    return os.path.join(CACHE_DIR, f"{_slug(company)}__{_slug(element_key)}.json")


def _asset_path(company: str, element_key: str, ext: str) -> str:
    return os.path.join(CACHE_DIR, f"{_slug(company)}__{_slug(element_key)}.{ext}")


def load_cached_element(company: str, element_key: str, asset_ext: str | None = None):
    if BACKEND_FORCE_REFRESH:
        return None
    meta_file = _meta_path(company, element_key)
    if not os.path.exists(meta_file):
        return None
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        saved_at = float(meta.get("saved_at", 0))
        if (time.time() - saved_at) > TTL_SECONDS:
            return None
        if asset_ext:
            asset_file = _asset_path(company, element_key, asset_ext)
            if not os.path.exists(asset_file):
                return None
            with open(asset_file, "rb") as af:
                meta["bytes"] = af.read()
        return meta
    except Exception:
        return None


def save_cached_element(company: str, element_key: str, payload: dict, raw_bytes: bytes | None = None, asset_ext: str | None = None):
    meta_file = _meta_path(company, element_key)
    record = dict(payload)
    record["saved_at"] = time.time()
    if asset_ext and raw_bytes is not None:
        asset_file = _asset_path(company, element_key, asset_ext)
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
# MODEL CALLERS & LOGO EXTRACTION
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
            mode_tag = "Search + URL Context" if (use_search and use_url_context) else ("Search" if use_search else "Direct")
            return res.text, f"Gemini ({model_id} • {mode_tag})"
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
                        return res.text, f"Gemini ({model_id} • Search)"
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
    text = "\n".join(text_parts).strip()
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


def get_or_resolve_official_url(company: str) -> str:
    cached = load_cached_element(company, "official_url_v1")
    if cached and cached.get("url"):
        return cached["url"]
    default_url = f"https://{_slug(company)}.com"
    if not GEMINI_KEY:
        return default_url
    try:
        domain_raw, _ = call_gemini(
            f"Return ONLY the canonical official homepage URL (e.g., https://supertails.com) for {company}. No markdown, no extra words.",
            use_search=True,
        )
        match = re.search(r"https?://[^\s\"'<>]+", domain_raw.strip())
        resolved = match.group(0).rstrip(".,)/") if match else default_url
        save_cached_element(company, "official_url_v1", {"url": resolved})
        return resolved
    except Exception:
        return default_url


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


def get_or_fetch_brand_logo(company: str, base_url: str):
    cached = load_cached_element(company, "brand_logo_v1", asset_ext="png")
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
                save_cached_element(company, "brand_logo_v1", {"source": source_label}, raw_bytes=png_bytes, asset_ext="png")
                return {"ok": True, "bytes": png_bytes, "source": source_label, "from_cache": False}
    except Exception:
        pass

    return {"ok": False, "bytes": None, "source": None, "from_cache": False}


def get_or_generate_text_element(company: str, element_key: str, prompt: str, preferred: str = "gemini", use_search: bool = False, use_url_context: bool = False):
    cached = load_cached_element(company, element_key)
    if cached:
        return {
            "ok": True,
            "content": cached["content"],
            "engine": cached["engine"],
            "from_cache": True,
            "age": format_age(cached["saved_at"]),
            "error": None,
        }
    try:
        content, engine = route_agent(prompt, preferred=preferred, use_search=use_search, use_url_context=use_url_context)
        save_cached_element(company, element_key, {"content": content, "engine": engine})
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


def get_or_generate_brand_intel(company: str, official_url: str):
    cached = load_cached_element(company, "brand_ad_intel_v3")
    if cached:
        return cached["content"]
    prompt = f"""
    Act as VP of Brand & Performance Creative auditing {company} (official website: {official_url}) across its live storefront, Meta Ad Library, Google Ads Transparency Center, and Google Search.
    STRICT FORMATTING (DO NOT USE ANY EMOJIS):
    - Output EXACTLY these 4 concise bullet points (max 18 words per bullet):
      - **Visual Design Language:** [Exact primary/secondary brand colors, card/UI styling, typography mood, and photography style]
      - **Meta & Social Ad Patterns:** [Dominant visual hooks, offer badges, and creative formats seen in their Meta ads]
      - **Google Search & Shopping Messaging:** [Primary headline angles, value props, and CTA patterns in search/shopping ads]
      - **Core Audience & Trust Triggers:** [Target persona setting and key credibility signals/social proof used]
    - Immediately follow with a compact 3-row **Creative Baseline & Opportunity Matrix** table:
      | Channel / Format | Current Baseline Pattern | Creative Fatigue / Gap | Next-Gen Hook Angle |
    """
    res = get_or_generate_text_element(company, "brand_ad_intel_v3", prompt, preferred="gemini", use_search=True, use_url_context=True)
    return res["content"] if res["ok"] else f"Authentic brand design language for {company}."


def get_or_generate_image_element(company: str, element_key: str, prompt: str, aspect_ratio: str = "1:1", logo_bytes: bytes | None = None):
    cached = load_cached_element(company, element_key, asset_ext="png")
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
                save_cached_element(company, element_key, {}, raw_bytes=raw_png, asset_ext="png")
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
# EXECUTIVE PDF BUILDER
# -----------------------------------------------------------------------------
def _clean_pdf_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "-", "\u2026": "...",
        "\u2192": "->", "\u20b9": "INR ", "\u00a0": " ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = text.replace("---DEEP_DIVE---", "\nDeep-Dive Notes:\n")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    return text.encode("latin-1", "ignore").decode("latin-1").strip()


class ExecutivePDF(FPDF):
    def __init__(self, company_name: str):
        super().__init__()
        self.company_name = _clean_pdf_text(company_name)

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(110, 110, 115)
        self.cell(0, 8, f"EXECUTIVE INTELLIGENCE BRIEF  |  {self.company_name.upper()}", align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(142, 142, 147)
        self.cell(0, 8, f"Soumya Ranjan Nayak   |   Page {self.page_no()}", align="C")

    def section_title(self, title: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(29, 29, 31)
        self.cell(0, 8, _clean_pdf_text(title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(210, 210, 215)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def render_markdown_block(self, md_text: str):
        lines = _clean_pdf_text(md_text).splitlines()
        table_rows = []

        def flush_table():
            nonlocal table_rows
            if not table_rows:
                return
            col_count = max(len(r) for r in table_rows)
            usable_w = self.w - self.l_margin - self.r_margin
            col_w = usable_w / max(1, col_count)
            for idx, row in enumerate(table_rows):
                if idx == 0:
                    self.set_fill_color(245, 245, 247)
                    self.set_font("Helvetica", "B", 8.5)
                    self.set_text_color(29, 29, 31)
                else:
                    self.set_fill_color(255, 255, 255)
                    self.set_font("Helvetica", "", 8.5)
                    self.set_text_color(51, 51, 54)
                padded = row + [""] * (col_count - len(row))
                max_lines = max(1, *(int(len(c) / max(10, (col_w / 2.0))) + 1 for c in padded))
                row_h = max_lines * 4.8
                if self.get_y() + row_h > self.h - 20:
                    self.add_page()
                y_start = self.get_y()
                x_start = self.l_margin
                for c_i, cell_txt in enumerate(padded):
                    self.set_xy(x_start + c_i * col_w, y_start)
                    self.multi_cell(col_w, 4.6, cell_txt, border=1, fill=(idx == 0))
                self.set_y(y_start + row_h)
            self.ln(3)
            table_rows = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                flush_table()
                self.ln(2)
                continue
            if line.startswith("|") and line.endswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if all(set(c) <= set("-: ") for c in cells):
                    continue
                table_rows.append(cells)
                continue
            flush_table()
            if line.startswith("#"):
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(0, 113, 227)
                self.multi_cell(0, 6, line.lstrip("#").strip())
                self.ln(1)
            elif line.startswith("- ") or line.startswith("* "):
                self.set_font("Helvetica", "", 9.5)
                self.set_text_color(29, 29, 31)
                self.multi_cell(0, 5.5, f"  -  {line[2:].strip()}")
                self.ln(1)
            else:
                self.set_font("Helvetica", "", 9.5)
                self.set_text_color(44, 44, 46)
                self.multi_cell(0, 5.5, line)
                self.ln(1)

        flush_table()


def build_executive_pdf(audit_data: dict) -> bytes:
    company = audit_data.get("company", "Brand")
    pdf = ExecutivePDF(company)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(29, 29, 31)
    pdf.cell(0, 10, _clean_pdf_text(company), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(110, 110, 115)
    pdf.cell(0, 7, f"Executive Intelligence Brief  |  {datetime.now().strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    sections = [
        ("1. SEO, AEO & GEO", audit_data.get("e1")),
        ("2. Paid Search & CRO", audit_data.get("e_paid")),
        ("3. Pricing & Unit Economics", audit_data.get("e2")),
        ("4. Ad Creative Studio", audit_data.get("e3")),
        ("5. Social & Brand Triage", audit_data.get("e4")),
    ]
    for title, item in sections:
        if item and item.get("ok"):
            pdf.section_title(title)
            pdf.render_markdown_block(item["content"])

    images_to_embed = [
        ("Meta Feed Ad (1:1)", audit_data.get("img_meta"), 95),
        ("Display Banner (16:9)", audit_data.get("img_banner"), 150),
        ("4-Second Video Hook Keyframe (16:9)", audit_data.get("img_hook_frame"), 150),
    ]
    valid_imgs = [(lbl, it, w) for lbl, it, w in images_to_embed if it and it.get("ok") and it.get("bytes")]
    if valid_imgs:
        pdf.add_page()
        pdf.section_title("6. Generated Ad Creatives")
        temp_files = []
        try:
            for lbl, it, w in valid_imgs:
                if pdf.get_y() > 205:
                    pdf.add_page()
                pdf.set_font("Helvetica", "B", 10.5)
                pdf.cell(0, 7, _clean_pdf_text(lbl), new_x="LMARGIN", new_y="NEXT")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                tmp.write(it["bytes"])
                tmp.close()
                temp_files.append(tmp.name)
                pdf.image(tmp.name, w=w)
                pdf.ln(6)
        finally:
            for p in temp_files:
                if os.path.exists(p):
                    os.remove(p)

    raw_out = pdf.output()
    return bytes(raw_out) if isinstance(raw_out, (bytes, bytearray)) else raw_out.encode("latin-1")


# -----------------------------------------------------------------------------
# LIVE AUDIT ORCHESTRATOR
# -----------------------------------------------------------------------------
def run_live_audit(company: str):
    with st.spinner(f"Running 5-module intelligence audit for {company}..."):
        official_url = get_or_resolve_official_url(company)
        brand_logo = get_or_fetch_brand_logo(company, official_url)
        brand_dna_text = get_or_generate_brand_intel(company, official_url)

        p1 = f"""
        Act as Principal SEO, AEO, and GEO Architect auditing {company} ({official_url}).
        STRICT FORMATTING:
        - Start with:
          | Search Pillar | Score /100 | Observable Diagnostic Signal | Primary Gap |
          Rows: 1. Technical & Programmatic SEO, 2. AEO, 3. GEO, 4. Entity & Local Schema, 5. Off-Site Consensus & Digital PR. Use integer-only scores.
        - Follow with 4 short bullets (max 16 words each).
        - End with '---DEEP_DIVE---' followed by an AI Prompt Visibility Matrix table and 5 bullets formatted as `- **[Area] Problem -> Fix:** [Diagnosis] -> [Action]`.
        """
        p_paid = f"""
        Act as VP of Performance Marketing & CRO auditing {company} ({official_url}).
        STRICT FORMATTING:
        - Start with:
          | Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal | Primary Leakage |
          Rows: 1. Non-Brand Search & PMax Efficiency, 2. Paid Social Acquisition & Creative Fatigue, 3. Landing Page & Product-to-Cart CRO, 4. Checkout, Booking & Post-Click Friction. Use integer-only scores.
        - Follow with 4 short bullets (max 16 words each).
        - End with '---DEEP_DIVE---' followed by 4 bullets (`- **[Area] Problem -> Fix:** ...`) and a 4-row experiment backlog table (`| Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |`).
        """
        p2 = f"""
        Act as VP of Pricing & Commercial Strategy auditing {company} ({official_url}).
        STRICT FORMATTING:
        - Line 1: **Current Pricing Strategy:** [1 concise sentence].
        - Follow with:
          | Pricing & Economics Pillar | Score /100 | Observable Pricing Signal | Margin / LTV Leakage |
          Rows: 1. Core SKU & Marketplace Price Positioning, 2. Shipping, Fee & Basket Threshold Architecture, 3. Subscription & Repeat-Cohort Monetization, 4. Private-Label & High-Margin Service Mix. Use integer-only scores.
        - Follow with 4 short bullets (max 16 words each).
        - End with '---DEEP_DIVE---' followed by 4 bullets (`- **[Lever] Problem -> Fix:** ...`) and a 4-row impact table (`| Pricing Lever | Target Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |`).
        """
        p3 = f"""
        Act as VP of Performance Creative for {company}. Brand baseline: {brand_dna_text}
        STRICT FORMATTING (NO EMOJIS):
        - Output 1. Google Search RSA Pack (3 headlines <=30 chars + 2 descriptions <=90 chars), 2. Meta Feed Ad (Primary Text <=110 chars, Headline <=35 chars, CTA), 3. 4-Second Video Hook (Scene + <=12-word hook).
        - End with '---DEEP_DIVE---' followed by 3 bullets (`- **[Channel] Problem -> Fix:** ...`) and a 4-row A/B testing table (`| Ad Variant | Hook / Angle | Target Persona | Primary KPI |`).
        """
        p4 = f"""
        Act as VP of Brand Reputation, Social Listening & Creator Partnerships auditing {company} ({official_url}).
        STRICT FORMATTING (NO EMOJIS):
        - Line 1: **Current Brand Sentiment Archetype:** [1 concise sentence].
        - Follow with:
          | Reputation & Listening Pillar | Score /100 | Observable Social / Review Signal | Primary Trust Risk |
          Rows: 1. Fulfillment & Post-Purchase Sentiment, 2. Clinical & Product Trust Authority, 3. Review Ecosystem Parity, 4. Community Advocacy & Earned Momentum. Use integer-only scores.
        - Follow with a 6-row table (3 Positive, 3 Negative): `| Polarity | Platform & Context | Representative Customer Feedback | Core Theme |`.
        - End with '---DEEP_DIVE---' followed by 4 bullets (`- **[Area] Problem -> Fix:** ...`), a 4-row SLA table (`| Listening Cluster & Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |`), and a 10-row creator table (`| Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |`).
        """

        e1 = get_or_generate_text_element(company, "agent1_seo_aeo_geo_v3", p1, preferred="gemini", use_search=True, use_url_context=True)
        e_paid = get_or_generate_text_element(company, "agent2_paid_cro_v2", p_paid, preferred="gemini", use_search=True, use_url_context=True)
        e2 = get_or_generate_text_element(company, "agent2_pricing_v2", p2, preferred="gemini", use_search=True, use_url_context=True)
        e3 = get_or_generate_text_element(company, "agent3_creative_v2", p3, preferred="gemini")
        e4 = get_or_generate_text_element(company, "agent4_social_v2", p4, preferred="gemini", use_search=True, use_url_context=True)

        img_meta = img_banner = img_hook_frame = None
        if GENERATE_IMAGES_DEFAULT:
            logo_bytes = brand_logo["bytes"] if brand_logo["ok"] else None
            img_meta = get_or_generate_image_element(company, "meta_ad_1x1_v3", f"Clean 1:1 Meta feed ad for {company}. {brand_dna_text} Max 2 clean UI elements.", "1:1", logo_bytes)
            img_banner = get_or_generate_image_element(company, "banner_ad_16x9_v3", f"Clean 16:9 display banner for {company}. {brand_dna_text} Max 2 clean UI elements.", "16:9", logo_bytes)
            img_hook_frame = get_or_generate_image_element(company, "video_hook_frame_16x9_v3", f"Clean 16:9 4-second video hook opening frame for {company}. {brand_dna_text} Max 2 clean UI overlays.", "16:9", logo_bytes)

        s_seo = extract_composite_score(e1.get("content", ""), 68)
        s_paid = extract_composite_score(e_paid.get("content", ""), 61)
        s_pri = extract_composite_score(e2.get("content", ""), 62)
        s_soc = extract_composite_score(e4.get("content", ""), 65)

        return {
            "company": company,
            "official_url": official_url,
            "is_showcase": False,
            "hooks": {
                "seo": (str(s_seo), f"Fix crawl/schema gaps and target high-intent search & AI answers for {company}."),
                "paid": (str(s_paid), f"Isolate brand vs. non-brand spend and cut funnel drop-offs for {company}."),
                "pricing": (str(s_pri), f"Gate promos, tune shipping thresholds, and lift high-margin mix for {company}."),
                "creative": ("72", f"Test high-contrast hooks and compliant ad copy with logo guardrails for {company}."),
                "social": (str(s_soc), f"Resolve top fulfillment/service friction and activate category creators for {company}."),
            },
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
# HEADER, LIVE AUDIT ROW & SEPARATE SAMPLE PRESET ROW
# -----------------------------------------------------------------------------
st.markdown("""
<div class="suite-eyebrow">Soumya Ranjan Nayak • AI Growth & Pricing Architecture</div>
<h1 class="suite-title">Executive Intelligence Suite.</h1>
<p class="suite-subtitle">
    Structured diagnostics across Organic Search (SEO/AEO/GEO), Paid Acquisition & CRO, Pricing Economics, Brand Creative, and Reputation Triage.
</p>
""", unsafe_allow_html=True)

if "selected_bento_v5" not in st.session_state:
    st.session_state["selected_bento_v5"] = None

if "last_audit_v5" not in st.session_state:
    st.session_state["last_audit_v5"] = build_sample_showcase("supertails")

# Line 1: Live Audit Brand Entry
c_in, c_run = st.columns([3.6, 1.2], vertical_alignment="center")
with c_in:
    target_company = st.text_input(
        "Target Company",
        placeholder="Enter any brand name to run a live 5-module audit (e.g., Ather Energy, Zepto, Zerodha)",
        label_visibility="collapsed",
    )
with c_run:
    if st.button("Run Live Audit", use_container_width=True):
        if not GEMINI_KEY and not CLAUDE_KEY:
            st.error("Backend API key is not configured in Streamlit Secrets.")
        elif not target_company.strip():
            st.warning("Enter a company name first.")
        else:
            st.session_state["last_audit_v5"] = run_live_audit(target_company.strip())
            st.session_state["selected_bento_v5"] = None
            st.rerun()

# Line 2: Sample Presets (Apple secondary outline pill buttons)
st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
p_lbl, p_b1, p_b2, _ = st.columns([2.2, 1.25, 1.25, 1.1], vertical_alignment="center")
with p_lbl:
    st.markdown('<div class="preset-strip-label">Sample Presets (pre-loaded reference audits for instant exploration):</div>', unsafe_allow_html=True)
with p_b1:
    st.markdown('<span class="sample-btn-hook" style="display:none;"></span>', unsafe_allow_html=True)
    if st.button("Sample: Supertails", key="preset_supertails", use_container_width=True):
        st.session_state["last_audit_v5"] = build_sample_showcase("supertails")
        st.session_state["selected_bento_v5"] = None
        st.rerun()
with p_b2:
    st.markdown('<span class="sample-btn-hook" style="display:none;"></span>', unsafe_allow_html=True)
    if st.button("Sample: Enphase", key="preset_enphase", use_container_width=True):
        st.session_state["last_audit_v5"] = build_sample_showcase("enphase")
        st.session_state["selected_bento_v5"] = None
        st.rerun()

# -----------------------------------------------------------------------------
# COMPANY HEADER & 5 UNIFORM BENTO TILES
# -----------------------------------------------------------------------------
audit = st.session_state.get("last_audit_v5") or build_sample_showcase("supertails")
company = audit.get("company", "Supertails")
official_url = audit.get("official_url", "")
hooks = audit.get("hooks") or {}

st.markdown("---")
h_left, h_right = st.columns([3.4, 1.2], vertical_alignment="center")
with h_left:
    logo_img_html = ""
    bl = audit.get("brand_logo") or {}
    if bl.get("ok") and bl.get("bytes"):
        b64 = base64.b64encode(bl["bytes"]).decode("utf-8")
        logo_img_html = f'<img src="data:image/png;base64,{b64}" style="height:28px;width:auto;margin-right:10px;vertical-align:middle;" />'
    st.markdown(f"<h2>{logo_img_html}{company}</h2>", unsafe_allow_html=True)
    st.caption(f"{official_url}  •  {'Sample Preset' if audit.get('is_showcase') else 'Live Audit'}")
with h_right:
    st.download_button(
        label="Download PDF",
        data=build_executive_pdf(audit),
        file_name=f"{_slug(company)}_executive_brief.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

selected_bento = st.session_state.get("selected_bento_v5")


def render_uniform_bento_row(keys: list[str]):
    cols = st.columns(len(keys))
    for i, m_key in enumerate(keys):
        with cols[i]:
            h_pair = hooks.get(m_key, ("65", "Click Inspect to view module diagnostics."))
            sc_val = str(h_pair[0]) if len(h_pair) > 0 else "65"
            one_line = str(h_pair[1]) if len(h_pair) > 1 else ""
            is_sel = (selected_bento == m_key)
            card_cls = "bento-card bento-card-selected" if is_sel else "bento-card"
            st.markdown(f"""
            <div class="{card_cls}">
                <div class="bento-header">
                    <span class="bento-pillar">{MODULE_LABELS[m_key]}</span>
                    <span class="bento-score">{sc_val}/100</span>
                </div>
                <div class="bento-oneliner">{one_line}</div>
            </div>
            """, unsafe_allow_html=True)
            btn_txt = "Close" if is_sel else "Inspect"
            if st.button(btn_txt, key=f"bento_btn_{m_key}", use_container_width=True):
                st.session_state["selected_bento_v5"] = None if is_sel else m_key
                st.rerun()


render_uniform_bento_row(["seo", "paid", "pricing"])
st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
render_uniform_bento_row(["creative", "social"])

# -----------------------------------------------------------------------------
# DETAIL SECTION (COLLAPSED BY DEFAULT ON LOAD; OPENS WHEN INSPECTED)
# -----------------------------------------------------------------------------
key_lookup = {
    "seo": "e1",
    "paid": "e_paid",
    "pricing": "e2",
    "creative": "e3",
    "social": "e4",
}

if selected_bento in key_lookup:
    st.markdown("---")
    item = audit.get(key_lookup[selected_bento])
    sel_score = hooks.get(selected_bento, ("65", ""))[0]
    with st.expander(f"{MODULE_FULL_TITLES[selected_bento]}  ({sel_score}/100)", expanded=True):
        if not item or not item.get("ok"):
            st.error(item.get("error", "Module unavailable.") if item else "Module unavailable.")
        else:
            st.caption(f"{item.get('engine', '')}  •  {item.get('age', '')}")

            if selected_bento == "creative" and audit.get("brand_intel"):
                st.markdown("### Brand Design Language & Creative Baseline")
                st.markdown(audit["brand_intel"])
                q = quote_plus(company)
                st.markdown(
                    f"[Meta Ad Library ↗](https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IN&q={q}&search_type=keyword_unordered)  •  "
                    f"[Google Ads Transparency ↗](https://adstransparency.google.com/?region=IN&domain={q})"
                )
                st.markdown("### Next-Gen Ad Copy & Hooks")

            parts = item["content"].split("---DEEP_DIVE---")
            st.markdown(parts[0].strip())
            if len(parts) > 1 and parts[1].strip():
                with st.expander(MODULE_DEEP_TITLES[selected_bento], expanded=False):
                    st.markdown(parts[1].strip())

            if selected_bento == "creative" and GENERATE_IMAGES_DEFAULT:
                imgs = [
                    ("Meta Feed Ad (1:1)", audit.get("img_meta")),
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
