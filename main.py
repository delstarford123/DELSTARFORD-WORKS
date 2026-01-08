import os
import datetime
import smtplib
import ssl
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

# Now we get the values using os.getenv()
SERVICE_ACCOUNT_KEY = os.getenv("SERVICE_ACCOUNT_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
        firebase_admin.initialize_app(cred, {
            'databaseURL': DATABASE_URL
        })
        print("Firebase Admin Initialized Successfully.")
    except Exception as e:
        print(f"Error Initializing Firebase: {e}")
        print("Make sure 'service account key.json' is in the root folder.")

# --- AI MODELS DATA ---
AI_MODELS = [
    # --- HEALTH & BIOTECH ---
    {"id": 1, "name": "DexaGen AI", "category": "Pharmacology", "price": "KSh 85,000", "tech": "DeepChem, WebGL", "desc": "Neuro-Symbolic engine simulating 3D drug interactions and molecular analysis."},
    {"id": 19, "name": "SMART HEALTH AI", "category": "Healthcare", "price": "KSh 95,000", "tech": "Scikit-learn, IoT", "desc": "Predicts malaria-prone regions via mosquito species tracking and doctor connectivity."},
    {"id": 20, "name": "Reen AI", "category": "EdTech / Science", "price": "KSh 40,000", "tech": "3D Rendering, Flask", "desc": "Interactive biochemistry tool for visualizing drug molecules and pharmacology data."},

    # --- AGRI-TECH ---
    {"id": 6, "name": "Agritech Field Manager", "category": "Agri-Tech", "price": "KSh 60,000", "tech": "Django, Plotly", "desc": "Lab-to-field experiment tracking with advanced data ingestion for agronomists."},
    {"id": 11, "name": "Plant Pathology AI", "category": "Agri-Tech", "price": "KSh 55,000", "tech": "PyTorch, IoT", "desc": "Disease detection system with voice navigation for hands-free field use."},
    {"id": 12, "name": "InsectAI", "category": "Agri-Tech", "price": "KSh 50,000", "tech": "TensorFlow, Audio", "desc": "Intelligent insect detection using sound analysis and environmental sensors."},
    {"id": 13, "name": "Poli AI", "category": "Agri-Tech", "price": "KSh 45,000", "tech": "Computer Vision", "desc": "Automated poultry management and health surveillance system."},
    {"id": 14, "name": "ANIPRO AI", "category": "FinTech / Agri", "price": "KSh 70,000", "tech": "Predictive Models", "desc": "Derisking platform connecting small-scale farmers to insurance providers."},

    # --- SECURITY & SURVEILLANCE ---
    {"id": 3, "name": "Usherbot Biometric", "category": "Security", "price": "KSh 75,000", "tech": "ONNX, Docker", "desc": "High-security fingerprint pipeline with embedding extraction and audit logs."},
    {"id": 17, "name": "KWS AI", "category": "Surveillance", "price": "KSh 80,000", "tech": "Computer Vision", "desc": "Wildlife park surveillance for early detection of poachers and abnormal conditions."},
    {"id": 10, "name": "AI Traffic Manager", "category": "Smart City", "price": "KSh 90,000", "tech": "YOLO, IoT", "desc": "Automated traffic flow optimization with voice assistance for navigation."},

    # --- BUSINESS & UTILITY ---
    {"id": 2, "name": "ScriptureAI", "category": "NLP", "price": "KSh 45,000", "tech": "Vector DB, RAG", "desc": "Semantic search engine for theological texts using Vector Embeddings."},
    {"id": 15, "name": "BKING", "category": "FinTech", "price": "KSh 120,000", "tech": "Banking Algorithms", "desc": "Intelligent banking system for credit facilities and insurers."},
    {"id": 4, "name": "Attendance Dashboard", "category": "Management", "price": "KSh 35,000", "tech": "Redis, WebSockets", "desc": "Real-time logs, summaries, and scheduled PDF reporting."},
    {"id": 7, "name": "Enterprise Chatbot", "category": "AI Services", "price": "KSh 30,000", "tech": "NLP, Firebase", "desc": "Automated support, bulk email/SMS handling, and E-Learning assistance."},
    {"id": 16, "name": "FREEZE AI", "category": "IoT", "price": "KSh 40,000", "tech": "Sensors, Flask", "desc": "Smart refrigerator maintenance system for early food spoilage detection."},

    # --- CONSUMER APPS ---
    {"id": 8, "name": "Eco-Ride", "category": "Environment", "price": "KSh 50,000", "tech": "React Native", "desc": "Carbon footprint tracking and climate change mitigation app."},
    {"id": 22, "name": "MIRA AI", "category": "GenAI", "price": "KSh 55,000", "tech": "Weather API, LLMs", "desc": "Weather-aware learning assistant adapting study focus to the environment."},
    {"id": 5, "name": "Digital Assistant", "category": "Productivity", "price": "KSh 25,000", "tech": "Voice API", "desc": "Personal assistant for scheduling, reminders, and task management."},
]


# --- PAGE ROUTES ---
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import jsonify, request

# ... existing imports ...

def send_email_notification(recipient_email, subject, body):
    """
    Robust email sender using Gmail TLS (Port 587)
    Matches keys: SENDER_EMAIL and SENDER_PASSWORD
    """
    # 1. Load Credentials (matching your .env names)
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = 587  # Standard TLS port for Gmail

    if not sender_email or not sender_password:
        print("CRITICAL: 'SENDER_EMAIL' or 'SENDER_PASSWORD' missing in environment.")
        return False

    try:
        # 2. Create the email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # 3. Connect securely using TLS (The fix for SystemExit error)
        context = ssl.create_default_context()
        print(f"Connecting to {smtp_server}:{smtp_port}...")
        
        # 
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()  # Identify ourselves
            server.starttls(context=context) # Upgrade connection to secure
            server.ehlo()  # Re-identify as encrypted
            
            print("Logging in...")
            server.login(sender_email, sender_password)
            
            print(f"Sending email to {recipient_email}...")
            server.send_message(msg)
            
        print("Email sent successfully!")
        return True

    except Exception as e:
        print(f"EMAIL ERROR: {e}")
        return False

@app.route('/custom', methods=['POST'])
def custom_solution():
    try:
        # 1. Capture Data
        # Support both JSON (if using fetch/axios) and Form Data (standard submit)
        data = request.form if request.form else request.json
        
        name = data.get('name')
        email = data.get('email')
        service = data.get('service')
        
        print(f"New Lead: {email} requesting {service}")

        # 2. Prepare Emails
        admin_subject = f"New Request: {service} from {name}"
        admin_body = f"""
        New Project Lead:
        -----------------
        Name: {name}
        Email: {email}
        Service: {service}
        Budget: {data.get('budget')}
        Timeline: {data.get('timeline')}
        
        Details:
        {data.get('details')}
        """
        
        user_subject = "We received your request - Delstarford Works"
        user_body = f"""
        Hi {name},

        Thank you for contacting Delstarford Works. We have received your request regarding "{service}".
        
        Our team is reviewing your details and will contact you within 24 hours.

        Best,
        Delstarford Works Team
        """

        # 3. Send Emails
        # Send to Admin (You)
        admin_email = os.environ.get('SENDER_EMAIL') 
        
        if send_email_notification(admin_email, admin_subject, admin_body):
            # Send confirmation to User
            send_email_notification(email, user_subject, user_body)
            return jsonify({"success": True, "message": "Request sent successfully!"}), 200
        else:
            return jsonify({"success": False, "message": "Server email configuration failed. Check logs."}), 500

    except Exception as e:
        print(f"ROUTE ERROR: {e}")
        return jsonify({"success": False, "message": f"Internal Server Error: {str(e)}"}), 500
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/services')
def services():
    return render_template('services.html')


@app.route('/ai-lab')
def ai_lab():
    # Note: Using ai_lab.html (with underscore) to match your folder
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

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/privacy')
def privacy():
    # Matches privacy.html in your screenshot
    return render_template('privacy.html')
@app.route('/case-study')
def case_study():
    return render_template('case_study.html')
# --- LOGIC ROUTES ---
# --- AUTHENTICATION ROUTES ---
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/estimator')
def estimator():
    return render_template('price_estimator.html')
@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/calculate-estimate', methods=['POST'])
def calculate_estimate():
    """
    Calculates the cost of an AI project based on data size and complexity.
    """
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
    
    # Cost Logic: (Base + ModelAdd) * Complexity + (DataSize * Rate)
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

@app.route('/dashboard-data')
def get_dashboard_data():
    """API for the JS dashboard to consume live data."""
    user_id = 'user_123'  # Hardcoded for demo; use session ID in production
    ref = db.reference(f'active_projects/{user_id}')
    data = ref.get()
    return jsonify(data)

# --- ADMIN ROUTES (Optional Helper) ---
@app.route('/admin/simulate-update')
def simulate_update():
    """Updates the dashboard for testing purposes."""
    try:
        user_id = 'user_123'
        # Update Project Status
        ref = db.reference(f'active_projects/{user_id}')
        ref.update({
            'status': 'Genetic Analysis Completed',
            'last_updated': str(datetime.datetime.now())
        })
        # Push Activity Notification
        act_ref = db.reference(f'users/{user_id}/activity')
        act_ref.push({
            'time': datetime.datetime.now().strftime("%H:%M"),
            'message': 'Lab results uploaded to secure server.'
        })
        return "Admin update simulated successfully!"
    except Exception as e:
        return f"Error: {e}"

if __name__ == '__main__':
    app.run(debug=True)