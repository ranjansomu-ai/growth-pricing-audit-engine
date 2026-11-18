import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import io
import time

# Page Config
st.set_page_config(page_title="AI Growth & Multimodal Ad Studio", page_icon="📈", layout="wide")

# App Header
st.title("📈 Executive Growth, Pricing & Multimodal Ad Studio")
st.markdown("### Powered by Soumya Ranjan Nayak's AI Strategy Framework")
st.write("Generate a strategic executive audit accompanied by live visual image ads and short video ad hooks rendered directly in the app.")

# Sidebar Configuration
st.sidebar.header("Configuration")
api_key_input = st.sidebar.text_input("Enter your Gemini API Key", type="password")

target_company = st.text_input("Target Company Name", placeholder="e.g., Supertails, Enphase Energy, Ather Energy")

if st.button("Run Audit & Generate Multimodal Ads"):
    if not api_key_input:
        st.error("Please enter your Gemini API Key in the sidebar to proceed.")
    elif not target_company:
        st.warning("Please enter a target company name.")
    else:
        with st.spinner(f"Analyzing {target_company} and generating strategic report, visual ad graphics, and video hooks..."):
            try:
                client = genai.Client(api_key=api_key_input)
                
                # 1. Generate Strategic Audit Report Text
                audit_prompt = f"""
                Act as an elite Growth and Creative Director. Provide a concise strategic executive audit for {target_company}:
                1. Executive Growth Scorecard Summary (Table format)
                2. Core Pricing & Performance Gaps
                3. Social Listening Sentiment Triage
                """
                text_response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=audit_prompt
                )
                
                st.success("Strategic Audit & Multimodal Suite Generated Successfully!")
                st.markdown("---")
                st.markdown("### 📊 Executive Strategic Report")
                st.markdown(text_response.text)
                
                st.markdown("---")
                st.markdown("### 🖼️ Generated Visual Ad Graphics (Rendered In-App)")
                
                col1, col2 = st.columns(2)
                
                # 2. Generate Meta/Social Feed Image Ad
                with col1:
                    st.markdown("#### Meta / Instagram Feed Ad")
                    try:
                        img_result = client.models.generate_images(
                            model='imagen-3.0-generate-002',
                            prompt=f"Professional high-converting commercial social media ad visual for {target_company}, vibrant modern design, high quality commercial photography",
                            config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="1:1")
                        )
                        for generated_image in img_result.generated_images:
                            image = Image.open(io.BytesIO(generated_image.image.image_bytes))
                            st.image(image, caption=f"Meta Ad Mockup for {target_company}", use_column_width=True)
                    except Exception as img_err:
                        st.warning(f"Image generation fallback: Visual creative concept layout for {target_company}.")
                
                # 3. Generate Display/Banner Ad
                with col2:
                    st.markdown("#### Display / Banner Ad")
                    try:
                        img_result_2 = client.models.generate_images(
                            model='imagen-3.0-generate-002',
                            prompt=f"Sleek digital banner advertisement graphic for {target_company}, value proposition focus, clean typography layout",
                            config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="16:9")
                        )
                        for generated_image in img_result_2.generated_images:
                            image2 = Image.open(io.BytesIO(generated_image.image.image_bytes))
                            st.image(image2, caption=f"Banner Ad Mockup for {target_company}", use_column_width=True)
                    except Exception as img_err:
                        st.warning(f"Image generation fallback: Banner creative layout for {target_company}.")
                
                st.markdown("---")
                st.markdown("### 🎬 Generated Short Video Ad Hook (Rendered In-App)")
                
                with st.spinner("Rendering cinematic short video ad hook..."):
                    try:
                        video_prompt = f"Cinematic short video ad hook for {target_company}, high energy product showcase, motion graphics and clean lighting"
                        operation = client.models.generate_videos(
                            model="veo-3.1-fast-generate-preview",
                            prompt=video_prompt,
                            config=types.GenerateVideosConfig(aspect_ratio="16:9", durationSeconds="4")
                        )
                        
                        # Poll operation until complete
                        while not operation.done:
                            time.sleep(5)
                            operation = client.operations.get(operation)
                        
                        if operation.response and operation.response.generated_videos:
                            gen_video = operation.response.generated_videos[0]
                            video_bytes = client.files.download(file=gen_video.video)
                            st.video(video_bytes)
                    except Exception as vid_err:
                        st.info(f"🎬 **Video Ad Hook Blueprint (Veo Ready):** Dynamic 4-second opening featuring customer satisfaction zoom-in, cinematic audio cue, and bold value-prop overlay for {target_company}.")

            except Exception as e:
                st.error(f"An error occurred: {e}")
