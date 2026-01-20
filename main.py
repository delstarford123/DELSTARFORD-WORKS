import os
import datetime
import smtplib
import ssl
import threading  # For background emails
import random     # For ticket IDs
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
# New Import for .env
from dotenv import load_dotenv

# Firebase Admin Imports
import firebase_admin
from firebase_admin import credentials, db

# --- LOAD SECRETS ---
load_dotenv()

# --- CONFIGURATION ---

# Add 'session' and 'redirect' to your flask imports
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash

# ... existing imports ...

app = Flask(__name__)

# [CRITICAL] Set a secret key for session security
app.secret_key = "DELSTARFORD_SECURE_KEY_2026" 

# --- WHITELIST CREDENTIALS ---
ADMIN_WHITELIST = {
    "email": "delstarfordisaiah@gmail.com",
    "password": "Delstarford123"
}
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

# --- AI MODELS DATA ---
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

# --- BACKGROUND EMAIL FUNCTION ---
def send_email_background(to_email, subject, html_content):
    """
    This function runs in a separate thread.
    It handles the slow connection to Gmail.
    """
    # Re-fetch env vars inside thread to be safe
    email_user = os.getenv("SENDER_EMAIL")
    email_pass = os.getenv("SENDER_PASSWORD")
    
    if not email_user or not email_pass:
        print("Error: Email credentials missing in background thread.")
        return

    try:
        # Create the email structure
        msg = MIMEMultipart('alternative')
        msg['From'] = email_user
        msg['To'] = to_email
        msg['Subject'] = subject

        # Attach the HTML body
        part = MIMEText(html_content, 'html')
        msg.attach(part)

        # Secure connection with explicit timeout (60 seconds)
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=60) as server:
            server.starttls(context=context) # Secure the connection
            server.login(email_user, email_pass)
            server.send_message(msg)
            
        print(f"Background Email sent successfully to {to_email}")
    except Exception as e:
        print(f"Failed to send background email: {e}")

# --- MAIN EMAIL WRAPPER ---
def send_email_html(to_email, subject, html_content):
    """
    Starts the email sending in a background thread and returns immediately.
    This prevents the 'Worker Timeout' error.
    """
    thread = threading.Thread(target=send_email_background, args=(to_email, subject, html_content))
    thread.start()
    return True

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

