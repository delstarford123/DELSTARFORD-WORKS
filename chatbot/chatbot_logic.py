import random
import re
from chatbot.chatbot_brain import ChatbotBrain

class ChatbotLogic:
    def __init__(self, model_dir, kb_data):
        self.brain = ChatbotBrain(model_dir)
        self.kb = kb_data
        
        self.jokes = [
            "Why did the AI cross the road? To optimize the other side!",
            "How many programmers does it take to change a light bulb? None, it's a hardware problem.",
            "I asked my computer for a joke, and it said '404: Sense of humor not found'."
        ]
        
        self.greetings = ["Hello! How can I assist you today?", "Hi there! MASHA at your service.", "Greetings! What can Delstarford Works do for you today?"]

    def process_request(self, query):
        q = query.lower().strip()
        company = self.kb.get("company_info", {})
        website = company.get("website", "www.delstarfordworks.co.ke")
        email = company.get("email", "delstarfordisaiah@gmail.com")
        
        # 1. Personality & Small Talk
        if q in ["hi", "hello", "hey", "greetings"]:
            return random.choice(self.greetings)
            
        if "joke" in q:
            return random.choice(self.jokes)
            
        if any(word in q for word in ["thank", "thanks"]):
            return "You're very welcome! Is there anything else you'd like to know?"

        # 2. Hardcoded Company Facts (Clickable Links)
        if any(word in q for word in ["who are you", "who is masha", "what are you"]):
            return f"I am MASHA, the official AI assistant for <b>{company.get('name')}</b>. {company.get('motto')}. Visit us at <a href='https://{website}' target='_blank'>{website}</a>."
            
        if any(word in q for word in ["contact", "phone", "email", "reach"]):
            contacts = ", ".join(company.get("contacts", []))
            return f"You can reach our team at <b>{contacts}</b> or via email at <a href='mailto:{email}'>{email}</a>."
            
        if any(word in q for word in ["services", "offerings", "what do you do"]):
            services_html = "".join([f"<li><a href='{s['link']}'>{s['name']}</a></li>" for s in company.get("services", [])])
            return f"Delstarford Works specializes in high-end technology solutions:<br><ul>{services_html}</ul>"

        if any(word in q for word in ["pricing", "cost", "how much", "rates"]):
            return f"Our pricing is project-dependent. AI models start at <b>KSh 15,000</b>. View our detailed <a href='/agreement'>Pricing & Plans</a> or get an <a href='/estimator'>Instant Estimate</a>."

        if any(word in q for word in ["payment", "how to pay", "pay"]):
            return "You can make payments easily using the <b>Quick Pay</b> button at the bottom left of your screen. We accept M-Pesa, Stripe, and PayPal."

        if any(word in q for word in ["location", "office", "where are you"]):
            return f"Delstarford Works is based in <b>{company.get('location')}</b>. We handle projects globally through our <a href='/dashboard'>Client Console</a>."

        # 3. Project-Specific Direct Matches
        for project in self.kb.get("projects", []):
            if project["name"].lower() in q:
                return f"<b>{project['name']}</b>: {project['desc']} <br>View details in our <a href='{project['link']}'>AI Market</a>."

        # 4. Brain (PDF Search)
        match, score = self.brain.find_best_match(q)
        
        if match and score > 0.25:
            return match
        elif match and score > 0.12:
            return f"I found this in our documents: <br><i>{match}</i>"
        else:
            return f"I couldn't find a specific answer in my database. Would you like to speak to a human representative? You can contact us at <b>0707605751</b> or email <a href='mailto:{email}'>{email}</a>."
