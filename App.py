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
.governance-note {
    font-size: 0.8rem;
    color: #86868B;
    margin-top: 0.9rem;
    padding-top: 0.65rem;
    border-top: 1px solid #F2F2F7;
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
force_
