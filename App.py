import streamlit as st
from google import genai
from google.genai import types
import anthropic
from PIL import Image
import io
import time

# Page Config
st.set_page_config(page_title="AI Growth & Creative Command Center", page_icon="📈", layout="wide")

# App Header
st.title("📈 Executive Growth, Pricing & Creative Command Center")
st.markdown("### Hybrid Multi-Agent Architecture (Gemini + Claude)")
st.write("Enter a target company once to orchestrate specialized sub-agents and render live image & video ad assets.")

# Sidebar Configuration
st.sidebar.header("🔑 API Credentials")
gemini_key = st.sidebar.text_input("Gemini API Key (Paid Billing Enabled)", type="password")
claude_key = st.sidebar.text_input("Anthropic API Key (Claude - Optional)", type="password")
generate_media = st.sidebar.checkbox("Generate Live Image & Video Ads", value=True)
st.sidebar.caption("Uncheck 'Generate Live Image & Video Ads' when testing text-only audits to save media tokens.")

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

def generate_ad_image(prompt, aspect_ratio="1:1"):
    """Generates an image using Nano Banana 2 (gemini-3.1-flash-image)."""
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

def generate_ad_video(prompt):
    """Generates a short 4-second video hook using Gemini Omni Flash (gemini-omni-1.2-flash)."""
    client = genai.Client(api_key=gemini_key)
    operation = client.models.generate_videos(
        model="gemini-omni-1.2-flash",
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=4
        )
    )
    while not operation.done:
        time.sleep(5)
        operation = client.operations.get(operation)
    if operation.response and operation.response.generated_videos:
        gen_video = operation.response.generated_videos[0]
        return client.files.download(file=gen_video.video)
    raise RuntimeError("No video returned by model.")

# Single Unified Input
target_company = st.text_input("Target Company Name", placeholder="e.g., Supertails, Enphase Energy, Ather Energy")

if st.button("🚀 Orchestrate Hybrid Multi-Agent Audit"):
    if not gemini_key and not claude_key:
        st.error("Please enter at least one API key (Gemini or Claude) in the sidebar.")
    elif not target_company:
        st.warning("Please enter a target company name.")
    else:
        with st.spinner(f"Orchestrating specialized agents for {target_company}..."):
            
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
            Act as Performance Creative Director for {target_company}.
            STRICT FORMATTING:
            - Output compact, high-converting ad copy in 3 short bulleted blocks:
              1. Google Search Ad (2 Headlines + 1 Description)
              2. Meta Feed Ad (Primary Text + Headline + CTA)
              3. 4-Second Video Hook (Visual Scene + Voiceover/Text Overlay)
            - End with '---DEEP_DIVE---' followed by exact image/video generation prompts used for rendering.
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
            render_tab(res3, engine3, "🔍 Click for Raw Media Generation Prompts")
            st.markdown("---")
            st.markdown("#### 🖼️ Live Generated Multimodal Ad Assets")

            if generate_media and gemini_key:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Meta Feed Ad Visual (1:1)**")
                    with st.spinner("Rendering Meta Feed creative..."):
                        try:
                            meta_prompt = f"High-converting commercial Instagram/Meta feed ad visual for {target_company}, vibrant modern studio photography, clean composition, minimal bold visual hook, no cluttered text"
                            img_meta = generate_ad_image(meta_prompt, aspect_ratio="1:1")
                            st.image(img_meta, caption=f"{target_company} — Meta Feed Ad (1:1)", use_container_width=True)
                        except Exception as e:
                            st.warning(f"Meta image render notice: {e}")

                with col2:
                    st.markdown("**Display Banner Visual (16:9)**")
                    with st.spinner("Rendering Display Banner creative..."):
                        try:
                            banner_prompt = f"Sleek widescreen digital display banner ad creative for {target_company}, crisp product/service hero shot, modern brand aesthetic, clean layout"
                            img_banner = generate_ad_image(banner_prompt, aspect_ratio="16:9")
                            st.image(img_banner, caption=f"{target_company} — Display Banner (16:9)", use_container_width=True)
                        except Exception as e:
                            st.warning(f"Banner image render notice: {e}")

                st.markdown("**🎬 4-Second Video Ad Hook (16:9 with Native Audio)**")
                with st.spinner("Rendering 4-second video hook (usually takes 15–40 seconds)..."):
                    try:
                        vid_prompt = f"Cinematic 4-second commercial social video ad hook for {target_company}, dynamic camera push-in, bright commercial lighting, energetic upbeat background audio"
                        video_bytes = generate_ad_video(vid_prompt)
                        st.video(video_bytes)
                    except Exception as e:
                        st.warning(f"Video render notice: {e}")
            elif not gemini_key:
                st.info("Enter your Gemini API Key in the sidebar to render live images and video hooks.")
            else:
                st.info("Live media generation is paused via the sidebar toggle.")

        with tab4:
            render_tab(res4, engine4, "🔍 Click for Rapid Brand Triage Playbook")
