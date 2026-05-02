import os
import datetime
import smtplib
import ssl
import threading
import random
import requests
import base64
import stripe
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from dotenv import load_dotenv

# Firebase Admin Imports
import firebase_admin
from firebase_admin import credentials, db, auth as firebase_auth

from chatbot.scripts.predict import ChatbotPredictor

# ==============================================================================
# 1. CONFIGURATION & SETUP
# ==============================================================================

# Load Environment Variables
load_dotenv()

app = Flask(__name__)

# --- CHATBOT INITIALIZATION ---
MODEL_DIR = os.path.join("chatbot", "model")
DATA_PATH = os.path.join("chatbot", "data", "knowledge.json")
try:
    if os.path.exists(os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl")):
        masha_predictor = ChatbotPredictor(MODEL_DIR, DATA_PATH)
        print("✅ MASHA Chatbot Initialized.")
    else:
        masha_predictor = None
        print("⚠️ WARNING: Chatbot model not found. Run train.py to enable MASHA.")
except Exception as e:
    masha_predictor = None
    print(f"❌ Error Initializing MASHA: {e}")
# [CRITICAL] Set a secret key for session security
app.secret_key = os.getenv("FLASK_SECRET_KEY", "DELSTARFORD_SECURE_KEY_2026")

# --- PAYMENT CONFIGURATION ---
# Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')

# PayPal
PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')

# M-Pesa (Sandbox Credentials)
MPESA_CONSUMER_KEY = os.getenv('MPESA_KEY')
MPESA_CONSUMER_SECRET = os.getenv('MPESA_SECRET')
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY', )
MPESA_SHORT_CODE = '174379' 
MPESA_CALLBACK_URL = os.getenv('MPESA_CALLBACK_URL', 'https://your-ngrok-url.ngrok-free.app/callback')

# --- WHITELIST CREDENTIALS (Admin) ---


# --- EMAIL CONFIG ---
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# --- FIREBASE INITIALIZATION ---
# Automatically loads credentials based on your .env file or fallback
SERVICE_ACCOUNT_KEY = os.getenv("SERVICE_ACCOUNT_KEY", 'service_account_key.json') 
DATABASE_URL = os.getenv("DATABASE_URL")

if not firebase_admin._apps:
    try:
        if os.path.exists(SERVICE_ACCOUNT_KEY):
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
            firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
            print("✅ Firebase Initialized Successfully.")
        else:
            print("⚠️ WARNING: service_account_key.json not found. Database features will fail.")
    except Exception as e:
        print(f"❌ Error Initializing Firebase: {e}")

# --- AI MODELS DATA ---
AI_MODELS = [
    {"id": 1, "name": "DexaGen AI", "category": "Pharmacology", "price": "KSh 85,000", "tech": "DeepChem, WebGL", "desc": "Neuro-Symbolic engine simulating 3D drug interactions."},
    {"id": 19, "name": "SMART HEALTH AI", "category": "Healthcare", "price": "KSh 95,000", "tech": "Scikit-learn, IoT", "desc": "Predicts malaria-prone regions via mosquito tracking."},
    {"id": 20, "name": "Reen AI", "category": "EdTech", "price": "KSh 40,000", "tech": "3D Rendering", "desc": "Interactive biochemistry tool for visualizing molecules."},
    {"id": 6, "name": "Agritech Field Manager", "category": "Agri-Tech", "price": "KSh 60,000", "tech": "Django, Plotly", "desc": "Lab-to-field experiment tracking."},
    {"id": 11, "name": "Plant Pathology AI", "category": "Agri-Tech", "price": "KSh 55,000", "tech": "PyTorch, IoT", "desc": "Disease detection system with voice navigation."},
    {"id": 14, "name": "ANIPRO AI", "category": "FinTech / Agri", "price": "KSh 70,000", "tech": "Predictive Models", "desc": "Derisking platform connecting farmers to insurance."},
    {"id": 2, "name": "ScriptureAI", "category": "NLP", "price": "KSh 45,000", "tech": "Vector DB, RAG", "desc": "Semantic search engine for theological texts."},
    {"id": 8, "name": "Eco-Ride", "category": "Environment", "price": "KSh 50,000", "tech": "React Native", "desc": "Carbon footprint tracking app."},
]

# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================

def get_mpesa_access_token():
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        r = requests.get(api_url, auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET))
        r.raise_for_status()
        return r.json()['access_token']
    except Exception as e:
        print(f"Error getting M-Pesa token: {e}")
        return None

