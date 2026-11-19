import streamlit as st
from google import genai
from google.genai import types
import anthropic

# Page Config
st.set_page_config(page_title="AI Growth & Creative Command Center", page_icon="📈", layout="wide")

# App Header
st.title("📈 Executive Growth, Pricing & Creative Command Center")
st.markdown("### Hybrid Multi-Agent Architecture (Gemini + Claude)")
st.write("Enter a target company once to orchestrate specialized sub-agents with automatic cross-provider failover.")

# Sidebar Configuration
st.sidebar.header("🔑 API Credentials")
gemini_key = st.sidebar.text_input("Gemini API Key (Google AI Studio)", type="password")
claude_key = st.sidebar.text_input("Anthropic API Key (Claude - Optional)", type="password")
st.sidebar.caption("Tip: Enter both keys for true hybrid routing + failover, or just one key to run all agents on that provider.")

# Helper Functions for Multi-Model Routing & Failover
def call_gemini(prompt, use_search=False):
    if not gemini_key:
        raise ValueError("Gemini API key not provided.")
    client = genai.Client(api_key=gemini_key)
    config = types.GenerateContentConfig(
        tools=[{"google_search": {}}] if use_search else None
    )
    # Try current production Flash/Hydrogen endpoints in order
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
    """Routes to preferred provider and automatically fails over to the backup provider."""
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

# Single Unified Input
target_company = st.text_input("Target Company Name", placeholder="e.g., Supertails, Enphase Energy, Ather Energy")

if st.button("🚀 Orchestrate Hybrid Multi-Agent Audit"):
    if not gemini_key and not claude_key:
        st.error("Please enter at least one API key (Gemini or Claude) in the sidebar.")
    elif not target_company:
        st.warning("Please enter a target company name.")
    else:
        with st.spinner(f"Orchestrating specialized agents for {target_company}..."):
            
            # Agent 1: Growth & SEO/GEO (Prefers Gemini + Live Search Grounding)
            p1 = f"""
            Act as Chief Growth Officer auditing {target_company}.
            STRICT FORMATTING:
            - Start with a compact Markdown scorecard table (Pillar | Score /100 | Key Gap) across Paid Search, SEO/GEO, Funnel CRO, Pricing, and Social.
            - Follow with EXACTLY 4 short, hard-hitting bullet points (max 15 words per bullet) on top growth levers.
            - End with '---DEEP_DIVE---' followed by a concise bulleted breakdown of AEO/GEO visibility and competitor gaps.
            """
            res1, engine1 = route_agent(p1, preferred="gemini", use_search=True)

            # Agent 2: Pricing & Unit Economics (Prefers Claude for commercial logic)
            p2 = f"""
            Act as VP of Pricing Strategy analyzing {target_company}.
            STRICT FORMATTING:
            - Output EXACTLY 4 punchy bullet points (max 15 words per bullet) identifying monetization leaks, LTV:CAC friction, and bundling opportunities.
            - End with '---DEEP_DIVE---' followed by a structured bulleted breakdown of tier optimization and margin expansion tactics.
            """
            res2, engine2 = route_agent(p2, preferred="claude")

            # Agent 3: Ad Creative Studio (Prefers Claude for copy; media slots ready for Gemini Imagen/Omni)
            p3 = f"""
            Act as Performance Creative Director for {target_company}.
            STRICT FORMATTING:
            - Output compact, high-converting ad copy in 3 short bulleted blocks:
              1. Google Search Ad (2 Headlines + 1 Description)
              2. Meta Feed Ad (Primary Text + Headline + CTA)
              3. 4-Second Video Hook (Visual Scene + Voiceover/Text Overlay)
            - End with '---DEEP_DIVE---' followed by exact image/video generation prompts ready for API rendering.
            """
            res3, engine3 = route_agent(p3, preferred="claude")

            # Agent 4: Social Triage (Prefers Gemini for fast sentiment synthesis)
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
            st.markdown("#### 🖼️ Live Multimodal Ad Slots (Ready for Paid Billing Activation)")
            col1, col2 = st.columns(2)
            with col1:
                st.info("🖼️ **Meta Feed Ad Visual (1:1)** — *Placeholder reserved for `gemini-nano-banana-2.1`*")
            with col2:
                st.info("📊 **Display Banner Visual (16:9)** — *Placeholder reserved for `gemini-nano-banana-2.1`*")
            st.info("🎬 **4-Second Video Hook (16:9)** — *Placeholder reserved for `gemini-omni-1.2-flash`*")

        with tab4:
            render_tab(res4, engine4, "🔍 Click for Rapid Brand Triage Playbook")
