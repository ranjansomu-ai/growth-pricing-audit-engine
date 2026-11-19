import streamlit as st
from google import genai
from google.genai import types
import anthropic
from PIL import Image
from urllib.parse import quote_plus
from fpdf import FPDF
import io
import os
import json
import time
import re
import tempfile
from datetime import datetime

# Page Config
st.set_page_config(
    page_title="Growth & Creative Intelligence — Executive Suite",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

CACHE_DIR = ".audit_cache"
TTL_SECONDS = 2 * 24 * 3600  # 2 days (48 hours)
os.makedirs(CACHE_DIR, exist_ok=True)

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
    padding-top: 2.5rem !important;
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
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #0071E3;
    margin-bottom: 0.35rem;
}
.apple-hero-title {
    font-size: 2.6rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
    color: #1D1D1F;
    margin: 0 0 0.6rem 0;
}
.apple-hero-subtitle {
    font-size: 1.12rem;
    font-weight: 400;
    line-height: 1.45;
    color: #6E6E73;
    max-width: 780px;
    margin: 0 0 1.8rem 0;
}

div[data-testid="stTextInput"] input {
    background-color: #FFFFFF !important;
    border: 1px solid #D2D2D7 !important;
    border-radius: 12px !important;
    padding: 0.75rem 1rem !important;
    font-size: 1rem !important;
    color: #1D1D1F !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #0071E3 !important;
    box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15) !important;
}

div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {
    border-radius: 980px !important;
    font-weight: 500 !important;
    font-size: 0.95rem !important;
    padding: 0.55rem 1.4rem !important;
    letter-spacing: -0.01em !important;
    transition: all 0.2s ease !important;
    border: none !important;
}
div[data-testid="stButton"] > button {
    background-color: #0071E3 !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(0, 113, 227, 0.22) !important;
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

div[data-baseweb="tab-list"] {
    background-color: #F5F5F7 !important;
    padding: 5px !important;
    border-radius: 980px !important;
    border: 1px solid #E5E5EA !important;
    gap: 4px !important;
    margin-bottom: 1.2rem !important;
}
button[data-baseweb="tab"] {
    border-radius: 980px !important;
    padding: 0.45rem 1.05rem !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: #6E6E73 !important;
    background-color: transparent !important;
    border: none !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background-color: #FFFFFF !important;
    color: #1D1D1F !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08) !important;
}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
    display: none !important;
}

.apple-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E5EA;
    border-radius: 20px;
    padding: 1.6rem 1.8rem;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
    margin-bottom: 1.2rem;
}
.apple-card-header {
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: #1D1D1F;
    margin-bottom: 0.25rem;
}
.apple-meta-pill {
    display: inline-block;
    background-color: #F5F5F7;
    color: #6E6E73;
    font-size: 0.78rem;
    font-weight: 500;
    padding: 0.22rem 0.75rem;
    border-radius: 980px;
    margin-bottom: 1rem;
}

table {
    width: 100% !important;
    border-collapse: collapse !important;
    margin: 0.8rem 0 1.2rem 0 !important;
    font-size: 0.91rem !important;
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
    background-color: #FBFBFD !important;
    border: 1px solid #E5E5EA !important;
    border-radius: 14px !important;
    margin-top: 0.8rem !important;
}
details[data-testid="stExpander"] summary {
    font-weight: 500 !important;
    color: #0071E3 !important;
}

