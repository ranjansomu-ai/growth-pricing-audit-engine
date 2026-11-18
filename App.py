import streamlit as st
import google.generativeai as genai

# Page Config
st.set_page_config(page_title="AI Growth & Pricing Audit Engine", page_icon="📈", layout="wide")

# App Header
st.title("📈 Executive Growth, Pricing & AEO/GEO Intelligence Audit")
st.markdown("### Powered by Soumya Ranjan Nayak's AI Strategy Framework")
st.write("Enter any target company below to run a real-time competitive benchmark across Performance Marketing, Pricing, Analytics, and AEO/GEO readiness.")

# Sidebar for API Key
st.sidebar.header("Configuration")
api_key_input = st.sidebar.text_input("Enter your Gemini API Key", type="password")

# Input for Target Company
target_company = st.text_input("Target Company Name", placeholder="e.g., Enphase Energy, Zoho, Ather Energy")

if st.button("Run Strategic Audit"):
    if not api_key_input:
        st.error("Please enter your Gemini API Key in the sidebar to proceed.")
    elif not target_company:
        st.warning("Please enter a target company name.")
    else:
        with st.spinner(f"Analyzing {target_company} and its top 2 competitors across 5 strategic pillars..."):
            try:
                # Configure Gemini API
                genai.configure(api_key=api_key_input)
                # Using Gemini 1.5 Flash for fast, high-quality analysis
                model = genai.GenerativeModel('gemini-4-hydrogen')
                
                # Master Prompt Payload
                prompt = f"""
                Act as an elite Growth, Performance Marketing, and Pricing Director advising private equity and executive leadership. 
                I want to audit a target company and its two main market competitors to deliver a high-value strategic intelligence report.

                Target Company: {target_company}

                Perform a comparative analysis across these 5 strategic pillars for all 3 entities (Target Company vs. Competitor 1 vs. Competitor 2). Do not just describe what they are doing; diagnose their weaknesses and provide actionable growth plays.

                1. Performance Marketing, SEO, AEO & GEO
                   - Analyze paid media footprint and estimated channel mix.
                   - Specifically evaluate AEO (Answer Engine Optimization) & GEO (Generative Engine Optimization) readiness: How well does each brand show up when AI assistants (ChatGPT, Perplexity, Gemini) recommend solutions in this category?
                   - Identify gaps where the target company is losing search real estate.

                2. Marketing Analytics & Funnels
                   - Evaluate conversion paths, tracking setup efficiency, and friction points in the user journey.
                   - Spot drop-off zones or attribution blind spots.

                3. Pricing Strategy & Monetization
                   - Analyze monetization models, tier structures, and value metrics (e.g., usage-based vs. seat-based).
                   - Identify "Monetization Leakage": Where is the target company leaving money on the table or failing to capture maximum customer lifetime value (LTV) compared to competitors?

                4. Data Analytics Maturity
                   - Assess data instrumentation health, product-led growth (PLG) analytics signals, and martech stack sophistication.

                5. Social Listening & Brand Sentiment
                   - Summarize public customer sentiment, recurring product/service complaints, and community perception pulled from public discussions.

                Formatting & Value Requirements:
                - Start with an "Executive Growth Health Scorecard" comparing the 3 entities across a 100-point scale.
                - For each pillar, conclude with a bolded "Growth Hack & Strategic Fix" callout box specifically designed for the target company to outmaneuver its rivals.
                - Maintain an authoritative, sharp, commercial tone suitable for a CMO or CEO review.
                """
                
                response = model.generate_content(prompt)
                
                st.success("Audit Complete!")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
