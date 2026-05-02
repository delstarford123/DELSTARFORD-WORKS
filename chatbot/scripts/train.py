import os
import json
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer

def train_chatbot_model(json_path, model_dir):
    print(f"Loading data from {json_path}...")
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        kb = json.load(f)
    
    data = []
    for doc in kb.get("documents", []):
        for paragraph in doc.get("content", []):
            data.append({
                "source": doc["title"],
                "text": paragraph
            })
    
    df = pd.DataFrame(data)
    
    if df.empty:
        print("Error: No text found in JSON.")
        return

    print(f"Training TF-IDF Vectorizer on {len(df)} chunks...")
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(df['text'].astype(str))

    # Create model directory if it doesn't exist
    os.makedirs(model_dir, exist_ok=True)

    # Save artifacts
    joblib.dump(vectorizer, os.path.join(model_dir, "tfidf_vectorizer.pkl"))
    joblib.dump(tfidf_matrix, os.path.join(model_dir, "document_vectors.pkl"))
    joblib.dump(df, os.path.join(model_dir, "knowledge_df.pkl"))
    
    print(f"Training complete. Artifacts saved to {model_dir}")

if __name__ == "__main__":
    JSON_PATH = os.path.join("chatbot", "data", "knowledge.json")
    MODEL_DIR = os.path.join("chatbot", "model")
    train_chatbot_model(JSON_PATH, MODEL_DIR)