# --- ADMIN REPLY ROUTE ---
@app.route('/admin-reply', methods=['POST'])
def admin_reply():
    try:
        data = request.json
        
        # 1. Extract Data
        db_path = data.get('dbPath')
        client_email = data.get('email')
        client_name = data.get('name')
        new_status = data.get('newStatus')
        reply_message = data.get('replyMessage')
        item_type = data.get('type') # 'lead' or 'ticket'
        
        # 2. Update Firebase Status
        if db_path:
            ref = db.reference(db_path)
            ref.update({
                'status': new_status,
                'last_admin_response': str(datetime.datetime.now())
            })

        # 3. Send Email (Only if there is a message)
        if reply_message:
            subject = f"Update on your Project: {new_status}" if item_type == 'lead' else f"Ticket Update: {new_status}"
            
            # Simple HTML Template for Reply
            html_content = f"""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2 style="color: #0f172a;">Hello {client_name},</h2>
                <p>There is an update regarding your {item_type}.</p>
                <p><strong>New Status:</strong> {new_status}</p>
                
                <div style="background: #f1f5f9; padding: 15px; border-left: 4px solid #10b981; margin: 20px 0;">
                    <strong>Admin Response:</strong><br>
                    {reply_message}
                </div>
                
                <p>Best Regards,<br>Delstarford Works Admin Team</p>
            </body>
            </html>
            """
            
            send_email_html(client_email, subject, html_content)
            return jsonify({"success": True, "message": "Email sent and DB updated"})
        else:
            return jsonify({"success": True, "message": "DB updated (no email sent)"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
# --- PROTECTED ADMIN ROUTES ---

@app.route('/admin-login')
def admin_login_page():
    # If already logged in, skip login page
    if session.get('is_admin'):
        return redirect(url_for('admin_page'))
    return render_template('admin_login.html')

@app.route('/admin-login-submit', methods=['POST'])
def admin_login_submit():
    email = request.form.get('email')
    password = request.form.get('password')
    
    # CHECK WHITELIST
    if email == ADMIN_WHITELIST["email"] and password == ADMIN_WHITELIST["password"]:
        session['is_admin'] = True
        return redirect(url_for('admin_page'))
    else:
        flash("Access Denied: Invalid Credentials.")
        return redirect(url_for('admin_login_page'))

@app.route('/admin-logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login_page'))

@app.route('/admin')
def admin_page():
    # SERVER-SIDE PROTECTION
    if not session.get('is_admin'):
        return redirect(url_for('admin_login_page'))
    
    return render_template('admin_response.html')

@app.route('/estimator')
def estimator():
    # If your estimator is inside custom.html, redirect there
    return render_template('custom.html')
# --- AGREEMENT ROUTES ---
@app.route('/agreement')
def agreement_page():
    return render_template('agreement.html')

@app.route('/submit-agreement', methods=['POST'])
def submit_agreement():
    try:
        data = request.form
        
        # 1. Extract Data
        client_name = data.get('client_name')
        sector = data.get('sector_select')
        custom_total = data.get('custom_total')
        justification = data.get('justification')
        signature = data.get('signature')
        date_signed = data.get('date')
        
        # 2. Determine Final Price
        standard_rates = {
            "Health": 30000,
            "Security": 28000,
            "Agriculture": 25000,
            "Education": 20000,
            "Social": 15000,
            "Finance": 10000
        }
        
        if sector == "Custom":
            total_cost = int(custom_total) if custom_total else 0
            details_text = f"Custom Budget Proposed. Justification: {justification}"
        else:
            total_cost = standard_rates.get(sector, 0)
            details_text = "Standard Industry Rate Applied."

        # 3. Save to Firebase
        contract_id = f"CNT-{random.randint(10000, 99999)}"
        try:
            ref = db.reference(f'agreements/{contract_id}')
            ref.set({
                'contract_id': contract_id,
                'client_name': client_name,
                'sector': sector,
                'total_cost': total_cost,
                'signature': signature,
                'date': date_signed,
                'status': 'Signed & Pending Review' if sector == 'Custom' else 'Active',
                'timestamp': str(datetime.datetime.now())
            })
        except Exception as e:
            print(f"DB Error: {e}")

        # 4. Send Emails (Re-using your professional templates)
        
        # Admin Email (Notification)
        admin_msg = f"""
        SIGNED CONTRACT ALERT
        ---------------------
        Client: {client_name}
        Sector: {sector}
        Value: {total_cost:,} KSH
        Signature: {signature}
        
        View full contract in Firebase Console.
        """
        # We assume you want the nice HTML version, so we map fields to your existing template
        admin_html = render_template('email_admin.html', 
                                     name=client_name, 
                                     email="[See Contract]", 
                                     service=f"AGREEMENT: {sector}", 
                                     budget=f"{total_cost:,} KSH", 
                                     timeline="Per Contract", 
                                     details=f"Digital Signature: {signature}<br>Date: {date_signed}<br>Notes: {details_text}")
        
        send_email_html(SENDER_EMAIL, f"📝 Contract Signed: {client_name}", admin_html)

        # Client Email (Receipt)
        # We reuse the client template but tweak the message slightly via the 'service' field
        client_html = render_template('email_client.html', 
                                      name=client_name, 
                                      service=f"Service Agreement ({contract_id})")
        
        send_email_html(SENDER_EMAIL, f"Agreement Receipt - {contract_id}", client_html)

        return jsonify({"success": True, "contract_id": contract_id})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# At the very top with other imports:
from werkzeug.utils import secure_filename
from email.mime.application import MIMEApplication # For attachments

# ... existing code ...

@app.route('/register')
def register_page():
    return render_template('register.html')
@app.route('/register2')
def register2_page():
    return render_template('register2.html')

@app.route('/submit-registration', methods=['POST'])
def submit_registration():
    try:
        # 1. Get Text Data
        data = request.form
        name = data.get('full_name')
        email = data.get('email')
        role = data.get('role')
        phone = data.get('phone')
        
        # 2. Handle Files (We will email them to Admin)
        uploaded_files = []
        for file_key in ['doc_id', 'doc_kra', 'doc_photo']:
            file = request.files.get(file_key)
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Read file data into memory to attach to email
                file_data = file.read()
                uploaded_files.append({'name': filename, 'data': file_data})

        # 3. Save Text Data to Firebase
        reg_id = f"MEM-{random.randint(10000, 99999)}"
        try:
            ref = db.reference(f'members/{reg_id}')
            ref.set({
                'member_id': reg_id,
                'name': name,
                'email': email,
                'role': role,
                'phone': phone,
                'payment_method': data.get('payment_method'),
                'status': 'Pending Review',
                'timestamp': str(datetime.datetime.now())
            })
        except Exception as e:
            print(f"DB Error: {e}")

        # 4. SEND EMAIL TO ADMIN (With Attachments)
        # We write a custom email sender here to handle attachments
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = SENDER_EMAIL # Send to yourself
            msg['Subject'] = f"📄 New Job Application: {name} ({role})"
            
            body = f"""
            NEW MEMBER REGISTRATION
            -----------------------
            Name: {name}
            Role: {role}
            Email: {email}
            Phone: {phone}
            
            Payment: {data.get('payment_method')}
            Signature: {data.get('signature')}
            
            ATTACHED: ID, KRA, and Photo.
            """
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach Files
            for f in uploaded_files:
                part = MIMEApplication(f['data'], Name=f['name'])
                part['Content-Disposition'] = f'attachment; filename="{f["name"]}"'
                msg.attach(part)
                
            # Connect & Send
            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
                
        except Exception as e:
            print(f"Email Attachment Error: {e}")

        # 5. Send Welcome Email to User (HTML)
        user_html = render_template('email_client.html', 
                                    name=name, 
                                    service=f"Application: {role} (Ref: {reg_id})")
        send_email_html(email, "Application Received - Delstarford Works", user_html)

        return jsonify({"success": True})

    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": str(e)}), 500
# --- SUPPORT TICKET SYSTEM ---
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
                'ticket_id': display_ticket_id, 
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

        # 4. Send Emails (Uses Background Threading)
        
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

# --- MAIN LOGIC ROUTE (Email + Form + Estimator) ---
@app.route('/custom', methods=['GET', 'POST'])
def custom_solution():
    if request.method == 'GET':
        return render_template('custom.html') 
    
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
            admin_html = render_template('email_admin.html', 
                                         name=name, email=email, service=service, 
                                         budget=budget, timeline=timeline, details=details)
            
            client_html = render_template('email_client.html', 
                                          name=name, service=service)

            # 3. SEND EMAILS (Now instant thanks to threading)
            send_email_html(SENDER_EMAIL, f"New Lead: {service} from {name}", admin_html)
            send_email_html(email, "We received your request - Delstarford Works", client_html)
            
            # 4. Save to Firebase
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
                print(f"Database Error: {e}")

            return jsonify({"success": True, "message": "Request sent! Check your email for confirmation."}), 200

        except Exception as e:
            print(f"Server Error: {e}")
            return jsonify({"success": False, "message": "Server error occurred."}), 500

# --- ESTIMATOR LOGIC ---
@app.route('/calculate-estimate', methods=['POST'])
def calculate_estimate():
    try:
        data = request.json
        BASE_PRICE = 15000  
        model_type = data.get('modelType')
        try:
            data_size = int(data.get('dataSize', 0))
        except ValueError:
            data_size = 0
            
        complexity = data.get('complexity', 'standard')
        
        multipliers = {'standard': 1.0, 'advanced': 2.5, 'enterprise': 5.0}
        model_adds = {'tabular': 5000, 'vision': 25000, 'nlp': 15000, 'bio': 30000}
        
        data_rate = (data_size / 1000) * 50
        subtotal = (BASE_PRICE + model_adds.get(model_type, 0)) * multipliers.get(complexity, 1.0)
        total_estimate = subtotal + data_rate
        
        return jsonify({
            "estimate": round(total_estimate, 2),
            "currency": "KSH",
            "breakdown": {"setup": subtotal, "data_processing": data_rate}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/dashboard-data')
def get_dashboard_data():
    user_id = 'user_123' 
    try:
        ref = db.reference(f'active_projects/{user_id}')
        data = ref.get()
        return jsonify(data if data else {})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)