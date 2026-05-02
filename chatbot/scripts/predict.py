import os
import json
from chatbot.chatbot_logic import ChatbotLogic

class ChatbotPredictor:
    def __init__(self, model_dir, json_path):
        # Load the JSON knowledge base once
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                kb_data = json.load(f)
        else:
            kb_data = {}
            print(f"⚠️ Warning: {json_path} not found.")

        # Initialize the logic handler
        self.logic = ChatbotLogic(model_dir, kb_data)

    def get_response(self, query):
        try:
            return self.logic.process_request(query)
        except Exception as e:
            print(f"Chatbot Error: {e}")
            return "I'm having a bit of trouble thinking right now. Please try again or contact support."

if __name__ == "__main__":
    # Local CLI Test
    MODEL_DIR = os.path.join("chatbot", "model")
    JSON_PATH = os.path.join("chatbot", "data", "knowledge.json")
    
    predictor = ChatbotPredictor(MODEL_DIR, JSON_PATH)
    print("MASHA CLI READY (Type 'quit' to exit)")
    while True:
        u = input("You: ")
        if u.lower() == 'quit': break
        print(f"MASHA: {predictor.get_response(u)}")
