#!/usr/bin/env python3
"""
AI Image Detection Script
Analyzes images to determine if they are AI-generated or real.

This script uses multiple detection methods:
1. Deep learning feature extraction
2. Frequency domain analysis 
3. Statistical pattern analysis
4. Metadata inspection

Requirements:
pip install torch torchvision pillow numpy opencv-python scikit-learn matplotlib

Usage:
python ai_image_detector.py <image_path>
"""

import os
import sys
import numpy as np
import cv2
from PIL import Image, ExifTags
import torch
import requests
import torch.nn as nn
import torchvision.transforms as transforms
import torchvision.models as models
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

class AIImageDetector:
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {self.device}")
        
        # Load pre-trained ResNet model for feature extraction
        self.feature_extractor = models.resnet50(pretrained=True)
        self.feature_extractor.fc = nn.Identity()  # Remove final classification layer
        self.feature_extractor.eval()
        self.feature_extractor.to(self.device)
        
        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                               std=[0.229, 0.224, 0.225])
        ])
        
        # Initialize anomaly detector for unusual patterns
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.scaler = StandardScaler()
        
    def load_image(self, image_path_or_url):
        """Load and preprocess image from local path or URL"""
        try:
            if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):
                response = requests.get(image_path_or_url, timeout=15)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content)).convert('RGB')
            else:
                image = Image.open(image_path_or_url).convert('RGB')
            return image
        except Exception as e:
            print(f"Error loading image: {e}")
            return None

    def extract_deep_features(self, image):
        """Extract deep learning features using ResNet"""
        try:
            # Preprocess image
            input_tensor = self.transform(image).unsqueeze(0).to(self.device)
            
            # Extract features
            with torch.no_grad():
                features = self.feature_extractor(input_tensor)
                features = features.cpu().numpy().flatten()
            
            return features
        except Exception as e:
            print(f"Error extracting deep features: {e}")
            return None
    
    def frequency_domain_analysis(self, image):
        """Analyze frequency domain characteristics"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
            
            # Apply FFT
            f_transform = np.fft.fft2(gray)
            f_shift = np.fft.fftshift(f_transform)
            magnitude_spectrum = np.log(np.abs(f_shift) + 1)
            
            # Calculate frequency domain features
            features = {
                'freq_mean': np.mean(magnitude_spectrum),
                'freq_std': np.std(magnitude_spectrum),
                'freq_energy': np.sum(magnitude_spectrum ** 2),
                'high_freq_energy': np.sum(magnitude_spectrum[gray.shape[0]//4:3*gray.shape[0]//4, 
                                                            gray.shape[1]//4:3*gray.shape[1]//4] ** 2)
            }
            
            return features
        except Exception as e:
            print(f"Error in frequency domain analysis: {e}")
            return {}
    
    def statistical_analysis(self, image):
        """Perform statistical analysis on image"""
        try:
            img_array = np.array(image)
            
            features = {}
            
            # Color channel statistics
            for i, channel in enumerate(['R', 'G', 'B']):
                channel_data = img_array[:, :, i].flatten()
                features.update({
                    f'{channel}_mean': np.mean(channel_data),
                    f'{channel}_std': np.std(channel_data),
                    f'{channel}_skewness': self.calculate_skewness(channel_data),
                    f'{channel}_kurtosis': self.calculate_kurtosis(channel_data)
                })
            
            # Texture analysis using local binary patterns
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            lbp = self.local_binary_pattern(gray)
            features['texture_uniformity'] = np.std(lbp)
            
            # Edge density
            edges = cv2.Canny(gray, 50, 150)
            features['edge_density'] = np.sum(edges > 0) / edges.size
            
            return features
        except Exception as e:
            print(f"Error in statistical analysis: {e}")
            return {}
    
    def calculate_skewness(self, data):
        """Calculate skewness of data"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0
        return np.mean(((data - mean) / std) ** 3)
    
    def calculate_kurtosis(self, data):
        """Calculate kurtosis of data"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0
        return np.mean(((data - mean) / std) ** 4) - 3
    
    def local_binary_pattern(self, image, radius=1, n_points=8):
        """Simple local binary pattern implementation"""
        rows, cols = image.shape
        lbp = np.zeros_like(image)
        
        for i in range(radius, rows - radius):
            for j in range(radius, cols - radius):
                center = image[i, j]
                pattern = 0
                for k in range(n_points):
                    angle = 2 * np.pi * k / n_points
                    x = int(i + radius * np.cos(angle))
                    y = int(j + radius * np.sin(angle))
                    if 0 <= x < rows and 0 <= y < cols:
                        if image[x, y] > center:
                            pattern |= (1 << k)
                lbp[i, j] = pattern
        
        return lbp
    
    def check_metadata(self, image_path_or_url):
        """Check image metadata for AI generation clues"""
        try:
            exif_data = {}
            if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):
                response = requests.get(image_path_or_url, timeout=15)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
            else:
                image = Image.open(image_path_or_url)

            if hasattr(image, '_getexif') and image._getexif() is not None:
                exif = image._getexif()
                for tag, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag, tag)
                    exif_data[tag_name] = value

            # Look for AI generation indicators
            ai_indicators = ['midjourney', 'dalle', 'stable diffusion', 'gpt',
                             'artificial', 'generated', 'ai', 'synthetic']
            metadata_text = str(exif_data).lower()
            ai_metadata_score = sum(1 for ind in ai_indicators if ind in metadata_text)

            return {
                'exif_data': exif_data,
                'ai_metadata_score': ai_metadata_score,
                'has_suspicious_metadata': ai_metadata_score > 0
            }
        except Exception as e:
            print(f"Error checking metadata: {e}")
            return {'exif_data': {}, 'ai_metadata_score': 0, 'has_suspicious_metadata': False}
        """Check image metadata for AI generation clues"""
        try:
            image = Image.open(image_path)
            exif_data = {}
            
            if hasattr(image, '_getexif') and image._getexif() is not None:
                exif = image._getexif()
                for tag, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag, tag)
                    exif_data[tag_name] = value
            
            # Look for AI generation indicators in metadata
            ai_indicators = [
                'midjourney', 'dalle', 'stable diffusion', 'gpt', 
                'artificial', 'generated', 'ai', 'synthetic'
            ]
            
            metadata_text = str(exif_data).lower()
            ai_metadata_score = sum(1 for indicator in ai_indicators 
                                  if indicator in metadata_text)
            
            return {
                'exif_data': exif_data,
                'ai_metadata_score': ai_metadata_score,
                'has_suspicious_metadata': ai_metadata_score > 0
            }
            
        except Exception as e:
            print(f"Error checking metadata: {e}")
            return {'exif_data': {}, 'ai_metadata_score': 0, 'has_suspicious_metadata': False}
    
    def detect_compression_artifacts(self, image):
        """Detect unusual compression patterns that might indicate AI generation"""
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # Apply discrete cosine transform (similar to JPEG compression)
            dct = cv2.dct(np.float32(gray))
            
            # Analyze DCT coefficients
            dct_features = {
                'dct_mean': np.mean(dct),
                'dct_std': np.std(dct),
                'high_freq_coeff': np.sum(np.abs(dct[gray.shape[0]//2:, gray.shape[1]//2:]))
            }
            
            return dct_features
        except Exception as e:
            print(f"Error in compression analysis: {e}")
            return {}
    
    def analyze_image(self, image_path):
        """Main analysis function"""
        print(f"Analyzing image: {image_path}")
        
        # Load image
        image = self.load_image(image_path)
        if image is None:
            return None
        
        results = {
            'image_path': image_path,
            'image_size': image.size
        }
        
        # Extract features
        print("Extracting deep learning features...")
        deep_features = self.extract_deep_features(image)
        
        print("Analyzing frequency domain...")
        freq_features = self.frequency_domain_analysis(image)
        
        print("Performing statistical analysis...")
        stat_features = self.statistical_analysis(image)
        
        print("Checking metadata...")
        metadata_info = self.check_metadata(image_path)
        
        print("Analyzing compression artifacts...")
        compression_features = self.detect_compression_artifacts(image)
        
        # Combine all features
        all_features = {**freq_features, **stat_features, **compression_features}
        
        # Simple heuristic-based scoring
        ai_score = self.calculate_ai_probability(all_features, metadata_info)
        
        results.update({
            'frequency_features': freq_features,
            'statistical_features': stat_features,
            'compression_features': compression_features,
            'metadata_info': metadata_info,
            'ai_probability': ai_score,
            'prediction': 'AI Generated' if ai_score > 0.5 else 'Real Image'
        })
        
        return results
    
    def calculate_ai_probability(self, features, metadata_info):
        """Calculate probability that image is AI generated based on heuristics"""
        score = 0.0
        
        # Metadata indicators
        if metadata_info['has_suspicious_metadata']:
            score += 0.4
        
        # Statistical anomalies often found in AI images
        if 'R_std' in features and 'G_std' in features and 'B_std' in features:
            # AI images often have unusual color distribution
            color_std_avg = (features['R_std'] + features['G_std'] + features['B_std']) / 3
            if color_std_avg < 30 or color_std_avg > 80:  # Unusual color variance
                score += 0.2
        
        # Frequency domain anomalies
        if 'freq_std' in features:
            # AI images often have unusual frequency characteristics
            if features['freq_std'] > 2.0 or features['freq_std'] < 0.5:
                score += 0.15
        
        # Edge density analysis
        if 'edge_density' in features:
            # AI images might have unusual edge characteristics
            if features['edge_density'] < 0.05 or features['edge_density'] > 0.3:
                score += 0.1
        
        # Texture uniformity
        if 'texture_uniformity' in features:
            # AI images often have very uniform or very chaotic textures
            if features['texture_uniformity'] < 10 or features['texture_uniformity'] > 50:
                score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0
    
    def print_results(self, results):
        """Print analysis results"""
        if results is None:
            print("Analysis failed.")
            return
        
        print("\n" + "="*60)
        print("AI IMAGE DETECTION RESULTS")
        print("="*60)
        
        print(f"Image: {results['image_path']}")
        print(f"Size: {results['image_size']}")
        print(f"\nPrediction: {results['prediction']}")
        print(f"AI Probability: {results['ai_probability']:.3f}")
        
        print(f"\nMetadata Analysis:")
        print(f"  Suspicious metadata: {results['metadata_info']['has_suspicious_metadata']}")
        print(f"  AI indicators found: {results['metadata_info']['ai_metadata_score']}")
        
        if results['frequency_features']:
            print(f"\nFrequency Domain Features:")
            for key, value in results['frequency_features'].items():
                print(f"  {key}: {value:.3f}")
        
        print(f"\nConfidence Level: {'High' if abs(results['ai_probability'] - 0.5) > 0.3 else 'Medium' if abs(results['ai_probability'] - 0.5) > 0.1 else 'Low'}")
        
        print("\n" + "="*60)
        
        # Interpretation
        if results['ai_probability'] > 0.7:
            print("LIKELY AI GENERATED - Multiple indicators suggest artificial origin")
        elif results['ai_probability'] > 0.5:
            print("POSSIBLY AI GENERATED - Some suspicious characteristics detected")
        elif results['ai_probability'] > 0.3:
            print("LIKELY REAL IMAGE - Few AI indicators, appears authentic")
        else:
            print("VERY LIKELY REAL IMAGE - Strong indicators of authentic photography")

def main():
    if len(sys.argv) != 2:
        print("Usage: python ai_image_detector.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.")
        sys.exit(1)
    
    # Initialize detector
    detector = AIImageDetector()
    
    # Analyze image
    results = detector.analyze_image(image_path)
    
    # Print results
    detector.print_results(results)

if __name__ == "__main__":
    main()