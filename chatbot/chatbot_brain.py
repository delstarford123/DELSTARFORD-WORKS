import os
import joblib
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

class ChatbotBrain:
    def __init__(self, model_dir):
        self.model_dir = model_dir
        
        # Paths to artifacts
        self.vectorizer_path = os.path.join(model_dir, "tfidf_vectorizer.pkl")
        self.matrix_path = os.path.join(model_dir, "document_vectors.pkl")
        self.df_path = os.path.join(model_dir, "knowledge_df.pkl")
        
        self.loaded = False
        if all(os.path.exists(p) for p in [self.vectorizer_path, self.matrix_path, self.df_path]):
            self.vectorizer = joblib.load(self.vectorizer_path)
            self.tfidf_matrix = joblib.load(self.matrix_path)
            self.df = joblib.load(self.df_path)
            self.loaded = True

    def find_best_match(self, query):
        if not self.loaded:
            return None, 0
            
        # Vectorize user query
        query_vec = self.vectorizer.transform([query.lower()])
        
        # Calculate cosine similarity against all document chunks
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Get the index of the best match
        best_idx = similarities.argsort()[-1]
        best_score = similarities[best_idx]
        
        if best_score > 0.1: # Minimum confidence threshold
            return self.df.iloc[best_idx]['text'], best_score
        
        return None, best_score
