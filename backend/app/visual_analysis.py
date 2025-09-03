# backend/app/visual_analysis.py
import requests
from PIL import Image
import imagehash
from google.cloud import vision
from google.cloud import speech
import subprocess
import os

# Initialize Google Cloud clients
vision_client = vision.ImageAnnotatorClient()
speech_client = speech.SpeechClient()


def get_image_fingerprint_from_url(image_url: str):
    """Downloads an image from a URL and computes its perceptual hash."""
    try:
        print(f"Fingerprinting image from: {image_url}")
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()
        image = Image.open(response.raw)
        p_hash = str(imagehash.phash(image))
        print(f"Perceptual hash: {p_hash}")
        return p_hash
    except Exception as e:
        print(f"Error fingerprinting image: {e}")
        return None


def analyze_image_content_from_url(image_url: str):
    """Analyzes image from URL for labels and text (OCR) using Google Cloud Vision."""
    try:
        print(f"Analyzing content for image: {image_url}")
        image = vision.Image()
        image.source.image_uri = image_url

        # Get labels
        label_response = vision_client.label_detection(image=image)
        labels = [label.description for label in label_response.label_annotations]

        # Get OCR text
        text_response = vision_client.text_detection(image=image)
        ocr_text = (
            text_response.text_annotations[0].description
            if text_response.text_annotations
            else ""
        )

        print(f"Vision API results: Labels={labels}, OCR Text length={len(ocr_text)}")
        return {"labels": labels, "ocr_text": ocr_text.strip()}
    except Exception as e:
        print(f"Error with Google Vision API: {e}")
        return {"labels": [], "ocr_text": ""}


def extract_audio_ffmpeg(video_path: str, audio_path: str):
    """Uses ffmpeg to extract audio from a video file as WAV (16-bit PCM)."""
    try:
        command = [
            "ffmpeg",
            "-y",              # overwrite output if exists
            "-i", video_path,  # input file
            "-vn",             # disable video
            "-acodec", "pcm_s16le",  # audio codec (raw PCM)
            "-ar", "44100",    # sample rate
            "-ac", "2",        # stereo
            audio_path,
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Audio extracted to {audio_path}")
    except Exception as e:
        raise RuntimeError(f"ffmpeg audio extraction failed: {e}")


def transcribe_audio_from_video_url(video_url: str):
    """Downloads a video, extracts audio with ffmpeg, and transcribes it."""
    video_path = "temp_video.mp4"
    audio_path = "temp_audio.wav"
    try:
        # Download video
        print(f"Downloading video: {video_url}")
        r = requests.get(video_url, stream=True, timeout=30)
        with open(video_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        # Extract audio with ffmpeg
        print("Extracting audio with ffmpeg...")
        extract_audio_ffmpeg(video_path, audio_path)

        # Transcribe audio
        print("Transcribing audio with Google Speech API...")
        with open(audio_path, "rb") as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=44100,
            language_code="en-US",
            audio_channel_count=2,
        )

        response = speech_client.recognize(config=config, audio=audio)
        transcript = " ".join(
            [result.alternatives[0].transcript for result in response.results]
        )
        print(f"Transcription complete: {transcript[:100]}...")
        return transcript

    except Exception as e:
        print(f"Error in video processing/transcription: {e}")
        return ""
    finally:
        # Clean up temp files
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
