import os
import datetime
import smtplib
import ssl
import random 
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, jsonify

# New Import for .env
from dotenv import load_dotenv

# Firebase Admin Imports
import firebase_admin
from firebase_admin import credentials, db

# --- LOAD SECRETS ---
load_dotenv()  # This loads the variables from .env

# --- CONFIGURATION ---
app = Flask(__name__)

# Load Environment Variables
SERVICE_ACCOUNT_KEY = os.getenv("SERVICE_ACCOUNT_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# Email Settings (Gmail Standard TLS)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# --- FIREBASE INITIALIZATION ---
if not firebase_admin._apps:
    try:
        if SERVICE_ACCOUNT_KEY and os.path.exists(SERVICE_ACCOUNT_KEY):
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
            firebase_admin.initialize_app(cred, {
                'databaseURL': DATABASE_URL
            })
            print("Firebase Admin Initialized Successfully.")
        else:
            print("WARNING: Service Account Key not found. Database features will fail.")
    except Exception as e:
        print(f"Error Initializing Firebase: {e}")

# --- AI MODELS DATA (For ai_lab.html) ---
AI_MODELS = [
    {"id": 1, "name": "DexaGen AI", "category": "Pharmacology", "price": "KSh 85,000", "tech": "DeepChem, WebGL", "desc": "Neuro-Symbolic engine simulating 3D drug interactions and molecular analysis."},
    {"id": 19, "name": "SMART HEALTH AI", "category": "Healthcare", "price": "KSh 95,000", "tech": "Scikit-learn, IoT", "desc": "Predicts malaria-prone regions via mosquito species tracking."},
    {"id": 20, "name": "Reen AI", "category": "EdTech", "price": "KSh 40,000", "tech": "3D Rendering", "desc": "Interactive biochemistry tool for visualizing drug molecules."},
    {"id": 6, "name": "Agritech Field Manager", "category": "Agri-Tech", "price": "KSh 60,000", "tech": "Django, Plotly", "desc": "Lab-to-field experiment tracking with advanced data ingestion."},
    {"id": 11, "name": "Plant Pathology AI", "category": "Agri-Tech", "price": "KSh 55,000", "tech": "PyTorch, IoT", "desc": "Disease detection system with voice navigation."},
    {"id": 14, "name": "ANIPRO AI", "category": "FinTech / Agri", "price": "KSh 70,000", "tech": "Predictive Models", "desc": "Derisking platform connecting farmers to insurance."},
    {"id": 2, "name": "ScriptureAI", "category": "NLP", "price": "KSh 45,000", "tech": "Vector DB, RAG", "desc": "Semantic search engine for theological texts."},
    {"id": 8, "name": "Eco-Ride", "category": "Environment", "price": "KSh 50,000", "tech": "React Native", "desc": "Carbon footprint tracking app."},
]

# --- HELPER FUNCTION: SEND HTML EMAIL ---
def send_email_html(to_email, subject, html_content):
    """
    Sends an HTML email using Gmail SMTP (TLS Port 587).
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Error: Email credentials missing.")
        return False

    try:
        # Create the email structure
        msg = MIMEMultipart('alternative')
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject

        # Attach the HTML body
        part = MIMEText(html_content, 'html')
        msg.attach(part)

        # Secure connection
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context) # Secure the connection
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# --- PAGE ROUTES ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/ai-lab')
def ai_lab():
    return render_template('ai_lab.html', models=AI_MODELS)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/location')
def location():
    return render_template('location.html')
@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/submit-ticket', methods=['POST'])
def submit_ticket():
    try:
        data = request.form
        
        # Generate a random number
        rand_num = random.randint(1000, 9999)

        # 1. CLEAN ID for Database Path (Firebase doesn't allow '#')
        db_key = f"TKT-{rand_num}"
        
        # 2. PRETTY ID for User/Email Display (We add the '#' here)
        display_ticket_id = f"#{db_key}"
        
        name = data.get('name')
        email = data.get('email')
        category = data.get('category')
        priority = data.get('priority')
        subject = data.get('subject')
        message = data.get('message')

        # 3. Save to Firebase using the CLEAN key
        try:
            # Notice we use 'db_key' (no hash) for the path
            ref = db.reference(f'support_tickets/{db_key}')
            ref.set({
                'ticket_id': display_ticket_id, # We save the pretty ID inside the data
                'status': 'Open',
                'name': name,
                'email': email,
                'category': category,
                'priority': priority,
                'subject': subject,
                'message': message,
                'timestamp': str(datetime.datetime.now())
            })
        except Exception as e:
            print(f"DB Error: {e}")

        # 4. Send Emails (Use display_ticket_id so it looks nice)
        
        # Admin Email
        admin_html = render_template('email_ticket_admin.html', 
                                     ticket_id=display_ticket_id, name=name, email=email, 
                                     category=category, priority=priority, 
                                     subject=subject, message=message)
        
        send_email_html(SENDER_EMAIL, f"[{priority.upper()}] New Ticket {display_ticket_id}: {subject}", admin_html)

        # User Email
        user_html = render_template('email_ticket_user.html', 
                                    name=name, ticket_id=display_ticket_id, subject=subject)
        
        send_email_html(email, f"Support Ticket Received - {display_ticket_id}", user_html)

        return jsonify({"success": True, "ticket_id": display_ticket_id})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/case-study')
def case_study():
    return render_template('case_study.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/estimator')
def estimator():
    # If your estimator is inside custom.html, redirect there
    return render_template('custom.html')

# --- MAIN LOGIC ROUTE (Email + Form + Estimator) ---
@app.route('/custom', methods=['GET', 'POST'])
def custom_solution():
    """
    Handles Project Requests:
    1. GET: Shows custom.html (your form).
    2. POST: Processes form, sends HTML emails, saves to Firebase.
    """
    # GET: Show the form page
    if request.method == 'GET':
        return render_template('custom.html') 
    
    # POST: Process the submission
    if request.method == 'POST':
        try:
            # 1. Get Data from Form
            data = request.form
            name = data.get('name')
            email = data.get('email')
            service = data.get('service')
            budget = data.get('budget')
            timeline = data.get('timeline')
            details = data.get('details')
            
            print(f"New Lead: {email} requesting {service}")

            # 2. GENERATE HTML EMAIL CONTENT
            # (Requires email_admin.html and email_client.html in /templates)
            
            admin_html = render_template('email_admin.html', 
                                         name=name, email=email, service=service, 
                                         budget=budget, timeline=timeline, details=details)
            
            client_html = render_template('email_client.html', 
                                          name=name, service=service)

            # 3. SEND EMAILS
            # Send to Admin (You)
            send_email_html(SENDER_EMAIL, f"New Lead: {service} from {name}", admin_html)
            
            # Send to Client (Confirmation)
            send_email_html(email, "We received your request - Delstarford Works", client_html)
            
            # 4. Save to Firebase (Backup)
            try:
                ref = db.reference('leads/service_requests')
                ref.push({
                    'name': name,
                    'email': email,
                    'service': service,
                    'details': details,
                    'budget': budget,
                    'timeline': timeline,
                    'timestamp': str(datetime.datetime.now())
                })
            except Exception as e:
                print(f"Database Error (Non-critical): {e}")

            return jsonify({"success": True, "message": "Request sent! Check your email for confirmation."}), 200

        except Exception as e:
            print(f"Server Error: {e}")
            return jsonify({"success": False, "message": "Server error occurred."}), 500

# --- ESTIMATOR LOGIC ROUTE ---
@app.route('/calculate-estimate', methods=['POST'])
def calculate_estimate():
    """
    Calculates the cost of an AI project based on data size and complexity.
    Called by JS in custom.html
    """
    try:
        data = request.json
        
        BASE_PRICE = 15000  
        
        model_type = data.get('modelType')
        try:
            data_size = int(data.get('dataSize', 0))
        except ValueError:
            data_size = 0
            
        complexity = data.get('complexity', 'standard')
        
        multipliers = {
            'standard': 1.0,
            'advanced': 2.5,
            'enterprise': 5.0
        }
        
        model_adds = {
            'tabular': 5000,
            'vision': 25000,
            'nlp': 15000,
            'bio': 30000
        }
        
        # Calculation Logic
        data_rate = (data_size / 1000) * 50
        subtotal = (BASE_PRICE + model_adds.get(model_type, 0)) * multipliers.get(complexity, 1.0)
        total_estimate = subtotal + data_rate
        
        return jsonify({
            "estimate": round(total_estimate, 2),
            "currency": "KSH",
            "breakdown": {
                "setup": subtotal,
                "data_processing": data_rate
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- DASHBOARD DATA ROUTE ---
@app.route('/dashboard-data')
def get_dashboard_data():
    """API for the JS dashboard to consume live data."""
    user_id = 'user_123' 
    try:
        ref = db.reference(f'active_projects/{user_id}')
        data = ref.get()
        return jsonify(data if data else {})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)