def generate_mpesa_password(timestamp):
    data_to_encode = MPESA_SHORT_CODE + MPESA_PASSKEY + timestamp
    return base64.b64encode(data_to_encode.encode()).decode('utf-8')

def send_email_background(to_email, subject, html_content):
    """ Runs in a separate thread to prevent blocking the user response """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print(">> Email credentials missing.")
        return

    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=60) as server:
            server.starttls(context=context)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print(f">> Email sent to {to_email}")
    except Exception as e:
        print(f">> Failed to send email: {e}")

def send_email_html(to_email, subject, html_content):
    thread = threading.Thread(target=send_email_background, args=(to_email, subject, html_content))
    thread.start()
    return True

def safe_dict(data):
    if isinstance(data, dict): return data
    if isinstance(data, list): return {str(i): v for i, v in enumerate(data) if v is not None}
    return {}

# ==============================================================================
# 3. PAGE ROUTES (View Layer)
# ==============================================================================
from flask import send_from_directory
import os

# ADD THESE ROUTES BEFORE YOUR @app.route('/')
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'sw.js', mimetype='application/javascript')

@app.route('/')
def home(): return render_template('home.html')

@app.route('/services')
def services(): return render_template('services.html')

@app.route('/ai-lab')
def ai_lab():
    return render_template('ai_lab.html', 
                           models=AI_MODELS, 
                           paypal_client_id=PAYPAL_CLIENT_ID,
                           stripe_publishable_key=STRIPE_PUBLISHABLE_KEY)


@app.route('/location')
def location(): return render_template('location.html')

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/privacy')
def privacy(): return render_template('privacy.html')

@app.route('/case-study')
def case_study(): return render_template('case_study.html')

