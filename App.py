import streamlit as st
from google import genai
from google.genai import types
import anthropic
from PIL import Image
import io
import base64
import time

# Page Config
st.set_page_config(page_title="AI Growth & Creative Command Center", page_icon="📈", layout="wide")

# App Header
st.title("📈 Executive Growth, Pricing & Creative Command Center")
st.markdown("### Hybrid Multi-Agent Architecture (Gemini + Claude)")
st.write("Enter a target company once to orchestrate specialized sub-agents and render brand-aligned image & video ad assets.")

# Sidebar Configuration
st.sidebar.header("🔑 API Credentials")
gemini_key = st.sidebar.text_input("Gemini API Key (Paid Billing Enabled)", type="password")
claude_key = st.sidebar.text_input("Anthropic API Key (Claude - Optional)", type="password")
generate_images = st.sidebar.checkbox("Generate Live Brand Image Ads", value=True)
generate_video = st.sidebar.checkbox("Generate Live Video Ad Hook (Omni Flash)", value=True)
st.sidebar.caption("Tip: Toggle media checkboxes off while testing text-only audits to save media credits.")

# Helper Functions for Multi-Model Routing & Failover
def call_gemini(prompt, use_search=False):
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
            return res.text, f"Gemini ({model_id})"
        except Exception as e:
            last_err = e
    raise last_err

def call_claude(prompt):
    if not claude_key:
        raise ValueError("Claude API key not provided.")
    client = anthropic.Anthropic(api_key=claude_key)
    msg = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text, "Claude (Sonnet 5.5)"

def route_agent(prompt, preferred="gemini", use_search=False):
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
    return f"⚠️ Agent temporarily unavailable. Details: {' | '.join(errors)}", "Unavailable"

def extract_brand_visual_dna(company):
    """Uses live Search grounding to extract brand colors, typography mood, customer persona, and active ad style."""
    prompt = f"""
    Research {company}'s current brand design language, visual identity, and active performance ads (Meta/Instagram/Google).
    Return ONLY a concise 2-sentence visual art-direction brief covering:
    1. Exact brand color palette, UI card aesthetic, and visual tone.
    2. Authentic target customer/subject setting and key value-prop badge style used in their real ads.
    Do not include intro text or bullet points.
    """
    dna, _ = call_gemini(prompt, use_search=True)
    return dna.strip()

def generate_ad_image(prompt, aspect_ratio="1:1"):
    """Generates a brand-aligned image using Nano Banana 2 (gemini-3.1-flash-image)."""
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
            return Image.open(io.BytesIO(part.inline_data.data))
    raise RuntimeError("No image bytes returned by model.")

def generate_ad_video_omni(prompt):
    """Generates a short video hook via Gemini Omni Flash Interactions API (Developer API compatible)."""
    client = genai.Client(api_key=gemini_key)
    interaction = client.interactions.create(
        model="gemini-omni-1.2-flash",
        input=prompt,
        response_modalities=["VIDEO"],
        generation_config={
            "video_config": {
                "aspect_ratio": "16:9",
                "duration_seconds": 4
            }
        }
    )
    # Poll if background processing is returned
    while getattr(interaction, "status", None) in ("in_progress", "queued", "running"):
        time.sleep(4)
        interaction = client.interactions.get(interaction.id)

    for output in getattr(interaction, "outputs", []) or []:
        if getattr(output, "type", None) == "video" and getattr(output, "data", None):
            video_data = output.data
            if isinstance(video_data, str):
                return base64.b64decode(video_data)
            return video_data
    raise RuntimeError(f"Video output not found in interaction response (status: {getattr(interaction, 'status', 'unknown')}).")

# Single Unified Input
target_company = st.text_input("Target Company Name", placeholder="e.g., Supertails, Enphase Energy, Ather Energy")

