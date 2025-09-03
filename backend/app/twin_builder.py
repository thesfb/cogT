# In backend/app/twin_builder.py

# Make sure all these imports are at the top of the file
import chromadb
from sentence_transformers import SentenceTransformer
from .mock_data import MOCK_TWEETS # Import our new mock data

# --- Keep these initializations ---
client = chromadb.PersistentClient(path="./db")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Embedding model loaded.")


# --- REPLACE the old function with this one ---
def build_and_store_twin(twitter_handle: str, post_limit: int = 50):
    """
    Builds a Twin from a local, pre-saved dataset for reliability and speed.
    """
    print(f"Building twin for @{twitter_handle} from mock data...")
    
    handle_key = twitter_handle.lower()
    
    # --- 1. Get Posts from our Mock Dataset ---
    if handle_key not in MOCK_TWEETS:
        print(f"No mock data found for @{handle_key}.")
        return {"status": "error", "message": f"No mock data available for this user."}
        
    posts = MOCK_TWEETS[handle_key]
    print(f"Found {len(posts)} posts for @{handle_key} in mock data.")

    # --- The rest of the logic is EXACTLY the same ---

    # --- 2. Create or Get ChromaDB Collection ---
    collection_name = f"vip_{handle_key}"
    collection = client.get_or_create_collection(name=collection_name)
    
    # --- 3. Generate Embeddings ---
    print("Generating embeddings for posts...")
    embeddings = model.encode(posts)
    ids = [str(i) for i in range(len(posts))]
    
    # --- 4. Store in ChromaDB ---
    collection.upsert(
        documents=posts,
        embeddings=embeddings.tolist(),
        ids=ids
    )
    
    print(f"Twin for @{handle_key} successfully built from mock data.")
    return {"status": "success", "posts_added": len(posts), "collection_name": collection_name}