@app.route('/login')
def login(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

# ==============================================================================
# TEAM ONBOARDING & REGISTRATION ROUTES
# ==============================================================================

@app.route('/register2', methods=['GET'])
def team_onboarding():
    """
    Serves the Enterprise Team & Partner Application Portal.
    """
    return render_template('register2.html')


@app.route('/submit-registration', methods=['POST'])
def submit_registration():
    """
    Processes the cryptographic team application. 
    Handles file size validations and triggers the frontend fallback if payload limits are exceeded.
    """
    try:
        data = request.form
        role = data.get('role', 'Applicant')
        email = data.get('email')
        full_name = data.get('full_name')
        user_id = f"USR-{random.randint(10000, 99999)}"
        
        # 1. FILE PAYLOAD VALIDATION (Triggers Fallback if too large)
        # Check total size of uploaded files to prevent server memory crashes
        total_file_size = 0
        for file_key in ['doc_id', 'doc_kra', 'doc_photo']:
            file = request.files.get(file_key)
            if file:
                file.seek(0, os.SEEK_END) # Go to end of file to get size
                total_file_size += file.tell()
                file.seek(0) # Reset file pointer for later use
        
        # If payload is over ~10MB, reject it with a 413 error.
        # This explicitly triggers the beautiful `mailto:` fallback we built in register2.html
        if total_file_size > 10 * 1024 * 1024:
            logger.warning(f"Payload too large ({total_file_size} bytes) for {email}. Triggering client fallback.")
            return jsonify({"success": False, "message": "Payload size exceeded limit."}), 413

        # 2. BUILD USER PROFILE
        user_profile = {
            'user_id': user_id, 
            'full_name': full_name,
            'email': email, 
            'role': role,
            'dob': data.get('dob'),
            'nationality': data.get('nationality'),
            'phone': data.get('phone'),
            'address': data.get('address'),
            'skills': data.get('skills', 'N/A'),
            'linkedin': data.get('linkedin', ''),
            'portfolio': data.get('portfolio', ''),
            'payment_method': data.get('payment_method'),
            'status': 'Pending Review', 
            'timestamp': str(datetime.datetime.now())
        }

        # Append specific financial node data based on selection
        if data.get('payment_method') == 'bank':
            user_profile.update({
                'bank_name': data.get('bank_name'), 
                'bank_branch': data.get('bank_branch'), 
                'bank_acc_name': data.get('bank_acc_name'), 
                'bank_acc_num': data.get('bank_acc_num')
            })
        else:
            user_profile.update({
                'mobile_provider': data.get('mobile_provider'), 
                'mobile_number': data.get('mobile_number')
            })

        # 3. SAVE TEXT DATA TO FIREBASE REALTIME DB
        db.reference(f'members/{user_id}').set(user_profile)

        # 4. EMAIL NOTIFICATIONS (Optional but recommended)
        # Notify the High Council
        admin_subject = f"New Team Application: {full_name} ({role})"
        admin_body = f"""
        <h2>New Application Received</h2>
        <p><strong>Name:</strong> {full_name}</p>
        <p><strong>Role:</strong> {role}</p>
        <p><strong>Email:</strong> {email}</p>
        <p>Please log in to the admin dashboard or check Firebase to view full details.</p>
        """
        send_email_html(SENDER_EMAIL, admin_subject, admin_body)

        # 5. SUCCESS RESPONSE
        return jsonify({"success": True, "message": "Profile secured and transmitted."})

    except Exception as e:
        logger.error(f"Registration Route Error: {e}")
        # A 500 error will securely trigger the frontend fallback mechanism
        return jsonify({"success": False, "message": "Transmission failed. Fallback required."}), 500
    
    
    
@app.route('/support')
def support(): return render_template('support.html')

@app.route('/agreement')
def agreement_page(): return render_template('agreement.html')
import os
import requests
import base64
import datetime
from flask import request, jsonify
from requests.auth import HTTPBasicAuth
from firebase_admin import db # Ensure db is imported if it isn't already at the top of your file
import stripe # Ensure stripe is imported if it isn't already

# Ensure Stripe uses the secret key from your .env
stripe.api_key = os.environ.get('SECRET_KEY')

# ==============================================================================
# 4. PAYMENT PROCESSING CONFIGURATION & HELPERS
# ==============================================================================

# Pull credentials securely from the .env file
MPESA_CONSUMER_KEY = os.environ.get('CONSUMER_KEY')
MPESA_CONSUMER_SECRET = os.environ.get('CONSUMER_SECRET')
MPESA_SHORT_CODE = os.environ.get('BUSINESS_SHORT_CODE')
MPESA_PASSKEY = os.environ.get('PASSKEY')
MPESA_CALLBACK_URL = os.environ.get('CALLBACK_URL')

def get_mpesa_access_token():
    """Authenticates with Daraja to get a temporary access token."""
    api_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        # HTTPBasicAuth automatically handles the required Base64 encoding of Key:Secret
        response = requests.get(api_url, auth=HTTPBasicAuth(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET))
        response.raise_for_status() # Will raise an exception for 400/500 errors
        return response.json()['access_token']
    except Exception as e:
        print(f"❌ Error getting M-Pesa token: {e}")
        if 'response' in locals() and response is not None:
            print(f"Safaricom Response: {response.text}")
        return None

def generate_mpesa_password(timestamp):
    """Generates the Base64 encoded password required for STK Push."""
    data_to_encode = MPESA_SHORT_CODE + MPESA_PASSKEY + timestamp
    encoded_string = base64.b64encode(data_to_encode.encode())
    return encoded_string.decode('utf-8')


# ==============================================================================
# 5. PAYMENT PROCESSING ROUTES
# ==============================================================================
# --- M-PESA STK PUSH ---
@app.route('/pay', methods=['POST'])
def pay():
    data = request.json
    raw_phone = data.get('phone') 
    cart_total = data.get('amount', 1)
    cart_items = data.get('items', []) 

    if not raw_phone:
         return jsonify({"error": "Phone number is required"}), 400

    # Sanitize phone number into 254XXXXXXXXX format
    clean_phone = ''.join(filter(str.isdigit, str(raw_phone)))
    if clean_phone.startswith('07') or clean_phone.startswith('01'): 
        formatted_phone = '254' + clean_phone[1:] 
    elif clean_phone.startswith('254') and len(clean_phone) == 12: 
        formatted_phone = clean_phone            
    elif len(clean_phone) == 9:
        formatted_phone = '254' + clean_phone
    else: 
        formatted_phone = clean_phone 

    # Handle Amount
    try:
        amount = int(cart_total)
        if amount <= 0: amount = 1
    except:
        amount = 1 
        
    # Authenticate with Daraja
    access_token = get_mpesa_access_token()
    if not access_token:
        return jsonify({"error": "Failed to authenticate with Safaricom. Check console logs."}), 500

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    password = generate_mpesa_password(timestamp)

    headers = {
        'Authorization': f'Bearer {access_token}', 
        'Content-Type': 'application/json'
    }
    
    payload = {
        "BusinessShortCode": MPESA_SHORT_CODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount, 
        "PartyA": formatted_phone, 
        "PartyB": MPESA_SHORT_CODE,
        "PhoneNumber": formatted_phone, 
        "CallBackURL": MPESA_CALLBACK_URL,
        "AccountReference": "WORKS LTD",
        "TransactionDesc": f"Order of {len(cart_items)} AI Models"
    }

    stk_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    
    try:
        response = requests.post(stk_url, json=payload, headers=headers)
        
        # --- NEW: BULLETPROOF ERROR CATCHING ---
        try:
            response_data = response.json()
        except Exception:
            print("=======================================")
            print(f"❌ SAFARICOM API REJECTED THE REQUEST")
            print(f"Status Code: {response.status_code}")
            print(f"Raw Response: {response.text}")
            print(f"Payload Sent: {payload}")
            print("=======================================")
            return jsonify({"error": "Safaricom API is temporarily down or rejected the payload. Check terminal."}), 500
        # ---------------------------------------

        # Log the Pending Order securely into Firebase
        if response_data.get('ResponseCode') == '0':
            checkout_request_id = response_data.get('CheckoutRequestID')
            try:
                 db.reference(f'payments/initiated/{checkout_request_id}').set({
                     'phone_number': formatted_phone,
                     'amount_billed': amount,
                     'items_purchased': cart_items,  
                     'status': 'Pending Verification',
                     'timestamp': str(datetime.datetime.now())
                 })
            except Exception as firebase_err: 
                 print("Firebase Error:", firebase_err) 
                 
            return jsonify(response_data)
        else:
            # If Daraja returns a clean JSON error message
            print("Daraja Error:", response_data)
            return jsonify({"error": response_data.get('errorMessage', 'Failed to initiate STK push')}), 400
            
    except Exception as e:
        print(f"STK Push Error: {e}")
        return jsonify({"error": str(e)}), 500
    
    
# --- M-PESA CALLBACK ---
@app.route('/callback', methods=['POST'])
def callback():
    data = request.json
    print(">> MPESA CALLBACK RECEIVED:", data)
    
    try:
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        
        if checkout_request_id:
            # Save raw callback
            db.reference(f'payments/callbacks/{checkout_request_id}').set({
                'payload': data, 
                'timestamp': str(datetime.datetime.now())
            })
            
            # Update original order status
            order_ref = db.reference(f'payments/initiated/{checkout_request_id}')
            if result_code == 0:
                order_ref.update({
                    'status': 'Payment Successful', 
                    'result_desc': stk_callback.get('ResultDesc')
                })
            else:
                order_ref.update({
                    'status': 'Payment Failed', 
                    'failure_reason': stk_callback.get('ResultDesc')
                })
                
    except Exception as e: 
        print("Error processing callback:", e)
        
    return "OK"
@app.route('/check-payment-status/<checkout_id>', methods=['GET'])
def check_payment_status(checkout_id):
    """Allows the frontend to poll the status of an M-Pesa transaction"""
    try:
        payment_ref = db.reference(f'payments/initiated/{checkout_id}')
        payment_data = payment_ref.get()
        
        if not payment_data:
            return jsonify({"status": "Not Found"}), 404
            
        return jsonify({
            "status": payment_data.get('status', 'Pending Verification'),
            "failure_reason": payment_data.get('failure_reason', '')
        })
    except Exception as e:
        print(f"Status Check Error: {e}")
        return jsonify({"error": str(e)}), 500
    
    
# --- STRIPE PAYMENT INTENT ---
@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    try:
        data = request.json
        amount = int(data.get('amount', 0))
        
        if amount <= 0:
            return jsonify(error="Invalid amount"), 400
            
        # Stripe accepts KES as a zero-decimal currency (KSh 100 = 100)
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='kes',
            automatic_payment_methods={'enabled': True},
        )
        return jsonify({'clientSecret': intent.client_secret})
    except Exception as e:
        print(f"Stripe Error: {e}")
        return jsonify(error=str(e)), 403
