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

# Page Config
st.set_page_config(
    page_title="Executive Intelligence Suite — Growth & Pricing Architecture",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

CACHE_DIR = ".audit_cache"
TTL_SECONDS = 2 * 24 * 3600  # 2 days (48 hours)
MAX_LOGO_BYTES = 5 * 1024 * 1024  # 5 MB realistic cap for brand logos
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

# -----------------------------------------------------------------------------
# APPLE LIGHT MODE DESIGN SYSTEM (CSS)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
html, body, [class*="css"], .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Arial, sans-serif !important;
    background-color: #FBFBFD !important;
    color: #1D1D1F !important;
    -webkit-font-smoothing: antialiased;
}

.block-container {
    max-width: 1140px !important;
    padding-top: 2.2rem !important;
    padding-bottom: 4rem !important;
}

section[data-testid="stSidebar"] {
    background-color: #F5F5F7 !important;
    border-right: 1px solid #E5E5EA !important;
}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #1D1D1F !important;
    letter-spacing: -0.01em !important;
}

.apple-eyebrow {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #0071E3;
    margin-bottom: 0.3rem;
}
.apple-hero-title {
    font-size: 2.5rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
    color: #1D1D1F;
    margin: 0 0 0.55rem 0;
}
.apple-hero-subtitle {
    font-size: 1.08rem;
    font-weight: 400;
    line-height: 1.45;
    color: #6E6E73;
    max-width: 800px;
    margin: 0 0 1.5rem 0;
}

div[data-testid="stTextInput"] input {
    background-color: #FFFFFF !important;
    border: 1px solid #D2D2D7 !important;
    border-radius: 12px !important;
    padding: 0.72rem 1rem !important;
    font-size: 0.98rem !important;
    color: #1D1D1F !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #0071E3 !important;
    box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15) !important;
}

div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {
    border-radius: 980px !important;
    font-weight: 500 !important;
    font-size: 0.92rem !important;
    padding: 0.52rem 1.3rem !important;
    letter-spacing: -0.01em !important;
    transition: all 0.18s ease !important;
    border: none !important;
}
div[data-testid="stButton"] > button {
    background-color: #0071E3 !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(0, 113, 227, 0.2) !important;
}
div[data-testid="stButton"] > button:hover {
    background-color: #0077ED !important;
    transform: translateY(-1px);
}
div[data-testid="stDownloadButton"] > button {
    background-color: #FFFFFF !important;
    color: #0071E3 !important;
    border: 1px solid #D2D2D7 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    background-color: #F5F5F7 !important;
    border-color: #0071E3 !important;
}

.command-banner {
    background: linear-gradient(135deg, #FFFFFF 0%, #F5F7FA 100%);
    border: 1px solid #E5E5EA;
    border-radius: 20px;
    padding: 1.3rem 1.6rem;
    margin: 1rem 0 1.2rem 0;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.03);
}
.kpi-mini-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E5EA;
    border-radius: 14px;
    padding: 0.85rem 1rem;
    height: 100%;
}
.kpi-mini-label {
    font-size: 0.73rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #6E6E73;
    margin-bottom: 0.25rem;
}
.kpi-mini-value {
    font-size: 0.92rem;
    font-weight: 600;
    color: #1D1D1F;
    line-height: 1.35;
}

.bento-tile {
    background-color: #FFFFFF;
    border: 1.5px solid #E5E5EA;
    border-radius: 18px;
    padding: 1.05rem 1.15rem 0.75rem 1.15rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
    transition: all 0.18s ease;
    margin-bottom: 0.45rem;
}
.bento-tile-active {
    background-color: #F4F9FF;
    border: 1.8px solid #0071E3;
    box-shadow: 0 6px 18px rgba(0, 113, 227, 0.12);
}
.bento-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.45rem;
}
.bento-title {
    font-size: 0.96rem;
    font-weight: 700;
    color: #1D1D1F;
    letter-spacing: -0.015em;
}
.score-pill-warn {
    background-color: #FFF2F0;
    color: #CF1322;
    border: 1px solid #FFCCC7;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.15rem 0.55rem;
    border-radius: 980px;
    white-space: nowrap;
}
.score-pill-mid {
    background-color: #FFFBE6;
    color: #AD6800;
    border: 1px solid #FFE58F;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.15rem 0.55rem;
    border-radius: 980px;
    white-space: nowrap;
}
.score-pill-good {
    background-color: #F6FFED;
    color: #237804;
    border: 1px solid #B7EB8F;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.15rem 0.55rem;
    border-radius: 980px;
    white-space: nowrap;
}
.bento-hook {
    font-size: 0.84rem;
    line-height: 1.42;
    color: #424245;
    margin-bottom: 0.2rem;
}

.apple-section-header {
    background-color: #FFFFFF;
    border: 1px solid #E5E5EA;
    border-radius: 16px;
    padding: 1.1rem 1.4rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
    margin-bottom: 1rem;
}
.apple-card-header {
    font-size: 1.22rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: #1D1D1F;
    margin-bottom: 0.3rem;
}
.apple-meta-pill {
    display: inline-block;
    background-color: #F5F5F7;
    color: #6E6E73;
    font-size: 0.78rem;
    font-weight: 500;
    padding: 0.22rem 0.75rem;
    border-radius: 980px;
}
.governance-note {
    font-size: 0.8rem;
    color: #86868B;
    margin-top: 1rem;
    padding-top: 0.65rem;
    border-top: 1px solid #E5E5EA;
}

table {
    width: 100% !important;
    border-collapse: collapse !important;
    margin: 0.8rem 0 1.2rem 0 !important;
    font-size: 0.91rem !important;
    background-color: #FFFFFF !important;
}
th {
    background-color: #F5F5F7 !important;
    color: #1D1D1F !important;
    font-weight: 600 !important;
    text-align: left !important;
    padding: 0.65rem 0.85rem !important;
    border-bottom: 1px solid #D2D2D7 !important;
}
td {
    padding: 0.65rem 0.85rem !important;
    border-bottom: 1px solid #E5E5EA !important;
    color: #1D1D1F !important;
}

