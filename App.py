import streamlit as st
from google import genai

# Page Config
st.set_page_config(page_title="AI Growth & Creative Command Center", page_icon="📈", layout="wide")

# App Header
st.title("📈 Executive Growth, Pricing & Creative Intelligence Suite")
st.markdown("### Powered by Soumya Ranjan Nayak's AI Strategy Framework")
st.write("Enter a target company once to orchestrate multi-agent audits across performance, pricing, creative ads, and brand sentiment.")

# Sidebar Configuration
st.sidebar.header("Configuration")
api_key_input = st.sidebar.text_input("Enter your Gemini API Key", type="password")

# Single Unified Input at the Top
target_company = st.text_input("Target Company Name", placeholder="e.g., Supertails, Enphase Energy, Ather Energy")

if st.button("🚀 Orchestrate Multi-Agent Audit & Creative Suite"):
    if not api_key_input:
        st.error("Please enter your Gemini API Key in the sidebar to proceed.")
    elif not target_company:
        st.warning("Please enter a target company name.")
    else:
        with st.spinner(f"Orchestrating multi-agent audit pipelines for {target_company}..."):
            try:
                client = genai.Client(api_key=api_key_input)
                
                # Agent 1: Overview & Scorecard Prompt
                agent1_prompt = f"Act as Chief Growth Officer. Provide a high-level executive health scorecard table and key posture summary for {target_company} across 5 core growth pillars. Use hard-hitting bullet points."
                res1 = client.models.generate_content(model='gemini-3.8-flash', contents=agent1_prompt)
                
                # Agent 2: Pricing & Unit Economics Prompt
                agent2_prompt = f"Act as Chief Pricing Officer. Analyze unit economics, LTV:CAC, monetization leakages, and pricing elasticity for {target_company}. Keep it punchy with collapsible deep dives."
                res2 = client.models.generate_content(model='gemini-3.8-flash', contents=agent2_prompt)
                
                # Agent 3: Creative & Ad Strategy Prompt
                agent3_prompt = f"Act as Creative Director. Outline high-converting ad copy and visual frameworks for {target_company}: Google Search ad copy, Meta visual concepts, and short video hook scripts."
                res3 = client.models.generate_content(model='gemini-3.8-flash', contents=agent3_prompt)
                
                # Agent 4: Social Triage & Brand Risk Prompt
                agent4_prompt = f"Act as Brand Reputation Director. Triage recent customer sentiment, identify friction points to curtail, and positive brand wins to amplify for {target_company}."
                res4 = client.models.generate_content(model='gemini-3.8-flash', contents=agent4_prompt)
                
                st.success("Multi-Agent Audit Orchestrated Successfully!")
                st.markdown("---")
                
                # Multi-Agent Tabbed Interface
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📊 Executive Scorecard", 
                    "💰 Pricing & Unit Economics", 
                    "🎨 Ad Creative Studio", 
                    "🚨 Brand & Social Triage"
                ])
                
                with tab1:
                    st.markdown("### Executive Overview & Health Scorecard")
                    st.markdown(res1.text)
                    with st.expander("🔍 Click to view deep-dive strategic analysis"):
                        st.markdown("Detailed methodology, market benchmarks, and competitor positioning matrices.")
                
                with tab2:
                    st.markdown("### Pricing Architecture & Monetization Levers")
                    st.markdown(res2.text)
                    with st.expander("🔍 Click to view pricing sensitivity & margin breakdown"):
                        st.markdown("Granular breakdown of subscription tier leakage and bundling efficiency.")
                
                with tab3:
                    st.markdown("### Ad Creative & Multimodal Studio")
                    st.markdown(res3.text)
                    
                    st.markdown("---")
                    st.markdown("#### Live Render-Ready Multimodal Slots (Placeholder Mode)")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info("🖼️ **Meta Feed Ad Visual Slot:** [Awaiting Cloud Billing / Imagen API Key Integration]")
                    with col2:
                        st.info("📊 **Display Banner Ad Slot:** [Awaiting Cloud Billing / Imagen API Key Integration]")
                    
                    st.info("🎬 **Short Video Ad Hook Slot:** [Awaiting Cloud Billing / Veo API Key Integration]")
                
                with tab4:
                    st.markdown("### Social Listening & Brand Sentiment Triage")
                    st.markdown(res4.text)
                    with st.expander("🔍 Click to view verbatim customer feedback & risk register"):
                        st.markdown("Aggregated sentiment logs and threat mitigation playbooks.")

            except Exception as e:
                st.error(f"An error occurred during multi-agent orchestration: {e}")
