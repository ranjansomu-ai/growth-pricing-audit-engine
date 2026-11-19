import streamlit as st
from google import genai
from google.genai import types
import anthropic
from PIL import Image
import io
import os
import json
import time
import re

# Page Config
st.set_page_config(page_title="AI Growth & Creative Command Center", page_icon="📈", layout="wide")

CACHE_DIR = ".audit_cache"
TTL_SECONDS = 2 * 24 * 3600  # 2 days (48 hours)
os.makedirs(CACHE_DIR, exist_ok=True)

# App Header
st.title("📈 Executive Growth, Pricing & Creative Command Center")
st.markdown("### Hybrid Multi-Agent Architecture (Gemini + Claude)")
st.write("Enter a target company once to orchestrate specialized sub-agents with 2-day per-element caching and selective retry.")

# Sidebar Configuration
st.sidebar.header("🔑 API Credentials")
gemini_key = st.sidebar.text_input("Gemini API Key (Paid Billing Enabled)", type="password")
claude_key = st.sidebar.text_input("Anthropic API Key (Claude - Optional)", type="password")

st.sidebar.header("💾 Credit Saver & Cache Controls")
generate_images = st.sidebar.checkbox("Enable Brand Image & Hook Keyframe Ads", value=True)
force_refresh = st.sidebar.checkbox("Force Refresh (Bypass 2-Day Cache)", value=False)
st.sidebar.caption("Successful elements are cached for 2 days. Failed elements are not cached and retry automatically on the next run.")

# Cache Helpers (Per-Element, 2-Day TTL)
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

# Model Callers
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
        max_tokens=1500,
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

def get_or_generate_brand_dna(company: str):
    cached = load_cached_element(company, "brand_dna")
    if cached:
        return cached["content"]
    try:
        dna, _ = call_gemini(
            f"""
            Research {company}'s current brand design language, visual identity, and active performance ads (Meta/Instagram/Google).
            Return ONLY a concise 2-sentence visual art-direction brief covering:
            1. Exact brand color palette, UI card aesthetic, and visual tone.
            2. Authentic target customer/subject setting and key value-prop badge style used in their real ads.
            Do not include intro text or bullet points.
            """,
            use_search=True
        )
        dna = dna.strip()
        save_cached_element(company, "brand_dna", {"content": dna})
        return dna
    except Exception:
        return f"Authentic commercial brand aesthetic for {company}."

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

# Single Unified Input
target_company = st.text_input("Target Company Name", placeholder="e.g., Supertails, Enphase Energy, Ather Energy")

if st.button("🚀 Orchestrate Hybrid Multi-Agent Audit"):
    if not gemini_key and not claude_key:
        st.error("Please enter at least one API key (Gemini or Claude) in the sidebar.")
    elif not target_company.strip():
        st.warning("Please enter a target company name.")
    else:
        company = target_company.strip()
        with st.spinner(f"Checking 2-day cache and running only missing/expired elements for {company}..."):
            brand_dna = get_or_generate_brand_dna(company) if gemini_key else f"Authentic commercial brand aesthetic for {company}."

            p1 = f"""
            Act as Chief Growth Officer auditing {company}.
            STRICT FORMATTING:
            - Start with a compact Markdown scorecard table (Pillar | Score /100 | Key Gap) across Paid Search, SEO/GEO, Funnel CRO, Pricing, and Social.
            - Follow with EXACTLY 4 short, hard-hitting bullet points (max 15 words per bullet) on top growth levers.
            - End with '---DEEP_DIVE---' followed by a concise bulleted breakdown of AEO/GEO visibility and competitor gaps.
            """
            p2 = f"""
            Act as VP of Pricing Strategy analyzing {company}.
            STRICT FORMATTING:
            - Output EXACTLY 4 punchy bullet points (max 15 words per bullet) identifying monetization leaks, LTV:CAC friction, and bundling opportunities.
            - End with '---DEEP_DIVE---' followed by a structured bulleted breakdown of tier optimization and margin expansion tactics.
            """
            p3 = f"""
            Act as Performance Creative Director for {company}. Brand Visual DNA: {brand_dna}
            STRICT FORMATTING:
            - Output compact, high-converting ad copy in 3 short bulleted blocks:
              1. Google Search Ad (2 Headlines + 1 Description)
              2. Meta Feed Ad (Primary Text + Headline + CTA)
              3. 4-Second Video Hook (Visual Scene + Voiceover/Text Overlay)
            - End with '---DEEP_DIVE---' followed by the extracted Brand Visual DNA and creative rationale.
            """
            p4 = f"""
            Act as Brand Reputation Lead for {company}.
            STRICT FORMATTING:
            - Output 2 short bullet points under '🚨 Friction to Curtail' and 2 short bullet points under '🚀 Wins to Amplify' (max 15 words per bullet).
            - End with '---DEEP_DIVE---' followed by a 3-step rapid response playbook.
            """

            e1 = get_or_generate_text_element(company, "agent1_scorecard", p1, preferred="gemini", use_search=True)
            e2 = get_or_generate_text_element(company, "agent2_pricing", p2, preferred="claude")
            e3 = get_or_generate_text_element(company, "agent3_creative", p3, preferred="claude")
            e4 = get_or_generate_text_element(company, "agent4_social", p4, preferred="gemini", use_search=True)

            img_meta = None
            img_banner = None
            img_hook_frame = None

            if generate_images:
                meta_prompt = (
                    f"Create an authentic high-converting Instagram/Meta feed advertisement creative for {company}. "
                    f"Strictly follow this brand design language: {brand_dna} "
                    f"Clean commercial composition, warm authentic photography, minimal clean callout badge, no cluttered text."
                )
                banner_prompt = (
                    f"Create a sleek widescreen digital display banner ad creative for {company}. "
                    f"Strictly follow this brand design language: {brand_dna} "
                    f"Hero product/service showcase, high visual contrast, clean modern layout."
                )
                hook_frame_prompt = (
                    f"Create the opening 0-second keyframe visual for a 4-second commercial video ad hook for {company}. "
                    f"Strictly follow this brand design language: {brand_dna} "
                    f"High-attention visual hook with clear focal subject and space for a bold short headline overlay."
                )
                img_meta = get_or_generate_image_element(company, "meta_ad_1x1", meta_prompt, aspect_ratio="1:1")
                img_banner = get_or_generate_image_element(company, "banner_ad_16x9", banner_prompt, aspect_ratio="16:9")
                img_hook_frame = get_or_generate_image_element(company, "video_hook_frame_16x9", hook_frame_prompt, aspect_ratio="16:9")

            st.session_state["last_audit"] = {
                "company": company,
                "e1": e1,
                "e2": e2,
                "e3": e3,
                "e4": e4,
                "img_meta": img_meta,
                "img_banner": img_banner,
                "img_hook_frame": img_hook_frame,
            }

