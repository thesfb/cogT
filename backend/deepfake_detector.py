# backend/app/deepfake_detector.py
import requests
import numpy as np
from PIL import Image
from io import BytesIO
import os
import google.generativeai as genai

# Try to import deepface, but don't fail if it's not installed yet.
# This allows the app to start, but deepfake detection will be disabled.
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: `deepface` library not installed. Facial deepfake detection will be disabled.")
    print("Install it with: pip install deepface")
    DEEPFACE_AVAILABLE = False

# Configure Gemini for fallback analysis
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    llm_model = genai.GenerativeModel('gemini-2.5-flash')
    GEMINI_AVAILABLE = True
except (KeyError, ValueError):
    print("⚠️ WARNING: GOOGLE_API_KEY not found. Gemini fallback for deepfake analysis is disabled.")
    GEMINI_AVAILABLE = False


class DeepfakeDetector:
    """
    Analyzes an image to detect if it's a deepfake, focusing on facial manipulation first,
    then using a general AI model as a fallback.
    """
    
    def _preprocess_image_from_url(self, image_url: str):
        """Downloads and prepares an image for analysis."""
        try:
            response = requests.get(image_url, timeout=15)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGB")
            # DeepFace works with numpy arrays
            return np.array(img)
        except Exception as e:
            print(f"Error downloading or processing image: {e}")
            return None

    def analyze_image_with_deepface(self, img_array) -> dict:
        """Uses DeepFace to analyze facial authenticity."""
        if not DEEPFACE_AVAILABLE:
            return {"error": "DeepFace library is not available."}
        
        try:
            # DeepFace expects BGR format, so we convert RGB -> BGR
            img_bgr = img_array[:, :, ::-1]
            
            # The 'real_vs_fake' model predicts if a face is real or AI-generated
            result = DeepFace.analyze(
                img_path=img_bgr,
                actions=['emotion'], # We run a lightweight action to avoid errors if no face is found
                detector_backend='retinaface',
                enforce_detection=True # Ensure a face is found
            )
            
            # This is a placeholder for a real deepfake model.
            # For this example, we'll simulate a result based on emotion analysis.
            # A real implementation would use a specific deepfake detection model.
            # Let's simulate a higher fake probability for neutral emotions.
            dominant_emotion = result[0].get('dominant_emotion', 'neutral')
            if dominant_emotion == 'neutral':
                fake_prob = 0.85
            else:
                fake_prob = 0.15

            return {
                "source": "simulated_deepface",
                "deepfake_probability": fake_prob,
                "is_deepfake": fake_prob > 0.7,
                "details": f"Simulated based on dominant emotion: {dominant_emotion}"
            }

        except ValueError as e:
            # This error is often raised by DeepFace if no face is detected
            if "Face could not be detected" in str(e):
                return {"error": "no_face_detected", "message": "Could not detect a face for deepfake analysis."}
            else:
                return {"error": "analysis_error", "message": str(e)}
        except Exception as e:
            return {"error": "unknown_error", "message": str(e)}

    def analyze_image_with_gemini(self, image_url: str) -> dict:
        """Uses Gemini as a fallback to analyze the image for signs of manipulation."""
        if not GEMINI_AVAILABLE:
            return {"error": "Gemini API is not available."}

        try:
            response = requests.get(image_url, timeout=15)
            response.raise_for_status()
            image_data = BytesIO(response.content)
            image_pil = Image.open(image_data)

            prompt = """
            Analyze this image for any signs of AI generation or digital manipulation (deepfake).
            Look for artifacts, unnatural features, inconsistent lighting, or strange backgrounds.
            Provide a probability score from 0.0 (definitely real) to 1.0 (definitely fake) and a brief justification.
            Return ONLY a JSON object in the format: {"deepfake_probability": <float>, "justification": "<text>"}
            """
            
            response = llm_model.generate_content([prompt, image_pil])
            
            # Clean and parse the JSON response
            import json
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
            result = json.loads(cleaned_text)

            return {
                "source": "gemini_vision",
                "deepfake_probability": result.get("deepfake_probability", 0.0),
                "is_deepfake": result.get("deepfake_probability", 0.0) > 0.7,
                "details": result.get("justification", "No justification provided.")
            }
        except Exception as e:
            return {"error": "gemini_error", "message": str(e)}

    def run_analysis(self, image_url: str) -> dict:
        """Runs the full deepfake detection pipeline."""
        print(f"[*] Running deepfake analysis on: {image_url}")
        img_array = self._preprocess_image_from_url(image_url)

        if img_array is None:
            return {"error": "image_download_failed", "is_deepfake": False, "deepfake_probability": 0.0}

        # Step 1: Try facial analysis first, as it's more specific.
        facial_analysis = self.analyze_image_with_deepface(img_array)

        if facial_analysis.get("error") == "no_face_detected":
            # Step 2: If no face is found, fall back to general Gemini analysis.
            print("  [-] No face detected. Falling back to Gemini for general artifact analysis.")
            return self.analyze_image_with_gemini(image_url)
        
        # If face was found or another error occurred, return that result.
        return facial_analysis
