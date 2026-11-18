import streamlit as st
import google.generativeai as genai

# Page Config
st.set_page_config(page_title="AI Growth & Pricing Audit Engine", page_icon="📈", layout="wide")

# App Header
st.title("📈 Executive Growth, Pricing & Creative Intelligence Audit")
st.markdown("### Powered by Soumya Ranjan Nayak's AI Strategy Framework")
st.write("Enter any target company below to run a real-time competitive benchmark complete with ad creative mockups and brand sentiment triage.")

# Sidebar for API Key & Settings
st.sidebar.header("Configuration")
api_key_input = st.sidebar.text_input("Enter your Gemini API Key", type="password")

# Input for Target Company
target_company = st.text_input("Target Company Name", placeholder="e.g., Enphase Energy, Supertails, Ather Energy")

if st.button("Run Strategic Audit & Creative Engine"):
    if not api_key_input:
        st.error("Please enter your Gemini API Key in the sidebar to proceed.")
    elif not target_company:
        st.warning("Please enter a target company name.")
    else:
        with st.spinner(f"Analyzing {target_company}, mapping competitors, and generating creative ad mockups..."):
            try:
                # Configure Gemini API with the correct, stable model name
                genai.configure(api_key=api_key_input)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = f"""
                Act as an elite Growth, Performance Marketing, and Pricing Director. 
                Perform a structured, high-value strategic audit and creative playbook for: {target_company} and its top 2 market competitors across 5 pillars.

                MANDATORY FORMATTING: Use tables, bullet points, and distinct visual callouts. Avoid long walls of text.

                Include these exact sections:
                
                1. EXECUTIVE HEALTH SCORECARD: A clean comparison table scoring each entity out of 100 across the 5 pillars.
                
                2. PILLAR 1 TO 4 BREAKDOWN:
                   - Pillar 1 (Performance, SEO, AEO & GEO)
                   - Pillar 2 (Marketing Analytics & Funnels)
                   - Pillar 3 (Pricing Strategy & Monetization Leakage)
                   - Pillar 4 (Data Analytics Maturity)
                   
                3. SPECIFIC AD CREATIVE MOCKUPS (For Pillar 1):
                   Provide 2-4 concrete ad concepts matching the brand's voice:
                   - **Google Search Ad:** (Headline, Description)
                   - **Meta Image Ad:** (Visual Concept, Primary Text, CTA)
                   - **Short Video Hook:** (First 3-second hook & script)
                   
                4. SOCIAL LISTENING & SENTIMENT TRIAGE (For Pillar 5):
                   - **Reputational Threats / Complaints to Curtail:** (Specific customer pain points)
                   - **Brand Wins / Positive Sentiment to Amplify:** (What to scale into campaigns)
                   
                5. FIRST-PERSON 90-DAY TURNAROUND PLAYBOOK:
                   - Bulleted list of immediate high-margin growth hacks.
                """
                
                response = model.generate_content(prompt)
                
                st.success("Strategic Audit & Creative Playbook Generated Successfully!")
                st.markdown("---")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
