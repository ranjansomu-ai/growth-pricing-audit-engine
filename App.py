import streamlit as st
from google import genai
import time

# Page Config
st.set_page_config(page_title="AI Growth & Ad Creative Engine", page_icon="📈", layout="wide")

# App Header
st.title("📈 Executive Growth, Pricing & Ad Creative Intelligence Suite")
st.markdown("### Powered by Soumya Ranjan Nayak's AI Strategy Framework")
st.write("Generate a strategic executive audit accompanied by visual ad mockups and short video ad hooks.")

# Sidebar Configuration
st.sidebar.header("Configuration")
api_key_input = st.sidebar.text_input("Enter your Gemini API Key", type="password")

target_company = st.text_input("Target Company Name", placeholder="e.g., Supertails, Enphase Energy, Ather Energy")

if st.button("Run Audit & Generate Creative Suite"):
    if not api_key_input:
        st.error("Please enter your Gemini API Key in the sidebar to proceed.")
    elif not target_company:
        st.warning("Please enter a target company name.")
    else:
        with st.spinner(f"Analyzing {target_company} and generating strategic & creative assets..."):
            try:
                client = genai.Client(api_key=api_key_input)
                
                prompt = f"""
                Act as an elite Growth, Performance Marketing, and Creative Director. 
                Perform a structured strategic audit and visual ad creative suite for: {target_company} and its competitors.

                Include these exact formatted sections:

                1. EXECUTIVE GROWTH SCORECARD TABLE
                   - Clean comparison table scoring entities across pillars (Performance, Analytics, Pricing, Data, Social).

                2. STRATEGIC PILLAR BREAKDOWN
                   - Core growth gaps, monetization leakages, and AEO/GEO readiness.

                3. RENDER-READY AD CREATIVE CONCEPTS (Visual Mockup Blueprints)
                   - **🔍 Google Search Ad Concept:** (Headlines, Display URL, Description)
                   - **🖼️ Meta Image Ad Concept:** (High-converting visual description, primary text, CTA button)
                   - **🎬 Short Video Ad Hook (First 3 Seconds):** (Cinematic visual hook, audio cue, and text overlay script)

                4. SOCIAL LISTENING & SENTIMENT TRIAGE
                   - **🚨 Customer Complaints to Curtail:**
                   - **🚀 Positive Sentiment to Amplify:**

                5. 90-DAY TURNAROUND PLAYBOOK
                   - Immediate high-margin strategic growth hacks.
                """
                
                # Automatic retry loop to handle temporary 503 server traffic spikes
                response = None
                for attempt in range(3):
                    try:
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=prompt
                        )
                        break
                    except Exception as api_err:
                        if attempt == 2:
                            raise api_err
                        time.sleep(2) # Wait 2 seconds before retrying
                
                st.success("Audit & Creative Suite Generated Successfully!")
                st.markdown("---")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"Server is experiencing high traffic. Please wait 10 seconds and click 'Run Audit' again. Details: {e}")
