import os
import json
import re
from pypdf import PdfReader

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_text_from_pdfs(data_dir):
    knowledge_base = {
        "company_info": {
            "name": "Delstarford Works",
            "motto": "Engineering the Future | Where Biology Meets Technology",
            "website": "www.delstarfordworks.co.ke",
            "contacts": ["0707605751"],
            "email": "delstarfordisaiah@gmail.com",
            "location": "Kenya",
            "services": [
                {"name": "Enterprise AI Solutions", "link": "/services"},
                {"name": "Custom Web Systems", "link": "/services"},
                {"name": "Agricultural Biotech Solutions", "link": "/services"},
                {"name": "Pharmacology AI (DexaGen)", "link": "/ai-lab"},
                {"name": "Agri-Tech Field Management", "link": "/ai-lab"},
                {"name": "NLP & Semantic Search (ScriptureAI)", "link": "/ai-lab"}
            ],
            "pages": {
                "home": "/",
                "services": "/services",
                "ai market": "/ai-lab",
                "pricing": "/agreement",
                "contact": "/contact",
                "support": "/support",
                "dashboard": "/dashboard"
            }
        },
        "projects": [
            {
                "name": "DexaGen AI",
                "desc": "A Neuro-Symbolic engine simulating 3D drug interactions for pharmacology.",
                "link": "/ai-lab"
            },
            {
                "name": "ScriptureAI",
                "desc": "A semantic search engine for theological texts using Vector DB and RAG.",
                "link": "/ai-lab"
            },
            {
                "name": "Smart Health AI",
                "desc": "Predicts malaria-prone regions via mosquito tracking using IoT.",
                "link": "/ai-lab"
            },
            {
                "name": "Plant Pathology AI",
                "desc": "A disease detection system for plants with voice navigation.",
                "link": "/ai-lab"
            }
        ],
        "documents": []
    }
    
    for filename in os.listdir(data_dir):
        if filename.endswith(".pdf"):
            file_path = os.path.join(data_dir, filename)
            print(f"Processing {filename}...")
            try:
                reader = PdfReader(file_path)
                doc_text = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text: doc_text += text + "\n"
                
                chunks = doc_text.split('\n\n')
                if len(chunks) < 5: chunks = doc_text.split('\n')
                
                valid_chunks = []
                for chunk in chunks:
                    cleaned = clean_text(chunk)
                    if len(cleaned) > 50:
                        valid_chunks.append(cleaned)
                
                knowledge_base["documents"].append({
                    "title": filename,
                    "content": valid_chunks
                })
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                
    return knowledge_base

if __name__ == "__main__":
    DATA_DIR = os.path.join("chatbot", "data")
    JSON_OUTPUT = os.path.join("chatbot", "data", "knowledge.json")
    kb = extract_text_from_pdfs(DATA_DIR)
    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=4, ensure_ascii=False)
    print(f"Extraction complete. Saved to {JSON_OUTPUT}")