if st.button("🚀 Orchestrate Hybrid Multi-Agent Audit"):
    if not gemini_key and not claude_key:
        st.error("Please enter at least one API key (Gemini or Claude) in the sidebar.")
    elif not target_company:
        st.warning("Please enter a target company name.")
    else:
        with st.spinner(f"Orchestrating specialized agents & brand DNA extraction for {target_company}..."):
            
            # Extract Brand Visual DNA first if Gemini key is available
            brand_dna = f"Authentic commercial brand aesthetic for {target_company}."
            if gemini_key:
                try:
                    brand_dna = extract_brand_visual_dna(target_company)
                except Exception:
                    pass

            # Agent 1: Growth & SEO/GEO
            p1 = f"""
            Act as Chief Growth Officer auditing {target_company}.
            STRICT FORMATTING:
            - Start with a compact Markdown scorecard table (Pillar | Score /100 | Key Gap) across Paid Search, SEO/GEO, Funnel CRO, Pricing, and Social.
            - Follow with EXACTLY 4 short, hard-hitting bullet points (max 15 words per bullet) on top growth levers.
            - End with '---DEEP_DIVE---' followed by a concise bulleted breakdown of AEO/GEO visibility and competitor gaps.
            """
            res1, engine1 = route_agent(p1, preferred="gemini", use_search=True)

            # Agent 2: Pricing & Unit Economics
            p2 = f"""
            Act as VP of Pricing Strategy analyzing {target_company}.
            STRICT FORMATTING:
            - Output EXACTLY 4 punchy bullet points (max 15 words per bullet) identifying monetization leaks, LTV:CAC friction, and bundling opportunities.
            - End with '---DEEP_DIVE---' followed by a structured bulleted breakdown of tier optimization and margin expansion tactics.
            """
            res2, engine2 = route_agent(p2, preferred="claude")

            # Agent 3: Ad Creative Studio
            p3 = f"""
            Act as Performance Creative Director for {target_company}. Brand Visual DNA: {brand_dna}
            STRICT FORMATTING:
            - Output compact, high-converting ad copy in 3 short bulleted blocks:
              1. Google Search Ad (2 Headlines + 1 Description)
              2. Meta Feed Ad (Primary Text + Headline + CTA)
              3. 4-Second Video Hook (Visual Scene + Voiceover/Text Overlay)
            - End with '---DEEP_DIVE---' followed by the extracted Brand Visual DNA and creative rationale.
            """
            res3, engine3 = route_agent(p3, preferred="claude")

            # Agent 4: Social Triage
            p4 = f"""
            Act as Brand Reputation Lead for {target_company}.
            STRICT FORMATTING:
            - Output 2 short bullet points under '🚨 Friction to Curtail' and 2 short bullet points under '🚀 Wins to Amplify' (max 15 words per bullet).
            - End with '---DEEP_DIVE---' followed by a 3-step rapid response playbook.
            """
            res4, engine4 = route_agent(p4, preferred="gemini", use_search=True)

        st.success(f"Multi-Agent Suite Complete for {target_company}!")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Growth & SEO Scorecard",
            "💰 Pricing & Unit Economics",
            "🎨 Ad Creative Studio",
            "🚨 Social & Brand Triage"
        ])

        def render_tab(content, engine_label, expander_title):
            st.caption(f"⚡ Powered by: **{engine_label}**")
            parts = content.split("---DEEP_DIVE---")
            st.markdown(parts[0].strip())
            if len(parts) > 1 and parts[1].strip():
                with st.expander(expander_title):
                    st.markdown(parts[1].strip())

        with tab1:
            render_tab(res1, engine1, "🔍 Click for Deep-Dive SEO/GEO & Competitor Analysis")

        with tab2:
            render_tab(res2, engine2, "🔍 Click for Pricing Tier & Margin Expansion Playbook")

        with tab3:
            render_tab(res3, engine3, "🔍 Click for Brand Visual DNA & Creative Rationale")
            st.markdown("---")
            st.markdown("#### 🖼️ Live Brand-Aligned Multimodal Ad Assets")

            if gemini_key and (generate_images or generate_video):
                if generate_images:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Meta Feed Ad Visual (1:1)**")
                        with st.spinner("Rendering brand-matched Meta Feed creative..."):
                            try:
                                meta_prompt = (
                                    f"Create an authentic high-converting Instagram/Meta feed advertisement creative for {target_company}. "
                                    f"Strictly follow this brand design language: {brand_dna} "
                                    f"Clean commercial composition, warm authentic photography, minimal clean callout badge, no cluttered text."
                                )
                                img_meta = generate_ad_image(meta_prompt, aspect_ratio="1:1")
                                st.image(img_meta, caption=f"{target_company} — Meta Feed Ad (1:1)", use_container_width=True)
                            except Exception as e:
                                st.warning(f"Meta image render notice: {e}")

                    with col2:
                        st.markdown("**Display Banner Visual (16:9)**")
                        with st.spinner("Rendering brand-matched Display Banner..."):
                            try:
                                banner_prompt = (
                                    f"Create a sleek widescreen digital display banner ad creative for {target_company}. "
                                    f"Strictly follow this brand design language: {brand_dna} "
                                    f"Hero product/service showcase, high visual contrast, clean modern layout."
                                )
                                img_banner = generate_ad_image(banner_prompt, aspect_ratio="16:9")
                                st.image(img_banner, caption=f"{target_company} — Display Banner (16:9)", use_container_width=True)
                            except Exception as e:
                                st.warning(f"Banner image render notice: {e}")

                if generate_video:
                    st.markdown("**🎬 4-Second Video Ad Hook (16:9 via Gemini Omni Flash)**")
                    with st.spinner("Rendering 4-second video hook via Interactions API (15–40 seconds)..."):
                        try:
                            vid_prompt = (
                                f"4-second high-converting commercial social video ad hook for {target_company}. "
                                f"Visual style and brand identity: {brand_dna} "
                                f"Dynamic camera push-in, bright natural commercial lighting, upbeat energetic audio cue."
                            )
                            video_bytes = generate_ad_video_omni(vid_prompt)
                            st.video(video_bytes)
                        except Exception as e:
                            st.warning(f"Video render notice: {e}")
            elif not gemini_key:
                st.info("Enter your Gemini API Key in the sidebar to render live brand-aligned images and video hooks.")
            else:
                st.info("Live media generation is paused via the sidebar toggles.")

        with tab4:
            render_tab(res4, engine4, "🔍 Click for Rapid Brand Triage Playbook")