.status-strip {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    background-color: #FFFFFF;
    border: 1px solid #E5E5EA;
    border-radius: 14px;
    padding: 0.75rem 1.2rem;
    margin: 1rem 0 1.4rem 0;
    font-size: 0.88rem;
    color: #1D1D1F;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# HERO HEADER
# -----------------------------------------------------------------------------
st.markdown("""
<div class="apple-eyebrow">Soumya Ranjan Nayak • AI Growth & Pricing Architecture</div>
<h1 class="apple-hero-title">Executive Intelligence Suite.</h1>
<p class="apple-hero-subtitle">
    Specialized multi-agent diagnostics across Organic Search (SEO/AEO/GEO), Paid Acquisition & CRO, Pricing Economics, Brand Creative, and Reputation Triage.
</p>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SIDEBAR CONFIGURATION
# -----------------------------------------------------------------------------
st.sidebar.header("API Credentials")
gemini_key = st.sidebar.text_input("Gemini API Key (Paid Tier)", type="password")
claude_key = st.sidebar.text_input("Anthropic API Key (Optional)", type="password")

st.sidebar.markdown("---")
st.sidebar.header("Studio & Cache Controls")
generate_images = st.sidebar.checkbox("Generate Brand Image & Hook Keyframes", value=True)
force_refresh = st.sidebar.checkbox("Force Refresh (Bypass 2-Day Cache)", value=False)
st.sidebar.caption("Completed modules cache for 48 hours. Partial failures retry selectively on next run.")

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
    if force_refresh:
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
# MODEL CALLERS
# -----------------------------------------------------------------------------
def call_gemini(prompt: str, use_search: bool = False):
    if not gemini_key:
        raise ValueError("Gemini API key not provided.")
    client = genai.Client(api_key=gemini_key)
    config = types.GenerateContentConfig(
        tools=[{"google_search": {}}] if use_search else None
    )
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
            return res.text, f"Gemini ({model_id})"
        except Exception as e:
            last_err = e
    raise last_err

def call_claude(prompt: str):
    if not claude_key:
        raise ValueError("Claude API key not provided.")
    client = anthropic.Anthropic(api_key=claude_key)
    msg = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=1600,
        messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text if msg.content else ""
    if not text:
        raise RuntimeError("Empty response from Claude.")
    return text, "Claude (Sonnet 5.5)"

def route_agent(prompt: str, preferred: str = "gemini", use_search: bool = False):
    order = ["gemini", "claude"] if preferred == "gemini" else ["claude", "gemini"]
    errors = []
    for provider in order:
        try:
            if provider == "gemini" and gemini_key:
                return call_gemini(prompt, use_search=use_search)
            elif provider == "claude" and claude_key:
                return call_claude(prompt)
        except Exception as e:
            errors.append(f"{provider.upper()}: {e}")
    raise RuntimeError(" | ".join(errors) if errors else "No API key available.")

def get_or_generate_text_element(company: str, element_key: str, prompt: str, preferred: str = "gemini", use_search: bool = False):
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
        content, engine = route_agent(prompt, preferred=preferred, use_search=use_search)
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

def get_or_generate_brand_intel(company: str):
    cached = load_cached_element(company, "brand_ad_intel_v2")
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
    Research {company}'s current brand design language and active ad messaging across Meta Ad Library, Google Ads Transparency Center, Instagram, and Google Search ads.
    STRICT FORMATTING — Output EXACTLY these 4 punchy bullet points (max 18 words per bullet) and nothing else:
    - **Visual Design Language:** [Exact primary/secondary brand colors, card/UI styling, typography mood, and photography style]
    - **Meta & Social Ad Patterns:** [Dominant visual hooks, offer badges, and creative formats seen in their Meta ads]
    - **Google Search & Shopping Messaging:** [Primary headline angles, value props, and CTA patterns in search/shopping ads]
    - **Core Audience & Trust Triggers:** [Target persona setting and key credibility signals/social proof used]
    """
    return get_or_generate_text_element(company, "brand_ad_intel_v2", prompt, preferred="gemini", use_search=True)

def get_or_generate_image_element(company: str, element_key: str, prompt: str, aspect_ratio: str = "1:1"):
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
        if not gemini_key:
            raise ValueError("Gemini API key required for image generation.")
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model="gemini-3.1-flash-image",
            contents=prompt,
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

# -----------------------------------------------------------------------------
# EXECUTIVE PDF BUILDER (5 SECTIONS + EMBEDDED AD MOCKUPS)
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
        pdf.render_markdown_block(audit