# ==============================================================================
# 5. FORM SUBMISSION & CLIENT ROUTES
# ==============================================================================

@app.route('/contact', methods=['POST'])
def submit_contact():
    try:
        data = request.json if request.is_json else request.form
        name, email, subject, message = data.get('name'), data.get('email'), data.get('subject'), data.get('message')

        admin_subject = f"📩 New Inquiry: {subject} from {name}"
        admin_body = render_template('email_contact_admin.html', name=name, email=email, subject=subject, message=message, timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        send_email_html(SENDER_EMAIL, admin_subject, admin_body)

        user_subject = "We received your message - Delstarford Works"
        user_body = render_template('email_contact_user.html', name=name)
        send_email_html(email, user_subject, user_body)

        try:
            db.reference('leads/contact_form').push({
                'name': name, 'email': email, 'subject': subject, 'message': message, 'timestamp': str(datetime.datetime.now())
            })
        except: pass

        return jsonify({"success": True, "message": "Message sent successfully!"})
    except Exception as e:
        return jsonify({"success": False, "message": "Server error. Please try again."}), 500

@app.route('/submit-ticket', methods=['POST'])
def submit_ticket():
    try:
        data = request.form
        db_key = f"TKT-{random.randint(1000, 9999)}"
        display_ticket_id = f"#{db_key}"
        
        db.reference(f'support_tickets/{db_key}').set({
            'ticket_id': display_ticket_id, 
            'name': data.get('name'), 'email': data.get('email'),
            'subject': data.get('subject'), 'message': data.get('message'),
            'priority': data.get('priority'), 'category': data.get('category'),
            'status': 'Open', 'timestamp': str(datetime.datetime.now())
        })
        
        admin_html = render_template('email_ticket_admin.html', ticket_id=display_ticket_id, name=data.get('name'), email=data.get('email'), subject=data.get('subject'), message=data.get('message'))
        send_email_html(SENDER_EMAIL, f"New Ticket {display_ticket_id}", admin_html)
        
        user_html = render_template('email_ticket_user.html', name=data.get('name'), ticket_id=display_ticket_id, subject=data.get('subject'))
        send_email_html(data.get('email'), f"Support Ticket Received - {display_ticket_id}", user_html)

        return jsonify({"success": True, "ticket_id": display_ticket_id})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/custom', methods=['GET', 'POST'])
def custom_solution():
    if request.method == 'GET': return render_template('custom.html')
    
    try:
        data = request.form
        name, email, service = data.get('name'), data.get('email'), data.get('service')
        
        db.reference('leads/service_requests').push({
            'name': name, 'email': email, 'service': service, 'details': data.get('details'),
            'status': 'Pending', 'timestamp': str(datetime.datetime.now())
        })
        
        admin_html = render_template('email_admin.html', name=name, email=email, service=service, details=data.get('details'))
        send_email_html(SENDER_EMAIL, f"New Lead: {service}", admin_html)
        
        client_html = render_template('email_client.html', name=name, service=service)
        send_email_html(email, "We received your request", client_html)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# --- CONTACT FORM ROUTE ---
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'GET':
        return render_template('contact.html')
    
    if request.method == 'POST':
        try:
            # 1. Get Data from Form
            data = request.json # Using JSON for AJAX
            if not data:
                data = request.form # Fallback for standard form submit

            name = data.get('name')
            email = data.get('email')
            subject = data.get('subject')
            message = data.get('message')

            # 2. EMAIL TO ADMIN (Notification)
            admin_subject = f"📩 New Inquiry: {subject} from {name}"
            admin_body = render_template('email_contact_admin.html', 
                                         name=name, email=email, subject=subject, message=message, 
                                         timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            send_email_html(SENDER_EMAIL, admin_subject, admin_body)

            # 3. EMAIL TO USER (Confirmation Receipt)
            user_subject = "We received your message - Delstarford Works"
            user_body = render_template('email_contact_user.html', name=name)
            send_email_html(email, user_subject, user_body)

            # 4. Save to Firebase (Optional Log)
            try:
                db.reference('leads/contact_form').push({
                    'name': name, 'email': email, 'subject': subject, 'message': message,
                    'timestamp': str(datetime.datetime.now())
                })
            except:
                pass

            return jsonify({"success": True, "message": "Message sent successfully!"})

        except Exception as e:
            print(f"Contact Error: {e}")
            return jsonify({"success": False, "message": "Server error. Please try again."}), 500
        
@app.route('/submit-agreement', methods=['POST'])
def submit_agreement():
    try:
        data = request.form
        client_name, sector, custom_total = data.get('client_name'), data.get('sector_select'), data.get('custom_total')
        
        standard_rates = {"Health": 30000, "Security": 28000, "Agriculture": 25000, "Education": 20000, "Social": 15000, "Finance": 10000}
        total_cost = int(custom_total) if sector == "Custom" and custom_total else standard_rates.get(sector, 0)
        
        contract_id = f"CNT-{random.randint(10000, 99999)}"
        db.reference(f'agreements/{contract_id}').set({
            'contract_id': contract_id, 'client_name': client_name, 'sector': sector, 
            'total_cost': total_cost, 'signature': data.get('signature'), 
            'date': data.get('date'), 'timestamp': str(datetime.datetime.now())
        })

        admin_html = render_template('email_admin.html', name=client_name, email="[Contract]", service=f"Contract: {sector}", budget=total_cost, timeline="Signed", details="See DB for Signature")
        send_email_html(SENDER_EMAIL, f"📝 Contract Signed: {client_name}", admin_html)
        
        client_html = render_template('email_client.html', name=client_name, service=f"Service Agreement ({contract_id})")
        send_email_html(SENDER_EMAIL, f"Agreement Receipt - {contract_id}", client_html)

        return jsonify({"success": True, "contract_id": contract_id})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/estimator')
def estimator():
    return render_template('custom.html')

@app.route('/calculate-estimate', methods=['POST'])
def calculate_estimate():
    try:
        data = request.json
        BASE_PRICE = 15000  
        model_type = data.get('modelType')
        data_size = int(data.get('dataSize', 0)) if data.get('dataSize') else 0
            
        complexity = data.get('complexity', 'standard')
        multipliers = {'standard': 1.0, 'advanced': 2.5, 'enterprise': 5.0}
        model_adds = {'tabular': 5000, 'vision': 25000, 'nlp': 15000, 'bio': 30000}
        
        data_rate = (data_size / 1000) * 50
        subtotal = (BASE_PRICE + model_adds.get(model_type, 0)) * multipliers.get(complexity, 1.0)
        total_estimate = subtotal + data_rate
        
        return jsonify({"estimate": round(total_estimate, 2), "currency": "KSH", "breakdown": {"setup": subtotal, "data_processing": data_rate}})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ==============================================================================
# 6. DASHBOARD & ADMIN ROUTES
# ==============================================================================

@app.route('/admin-login')
def admin_login_page():
    if session.get('is_admin'): return redirect(url_for('admin_page'))
    return render_template('admin_login.html')

@app.route('/admin-login-submit', methods=['POST'])
def admin_login_submit():
    email = request.form.get('email')
    password = request.form.get('password')
    
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
    if not session.get('is_admin'): return redirect(url_for('admin_login_page'))
    return render_template('admin_response.html')




from flask import render_template, make_response

from flask import render_template, make_response
import logging

# ==============================================================================
# CLIENT DASHBOARD ROUTE
# ==============================================================================
@app.route('/dashboard', methods=['GET'])
def dashboard():
    """
    Secure Client Dashboard Route.
    Serves the portal UI. Authentication and data fetching are strictly 
    managed client-side via Firebase to ensure real-time syncing.
    """
    try:
        response = make_response(render_template('dashboard.html'))
        
        # Security: Strictly prevent browser caching to protect sensitive 
        # financial and API data on shared devices after logout.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
        
    except Exception as e:
        logging.error(f"Failed to load dashboard: {e}")
        return make_response("System Error: Dashboard temporarily unavailable. Please contact support.", 500)

@app.route('/admin-dashboard', methods=['GET'])
def admin_dashboard():
    """
    Admin Command Center Route.
    Serves the secure admin UI. Role validation is handled client-side.
    """
    response = make_response(render_template('admin_dashboard.html'))
    # Strict cache prevention for high-clearance administrative routes
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return response

@app.route('/admin-reply', methods=['POST'])
def admin_reply():
    try:
        data = request.json
        db_path, client_email, client_name = data.get('dbPath'), data.get('email'), data.get('name')
        new_status, reply_message, item_type = data.get('newStatus'), data.get('replyMessage'), data.get('type') 
        
        if db_path:
            db.reference(db_path).update({'status': new_status, 'last_admin_response': str(datetime.datetime.now())})

        if reply_message:
            subject = f"Update on your Project: {new_status}"
            html_content = f"""
            <html><body>
                <h2 style="color: #0f172a;">Hello {client_name},</h2>
                <p>Status Update for your {item_type}: <strong>{new_status}</strong></p>
                <div style="background: #f1f5f9; padding: 15px; border-left: 4px solid #10b981;">
                    <strong>Admin Response:</strong><br>{reply_message}
                </div>
                <p>Regards,<br>Delstarford Works</p>
            </body></html>
            """
            send_email_html(client_email, subject, html_content)
            return jsonify({"success": True, "message": "Email sent and DB updated"})
        else:
            return jsonify({"success": True, "message": "DB updated (no email sent)"})
    except Exception as e:
       return jsonify({"success": False, "message": str(e)}), 500

@app.route('/get-clients', methods=['GET'])
def get_clients():
    try:
        raw_service_reqs = db.reference('leads/service_requests').get()
        raw_agreements = db.reference('agreements').get()
        raw_members = db.reference('members').get()
        
        clients = []
        service_reqs = safe_dict(raw_service_reqs)
        agreements = safe_dict(raw_agreements)
        members = safe_dict(raw_members)

        for key, req in service_reqs.items():
            if not isinstance(req, dict): continue
            timestamp = str(req.get('timestamp', ''))
            clients.append({
                "id": str(key), "name": str(req.get('name', 'Unknown')), "email": str(req.get('email', 'N/A')),
                "request": str(req.get('service', 'General Inquiry')), "status": str(req.get('status', 'Pending')),
                "date": timestamp[:10] if len(timestamp) >= 10 else "N/A", "type": "lead"
            })

        for key, agmt in agreements.items():
            if not isinstance(agmt, dict): continue
            date_str = str(agmt.get('date', ''))
            clients.append({
                "id": str(key), "name": str(agmt.get('client_name', 'Unknown')), "email": "Contract Signed",
                "request": f"Contract: {agmt.get('sector', 'General')}", "status": "Approved",
                "date": date_str[:10] if len(date_str) >= 10 else "N/A", "type": "agreement"
            })

        for key, member in members.items():
            if not isinstance(member, dict): continue
            timestamp = str(member.get('timestamp', ''))
            member_data = {
                "id": str(key), "name": str(member.get('full_name', 'Unknown')), "email": str(member.get('email', 'N/A')),
                "request": f"Registration: {member.get('role', 'Member')}", "status": str(member.get('status', 'Pending Review')),
                "date": timestamp[:10] if len(timestamp) >= 10 else "N/A", "type": "registration"
            }
            member_data.update(member)
            clients.append(member_data)

        clients.reverse()
        return jsonify({"success": True, "clients": clients})
    except Exception as e:
        return jsonify({"success": False, "error": f"Python Error: {str(e)}"}), 500

@app.route('/get-announcements', methods=['GET'])
def get_announcements():
    try:
        data = db.reference('announcements').get()
        updates_list = []
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, dict):
                    val['id'] = key
                    updates_list.append(val)
            updates_list.reverse()
        return jsonify({"success": True, "updates": updates_list})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
@app.route('/terms')
def terms():
    """Renders the Terms of Service page."""
    return render_template('terms.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint for MASHA Chatbot"""
    if not masha_predictor:
        return jsonify({"response": "I'm currently undergoing maintenance. Please try again later or contact our support team."})
    
    try:
        data = request.json
        user_query = data.get('message', '')
        if not user_query:
            return jsonify({"response": "I didn't quite catch that. Could you please say something?"})
        
        response = masha_predictor.get_response(user_query)
        return jsonify({"response": response})
    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({"response": "I'm sorry, I encountered an internal error. Could you try rephrasing your question?"}), 500

@app.route('/post-announcement', methods=['POST'])
def post_announcement():
    try:
        data = request.json
        import time
        update_id = f"UPD-{int(time.time())}"
        
        db.reference(f'announcements/{update_id}').set({
            "title": data.get('title'), "description": data.get('description'),
            "type": data.get('type', 'ANNOUNCEMENT'), "date": data.get('date'),
            "location": data.get('location', 'Remote'),
            "priority": "High" if data.get('type') == "EVENT" else "Normal"
        })
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/dashboard-data', methods=['POST'])
def get_dashboard_data():
    try:
        user_email = request.json.get('email') if request.json else None
        if not user_email: return jsonify({"error": "Email required"}), 400

        all_requests = safe_dict(db.reference('leads/service_requests').get())
        user_projects = []
        
        for key, proj in all_requests.items():
            if isinstance(proj, dict) and proj.get('email') == user_email:
                status = str(proj.get('status', 'Pending'))
                progress = 0.1 if status == 'Pending' else (0.6 if status == 'In Progress' else 1.0)
                timestamp = str(proj.get('timestamp', ''))
                user_projects.append({
                    "name": str(proj.get('service', 'Custom Request')), "type": "Requested Service", 
                    "status": status, "progress": progress, "date": timestamp[:10] if len(timestamp) >= 10 else "N/A"
                })

        return jsonify({"success": True, "projects": user_projects})
    except Exception as e:
        print(f"Dashboard Data Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================================================================
# 7. RUN SERVER
# ==============================================================================
if __name__ == '__main__':
    # 'host=0.0.0.0' makes the server accessible on your local network/phone
    app.run(host='0.0.0.0', port=5000, debug=True)