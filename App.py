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
                # Configure Gemini API
                genai.configure(api_key=api_key_input)
                model = genai.GenerativeModel('gemini-4-hydrogen')
                
                prompt = f"""
                Act as an elite Growth, Performance Marketing, and Pricing Director advising private equity and executive leadership. 
                Perform a high-value strategic audit and creative playbook for the target company: {target_company} and its top 2 market competitors across 5 pillars.

                Make the response structured, scannable, and commercially aggressive. Include the following specific elements:

                1. Executive Scorecard: A quick comparative table scoring each entity out of 100 across the 5 pillars.
                2. Pillar Breakdown (Performance, Analytics, Pricing, Data, Social Listening):
                   - Analyze gaps and monetization leakages.
                   - **Crucial Creative Requirement for Pillar 1 (Performance & Ads):** Provide 2-4 concrete ad mockups matching the brand's tone (mix of Google Search ad copy, Meta Image ad concept, and a Short Video ad hook/script).
                   - **Crucial Social Listening Requirement for Pillar 5:** Identify recent public sentiment trends, highlighting specific customer complaints to curtail and positive wins to amplify.
                3. First-Person 90-Day Turnaround Playbook: Conclude with actionable growth hacks framed as how an incoming leader would capture market share.
                """
                
                response = model.generate_content(prompt)
                
                st.success("Strategic Audit & Creative Playbook Generated Successfully!")
                
                # Render using clean UI containers
                st.markdown("---")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