# Render Last Audit from Session State
audit = st.session_state.get("last_audit")
if audit:
    company = audit["company"]
    tracked_items = [
        audit["e1"], audit["e2"], audit["e3"], audit["e4"],
        audit.get("img_meta"), audit.get("img_banner"), audit.get("img_hook_frame")
    ]
    active_items = [x for x in tracked_items if isinstance(x, dict)]
    cached_count = sum(1 for x in active_items if x.get("ok") and x.get("from_cache"))
    fresh_count = sum(1 for x in active_items if x.get("ok") and not x.get("from_cache"))
    failed_count = sum(1 for x in active_items if not x.get("ok"))

    st.success(
        f"Audit Suite Loaded for **{company}** • "
        f"Cache Hits: **{cached_count}** | Freshly Generated: **{fresh_count}** | Failed: **{failed_count}**"
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Growth & SEO Scorecard",
        "💰 Pricing & Unit Economics",
        "🎨 Ad Creative Studio",
        "🚨 Social & Brand Triage"
    ])

    def render_text_tab(item, expander_title):
        if not item["ok"]:
            st.error(f"This element failed to generate: {item['error']}")
            st.caption("Click '🚀 Orchestrate Hybrid Multi-Agent Audit' again to retry only this failed element.")
            return
        cache_tag = f"Cached ({item['age']})" if item["from_cache"] else "Freshly Generated"
        st.caption(f"⚡ Powered by: **{item['engine']}** • 🕒 {cache_tag}")
        parts = item["content"].split("---DEEP_DIVE---")
        st.markdown(parts[0].strip())
        if len(parts) > 1 and parts[1].strip():
            with st.expander(expander_title):
                st.markdown(parts[1].strip())

    with tab1:
        render_text_tab(audit["e1"], "🔍 Click for Deep-Dive SEO/GEO & Competitor Analysis")

    with tab2:
        render_text_tab(audit["e2"], "🔍 Click for Pricing Tier & Margin Expansion Playbook")

    with tab3:
        render_text_tab(audit["e3"], "🔍 Click for Brand Visual DNA & Creative Rationale")
        st.markdown("---")
        st.markdown("#### 🖼️ Brand-Aligned Multimodal Ad Assets")

        if generate_images:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Meta Feed Ad Visual (1:1)**")
                m = audit.get("img_meta")
                if m and m["ok"]:
                    st.image(m["bytes"], caption=f"{company} — Meta Feed Ad (1:1)", use_container_width=True)
                    st.caption(f"🕒 {'Cached (' + m['age'] + ')' if m['from_cache'] else 'Freshly Generated'}")
                elif m:
                    st.warning(f"Meta image failed (will retry on next run): {m['error']}")

            with col2:
                st.markdown("**Display Banner Visual (16:9)**")
                b = audit.get("img_banner")
                if b and b["ok"]:
                    st.image(b["bytes"], caption=f"{company} — Display Banner (16:9)", use_container_width=True)
                    st.caption(f"🕒 {'Cached (' + b['age'] + ')' if b['from_cache'] else 'Freshly Generated'}")
                elif b:
                    st.warning(f"Banner image failed (will retry on next run): {b['error']}")

            st.markdown("**🎬 4-Second Video Ad Hook — Opening Keyframe & Storyboard (16:9)**")
            hf = audit.get("img_hook_frame")
            if hf and hf["ok"]:
                st.image(hf["bytes"], caption=f"{company} — 4s Video Hook Opening Keyframe (16:9)", use_container_width=True)
                st.caption(f"🕒 {'Cached (' + hf['age'] + ')' if hf['from_cache'] else 'Freshly Generated'}")
            elif hf:
                st.warning(f"Video hook keyframe failed (will retry on next run): {hf['error']}")

    with tab4:
        render_text_tab(audit["e4"], "🔍 Click for Rapid Brand Triage Playbook")
