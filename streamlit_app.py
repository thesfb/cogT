import streamlit as st
import requests
import time
import json

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"  # Use http://127.0.0.1 for local development

# List of VIPs available in the mock_data.py file
AVAILABLE_VIPS = [
    "leomaxwell", "arthurvance", "dranyasharma", "kenjitanaka",
    "drelaravoss", "jaxvolkov", "silasthorne", "rohandesai",
    "juliancroft", "chefmateorossi"
]

# --- Helper Functions to Interact with API ---

def check_api_status():
    """Checks if the backend API is online."""
    try:
        # Increased timeout to 30 seconds to allow the backend models to load
        response = requests.get(f"{API_BASE_URL}/health", timeout=30)
        if response.status_code == 200:
            return True, response.json()
        return False, {"status": "error", "detail": f"Status code: {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return False, {"status": "error", "detail": "Connection failed. Is the backend running?"}

def build_twin(twitter_handle):
    """Sends a request to build a cognitive twin."""
    url = f"{API_BASE_URL}/build-twin"
    payload = {"twitter_handle": twitter_handle}
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"API request failed: {e}"}

def trigger_scanners():
    """Sends a request to trigger the background scanners."""
    url = f"{API_BASE_URL}/scanners/trigger"
    try:
        response = requests.post(url, timeout=10)
        if response.status_code == 202:
            return response.json()
        return {"status": "error", "message": f"Failed with status code: {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"API request failed: {e}"}

def analyze_threat(payload):
    """Sends content to the threat analysis endpoint."""
    url = f"{API_BASE_URL}/analyze/threat"
    try:
        response = requests.post(url, json=payload, timeout=60)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"API request failed: {e}"}


# --- Streamlit UI ---

st.set_page_config(page_title="VIP Guardian", layout="wide", initial_sidebar_state="expanded")

# --- Sidebar ---
with st.sidebar:
    st.title("🛡️ VIP Guardian")
    st.markdown("Your real-time digital impersonation shield.")

    # API Status Check
    st.subheader("API Status")
    api_online, api_details = check_api_status()
    if api_online:
        st.success("Backend is Online")
        with st.expander("Show Details"):
            st.json(api_details)
    else:
        st.error("Backend is Offline")
        st.json(api_details)
        st.warning("Please start the FastAPI backend to use this dashboard.")

    st.divider()

    # Twin Builder
    st.subheader("Cognitive Twin Builder")
    selected_vip_build = st.selectbox("Select a VIP to build/rebuild", options=AVAILABLE_VIPS, key="vip_build")
    if st.button("Build Digital Twin"):
        if not api_online:
            st.error("Cannot build twin. Backend is offline.")
        else:
            with st.spinner(f"Building twin for @{selected_vip_build}... This may take a moment."):
                result = build_twin(selected_vip_build)
                if result.get("status") == "success":
                    st.success(f"Successfully built twin for @{selected_vip_build}!")
                    st.write(f"Posts processed: {result.get('posts_added')}")
                else:
                    st.error(f"Error: {result.get('message', 'Unknown error')}")

    st.divider()

    # Scanner Control
    st.subheader("Platform Scanners")
    if st.button("Trigger Reddit & Telegram Scan"):
        if not api_online:
            st.error("Cannot trigger scanners. Backend is offline.")
        else:
            with st.spinner("Sending scan command to backend..."):
                result = trigger_scanners()
                if result and "message" in result:
                    st.success(result["message"])
                else:
                    st.error(f"Failed to trigger scanners: {result.get('message', 'Unknown error')}")
    st.info("Scans run in the background. Check your FastAPI console for progress.", icon="ℹ️")


# --- Main Content ---
st.title("Threat Analysis Center")
st.markdown("Manually submit content to analyze it against a VIP's digital twin.")

if not api_online:
    st.error("Threat analysis is disabled because the backend is offline.", icon="🚨")
else:
    # --- Input Form ---
    col1, col2 = st.columns(2)
    with col1:
        vip_to_analyze = st.selectbox("Select VIP to analyze against", options=AVAILABLE_VIPS, key="vip_analyze")
        text_to_check = st.text_area("Text to Analyze", height=200, placeholder="Paste the suspicious text content here...")

    with col2:
        image_url = st.text_input("Image URL (Optional)", placeholder="https://example.com/image.jpg")
        video_url = st.text_input("Video URL (Optional)", placeholder="https://example.com/video.mp4")
        source_url = st.text_input("Source URL (Optional)", placeholder="https://reddit.com/post/...")
    
    analyze_button = st.button("Analyze Threat", type="primary", use_container_width=True)

    if analyze_button:
        if not vip_to_analyze or not text_to_check:
            st.warning("Please select a VIP and enter text to analyze.")
        else:
            payload = {
                "twitter_handle": vip_to_analyze,
                "text_to_check": text_to_check,
                "image_url": image_url if image_url else None,
                "video_url": video_url if video_url else None,
                "source_url": source_url if source_url else None,
                "platform": "Manual Analysis",
                "enable_alerts": True
            }

            with st.spinner("AI analysis in progress... This can take up to a minute for videos."):
                analysis_result = analyze_threat(payload)

            # --- Results Display ---
            if analysis_result and "analysis" in analysis_result:
                st.subheader("Analysis Results")
                analysis_data = analysis_result["analysis"]
                threat_response = analysis_result.get("threat_response", {})
                
                # Threat Score Gauge
                threat_score = threat_response.get("threat_score", 0)
                threat_level = threat_response.get("threat_level", "low").upper()
                
                color = "green"
                if threat_level == "MEDIUM": color = "orange"
                if threat_level in ["HIGH", "CRITICAL"]: color = "red"

                st.markdown(f"""
                <div style="background-color: #222; border-radius: 10px; padding: 20px; text-align: center;">
                    <h3 style="color: #fff; margin-bottom: 10px;">Overall Threat Level: <span style="color:{color};">{threat_level}</span></h3>
                    <h1 style="color: {color}; font-size: 4em; margin:0;">{threat_score:.1f} / 10</h1>
                </div>
                """, unsafe_allow_html=True)

                st.write("") # Spacer

                # Key Metrics
                m_col1, m_col2, m_col3 = st.columns(3)
                m_col1.metric("Cognitive Dissonance", f"{analysis_data.get('dissonance_score', 0):.1f}/10", help="How much the content contradicts the VIP's known views.")
                m_col2.metric("Stylometric Drift", f"{analysis_data.get('drift_score', 0):.1f}%", help="How different the writing style is from the VIP's.")
                m_col3.metric("Visual Threat Score", f"{analysis_data.get('visual_threat_score', 0):.1f}/10", help="Dissonance found in text from images (OCR) or videos (transcripts).")

                # Detailed Breakdown
                with st.expander("Show Detailed Analysis Breakdown", expanded=True):
                    st.write("**Justification from AI:**", f"_{analysis_data.get('justification', 'N/A')}_")
                    st.json(analysis_result)

                # Alert Information
                if threat_response:
                    st.subheader("Alert & Evidence")
                    if threat_response.get("telegram_sent"):
                        st.success(f"Alert sent successfully via Telegram! Level: {threat_level}")
                    else:
                        st.info(f"Alert not sent to Telegram (Threat level '{threat_level}' may be too low). Check console for details.")
                    
                    st.info(f"**Evidence ID:** `{threat_response.get('evidence_id')}`")
                    st.code(f"**Blockchain Hash (Simulated):** {threat_response.get('blockchain_hash')}", language=None)
            
            else:
                st.error("Analysis failed. See details below:")
                st.json(analysis_result)