details[data-testid="stExpander"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E5E5EA !important;
    border-radius: 14px !important;
    margin-top: 0.8rem !important;
}
details[data-testid="stExpander"] summary {
    font-weight: 500 !important;
    color: #0071E3 !important;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PRE-LOADED EXECUTIVE SHOWCASE SNAPSHOTS (INSTANT DEMO FOR VISITORS)
# -----------------------------------------------------------------------------
MODULE_ORDER = ["seo", "paid", "pricing", "creative", "social"]

MODULE_META = {
    "seo": {
        "short_title": "SEO, AEO & GEO",
        "full_title": "Organic Search Intelligence: SEO, AEO & GEO",
        "expander": "View AI Prompt Visibility Matrix & Technical SEO Blueprint",
        "governance": "Governance Note: Diagnostic signals are synthesized via live AI search & URL context grounding; verify named entities and exact review counts prior to board distribution."
    },
    "paid": {
        "short_title": "Paid Search & CRO",
        "full_title": "Paid Acquisition, Shopping & Funnel CRO",
        "expander": "View PMax Architecture, Funnel Fixes & Experiment Backlog",
        "governance": "Governance Note: Benchmarks reflect observable live storefront/ad signals and industry unit-economics heuristics; validate against live ad-account telemetry."
    },
    "pricing": {
        "short_title": "Pricing & Unit Economics",
        "full_title": "Pricing Architecture & Unit Economics",
        "expander": "View Tier Optimization Playbook & Unit-Economics Impact Matrix",
        "governance": "Governance Note: Pricing signals reflect live storefront/search observations; model exact contribution-margin sensitivity against internal SKU COGS and freight tables."
    },
    "creative": {
        "short_title": "Ad Creative Studio",
        "full_title": "Next-Gen Ad Copy & Creative Hooks",
        "expander": "View Creative Rationale & A/B Testing Matrix",
        "governance": "Governance Note: Ad copy follows strict platform character caps; visual concepts are AI-rendered prototypes for creative direction and A/B testing."
    },
    "social": {
        "short_title": "Social & Brand Triage",
        "full_title": "Brand Reputation, Social Listening & Creator Partnerships",
        "expander": "View Rapid Triage Playbook, Escalation SLAs & Top 10 Creator Outreach Roster",
        "governance": "Governance Note: Customer feedback snippets, scores, and creator handles are synthesized via live search & URL context grounding; verify active handle metrics and CS ticket taxonomy before outreach."
    }
}


def _sample_item(content: str, engine: str = "Executive Snapshot"):
    return {"ok": True, "content": content, "engine": engine, "from_cache": True, "age": "curated demo", "error": None}


def build_sample_showcase(brand_key: str) -> dict:
    if brand_key == "enphase":
        return {
            "company": "Enphase Energy",
            "official_url": "https://enphase.com",
            "is_showcase": True,
            "kpis": {
                "margin_lever": "IQ Battery + IQ8 attach & installer tiering (+240 bps)",
                "funnel_leak": "Long homeowner solar payback & installer quote friction",
                "reputation_risk": "Firmware/monitoring tickets & regional installer SLAs"
            },
            "tile_hooks": {
                "seo": ("67", "Strong microinverter authority, but AI answer engines need sharper homeowner payback & grid-outage comparisons."),
                "paid": ("63", "High-intent solar search captures demand; simplifying homeowner savings calculators lifts qualified lead CVR."),
                "pricing": ("64", "Enphase pairs premium IQ microinverters and IQ Batteries with installer volume tiers and storage-attach incentives."),
                "creative": ("71", "Lead with outage resilience, 25-year reliability, and whole-home energy independence over spec-sheet jargon."),
                "social": ("68", "Homeowners praise app telemetry and backup reliability; fast installer escalation closes regional service gaps.")
            },
            "brand_logo": {"ok": False, "bytes": None, "source": None, "from_cache": False},
            "brand_intel": _sample_item(
                "- **Visual Design Language:** Crisp solar-white surfaces, electric blue & emerald accents, clean technical cards, and bright residential photography.\n"
                "- **Meta & Social Ad Patterns:** Homeowner energy independence stories, blackout/outage hooks, and installer co-marketing creatives.\n"
                "- **Google Search & Shopping Messaging:** Microinverter reliability, battery storage readiness, and local installer discovery CTAs.\n"
                "- **Core Audience & Trust Triggers:** Homeowners and certified solar installers anchored by engineering reliability and app monitoring.\n\n"
                "| Channel / Format | Current Baseline Pattern | Creative Fatigue / Gap | Next-Gen Hook Angle |\n"
                "| --- | --- | --- | --- |\n"
                "| Paid Social & Video | Hardware & solar panel overview ads | Spec-heavy framing under-indexes on outage peace-of-mind | 4s blackout-to-backup homeowner hook |\n"
                "| Search & Demand Gen | Broad solar & microinverter queries | Generic homeowner vs. installer intent mix | Segmented savings & certified-installer proof |\n"
                "| Web & Lead Funnels | Multi-step system sizing & installer handoff | Decision drop-off before local quote request | Instant bill-offset & battery-readiness check |",
                "Gemini Search + URL Context"
            ),
            "e1": _sample_item(
                "| Search Pillar | Score /100 | Observable Diagnostic Signal | Primary Gap |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Technical & Programmatic SEO | 72 | Deep product/solution pages and regional localization across key markets | Faceted installer/product comparison indexation & speed hygiene |\n"
                "| 2. AEO | 66 | Strong technical definitions; opportunities to win concise homeowner FAQ snippets | Structured comparison blocks for NEM/net-metering & battery sizing |\n"
                "| 3. GEO | 64 | High brand recognition in solar Q&A; needs clearer positioning on storage & backup | Authoritative citation assets on microinverter vs. string inverter TCO |\n"
                "| 4. Entity & Local Schema | 69 | Strong Organization & Product entity graph; regional installer pages vary | Deeper local/service schema & consistent regional NAP signals |\n"
                "| 5. Off-Site Consensus & Digital PR | 65 | Active homeowner forums and industry press coverage | Structured third-party review & installer proof aggregation |\n\n"
                "- Build comparison hubs answering microinverter vs. string inverter reliability and payback.\n"
                "- Add concise FAQ schema blocks on battery backup sizing and utility tariff shifts.\n"
                "- Strengthen regional homeowner proof and installer directory pages for local search.\n"
                "- Publish benchmark guides on whole-home energy management and EV charging integration.\n"
                "---DEEP_DIVE---\n"
                "| High-Intent Buyer Prompt | Current AI Winner | Enphase Energy Vulnerability | Asset Needed to Win |\n"
                "| --- | --- | --- | --- |\n"
                "| Best home solar microinverter & battery setup | Solar review aggregators | Technical specs outweigh plain-English homeowner outcomes | Side-by-side reliability & backup sizing guide |\n"
                "| How much does solar + battery backup save | Utility & solar calculators | Regional tariff rules differ across states/markets | Interactive payback & tariff-impact explainer |\n"
                "| Reliable solar installer near me | Local directories & Maps | Lead handoff friction between brand & installers | Verified installer checklist & local proof hub |\n"
                "| Microinverter vs string inverter maintenance | Forum & installer threads | Scattered anecdotal comparisons | Transparent lifecycle & warranty comparison table |\n\n"
                "### Technical, Entity & Off-Site Execution Plan\n"
                "- **[AEO] Problem -> Fix:** Complex technical copy buries direct answers -> Add 40-word answer-first blocks on FAQ and sizing pages.\n"
                "- **[GEO] Problem -> Fix:** LLMs cite third-party forums for TCO comparisons -> Publish transparent lifecycle reliability and TCO benchmarks.\n"
                "- **[Schema] Problem -> Fix:** Inconsistent structured data across regional/product templates -> Standardize Product, FAQPage, and Organization JSON-LD.\n"
                "- **[SEO] Problem -> Fix:** Thin regional landing pages compete with generic terms -> Enrich local pages with real regional case studies and incentives.\n"
                "- **[Off-Site] Problem -> Fix:** Positive homeowner app stories stay siloed -> Syndicate verified homeowner case studies and PR proof."
            ),
            "e_paid": _sample_item(
                "| Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal | Primary Leakage |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Non-Brand Search & PMax Efficiency | 65 | High intent on solar/storage terms alongside broad hardware queries | Broad non-brand clicks before homeowner readiness qualification |\n"
                "| 2. Paid Social Acquisition & Creative Fatigue | 61 | Strong visual energy assets; repeated hardware framing in prospecting | Top-of-funnel ads over-index on specs vs. bill/outage triggers |\n"
                "| 3. Landing Page & Product-to-Cart CRO | 62 | Clear product overview; multi-step path to qualified lead/quote | High friction before homeowners see tailored system fit |\n"
                "| 4. Checkout, Booking & Post-Click Friction | 64 | Installer routing exists; speed-to-lead varies by partner | Delayed installer follow-up erodes high-intent lead conversion |\n\n"
                "- Separate homeowner lead-gen campaigns from installer-focused acquisition.\n"
                "- Lead paid social hooks with power-outage protection and monthly bill control.\n"
                "- Shorten initial landing-page qualification to 3 quick inputs before quote capture.\n"
                "- Track qualified-lead-to-proposal conversion rather than raw form fills.\n"
                "---DEEP_DIVE---\n"
                "### Paid Architecture & Funnel Fixes\n"
                "- **[Search/PMax] Problem -> Fix:** Blended brand and non-brand signals mask true acquisition efficiency -> Split brand defense from non-brand storage/solar capture.\n"
                "- **[Paid Social] Problem -> Fix:** Static hardware creatives fatigue among homeowners -> Test outage-resilience and bill-predictability video hooks.\n"
                "- **[Landing Page] Problem -> Fix:** Long forms depress mobile completion rates -> Progressive-disclose system estimates before asking for contact details.\n"
                "- **[Post-Click] Problem -> Fix:** Slow partner handoffs lose hot prospects -> Enforce instant confirmation and SLA-tracked installer routing.\n\n"
                "### CRO & Paid Experiment Backlog\n"
                "| Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |\n"
                "| --- | --- | --- | --- |\n"
                "| Progressive 3-step solar + battery estimator on mobile LPs | Qualified Lead CVR | Cost per Qualified Lead | +15-22% mobile form completion |\n"
                "| Outage & backup hook vs. hardware spec hook on Meta/YouTube | Thumbstop & Qualified CTR | Lead Quality Score | +18-25% engaged click rate |\n"
                "| Instant next-step timeline after quote submission | Proposal Booking Rate | Installer SLA Breach Rate | +10-16% speed-to-contact lift |\n"
                "| Dedicated high-intent storage/backup search ad groups | Storage Lead Share | Blended Non-Brand CPA | +12-18% higher-AOV inquiry mix |"
            ),
            "e2": _sample_item(
                "**Current Pricing Strategy:** Enphase pairs premium IQ microinverter and battery hardware pricing with multi-tier installer commercial programs, volume incentives, and high-margin software/monitoring value.\n\n"
                "| Pricing & Economics Pillar | Score /100 | Observable Pricing Signal | Margin / LTV Leakage |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Core SKU & Marketplace Price Positioning | 68 | Premium hardware positioning anchored by reliability and warranty | Price sensitivity against lower-cost string/hybrid alternatives |\n"
                "| 2. Shipping, Fee & Basket Threshold Architecture | 62 | Commercial/installer logistics and regional fulfillment tiers | Freight/handling friction on smaller or split replenishment orders |\n"
                "| 3. Subscription & Repeat-Cohort Monetization | 63 | Ongoing monitoring and energy-management ecosystem value | Under-monetized post-install upgrade and expansion touchpoints |\n"
                "| 4. Private-Label & High-Margin Service Mix | 64 | Integrated microinverter + battery + smart energy ecosystem | Attach-rate gap between solar core and battery/software expansion |\n\n"
                "- Bundle microinverters, battery storage, and smart load management into clear packages.\n"
                "- Tie installer volume rebates to multi-product system attach rates.\n"
                "- Standardize transparent commercial/freight terms across order tiers.\n"
                "- Create clear post-install expansion paths for battery add-ons and EV readiness.\n"
                "---DEEP_DIVE---\n"
                "### Tier Optimization & Margin Execution Plan\n"
                "- **[Package Tiers] Problem -> Fix:** A la carte hardware quotes obscure total system value -> Offer Good/Better/Best solar + storage + smart-control tiers.\n"
                "- **[Partner Incentives] Problem -> Fix:** Flat volume discounts do not reward ecosystem attach -> Weight rebates toward battery and smart-panel attachment.\n"
                "- **[Freight & Fees] Problem -> Fix:** Fragmented order sizes create logistics overhead -> Incentivize consolidated project/batch ordering thresholds.\n"
                "- **[Expansion LTV] Problem -> Fix:** Post-install engagement plateaus after commissioning -> Trigger timely storage/EV expansion offers via app milestones.\n\n"
                "### Unit Economics & Pricing Impact Matrix\n"
                "| Pricing Lever | Target Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| Solar + Battery Tiered Bundles | New residential buyers | Clear package pricing with backup tiers | +200-280 bps blended margin | Preserve entry solar option for budget buyers |\n"
                "| Attach-Weighted Partner Tiers | Certified installers | Higher rebates on bundled storage/EMS orders | +12-18% storage attach rate | Protect installer net margin on competitive bids |\n"
                "| Consolidated Batch Ordering | Regional partners/orders | Threshold-based logistics & fulfillment terms | -100-140 bps freight drag | Avoid minimum-order barriers for small pilots |\n"
                "| Post-Install Expansion Offers | Existing app users | Usage-triggered storage & load-control upgrades | +15-22% expansion LTV | Keep app experience helpful, never spammy |"
            ),
            "e3": _sample_item(
                "1. **Google Search RSA Pack**\n"
                "- Headline 1: Smart Solar & Battery Systems\n"
                "- Headline 2: Reliable Power When Grid Drops\n"
                "- Headline 3: Connect With Certified Pros\n"
                "- Description 1: Protect your home with reliable solar and battery storage. Get a tailored system plan.\n"
                "- Description 2: Monitor energy in real time and cut grid reliance. Request your free home assessment.\n\n"
                "2. **Meta Feed Ad**\n"
                "- Primary Text: Keep lights, Wi-Fi, and essential appliances running smoothly with smart solar + battery storage.\n"
                "- Headline: Smart Solar + Backup Made Simple\n"
                "- CTA: Learn More\n\n"
                "3. **4-Second Video Hook**\n"
                "- Visual Scene: Home evening lights stay steady while neighboring street goes dark; homeowner checks clean phone app.\n"
                "- Voiceover/Text Overlay: Outage outside. Power inside. (6 words)\n"
                "---DEEP_DIVE---\n"
                "### Creative Rationale & Baseline Evolution\n"
                "- **[Meta/Video] Problem -> Fix:** Technical hardware visuals feel abstract to everyday homeowners -> Lead with relatable home backup and app clarity in 4 seconds.\n"
                "- **[Search RSA] Problem -> Fix:** Overly broad headlines dilute intent -> Pair outcome-led headlines with direct assessment CTAs.\n"
                "- **[Funnel Alignment] Problem -> Fix:** Disconnect between ad promise and quote page -> Carry the exact backup/savings framing onto the landing hero.\n\n"
                "### Creative A/B Testing Matrix\n"
                "| Ad Variant | Hook / Angle | Target Persona | Primary KPI |\n"
                "| --- | --- | --- | --- |\n"
                "| Variant A (Outage Hook) | Seamless backup during grid dips | Outage-prone homeowners | Qualified Lead CVR |\n"
                "| Variant B (Bill Control) | Predictable energy & self-consumption | High-bill / EV homeowners | Cost per Qualified Lead |\n"
                "| Variant C (App Telemetry) | Real-time visibility & control in-app | Tech-forward homeowners | 3s/ThruPlay & LP CTR |\n"
                "| Variant D (Installer Trust) | Certified local execution & warranty | Cautious first-time buyers | Proposal Completion Rate |"
            ),
            "e4": _sample_item(
                "**Current Brand Sentiment Archetype:** Enphase Energy commands strong engineering trust and app loyalty among solar homeowners, while reputation risks center on installer execution quality and support resolution speed.\n\n"
                "| Reputation & Listening Pillar | Score /100 | Observable Social / Review Signal | Primary Trust Risk |\n"
                "| --- | --- | --- | --- |\n"
                "| 1. Fulfillment & Post-Purchase Sentiment | 66 | Commissioning timelines depend heavily on local installers | Third-party installer delays blamed on the brand |\n"
                "| 2. Clinical & Product Trust Authority | 74 | Strong reputation for microinverter reliability and monitoring UX | Hardware/RMA or firmware hiccups creating vocal threads |\n"
                "| 3. Review Ecosystem Parity | 65 | High app/product affinity vs. mixed local installer reviews | Uneven public review sentiment across regions |\n"
                "| 4. Community Advocacy & Earned Momentum | 69 | Active solar owner communities sharing system performance | Unanswered troubleshooting threads lingering in public forums |\n\n"
                "| Polarity | Platform & Context | Representative Customer Feedback | Core Theme |\n"
                "| --- | --- | --- | --- |\n"
                "| Positive | Solar Owner Forums | Per-panel monitoring makes spotting any issue effortless and reliable. | App & Telemetry Value |\n"
                "| Positive | Homeowner Reviews | System has run steadily with clear visibility into daily generation. | Hardware Reliability |\n"
                "| Positive | Community Threads | Having battery backup kept essentials running smoothly during an outage. | Backup Peace of Mind |\n"
                "| Negative | Installer / Review Threads | Waiting weeks for local installer follow-up after initial inquiry. | Installer Speed-to-Lead |\n"
                "| Negative | Support / Forum Threads | Support ticket took multiple back-and-forths to resolve commissioning check. | Support Resolution SLA |\n"
                "| Negative | Regional Discussions | Confusing explanation of net-metering rules during sales pitch. | Expectation Clarity |\n\n"
                "---DEEP_DIVE---\n"
                "### Rapid Triage & Reputation Execution Plan\n"
                "- **[Installer SLA] Problem -> Fix:** Slow partner follow-up hurts brand perception -> Audit lead-routing SLAs and re-route stalled inquiries fast.\n"
                "- **[Forum Triage] Problem -> Fix:** Unresolved technical threads shape buyer research -> Assign dedicated technical community specialists with clear escalation paths.\n"
                "- **[Expectation Setting] Problem -> Fix:** Permitting/utility delays surprise buyers -> Publish clear milestone timelines from design to permission-to-operate.\n"
                "- **[Advocacy Loop] Problem -> Fix:** Happy owners rarely post structured reviews -> Prompt satisfied post-commissioning owners to share verified stories.\n\n"
                "### Social Listening & Escalation SLA Matrix\n"
                "| Listening Cluster & Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |\n"
                "| --- | --- | --- | --- |\n"
                "| Outage / System Fault Mentions | Repeated failure or safety/outage claims | High (<2h triage) | Technical Support + Field Ops root-cause check |\n"
                "| Installer Delay Complaints | Stalled install or slow callback threads | Medium (<24h response) | Partner Ops + CX escalates with partner & customer |\n"
                "| App & Monitoring Questions | Setup, login, or reporting confusion | Low-Med (<12h response) | Digital Care shares guided help flow & resolves |\n"
                "| Creator & Press Mentions | Reviews, comparisons, or policy commentary | Medium (<24h response) | Brand/Comms logs sentiment & offers technical briefing |\n\n"
                "### Top 10 Influencers & YouTube Channels for Brand Collaboration\n"
                "| Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| 1 | Undecided with Matt Ferrell | YouTube | Clean energy & home tech explainers | Deep dive on microinverters, storage & home resilience |\n"
                "| 2 | Nate's Solar / Home Solar Channels | YouTube | DIY & homeowner solar system breakdowns | Real-world performance & monitoring walkthrough |\n"
                "| 3 | Engineering / Grid Tech Creators | YouTube | Grid resilience & energy transition viewers | Explaining distributed energy & backup architecture |\n"
                "| 4 | Smart Home & EV Lifestyle Creators | YouTube & Instagram | Homeowners pairing EVs with home energy | Whole-home solar + EV charging daily routine |\n"
                "| 5 | Personal Finance & Homeownership Creators | YouTube & Instagram | Cost-conscious homeowners evaluating ROI | Breaking down long-term utility bill & payback math |\n"
                "| 6 | Sustainable Living & Off-Grid Creators | YouTube | Eco-minded home upgraders | Practical home efficiency & backup readiness tour |\n"
                "| 7 | Real Estate & Home Reno Creators | Instagram & YouTube | Renovating/building homeowners | Planning solar-ready roofs and smart panels early |\n"
                "| 8 | Regional Climate & Energy Commentators | YouTube & LinkedIn | Policy & utility tariff watchers | Explaining how tariff shifts affect solar + storage value |\n"
                "| 9 | Consumer Tech Reviewers | YouTube | Smart-device & energy-app reviewers | Hands-on review of energy monitoring UX & alerts |\n"
                "| 10 | Local Homeowner Advocates | Instagram & YouTube | Regional community trust builders | Authentic neighborhood walkthrough post-installation |"
            )
        }

    return {
        "company": "Supertails",
        "official_url": "https://supertails.com",
        "is_showcase": True,
        "kpis": {
            "margin_lever": "Gate promos + split MOV + private-label mix (+220-300 bps)",
            "funnel_leak": "Mobile web CVR trails app by ~2.5x + checkout fee/COD friction",
            "reputation_risk": "Fake '1-ring' delivery attempts & slow refund/cancellation UX"
        },
        "tile_hooks": {
            "seo": ("68", "Strong vet & pet-care authority, but category & AI answer visibility leaks to quick-commerce and marketplaces."),
            "paid": ("61", "PMax brand overlap and low-AOV prospecting dilute return; margin-tiered bidding and checkout fixes unlock quick gains."),
            "pricing": ("62", "Aggressive 3P discounting and flat Rs 699 shipping subsidize low-margin kibble; gating promos and subscriptions lifts margin."),
            "creative": ("74", "Pair vet-curated skin/life-stage bundles and 4s visual hooks with verified brand logo guardrails."),
            "social": ("65", "Fear Free vets and 30-min dark-store speed win trust, while 3PL delivery & refund friction drive vocal complaints.")
        },
        "brand_logo": {"ok": False, "bytes": None, "source": None, "from_cache": False},
        "brand_intel": _sample_item(
            "- **Visual Design Language:** Vibrant orange and deep navy accents, rounded cards, friendly sans-serif typography, and candid pet-parent photography.\n"
            "- **Meta & Social Ad Patterns:** Dynamic SKU carousels, creator reels, situational hooks, and express delivery or discount badges.\n"
            "- **Google Search & Shopping Messaging:** Pet store headlines, vet care access, fast delivery cues, and direct shop CTAs.\n"
            "- **Core Audience & Trust Triggers:** Urban Indian pet parents anchored by certified vets, community scale, and verified reviews.\n\n"
            "| Channel / Format | Current Baseline Pattern | Creative Fatigue / Gap | Next-Gen Hook Angle |\n"
            "| --- | --- | --- | --- |\n"
            "| Meta Feed & Carousels | Generic SKU/discount cards | Commodity lookalike fatigue vs. q-commerce | Vet-curated breed & life-stage bundles |\n"
            "| Reels & Short Video | Standard pet/offer clips | Over-used discount framing over clinical trust | 4s split-screen vet check & care hook |\n"
            "| Search & Shopping | Broad pet food & delivery terms | High CPC overlap with marketplaces | Bundle + free vet consult value hooks |",
            "Gemini Search + URL Context"
        ),
        "e1": _sample_item(
            "| Search Pillar | Score /100 | Observable Diagnostic Signal | Primary Gap |\n"
            "| --- | --- | --- | --- |\n"
            "| 1. Technical & Programmatic SEO | 69 | Broad catalog and vet-content footprint on storefront | Faceted filter crawl bloat & out-of-stock SKU indexation |\n"
            "| 2. AEO | 67 | Strong pet health/care topics; structured Q&A opportunities | Concise answer blocks for breed, diet & symptom queries |\n"
            "| 3. GEO | 65 | Recognizable Indian pet-care brand; mixed LLM recommendation share | Comparison & authority assets for AI shopping/vet prompts |\n"
            "| 4. Entity & Local Schema | 70 | Clinic presence and vet care positioning across key cities | Unified Organization, Vet/Clinic, and Product JSON-LD |\n"
            "| 5. Off-Site Consensus & Digital PR | 66 | Active Reddit pet communities and review profiles | Balancing delivery complaints with verified vet/care proof |\n\n"
            "- Prune low-value faceted URLs and handle out-of-stock SKUs cleanly.\n"
            "- Add structured vet-backed Q&A blocks to win AI Overviews and featured snippets.\n"
            "- Build breed- and life-stage nutrition guides that LLMs cite reliably.\n"
            "- Tighten local clinic schema and GBP consistency across active cities.\n"
            "---DEEP_DIVE---\n"
            "| High-Intent Buyer Prompt | Current AI Winner | Supertails Vulnerability | Asset Needed to Win |\n"
            "| --- | --- | --- | --- |\n"
            "| Best vet-recommended dog food in India | Review blogs & Reddit | Generic listicles outrank brand guides | Vet-authored ingredient & life-stage matrix |\n"
            "| Online vet consultation India for pet skin issue | Telehealth & forums | Symptom-to-consult path not always surfaced first | Structured symptom-triage & vet-consult guide |\n"
            "| Fast pet food delivery near me | Quick-commerce apps | Perceived slower on instant micro-baskets | City-level delivery + care bundle landing pages |\n"
            "| Best puppy/kitten starter essentials | Marketplaces & blogs | Fragmented category discovery | Complete life-stage checklist & bundle hub |\n\n"
            "### Technical, Entity & Off-Site Execution Plan\n"
            "- **[SEO] Problem -> Fix:** Parameter/filter combinations dilute crawl budget -> Canonicalize and noindex low-utility sort/filter permutations.\n"
            "- **[AEO] Problem -> Fix:** Long articles delay direct answers -> Add crisp 40-50 word summary answers at top of high-intent guides.\n"
            "- **[GEO] Problem -> Fix:** LLMs rely on Reddit/blogs for product picks -> Publish transparent nutrition comparisons and clinical FAQs.\n"
            "- **[Schema] Problem -> Fix:** Partial markup across product and clinic templates -> Enforce valid Product, Offer, MedicalClinic, and FAQ schema.\n"
            "- **[Off-Site] Problem -> Fix:** Delivery threads skew public sentiment -> Pair responsive CX with verified vet-care and customer stories."
        ),
        "e_paid": _sample_item(
            "| Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal | Primary Leakage |\n"
            "| --- | --- | --- | --- |\n"
            "| 1. Non-Brand Search & PMax Efficiency | 60 | PMax and Search capture both brand and category demand | Brand cannibalization & low-margin staple bidding pressure |\n"
            "| 2. Paid Social Acquisition & Creative Fatigue | 62 | Active Meta prospecting and retention/offer ads | Low-AOV trial orders & overlapping retargeting cohorts |\n"
            "| 3. Landing Page & Product-to-Cart CRO | 59 | Mobile web and app flows serve distinct buyer journeys | Mobile web CVR lag vs. app & missing unit-price cues |\n"
            "| 4. Checkout, Booking & Post-Click Friction | 63 | Express checkout plus platform/COD fee mechanics | Fee/COD friction & delivery SLA uncertainty at checkout |\n\n"
            "- Exclude brand terms from non-brand PMax and tier by margin.\n"
            "- Suppress recent repeat buyers from aggressive acquisition retargeting.\n"
            "- Surface clear price-per-kg/unit cues and guided breed/size selectors.\n"
            "- Simplify checkout fees, COD messaging, and delivery expectations.\n"
            "---DEEP_DIVE---\n"
            "### Paid Architecture & Funnel Fixes\n"
            "- **[PMax] Problem -> Fix:** Unsegmented PMax blends brand and high/low-margin SKUs -> Separate brand exclusions and segment campaigns by margin tier.\n"
            "- **[Paid Social] Problem -> Fix:** Retargeting hits recent buyers and low-margin trials -> Exclude active repeaters and optimize toward higher-LTV baskets.\n"
            "- **[PDP CRO] Problem -> Fix:** Pack-size/unit math slows mobile add-to-cart -> Show per-kg/unit pricing clearly with 1-tap pack/bundle selection.\n"
            "- **[Checkout] Problem -> Fix:** Extra fees and COD drop-offs stall completion -> Test cleaner fee framing, prepaid nudges, and clear ETA windows.\n\n"
            "### CRO & Paid Experiment Backlog\n"
            "| Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |\n"
            "| --- | --- | --- | --- |\n"
            "| Split PMax by margin tier with brand exclusions | Contribution Margin ROAS | New-to-Brand Share | +15-22% margin-adjusted return |\n"
            "| Exclude recent repeaters from Meta retargeting | Prospecting / Blended ROAS | Paid Social CAC | -12-18% wasted retargeting spend |\n"
            "| Add unit-price badges & guided bundle selector on PDP | Mobile Add-to-Cart & CVR | Page Load / LCP | +12-20% mobile conversion lift |\n"
            "| Streamline checkout fee & COD/prepaid prompt | Checkout-to-Paid CVR | Gross Margin & RTO % | +5-9% checkout completion lift |"
        ),
        "e2": _sample_item(
            "**Current Pricing Strategy:** Supertails combines competitive marketplace-aligned pricing on staple pet foods with free-shipping thresholds, checkout/COD fee mechanics, and growing private-label and vet-service monetization.\n\n"
            "| Pricing & Economics Pillar | Score /100 | Observable Pricing Signal | Margin / LTV Leakage |\n"
            "| --- | --- | --- | --- |\n"
            "| 1. Core SKU & Marketplace Price Positioning | 63 | Competitive discounting on third-party staples vs. q-commerce | Margin compression on commodity food SKUs |\n"
            "| 2. Shipping, Fee & Basket Threshold Architecture | 59 | Free-shipping MOV paired with platform/COD surcharges | Heavy/bulky freight subsidy & small-basket fee friction |\n"
            "| 3. Subscription & Repeat-Cohort Monetization | 61 | Repeat replenishment potential across food & consumables | Episodic one-off buying instead of locked-in recurring cadence |\n"
            "| 4. Private-Label & High-Margin Service Mix | 65 | Owned brands and vet consultations carry higher margin potential | Owned-brand & service attach still small share of total mix |\n\n"
            "- Gate steep promo discounts behind private-label or higher-AOV baskets.\n"
            "- Align shipping thresholds with parcel weight and dark-store zones.\n"
            "- Differentiate subscription savings across staples vs. owned brands.\n"
            "- Convert vet consultations smoothly into high-margin care/nutrition carts.\n"
            "---DEEP_DIVE---\n"
            "### Tier Optimization & Margin Execution Plan\n"
            "- **[Promo Gating] Problem -> Fix:** Broad discounts erode margin on commodity staples -> Gate top promo tiers behind owned-brand or higher basket thresholds.\n"
            "- **[Shipping/Fees] Problem -> Fix:** Flat thresholds strain heavy bags and small orders -> Calibrate MOV by weight/zone and keep fee rules transparent.\n"
            "- **[Subscriptions] Problem -> Fix:** Flat auto-ship discounts give away margin on 3P items -> Tier repeat savings higher on owned brands and bundles.\n"
            "- **[Vet-to-Cart] Problem -> Fix:** Vet consults and commerce carts operate too separately -> Streamline post-consult care/nutrition basket recommendations.\n\n"
            "### Unit Economics & Pricing Impact Matrix\n"
            "| Pricing Lever | Target Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| Promo & Basket Gating | Deal-seeking staple buyers | Require owned-brand mix or higher AOV for top promos | +200-300 bps blended GM | Keep welcome offer for first-time trial |\n"
            "| Weight/Zone Shipping MOV | Heavy-bag & small-cart buyers | Dynamic threshold & zone-aware fulfillment rules | -120-160 bps freight drag | Offer multi-pack value to lift AOV cleanly |\n"
            "| Tiered Auto-Ship | Repeat food/treat buyers | Higher recurring perks on owned brands & bundles | +20-30% repeat order LTV | Allow easy pause/skip to prevent churn |\n"
            "| Consult-to-Care Bundle | Vet consultation users | Post-consult tailored care/supplement cart flow | +15-22% consult-to-order rate | Keep clinical advice unbiased and trustworthy |"
        ),
        "e3": _sample_item(
            "1. **Google Search RSA Pack**\n"
            "- Headline 1: Vet-Curated Pet Care & Food\n"
            "- Headline 2: Fast Delivery & Vet Support\n"
            "- Headline 3: Trusted By Indian Pet Parents\n"
            "- Description 1: Shop authentic pet food, treats, and vet-backed essentials with fast doorstep delivery.\n"
            "- Description 2: Get expert vet guidance and easy repeat orders for happy, healthy pets every day.\n\n"
            "2. **Meta Feed Ad**\n"
            "- Primary Text: Upgrade daily pet routines with vet-curated nutrition and care bundles—built for busy pet parents.\n"
            "- Headline: Vet-Curated Care Bundles\n"
            "- CTA: Shop Now\n\n"
            "3. **4-Second Video Hook**\n"
            "- Visual Scene: Pet parent checks ingredient label at home while pet waits eagerly; quick cut to vet-approved bundle.\n"
            "- Voiceover/Text Overlay: Know what goes in their bowl. (6 words)\n"
            "---DEEP_DIVE---\n"
            "### Creative Rationale & Baseline Evolution\n"
            "- **[Meta/Video] Problem -> Fix:** Generic discount banners blend into crowded feeds -> Lead with ingredient trust and life-stage relevance in 4 seconds.\n"
            "- **[Search RSA] Problem -> Fix:** Repetitive promo copy misses high-intent care buyers -> Balance fast delivery with vet authority and trust proof.\n"
            "- **[Visual Guardrail] Problem -> Fix:** AI wordmark/logo drift hurts brand polish -> Lock official brand logo placement and cap overlay badges.\n\n"
            "### Creative A/B Testing Matrix\n"
            "| Ad Variant | Hook / Angle | Target Persona | Primary KPI |\n"
            "| --- | --- | --- | --- |\n"
            "| Variant A (Vet Trust) | Vet-curated nutrition & care | Health-focused pet parents | First-Order Contribution ROAS |\n"
            "| Variant B (Speed/Convenience) | Rapid restock when running low | Busy urban apartment owners | Mobile Add-to-Cart & CVR |\n"
            "| Variant C (Life-Stage Kit) | Puppy/kitten/senior starter bundle | New & transitioning pet parents | Average Order Value (AOV) |\n"
            "| Variant D (UGC Story) | Real pet parent & vet tip reel | Community/social scrollers | Thumbstop Rate & CTR |"
        ),
        "e4": _sample_item(
            "**Current Brand Sentiment Archetype:** Supertails earns strong affection for Fear Free vet care and fast local convenience, while delivery exceptions, cancellation/refund friction, and review gaps drive negative sentiment.\n\n"
            "| Reputation & Listening Pillar | Score /100 | Observable Social / Review Signal | Primary Trust Risk |\n"
            "| --- | --- | --- | --- |\n"
            "| 1. Fulfillment & Post-Purchase Sentiment | 58 | Complaints around delayed shipments, missed delivery attempts & cancellations | Courier/SLA failures eroding repeat trust |\n"
            "| 2. Clinical & Product Trust Authority | 74 | Positive feedback on Fear Free vets and authentic product sourcing | Isolated service/escalation disputes hurting trust |\n"
            "| 3. Review Ecosystem Parity | 62 | Strong site claims vs. mixed public review/forum threads | Rating/sentiment gap across external platforms |\n"
            "| 4. Community Advocacy & Earned Momentum | 66 | Loyal pet-parent community and growth milestones | Unresolved public threads amplifying negative buzz |\n\n"
            "| Polarity | Platform & Context | Representative Customer Feedback | Core Theme |\n"
            "| --- | --- | --- | --- |\n"
            "| Positive | Local Clinic Reviews | Calm, gentle vet team took time explaining care without rushing. | Fear Free Vet Experience |\n"
            "| Positive | Pet Parent Forums | Genuine branded food and quick arrival when local stock is available. | Product & Local Speed |\n"
            "| Positive | Customer Stories | Helpful guidance when choosing diet/care options for a new pet. | Care Guidance Value |\n"
            "| Negative | Community / Forum Threads | Marked attempted delivery without a real call or doorstep visit. | Fake Delivery Attempt |\n"
            "| Negative | Review / App Feedback | Hard to cancel or get timely refund updates once an order stalls. | Cancellation & Refund UX |\n"
            "| Negative | Support Escalations | Automated replies loop before reaching a human who can fix the order. | Support Escalation Gap |\n\n"
            "---DEEP_DIVE---\n"
            "### Rapid Triage & Reputation Execution Plan\n"
            "- **[Logistics Triage] Problem -> Fix:** Fake delivery attempts and delays trigger angry posts -> Audit courier call/GPS logs and trigger fast replacement/SLA fixes.\n"
            "- **[Self-Serve UX] Problem -> Fix:** Missing/unclear cancellation and slow refunds fuel escalations -> Add clear order cancellation/help flows and faster refund SLAs.\n"
            "- **[Human Escalation] Problem -> Fix:** Bot loops frustrate urgent pet-care/order issues -> Route stalled orders and clinical escalations to live agents fast.\n"
            "- **[Trust Amplification] Problem -> Fix:** Negative threads overshadow positive care wins -> Spotlight verified vet care and real customer stories consistently.\n\n"
            "### Social Listening & Escalation SLA Matrix\n"
            "| Listening Cluster & Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |\n"
            "| --- | --- | --- | --- |\n"
            "| Delivery Failure / Fake Attempt | 'Attempted delivery', 'no call', or overdue order | High (<1h triage) | Logistics & CX verify courier status and resolve |\n"
            "| Clinical / Vet Escalation | Care complaint or clinic service dispute | High (<2h triage) | Clinical Quality / Clinic Lead reviews & follows up |\n"
            "| Refund & Cancellation Friction | Refund delay or cancellation complaint | Medium (<12h response) | Billing/CX resolves ticket and updates status clearly |\n"
            "| Creator & Community Buzz | Product reviews, Indie/adoption stories, mentions | Medium (<24h response) | Brand/Community team engages & logs insights |\n\n"
            "### Top 10 Influencers & YouTube Channels for Brand Collaboration\n"
            "| Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 1 | Indian Pet Care & Dog Training YouTubers | YouTube | Indian dog parents seeking diet & training tips | Vet-backed nutrition myth-busting & feeding routine |\n"
            "| 2 | Indie Dog & Rescue Creators | Instagram & YouTube | High-empathy Indian pet & indie adoption audience | Indie/rescue care & nutrition starter kit story |\n"
            "| 3 | Veterinarian & Pet Health Educators | YouTube & Instagram | Credibility-first pet health & preventive care | Fear Free vet Q&A on skin, coat & digestion |\n"
            "| 4 | Cat Parent & Feline Lifestyle Creators | Instagram & YouTube | Engaged urban cat owners | Cat nutrition, litter/hygiene & enrichment picks |\n"
            "| 5 | Puppy Parenting & First-Time Owner Channels | YouTube | New pet parents buying starter bundles | First 90 days puppy checklist & vet prep guide |\n"
            "| 6 | Pet Product & Unboxing Reviewers | YouTube Shorts & Reels | Comparison & value-conscious buyers | Honest breakdown of food, treats & grooming gear |\n"
            "| 7 | Bengaluru / Metro Pet Community Creators | Instagram | High-density urban pet hubs | Local pet-friendly routines & fast care access |\n"
            "| 8 | Pet Wellness, Grooming & Coat Care Creators | Instagram & YouTube | Skin/coat & seasonal care seekers | Coat & skin care routine across seasons |\n"
            "| 9 | Multi-Pet Household Vloggers | YouTube | High-frequency repeat food & supply buyers | Managing multi-pet monthly replenishment easily |\n"
            "| 10 | Pet Behavior & Enrichment Creators | Instagram & YouTube | Engaged millennial/Gen-Z pet parents | Enrichment + balanced treat/nutrition pairing |"
        )
    }


# -----------------------------------------------------------------------------
# HERO HEADER
# -----------------------------------------------------------------------------
st.markdown("""
<div class="apple-eyebrow">Soumya Ranjan Nayak • AI Growth & Pricing Architecture</div>
<h1 class="apple-hero-title">Executive Intelligence Suite.</h1>
<p class="apple-hero-subtitle">
    Interactive multi-agent diagnostics across Organic Search (SEO/AEO/GEO), Paid Acquisition & CRO, Pricing Economics, Brand Creative, and Reputation Triage.
</p>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SIDEBAR CONFIGURATION (NO USER API KEYS OR USER FORCE-REFRESH)
# -----------------------------------------------------------------------------
st.sidebar.header("Studio & Brand Guardrails")
generate_images = st.sidebar.checkbox("Generate Brand Image & Hook Keyframes", value=True)
raw_logo_upload = st.sidebar.file_uploader(
    "Brand Logo Override (Max 5 MB)",
    type=["png", "jpg", "jpeg", "webp"],
    help="Optional override if automated website logo extraction needs replacement. Max file size: 5 MB."
)

uploaded_logo = None
if raw_logo_upload is not None:
    if raw_logo_upload.size > MAX_LOGO_BYTES:
        st.sidebar.error("Logo exceeds the 5 MB limit. Please upload a file under 5 MB.")
    else:
        uploaded_logo = raw_logo_upload

st.sidebar.markdown("---")
st.sidebar.caption("Powered by Gemini Search + Live URL Context with 48-hour intelligent caching.")

# -----------------------------------------------------------------------------
# CACHE HELPERS (PER-ELEMENT, 2-DAY TTL)
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
# MODEL CALLERS (WITH GEMINI URL_CONTEXT + GOOGLE_SEARCH & CLAUDE WEB_SEARCH)
# -----------------------------------------------------------------------------
def call_gemini(prompt: str, use_search: bool = False, use_url_context: bool = False):
    if not GEMINI_KEY:
        raise ValueError("Backend GEMINI_API_KEY is not configured.")
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
                config=config
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
                        config=types.GenerateContentConfig(tools=fallback_tools)
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
        raise ValueError("Backend ANTHROPIC_API_KEY is not configured.")
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
    raise RuntimeError(" | ".join(errors) if errors else "No backend API key configured.")


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
            use_search=True
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
                "Accept": "image/png,image/jpeg,image/webp,image/*,*/*;q=0.8"
            }
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


def get_or_fetch_brand_logo(company: str, base_url: str, manual_upload=None):
    if manual_upload is not None:
        try:
            raw_in = manual_upload.getvalue()
            if len(raw_in) > MAX_LOGO_BYTES:
                return {"ok": False, "bytes": None, "source": None, "from_cache": False}
            img = Image.open(io.BytesIO(raw_in)).convert("RGBA")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            raw_png = buf.getvalue()
            save_cached_element(company, "brand_logo_v1", {"source": "Uploaded Brand Logo"}, raw_bytes=raw_png, asset_ext="png")
            return {"ok": True, "bytes": raw_png, "source": "Uploaded Brand Logo", "from_cache": False}
        except Exception:
            pass

    cached = load_cached_element(company, "brand_logo_v1", asset_ext="png")
    if cached:
        return {"ok": True, "bytes": cached["bytes"], "source": cached.get("source", f"Official Site ({base_url})"), "from_cache": True}

    try:
        req = urllib.request.Request(
            base_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
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
            "error": None
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
            "error": None
        }
    except Exception as e:
        return {
            "ok": False,
            "content": None,
            "engine": "Unavailable",
            "from_cache": False,
            "age": None,
            "error": str(e)
        }


def get_or_generate_brand_intel(company: str, official_url: str):
    cached = load_cached_element(company, "brand_ad_intel_v3")
    if cached:
        return {
            "ok": True,
            "content": cached["content"],
            "engine": cached["engine"],
            "from_cache": True,
            "age": format_age(cached["saved_at"]),
            "error": None
        }
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
    return get_or_generate_text_element(company, "brand_ad_intel_v3", prompt, preferred="gemini", use_search=True, use_url_context=True)


def get_or_generate_image_element(company: str, element_key: str, prompt: str, aspect_ratio: str = "1:1", logo_bytes: bytes | None = None):
    cached = load_cached_element(company, element_key, asset_ext="png")
    if cached:
        return {
            "ok": True,
            "bytes": cached["bytes"],
            "from_cache": True,
            "age": format_age(cached["saved_at"]),
            "error": None
        }
    try:
        if not GEMINI_KEY:
            raise ValueError("Backend GEMINI_API_KEY required for image generation.")
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
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio)
            )
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
                    "error": None
                }
        raise RuntimeError("No image bytes returned by model.")
    except Exception as e:
        return {
            "ok": False,
            "bytes": None,
            "from_cache": False,
            "age": None,
            "error": str(e)
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
    if scores:
        return round(sum(scores) / len(scores))
    return fallback


def score_badge_html(score_str: str) -> str:
    try:
        s = int(re.sub(r"[^\d]", "", str(score_str)) or "65")
    except Exception:
        s = 65
    if s >= 75:
        cls = "score-pill-good"
    elif s >= 62:
        cls = "score-pill-mid"
    else:
        cls = "score-pill-warn"
    return f'<span class="{cls}">{s} / 100</span>'

# -----------------------------------------------------------------------------
# EXECUTIVE PDF BUILDER
# -----------------------------------------------------------------------------
def _clean_pdf_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "-", "\u2026": "...",
        "\u2192": "->", "\u20b9": "INR ", "\u00a0": " "
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = text.replace("---DEEP_DIVE---", "\nDeep-Dive Strategic Notes:\n")
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
        self.cell(0, 8, f"EXECUTIVE GROWTH & CREATIVE AUDIT  |  {self.company_name.upper()}", align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(142, 142, 147)
        self.cell(0, 8, f"Soumya Ranjan Nayak  -  AI Strategy Framework   |   Page {self.page_no()}", align="C")

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
                max_lines = 1
                for cell_txt in padded:
                    est = max(1, int(len(cell_txt) / max(10, (col_w / 2.0))) + 1)
                    max_lines = max(max_lines, est)
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
                clean_h = line.lstrip("#").strip()
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(0, 113, 227)
                self.multi_cell(0, 6, clean_h)
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
    company = audit_data["company"]
    pdf = ExecutivePDF(company)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(29, 29, 31)
    pdf.cell(0, 11, _clean_pdf_text(f"{company}"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(110, 110, 115)
    date_str = datetime.now().strftime("%B %d, %Y")
    pdf.cell(0, 7, f"Executive Growth, Search, Paid CRO, Pricing & Creative Report  |  {date_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if audit_data["e1"]["ok"]:
        pdf.section_title("1. Organic Search Intelligence (SEO, AEO & GEO)")
        pdf.render_markdown_block(audit_data["e1"]["content"])

    if audit_data["e_paid"]["ok"]:
        pdf.section_title("2. Paid Search, Shopping & Funnel CRO Diagnostics")
        pdf.render_markdown_block(audit_data["e_paid"]["content"])

    if audit_data["e2"]["ok"]:
        pdf.section_title("3. Pricing Architecture & Unit Economics")
        pdf.render_markdown_block(audit_data["e2"]["content"])

    pdf.section_title("4. Brand Design Language & Ad Creative Strategy")
    if audit_data.get("brand_intel") and audit_data["brand_intel"]["ok"]:
        pdf.render_markdown_block(audit_data["brand_intel"]["content"])
        pdf.ln(2)
    if audit_data["e3"]["ok"]:
        pdf.render_markdown_block(audit_data["e3"]["content"])

    if audit_data["e4"]["ok"]:
        pdf.section_title("5. Brand Reputation, Social Listening & Creator Partnerships")
        pdf.render_markdown_block(audit_data["e4"]["content"])

    images_to_embed = [
        ("Meta Feed Ad Creative (1:1)", audit_data.get("img_meta"), 95),
        ("Display Banner Ad Creative (16:9)", audit_data.get("img_banner"), 150),
        ("4-Second Video Hook Opening Keyframe (16:9)", audit_data.get("img_hook_frame"), 150),
    ]
    valid_imgs = [(label, item, w) for label, item, w in images_to_embed if item and item.get("ok") and item.get("bytes")]

    if valid_imgs:
        pdf.add_page()
        pdf.section_title("6. Generated Brand-Aligned Ad Mockups")
        temp_files = []
        try:
            for label, item, target_w in valid_imgs:
                if pdf.get_y() > 205:
                    pdf.add_page()
                pdf.set_font("Helvetica", "B", 10.5)
                pdf.set_text_color(29, 29, 31)
                pdf.cell(0, 7, _clean_pdf_text(label), new_x="LMARGIN", new_y="NEXT")

                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                tmp.write(item["bytes"])
                tmp.close()
                temp_files.append(tmp.name)

                pdf.image(tmp.name, w=target_w)
                pdf.ln(6)
        finally:
            for path in temp_files:
                if os.path.exists(path):
                    os.remove(path)

    raw_out = pdf.output()
    return bytes(raw_out) if isinstance(raw_out, (bytes, bytearray)) else raw_out.encode("latin-1")

# -----------------------------------------------------------------------------
# RUN LIVE AUDIT ORCHESTRATOR
# -----------------------------------------------------------------------------
def run_live_audit(company: str):
    with st.spinner(f"Orchestrating 5 specialized sub-agents for {company}..."):
        official_url = get_or_resolve_official_url(company)
        brand_logo = get_or_fetch_brand_logo(company, official_url, manual_upload=uploaded_logo)
        brand_intel = get_or_generate_brand_intel(company, official_url)
        brand_dna_text = brand_intel["content"] if brand_intel["ok"] else f"Authentic commercial brand aesthetic for {company}."

        p1 = f"""
        Act as Principal SEO, AEO (Answer Engine Optimization), and GEO (Generative Engine Optimization) Architect auditing {company} (inspecting live storefront URL: {official_url} alongside live search index signals).
        STRICT FORMATTING:
        - Start with a compact Markdown scorecard table with EXACT columns (use integer-only numbers like 68 in Score /100, never '68/100'):
          | Search Pillar | Score /100 | Observable Diagnostic Signal | Primary Gap |
          Rows MUST be:
          1. Technical & Programmatic SEO
          2. AEO
          3. GEO
          4. Entity & Local Schema
          5. Off-Site Consensus & Digital PR
        - Follow with EXACTLY 4 short, hard-hitting bullet points (max 16 words per bullet) on highest-ROI organic search levers.
        - End with '---DEEP_DIVE---' followed by:
          1. A compact 4-row **AI Prompt Visibility Matrix** table (| High-Intent Buyer Prompt | Current AI Winner | {company} Vulnerability | Asset Needed to Win |)
          2. **Technical, Entity & Off-Site Execution Plan**: Output EXACTLY 5 scannable bullet points (max 25 words each) formatted strictly as `- **[Category] Problem -> Fix:** [Diagnosis] -> [Action]`.
        """

        p_paid = f"""
        Act as VP of Performance Marketing & Conversion Rate Optimization (CRO) auditing {company} (inspecting live storefront UX/checkout signals at {official_url} and active ad signals).
        STRICT FORMATTING:
        - Start with a compact Markdown scorecard table with EXACT columns (use integer-only numbers like 61 in Score /100, never '61/100'):
          | Paid & Funnel Pillar | Score /100 | Observable Diagnostic Signal | Primary Leakage |
          Rows MUST be:
          1. Non-Brand Search & PMax Efficiency
          2. Paid Social Acquisition & Creative Fatigue
          3. Landing Page & Product-to-Cart CRO
          4. Checkout, Booking & Post-Click Friction
        - Follow with EXACTLY 4 short, hard-hitting bullet points (max 16 words per bullet) on immediate ROAS and conversion lifts.
        - End with '---DEEP_DIVE---' followed by:
          1. **Paid Architecture & Funnel Fixes**: Output 4 scannable bullet points (max 25 words each) formatted strictly as `- **[Area] Problem -> Fix:** [Diagnosis] -> [Action]`.
          2. A compact 4-row **CRO & Paid Experiment Backlog** table:
             | Test Hypothesis | Primary Metric | Guardrail Metric | Expected Impact |
        """

        p2 = f"""
        Act as VP of Pricing & Commercial Strategy auditing {company} (inspecting live pricing, shipping thresholds, fees, and product mix at {official_url} plus market search signals).
        STRICT FORMATTING:
        - Line 1 MUST be a bold 1-sentence executive summary of the brand's current pricing model, formatted strictly as:
          **Current Pricing Strategy:** [1 concise sentence summarizing price positioning, shipping/fee thresholds, discounting posture, and core monetization model].
        - Immediately follow with a compact Markdown scorecard table with EXACT columns (use integer-only numbers like 62 in Score /100, never '62/100'):
          | Pricing & Economics Pillar | Score /100 | Observable Pricing Signal | Margin / LTV Leakage |
          Rows MUST be:
          1. Core SKU & Marketplace Price Positioning
          2. Shipping, Fee & Basket Threshold Architecture
          3. Subscription & Repeat-Cohort Monetization
          4. Private-Label & High-Margin Service Mix
        - Follow with EXACTLY 4 short, hard-hitting bullet points (max 16 words per bullet) on immediate gross margin and LTV expansion levers.
        - End with '---DEEP_DIVE---' followed by:
          1. **Tier Optimization & Margin Execution Plan**: Output 4 scannable bullet points (max 25 words each) formatted strictly as `- **[Lever] Problem -> Fix:** [Current margin/pricing leak] -> [Exact tier, threshold, or bundling mechanism]`.
          2. A compact 4-row **Unit Economics & Pricing Impact Matrix** table:
             | Pricing Lever | Target Cohort | Mechanism | Margin / LTV Lift | Volume / Churn Guardrail |
        """

        p3 = f"""
        Act as VP of Performance Creative & Brand Strategy for {company}.
        Current Brand & Ad Baseline:
        {brand_dna_text}

        STRICT FORMATTING (DO NOT USE ANY EMOJIS):
        - Output compact, high-converting ad concepts in 3 short blocks:
          1. **Google Search RSA Pack** (3 Headlines <=30 chars each + 2 Descriptions <=90 chars each)
          2. **Meta Feed Ad** (Primary Text <=110 chars + Headline <=35 chars + CTA)
          3. **4-Second Video Hook** (Visual Scene + Voiceover/Text Overlay <=12 words)
        - End with '---DEEP_DIVE---' followed by:
          1. **Creative Rationale & Baseline Evolution**: Output 3 scannable bullet points (max 25 words each) formatted strictly as `- **[Channel] Problem -> Fix:** [Current creative fatigue/gap] -> [How new hook improves CTR/CVR]`.
          2. A compact 4-row **Creative A/B Testing Matrix** table:
             | Ad Variant | Hook / Angle | Target Persona | Primary KPI |
        """

        p4 = f"""
        Act as VP of Brand Reputation, Social Listening & Creator Partnerships auditing {company} ({official_url}) using live web, Reddit, review aggregator, and YouTube search signals.
        STRICT FORMATTING (DO NOT USE ANY EMOJIS):
        - Line 1 MUST be a bold 1-sentence executive summary of the brand's current public reputation posture, formatted strictly as:
          **Current Brand Sentiment Archetype:** [1 concise sentence contrasting core brand strengths/advocacy against primary public friction points].
        - Immediately follow with a compact Markdown scorecard table with EXACT columns (use integer-only numbers like 64 in Score /100, never '64/100'):
          | Reputation & Listening Pillar | Score /100 | Observable Social / Review Signal | Primary Trust Risk |
          Rows MUST be:
          1. Fulfillment & Post-Purchase Sentiment
          2. Clinical & Product Trust Authority
          3. Review Ecosystem Parity
          4. Community Advocacy & Earned Momentum
        - Immediately follow with **Voice of the Customer — Recent Platform Signals** formatted as a compact 6-row table:
          | Polarity | Platform & Context | Representative Customer Feedback | Core Theme |
        - End with '---DEEP_DIVE---' followed by:
          1. **Rapid Triage & Reputation Execution Plan**: Output 4 scannable bullet points (max 25 words each) formatted strictly as `- **[Area] Problem -> Fix:** [Current sentiment/ops trigger] -> [Exact SLA, product, or comms action]`.
          2. **Social Listening & Escalation SLA Matrix**: A compact 4-row table:
             | Listening Cluster & Channels | Trigger Signal | Severity & SLA | Owner & Resolution Play |
          3. **Top 10 Influencers & YouTube Channels for Brand Collaboration**: A 10-row outreach table:
             | Rank | Creator / Channel Name | Primary Platform | Category & Audience Fit | Recommended Collab Angle |
        """

        e1 = get_or_generate_text_element(company, "agent1_seo_aeo_geo_v3", p1, preferred="gemini", use_search=True, use_url_context=True)
        e_paid = get_or_generate_text_element(company, "agent2_paid_cro_v2", p_paid, preferred="gemini", use_search=True, use_url_context=True)
        e2 = get_or_generate_text_element(company, "agent2_pricing_v2", p2, preferred="gemini", use_search=True, use_url_context=True)
        e3 = get_or_generate_text_element(company, "agent3_creative_v2", p3, preferred="gemini")
        e4 = get_or_generate_text_element(company, "agent4_social_v2", p4, preferred="gemini", use_search=True, use_url_context=True)

        img_meta = None
        img_banner = None
        img_hook_frame = None
        if generate_images:
            logo_bytes = brand_logo["bytes"] if brand_logo["ok"] else None
            meta_prompt = (
                f"Create a sleek, modern Instagram/Meta feed advertisement creative (1:1) for {company}. "
                f"Strictly align with this brand design language: {brand_dna_text} "
                f"Apple-inspired clean commercial composition, authentic natural photography, MAXIMUM 2 clean UI elements (1 crisp offer pill badge + 1 primary CTA button), generous breathing room, zero cluttered text."
            )
            banner_prompt = (
                f"Create a sleek widescreen digital display banner ad creative (16:9) for {company}. "
                f"Strictly align with this brand design language: {brand_dna_text} "
                f"Hero product/service showcase on clean off-white/warm brand backdrop, MAXIMUM 2 clean UI elements (1 bold headline + 1 CTA button), zero clutter."
            )
            hook_frame_prompt = (
                f"Create the opening 0-second keyframe visual for a 4-second commercial video ad hook (16:9) for {company}. "
                f"Strictly align with this brand design language: {brand_dna_text} "
                f"High-attention candid hero moment with clean composition, MAXIMUM 2 clean UI overlays (1 short 4-word hook headline + 1 subtle CTA badge), zero clutter."
            )
            img_meta = get_or_generate_image_element(company, "meta_ad_1x1_v3", meta_prompt, aspect_ratio="1:1", logo_bytes=logo_bytes)
            img_banner = get_or_generate_image_element(company, "banner_ad_16x9_v3", banner_prompt, aspect_ratio="16:9", logo_bytes=logo_bytes)
            img_hook_frame = get_or_generate_image_element(company, "video_hook_frame_16x9_v3", hook_frame_prompt, aspect_ratio="16:9", logo_bytes=logo_bytes)

        s_seo = extract_composite_score(e1.get("content", ""), 68)
        s_paid = extract_composite_score(e_paid.get("content", ""), 61)
        s_pri = extract_composite_score(e2.get("content", ""), 62)
        s_soc = extract_composite_score(e4.get("content", ""), 65)

        return {
            "company": company,
            "official_url": official_url,
            "is_showcase": False,
            "kpis": {
                "margin_lever": f"See {company} pricing & tier levers in Pricing tile",
                "funnel_leak": f"See {company} acquisition & CRO leaks in Paid tile",
                "reputation_risk": f"See {company} sentiment & SLA risks in Social tile"
            },
            "tile_hooks": {
                "seo": (str(s_seo), f"Organic search, AI answer visibility, and schema audit for {company}."),
                "paid": (str(s_paid), f"Paid search/social efficiency, landing page UX, and checkout diagnostics for {company}."),
                "pricing": (str(s_pri), f"Price positioning, shipping/fee thresholds, and margin expansion levers for {company}."),
                "creative": ("72", f"Brand-aligned ad copy, RSA pack, and visual creatives for {company}."),
                "social": (str(s_soc), f"Customer sentiment signals, escalation SLAs, and creator outreach for {company}.")
            },
            "brand_logo": brand_logo,
            "brand_intel": brand_intel,
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
# SEARCH BAR + SAMPLE SHOWCASE LAUNCHERS
# -----------------------------------------------------------------------------
if "active_module" not in st.session_state:
    st.session_state["active_module"] = "pricing"

if "last_audit" not in st.session_state:
    st.session_state["last_audit"] = build_sample_showcase("supertails")

col_input, col_btn, col_s1, col_s2 = st.columns([2.6, 1.35, 1.15, 1.25], vertical_alignment="bottom")
with col_input:
    target_company = st.text_input(
        "Target Company",
        placeholder="Enter any brand (e.g., Ather Energy, Zepto, Zerodha)",
        label_visibility="collapsed"
    )
with col_btn:
    run_clicked = st.button("Run Live Audit", use_container_width=True)
with col_s1:
    if st.button("Demo: Supertails", use_container_width=True):
        st.session_state["last_audit"] = build_sample_showcase("supertails")
        st.rerun()
with col_s2:
    if st.button("Demo: Enphase", use_container_width=True):
        st.session_state["last_audit"] = build_sample_showcase("enphase")
        st.rerun()

if run_clicked:
    if not GEMINI_KEY and not CLAUDE_KEY:
        st.error("Backend API key is not configured yet. Add GEMINI_API_KEY in Streamlit Secrets to run live audits, or use the Demo buttons.")
    elif not target_company.strip():
        st.warning("Please enter a target company name.")
    else:
        st.session_state["last_audit"] = run_live_audit(target_company.strip())
        st.rerun()

# -----------------------------------------------------------------------------
# COMMAND BANNER + INTERACTIVE BENTO TILES + FOCUSED MODULE VIEW
# -----------------------------------------------------------------------------
audit = st.session_state.get("last_audit")
if audit:
    company = audit["company"]
    official_url = audit.get("official_url", "")
    is_showcase = audit.get("is_showcase", False)
    kpis = audit.get("kpis", {})
    hooks = audit.get("tile_hooks", {})

    scores_num = []
    for k in ["seo", "paid", "pricing", "social"]:
        try:
            scores_num.append(int(hooks.get(k, ("65", ""))[0]))
        except Exception:
            pass
    composite_health = round(sum(scores_num) / len(scores_num)) if scores_num else 66

    col_banner, col_pdf = st.columns([3.4, 1.2], vertical_alignment="top")
    with col_banner:
        mode_label = "Curated Executive Snapshot" if is_showcase else "Live Search + URL Context Audit"
        logo_html = ""
        bl = audit.get("brand_logo") or {}
        if bl.get("ok") and bl.get("bytes"):
            b64_logo = base64.b64encode(bl["bytes"]).decode("utf-8")
            logo_html = f'<img src="data:image/png;base64,{b64_logo}" style="height:36px;width:auto;border-radius:8px;margin-right:12px;vertical-align:middle;" />'

        st.markdown(f"""
        <div class="command-banner">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.6rem;">
                <div>
                    {logo_html}
                    <span style="font-size:1.35rem;font-weight:700;letter-spacing:-0.02em;color:#1D1D1F;vertical-align:middle;">{company}</span>
                    <span style="font-size:0.85rem;color:#6E6E73;margin-left:8px;vertical-align:middle;">• <a href="{official_url}" target="_blank" style="color:#0071E3;text-decoration:none;">{official_url}</a></span>
                </div>
                <div>
                    <span class="apple-meta-pill">{mode_label}</span>
                    {score_badge_html(composite_health)}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_pdf:
        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
        pdf_bytes = build_executive_pdf(audit)
        st.download_button(
            label="Download Executive PDF",
            data=pdf_bytes,
            file_name=f"{_slug(company)}_executive_audit.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="kpi-mini-card"><div class="kpi-mini-label">Primary Margin / Monetization Lever</div><div class="kpi-mini-value">{kpis.get("margin_lever", "")}</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="kpi-mini-card"><div class="kpi-mini-label">Primary Funnel / Growth Leak</div><div class="kpi-mini-value">{kpis.get("funnel_leak", "")}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="kpi-mini-card"><div class="kpi-mini-label">Primary Reputation / Trust Watchout</div><div class="kpi-mini-value">{kpis.get("reputation_risk", "")}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    active_mod = st.session_state.get("active_module", "pricing")
    row1_keys = ["seo", "paid", "pricing"]
    row2_keys = ["creative", "social"]

    def render_bento_row(keys: list[str]):
        cols = st.columns(len(keys))
        for idx, m_key in enumerate(keys):
            with cols[idx]:
                sc_str, hook_txt = hooks.get(m_key, ("65", "Click to inspect diagnostics."))
                is_sel = (active_mod == m_key)
                tile_cls = "bento-tile bento-tile-active" if is_sel else "bento-tile"
                st.markdown(f"""
                <div class="{tile_cls}">
                    <div class="bento-top-row">
                        <span class="bento-title">{MODULE_META[m_key]["short_title"]}</span>
                        {score_badge_html(sc_str)}
                    </div>
                    <div class="bento-hook">{hook_txt}</div>
                </div>
                """, unsafe_allow_html=True)
                btn_label = "Viewing Module" if is_sel else f"Open {MODULE_META[m_key]['short_title']}"
                if st.button(btn_label, key=f"tile_btn_{m_key}", use_container_width=True):
                    st.session_state["active_module"] = m_key
                    st.rerun()

    render_bento_row(row1_keys)
    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
    render_bento_row(row2_keys)

    st.markdown("---")

    def render_focused_text_module(m_key: str, item: dict):
        meta = MODULE_META[m_key]
        if not item or not item.get("ok"):
            st.error(f"Module unavailable: {item.get('error', 'Unknown error')}")
            return
        cache_tag = f"Cached ({item['age']})" if item.get("from_cache") else "Freshly Generated"
        st.markdown(f"""
        <div class="apple-section-header">
            <div class="apple-card-header">{meta["full_title"]}</div>
            <div class="apple-meta-pill">{item['engine']}  •  {cache_tag}</div>
        </div>
        """, unsafe_allow_html=True)

        parts = item["content"].split("---DEEP_DIVE---")
        st.markdown(parts[0].strip())
        if len(parts) > 1 and parts[1].strip():
            with st.expander(meta["expander"], expanded=True):
                st.markdown(parts[1].strip())
        st.markdown(f'<div class="governance-note">{meta["governance"]}</div>', unsafe_allow_html=True)

    if active_mod in ("seo", "paid", "pricing", "social"):
        key_map = {"seo": "e1", "paid": "e_paid", "pricing": "e2", "social": "e4"}
        render_focused_text_module(active_mod, audit.get(key_map[active_mod]))

    elif active_mod == "creative":
        bi = audit.get("brand_intel")
        bi_meta = ""
        if bi and bi.get("ok"):
            bi_cache = f"Cached ({bi['age']})" if bi.get("from_cache") else "Freshly Generated"
            bi_meta = f'<div class="apple-meta-pill">{bi["engine"]}  •  {bi_cache}</div>'

        st.markdown(f"""
        <div class="apple-section-header">
            <div class="apple-card-header">Current Brand Design Language & Active Ad Patterns</div>
            {bi_meta}
        </div>
        """, unsafe_allow_html=True)

        if bi and bi.get("ok"):
            st.markdown(bi["content"])

        q = quote_plus(company)
        meta_lib_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IN&q={q}&search_type=keyword_unordered"
        google_trans_url = f"https://adstransparency.google.com/?region=IN&domain={q}"
        st.markdown(
            f"**Verify Live Ad Libraries:**   "
            f"[Meta Ad Library for {company} ↗]({meta_lib_url})   |   "
            f"[Google Ads Transparency Center ↗]({google_trans_url})"
        )

        st.markdown("---")
        render_focused_text_module("creative", audit.get("e3"))

        if generate_images:
            st.markdown("---")
            bl = audit.get("brand_logo") or {}
            logo_badge = (
                f"Logo Guardrail Active ({bl.get('source', 'Official Website')})"
                if bl.get("ok")
                else "Logo Guardrail Active (Clean Safe-Zone Mode — No Hallucinated Wordmarks)"
            )
            st.markdown(f"""
            <div class="apple-section-header">
                <div class="apple-card-header">Brand-Aligned Visual Creatives</div>
                <div class="apple-meta-pill">Nano Banana 2 (gemini-3.1-flash-image)  •  {logo_badge}</div>
            </div>
            """, unsafe_allow_html=True)

            if bl.get("ok") and bl.get("bytes"):
                c_logo, c_note = st.columns([0.6, 4.4], vertical_alignment="center")
                with c_logo:
                    st.image(bl["bytes"], width=76)
                with c_note:
                    st.caption(f"Verified reference asset extracted from **{bl.get('source')}** (<=5 MB) and passed into image generation.")

            has_any_img = any(
                (audit.get(k) or {}).get("ok") and (audit.get(k) or {}).get("bytes")
                for k in ["img_meta", "img_banner", "img_hook_frame"]
            )
            if not has_any_img:
                st.info("Visual mockups are generated automatically during a Live Audit when image generation is enabled.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Meta Feed Ad (1:1)**")
                    m = audit.get("img_meta")
                    if m and m.get("ok"):
                        st.image(m["bytes"], use_container_width=True)
                with col2:
                    st.markdown("**Display Banner (16:9)**")
                    b = audit.get("img_banner")
                    if b and b.get("ok"):
                        st.image(b["bytes"], use_container_width=True)

                st.markdown("---")
                st.markdown("**4-Second Video Hook — Opening Keyframe (16:9)**")
                hf = audit.get("img_hook_frame")
                if hf and hf.get("ok"):
                    st.image(hf["bytes"], use_container_width=True)
