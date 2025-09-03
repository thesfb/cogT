# In backend/app/analysis.py

import chromadb
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import os
import json
import nltk
import string

# --- Load API Key and Configure Gemini ---
# This ensures the API key from your .env file is loaded
from dotenv import load_dotenv
load_dotenv() 

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
llm_model = genai.GenerativeModel('gemini-2.5-flash')

# --- Initialize ChromaDB Client and the Embedding Model ---
# These are the same as in the twin_builder, ensuring this module can access the DB
client = chromadb.PersistentClient(path="./db")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Analysis Engine: Embedding model loaded.")


def check_dissonance(twitter_handle: str, text_to_check: str):
    """
    Checks for cognitive dissonance between a new claim and a VIP's established public persona.
    """
    collection_name = f"vip_{twitter_handle.lower()}"
    
    # --- 1. Access the Twin's Knowledge Base (ChromaDB) ---
    try:
        collection = client.get_collection(name=collection_name)
    except ValueError:
        return {"error": f"Cognitive Twin for {twitter_handle} not found. Please build it first."}
    
    # --- 2. Perform a Semantic Search ---
    # Find the 3 most relevant "memories" or "ground truths" from the VIP's past statements.
    print(f"Searching for relevant statements from @{twitter_handle}...")
    query_embedding = embedding_model.encode(text_to_check).tolist()
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )
    
    ground_truth_statements = results['documents'][0]
    
    if not ground_truth_statements:
         return {"error": "Could not find any relevant statements in the Twin's knowledge base."}

    # --- 3. Construct a Prompt for the LLM (Prompt Engineering) ---
    # This is where we instruct the AI on how to behave.
    prompt = f"""
    Analyze for cognitive dissonance. I will provide an external claim and the ground truth from a VIP's public record.
    Your task is to provide a dissonance score from 1.0 (no dissonance) to 10.0 (direct contradiction) and a brief, one-sentence justification for your score.
    Return the response ONLY in this exact JSON format: {{"score": <score_float>, "justification": "<text>"}}

    ---
    EXTERNAL CLAIM:
    "{text_to_check}"

    GROUND TRUTH (VIP's past statements):
    - "{ground_truth_statements[0]}"
    - "{ground_truth_statements[1]}"
    - "{ground_truth_statements[2]}"
    ---

    JSON RESPONSE:
    """
    
    # --- 4. Call the Gemini API ---
    print("Calling Gemini Pro for analysis...")
    response = llm_model.generate_content(prompt)
    
    # --- 5. Parse and Return the Result ---
    try:
        # Clean up the response to make sure it's valid JSON
        cleaned_response = response.text.strip().replace('`', '')
        if cleaned_response.startswith("json"):
            cleaned_response = cleaned_response[4:]
        
        result_json = json.loads(cleaned_response)
        print(f"Analysis complete. Dissonance score: {result_json.get('score')}")
        return result_json
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response was: {response.text}")
        return {"error": "Failed to parse the analysis from the AI model."}

nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

# --- New Logic for Stylometric Drift ---

def calculate_fingerprint(text: str):
    """Calculates a stylistic fingerprint for a given block of text."""
    # Tokenize the text into sentences and words
    sentences = nltk.sent_tokenize(text)
    words = nltk.word_tokenize(text)
    
    # Filter out punctuation
    words_no_punct = [word for word in words if word not in string.punctuation]
    
    if not sentences or not words_no_punct:
        return {
            "avg_sent_len": 0,
            "avg_word_len": 0,
            "punct_freq": 0
        }

    # Calculate metrics
    avg_sent_len = len(words_no_punct) / len(sentences)
    avg_word_len = sum(len(word) for word in words_no_punct) / len(words_no_punct)
    punct_count = len([word for word in words if word in string.punctuation])
    punct_freq = (punct_count / len(words)) * 100 # Punctuation per 100 words

    return {
        "avg_sent_len": avg_sent_len,
        "avg_word_len": avg_word_len,
        "punct_freq": punct_freq
    }

def check_stylometric_drift(twitter_handle: str, text_to_check: str):
    """
    Compares the stylistic fingerprint of a new text against the VIP's established style.
    """
    collection_name = f"vip_{twitter_handle.lower()}"
    
    # --- 1. Access the Twin's Knowledge Base (ChromaDB) ---
    try:
        collection = client.get_collection(name=collection_name)
    except ValueError:
        return {"error": f"Cognitive Twin for {twitter_handle} not found. Please build it first."}

    # --- 2. Calculate Fingerprints ---
    # Combine all of the VIP's documents into a single text block
    vip_docs = collection.get()['documents']
    vip_corpus = " ".join(vip_docs)
    
    true_fingerprint = calculate_fingerprint(vip_corpus)
    suspect_fingerprint = calculate_fingerprint(text_to_check)

    if true_fingerprint['avg_sent_len'] == 0:
         return {"error": "Could not generate a valid fingerprint for the VIP."}

    # --- 3. Calculate Drift Score ---
    # Calculate the percentage difference for each metric
    sent_len_drift = abs(true_fingerprint['avg_sent_len'] - suspect_fingerprint['avg_sent_len']) / true_fingerprint['avg_sent_len']
    word_len_drift = abs(true_fingerprint['avg_word_len'] - suspect_fingerprint['avg_word_len']) / true_fingerprint['avg_word_len']
    
    # Average the drifts to get a single score
    total_drift = (sent_len_drift + word_len_drift) * 50 # Scale to be a percentage
    
    print(f"Stylometric Drift calculated: {total_drift:.2f}%")

    return {"drift_score": round(total_drift, 2)}