# -*- coding: utf-8 -*-
import os

# Limit multi-threaded libraries to 1 thread to prevent cPanel crash
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

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
        print("[OK] MASHA Chatbot Initialized.")
    else:
        masha_predictor = None
        print("[WARNING] Chatbot model not found. Run train.py to enable MASHA.")
except Exception as e:
    masha_predictor = None
    print(f"[ERROR] Error Initializing MASHA: {e}")
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
ADMIN_WHITELIST = {
    "email": "admin@delstarfordworks.co.ke",
    "password": "AdminPassword123!"
}

# --- EMAIL CONFIG ---
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# --- FIREBASE INITIALIZATION ---
# Automatically loads credentials based on your .env file or fallback
SERVICE_ACCOUNT_KEY = os.getenv("SERVICE_ACCOUNT_KEY", 'service_account_key.json') 
DATABASE_URL = os.getenv("DATABASE_URL")

if not firebase_admin._apps:
    try:
        if os.path.exists(SERVICE_ACCOUNT_KEY):
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
            firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
            print("[OK] Firebase Initialized Successfully.")
        else:
            print("[WARNING] service_account_key.json not found. Database features will fail.")
    except Exception as e:
        print(f"[ERROR] Error Initializing Firebase: {e}")

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
        r = requests.get(api_url, auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET), timeout=15)
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
        if SMTP_SERVER.lower() in ['localhost', '127.0.0.1']:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=60) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=60) as server:
                # Some local servers don't support STARTTLS, so we can try to wrap it or ignore errors
                try:
                    server.starttls(context=context)
                except Exception as e:
                    print(f">> STARTTLS skipped or failed: {e}")
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

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'images'), 'logo.png', mimetype='image/vnd.microsoft.icon')

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

@app.route('/works')
def works(): return render_template('works.html')

@app.route('/quickpay')
@app.route('/quick-pay')
def quick_pay():
    """Renders the standalone Quick Pay portal for direct link sharing."""
    return render_template('quick_pay.html')

# ==============================================================================
# ADVANCED AGRICULTURAL AI SYSTEM MODULES
# ==============================================================================

@app.route('/diagnostics/segmentation')
def disease_segmentation():
    """
    Renders the Leaf Disease Semantic Segmentation Lab.
    """
    return render_template('disease_segmentation.html')

@app.route('/finance/risk-scorer')
def risk_scorer():
    """
    Renders the Micro-Lending Agronomic Risk Scorer.
    """
    return render_template('risk_scorer.html')

@app.route('/biotech/bsf-simulator')
def bsf_simulator():
    """
    Renders the Black Soldier Fly Biomass Growth Simulator.
    """
    return render_template('bsf_simulator.html')

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

@app.route('/submit-general-registration', methods=['POST'])
def submit_general_registration():
    """
    Handles background tasks for general user registration.
    """
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        uid = data.get('uid')

        # Notify Admin of New User
        admin_subject = f"New User Registration: {name}"
        admin_body = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; color: #0f172a;">
            <h2 style="color: #3b82f6;">New Client Account Created</h2>
            <p>A new user has registered an account on Delstarford Works.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Phone:</strong> {phone}</p>
            <p><strong>Firebase UID:</strong> {uid}</p>
            <p style="margin-top: 20px; font-size: 0.85rem; color: #64748b;">This user has been assigned the 'Client' role by default.</p>
        </div>
        """
        send_email_html(SENDER_EMAIL, admin_subject, admin_body)

        # Send Welcome Email to User
        user_subject = "Welcome to Delstarford Works!"
        user_body = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background: #f8fafc; color: #0f172a; border-radius: 12px; border: 1px solid #e2e8f0;">
            <h2 style="color: #3b82f6; margin-top: 0;">Welcome, {name}!</h2>
            <p>Your account has been successfully created. You now have access to the Delstarford Works Client Console.</p>
            <p>With your account, you can:</p>
            <ul style="line-height: 1.6;">
                <li>Track your project progress in real-time.</li>
                <li>Access premium AI models in our lab.</li>
                <li>Manage your payments and invoices.</li>
                <li>Communicate directly with our engineering team.</li>
            </ul>
            <div style="margin-top: 30px;">
                <a href="https://delstarfordworks.co.ke/dashboard" style="background: #3b82f6; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; font-weight: bold;">Access Your Dashboard</a>
            </div>
            <p style="margin-top: 40px; font-size: 0.85rem; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 20px;">
                If you did not create this account, please contact us immediately at support@delstarfordworks.co.ke
            </p>
        </div>
        """
        send_email_html(email, user_subject, user_body)

        return jsonify({"success": True})
    except Exception as e:
        print(f"General Registration Error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    
    
    
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

# B2C Credentials
DARAJA_INITIATOR_NAME = os.environ.get('DARAJA_INITIATOR_NAME')
DARAJA_SECURITY_CREDENTIAL = os.environ.get('DARAJA_SECURITY_CREDENTIAL')
DARAJA_B2C_TIMEOUT_URL = os.environ.get('DARAJA_B2C_TIMEOUT_URL')
DARAJA_B2C_RESULT_URL = os.environ.get('DARAJA_B2C_RESULT_URL')

def get_mpesa_access_token():
    """Authenticates with Daraja to get a temporary access token."""
    api_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        # HTTPBasicAuth automatically handles the required Base64 encoding of Key:Secret
        response = requests.get(api_url, auth=HTTPBasicAuth(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET), timeout=15)
        response.raise_for_status() # Will raise an exception for 400/500 errors
        return response.json()['access_token']
    except Exception as e:
        print(f"[ERROR] Error getting M-Pesa token: {e}")
        if 'response' in locals() and response is not None:
            print(f"Safaricom Response: {response.text}")
        return None

def generate_mpesa_password(timestamp):
    """Generates the Base64 encoded password required for STK Push."""
    data_to_encode = MPESA_SHORT_CODE + MPESA_PASSKEY + timestamp
    encoded_string = base64.b64encode(data_to_encode.encode())
    return encoded_string.decode('utf-8')

def initiate_b2c_payment(phone_number, amount, reason, command_id="SalaryPayment"):
    """Initiates a B2C payment using Daraja API."""
    access_token = get_mpesa_access_token()
    if not access_token:
        print("[ERROR] Failed to get access token for B2C.")
        return {"error": "Authentication failed"}

    # Sanitize phone (e.g. 2547...)
    clean_phone = ''.join(filter(str.isdigit, str(phone_number)))
    if clean_phone.startswith('0'):
        clean_phone = '254' + clean_phone[1:]
    elif clean_phone.startswith('+254'):
        clean_phone = clean_phone[1:]

    import uuid
    payload = {
        "OriginatorConversationID": str(uuid.uuid4()),
        "InitiatorName": DARAJA_INITIATOR_NAME,
        "SecurityCredential": DARAJA_SECURITY_CREDENTIAL,
        "CommandID": command_id,
        "Amount": amount,
        "PartyA": MPESA_SHORT_CODE,
        "PartyB": clean_phone,
        "Remarks": reason,
        "QueueTimeOutURL": DARAJA_B2C_TIMEOUT_URL,
        "ResultURL": DARAJA_B2C_RESULT_URL,
        "Occasion": reason
    }
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Use sandbox for development, switch to production if needed
    # b2c_url = "https://api.safaricom.co.ke/mpesa/b2c/v3/paymentrequest"
    b2c_url = "https://api.safaricom.co.ke/mpesa/b2c/v3/paymentrequest" # Assuming prod as per URL 

    try:
        response = requests.post(b2c_url, json=payload, headers=headers, timeout=15)
        return response.json()
    except Exception as e:
        print(f"B2C Exception: {e}")
        return {"error": str(e)}



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
        response = requests.post(stk_url, json=payload, headers=headers, timeout=15)
        
        # --- NEW: BULLETPROOF ERROR CATCHING ---
        try:
            response_data = response.json()
        except Exception:
            print("=======================================")
            print(f"[ERROR] SAFARICOM API REJECTED THE REQUEST")
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
# EVENTS & TRAINING HUB ROUTES
# ==============================================================================

@app.route('/events')
def events_page():
    try:
        # Fetch announcements of type 'EVENT' from Firebase
        all_announcements = db.reference('announcements').get()
        events = []
        today = datetime.date.today()
        
        if all_announcements:
            for key, val in all_announcements.items():
                if isinstance(val, dict) and val.get('type') == 'EVENT':
                    val['id'] = key
                    
                    # Calculate if registration is expired (more than 2 days past)
                    event_date_str = val.get('date')
                    is_expired = False
                    if event_date_str:
                        try:
                            event_date = datetime.datetime.strptime(event_date_str, '%Y-%m-%d').date()
                            if (today - event_date).days > 2:
                                is_expired = True
                        except: pass
                    
                    val['is_expired'] = is_expired
                    events.append(val)
        
        # Sort by date
        events.sort(key=lambda x: x.get('date', ''), reverse=True)

        # Check if specific event registration is requested (for sharing)
        event_id = request.args.get('event_id')
        single_event = None
        if event_id:
            val = db.reference(f'announcements/{event_id}').get()
            if isinstance(val, dict) and val.get('type') == 'EVENT':
                val['id'] = event_id
                event_date_str = val.get('date')
                is_expired = False
                if event_date_str:
                    try:
                        event_date = datetime.datetime.strptime(event_date_str, '%Y-%m-%d').date()
                        if (today - event_date).days > 2:
                            is_expired = True
                    except: pass
                val['is_expired'] = is_expired
                single_event = val
        
        is_admin = request.args.get('admin') == 'true'
        return render_template('events.html', events=events, single_event=single_event, is_admin=is_admin)
    except Exception as e:
        print(f"Error loading events: {e}")
        return render_template('events.html', events=[], single_event=None)

@app.route('/api/register-event', methods=['POST'])
def register_event():
    try:
        data = request.json
        event_id = data.get('eventId')
        event_name = data.get('eventName')
        name = data.get('name')
        email = data.get('email')
        role = data.get('role')

        # 1. Fetch Event Details and Validate Date
        event_ref = db.reference(f'announcements/{event_id}')
        event_data = event_ref.get()
        
        if not event_data:
            return jsonify({"success": False, "message": "Event not found."}), 404
        
        event_date_str = event_data.get('date')
        if event_date_str:
            try:
                event_date = datetime.datetime.strptime(event_date_str, '%Y-%m-%d').date()
                today = datetime.date.today()
                # If today is more than 2 days past the event date
                if (today - event_date).days > 2:
                    return jsonify({"success": False, "message": "Registration for this event is closed (Deadline: 2 days post-event)."}), 400
            except Exception as date_err:
                print(f"Date parsing error: {date_err}")

        # 2. Log Registration to Firebase
        reg_id = f"REG-{random.randint(1000, 9999)}"
        db.reference(f'event_registrations/{event_id}/{reg_id}').set({
            'name': name,
            'email': email,
            'role': role,
            'timestamp': str(datetime.datetime.now())
        })

        # 3. Fetch Google Meet Link from the specific event in Firebase
        assigned_link = event_data.get('meet_link', "https://meet.google.com/new")

        # 4. Dispatch the Email with the Meet Link
        subject = f"Registration Confirmed: {event_name}"
        
        location_str = event_data.get('location', 'Remote')
        lat = event_data.get('latitude')
        lng = event_data.get('longitude')
        description = event_data.get('description', 'No description provided.')
        event_date_formatted = event_data.get('date', 'TBA')
        
        map_link_html = ""
        if lat and lng:
            map_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            map_link_html = """
            <div style="margin-top: 15px; padding: 12px; background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0;">
                <p style="margin: 0; font-size: 13.5px; color: #475569;">
                    * <strong>Pinned Event Coordinates</strong>:
                </p>
                <a href="{map_url}" target="_blank" style="color: #2563eb; font-weight: 700; text-decoration: none; font-size: 13.5px; display: inline-block; margin-top: 6px;">
                    View on Google Maps & Get Directions &rarr;
                </a>
            </div>
            """.replace('{map_url}', map_url)
        
        html_content = f"""
        <html>
        <body style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #334155; background-color: #f8fafc; padding: 40px 20px; margin: 0;">
            <div style="background-color: white; padding: 40px; border-radius: 16px; border-top: 6px solid #3b82f6; max-width: 600px; margin: 0 auto; box-shadow: 0 10px 25px rgba(15, 23, 42, 0.05); border: 1px solid #e2e8f0;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h2 style="color: #0f172a; font-size: 24px; font-weight: 800; margin: 0 0 10px 0; letter-spacing: -0.5px;">Registration Confirmed!</h2>
                    <p style="color: #64748b; font-size: 15px; margin: 0;">You have successfully secured a spot for our upcoming event.</p>
                </div>
                
                <hr style="border: none; border-top: 1px solid #f1f5f9; margin-bottom: 30px;">
                
                <h3 style="color: #0f172a; font-size: 18px; font-weight: 700; margin: 0 0 15px 0;">Hello {name},</h3>
                <p style="font-size: 15px; line-height: 1.6; color: #475569; margin: 0 0 25px 0;">
                    Your application for <strong style="color: #2563eb;">{event_name}</strong> is confirmed. Below are the key event activities and details:
                </p>
                
                <div style="background-color: #f8fafc; padding: 25px; border-radius: 12px; margin-bottom: 30px; border: 1px solid #f1f5f9;">
                    <h4 style="margin: 0 0 10px 0; font-size: 12px; font-weight: 800; color: #3b82f6; text-transform: uppercase; letter-spacing: 0.5px;">Event Agenda & Details</h4>
                    <p style="margin: 0 0 20px 0; font-size: 14.5px; line-height: 1.6; color: #334155; font-style: italic;">"{description}"</p>
                    
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                        <tr>
                            <td style="padding: 8px 0; color: #64748b; font-weight: 600; width: 100px; vertical-align: top;">Date:</td>
                            <td style="padding: 8px 0; color: #0f172a; font-weight: 700;">{event_date_formatted}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #64748b; font-weight: 600; vertical-align: top;">Location:</td>
                            <td style="padding: 8px 0; color: #0f172a; font-weight: 700;">{location_str}</td>
                        </tr>
                    </table>
                    {map_link_html}
                </div>
                
                <div style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; border: 1px solid #bfdbfe;">
                    <p style="margin: 0 0 15px 0; font-size: 13px; font-weight: 800; color: #1e40af; text-transform: uppercase; letter-spacing: 1px;">Google Meet Conference Node</p>
                    <a href="{assigned_link}" target="_blank" style="background-color: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 800; display: inline-block; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25); font-size: 15px;">Join Live Broadcast</a>
                    <p style="margin: 15px 0 0 0; font-size: 11.5px; color: #64748b;">Or copy this secure link: <span style="font-family: monospace; font-weight: 600; color: #475569;">{assigned_link}</span></p>
                </div>
                
                <p style="font-size: 14px; line-height: 1.5; color: #64748b; margin-bottom: 30px;">
                    Please join the call 5 minutes early to test your speaker and microphone configuration. If you have any inquiries, feel free to open a support ticket on your dashboard.
                </p>
                
                <hr style="border: none; border-top: 1px solid #f1f5f9; margin-bottom: 25px;">
                
                <p style="font-size: 14px; color: #64748b; margin: 0; line-height: 1.5;">
                    Best regards,<br>
                    <strong style="color: #0f172a;">Delstarford Works Operations</strong><br>
                    <span style="font-size: 12px;">Security & Systems Command</span>
                </p>
            </div>
        </body>
        </html>
        """
        
        send_email_html(email, subject, html_content)

        return jsonify({"success": True, "message": "Registered successfully."})
        
    except Exception as e:
        print(f"Event Registration Error: {e}")
        return jsonify({"success": False, "message": "Server error. Please try again."}), 500

import csv
import io
from flask import Response

@app.route('/api/download-registrations/<event_id>', methods=['GET'])
def download_registrations(event_id):
    try:
        registrations_ref = db.reference(f'event_registrations/{event_id}')
        data = registrations_ref.get()
        
        if not data:
            return "No registrations found for this event.", 404

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Registration ID', 'Name', 'Email', 'Role', 'Timestamp'])
        
        for reg_id, reg_data in data.items():
            cw.writerow([
                reg_id,
                reg_data.get('name', ''),
                reg_data.get('email', ''),
                reg_data.get('role', ''),
                reg_data.get('timestamp', '')
            ])
            
        output = si.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=registrations_{event_id}.csv"}
        )
    except Exception as e:
        return str(e), 500

# ==============================================================================
# 5. FORM SUBMISSION & CLIENT ROUTES
# ==============================================================================

@app.route('/contact', methods=['POST'])
def submit_contact():
    try:
        data = request.json if request.is_json else request.form
        name, email, subject, message = data.get('name'), data.get('email'), data.get('subject'), data.get('message')

        admin_subject = f"[INQUIRY] New Inquiry: {subject} from {name}"
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
            admin_subject = f"[INQUIRY] New Inquiry: {subject} from {name}"
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
        send_email_html(SENDER_EMAIL, f"[CONTRACT] Contract Signed: {client_name}", admin_html)
        
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
        
        announcement_data = {
            "title": data.get('title'), 
            "description": data.get('description'),
            "type": data.get('type', 'ANNOUNCEMENT'), 
            "date": data.get('date'),
            "location": data.get('location', 'Remote'),
            "priority": "High" if data.get('type') == "EVENT" else "Normal"
        }

        # Add Google Meet Link if provided
        if data.get('meet_link'):
            announcement_data['meet_link'] = data.get('meet_link')

        # Add Coordinates for Map Pinning if provided
        if data.get('latitude'):
            announcement_data['latitude'] = data.get('latitude')
        if data.get('longitude'):
            announcement_data['longitude'] = data.get('longitude')
        
        db.reference(f'announcements/{update_id}').set(announcement_data)
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
# B2C PAYROLL & STIPENDS ROUTES
# ==============================================================================

@app.route('/admin/api/b2c-pay', methods=['POST'])
def b2c_pay():
    data = request.json
    phone = data.get('phone')
    amount = data.get('amount')
    reason = data.get('reason', 'Stipend')
    name = data.get('name', 'Unknown')
    email = data.get('email', '')

    res = initiate_b2c_payment(phone, amount, reason)
    if 'error' not in res and res.get('ResponseCode') == '0':
        db.reference(f'b2c_payments/history/{res.get("OriginatorConversationID")}').set({
            'name': name, 'email': email, 'phone': phone, 'amount': amount,
            'reason': reason, 'status': 'Pending Verification', 
            'timestamp': str(datetime.datetime.now()),
            'conversation_id': res.get('ConversationID')
        })
        return jsonify({"success": True, "message": "Payment initiated."})
    return jsonify({"success": False, "error": res.get('errorMessage', str(res))})

@app.route('/admin/api/b2c-schedule', methods=['POST'])
def b2c_schedule():
    data = request.json
    schedule_id = f"SCH-{int(datetime.datetime.now().timestamp())}"
    db.reference(f'b2c_payments/schedules/{schedule_id}').set({
        'name': data.get('name'), 'phone': data.get('phone'), 'email': data.get('email'),
        'amount': data.get('amount'), 'reason': data.get('reason'),
        'frequency': data.get('frequency'), 'start_time': data.get('start_time'),
        'last_run': '', 'status': 'Active'
    })
    return jsonify({"success": True, "message": "Schedule added."})

@app.route('/mpesa/b2c/timeout', methods=['POST'])
def b2c_timeout():
    data = request.json
    print("B2C Timeout:", data)
    return "OK"

@app.route('/mpesa/b2c/result', methods=['POST'])
def b2c_result():
    data = request.json
    print("B2C Result:", data)
    try:
        result = data.get('Result', {})
        conv_id = result.get('OriginatorConversationID')
        if conv_id:
            status = 'Completed' if result.get('ResultCode') == 0 else 'Failed'
            db.reference(f'b2c_payments/history/{conv_id}').update({
                'status': status,
                'result_desc': result.get('ResultDesc')
            })
    except Exception as e:
        print("Error in B2C result:", e)
    return "OK"

@app.route('/admin/api/b2c-statements', methods=['GET'])
def b2c_statements():
    try:
        data = db.reference('b2c_payments/history').get() or {}
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Transaction ID', 'Name', 'Phone', 'Amount', 'Reason', 'Status', 'Date'])
        for k, v in data.items():
            if isinstance(v, dict):
                cw.writerow([k, v.get('name'), v.get('phone'), v.get('amount'), v.get('reason'), v.get('status'), v.get('timestamp')])
        
        output = si.getvalue()
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=payroll_statements.csv"})
    except Exception as e:
        return str(e), 500

import time
import uuid as uuid_module

# ==============================================================================
# BULK PAYROLL ROUTE - Professional Multi-Recipient Payment System
# ==============================================================================

@app.route('/admin/api/bulk-pay', methods=['POST'])
def bulk_pay():
    """
    Initiates M-Pesa B2C payments to multiple recipients in a single batch.
    Each recipient has: employee_number, name, phone, amount, department, narration.
    Records a full audit trail with a unique Batch ID in Firebase.
    """
    try:
        data = request.json
        recipients = data.get('recipients', [])
        batch_label = data.get('batch_label', 'Payroll Run')
        initiated_by = data.get('initiated_by', 'System Admin')
        max_cap = data.get('max_cap', None)  # Optional total amount cap

        if not recipients or not isinstance(recipients, list):
            return jsonify({"success": False, "error": "No recipients provided."}), 400

        # Validate all recipients before processing
        for i, r in enumerate(recipients):
            if not r.get('phone'):
                return jsonify({"success": False, "error": f"Recipient #{i+1} missing phone number."}), 400
            if not r.get('amount') or int(r.get('amount', 0)) < 10:
                return jsonify({"success": False, "error": f"Recipient #{i+1} has invalid amount (min KSh 10)."}), 400

        # Optional: Enforce total amount cap
        total_amount = sum(int(r.get('amount', 0)) for r in recipients)
        if max_cap and total_amount > int(max_cap):
            return jsonify({
                "success": False,
                "error": f"Total amount KSh {total_amount:,} exceeds configured cap of KSh {int(max_cap):,}."
            }), 400

        # Generate a unique Batch ID for this run
        batch_id = f"BATCH-{int(time.time())}-{uuid_module.uuid4().hex[:6].upper()}"
        batch_timestamp = str(datetime.datetime.now())

        # Write the batch header to Firebase (audit trail)
        db.reference(f'b2c_payments/batches/{batch_id}').set({
            'batch_label': batch_label,
            'initiated_by': initiated_by,
            'total_recipients': len(recipients),
            'total_amount': total_amount,
            'status': 'Processing',
            'created_at': batch_timestamp,
            'recipient_count': len(recipients)
        })

        results = []
        successful_count = 0
        failed_count = 0

        for idx, recipient in enumerate(recipients):
            emp_num   = recipient.get('employee_number', f'EMP-{idx+1:03d}')
            name      = recipient.get('name', 'Unknown')
            phone     = recipient.get('phone', '')
            amount    = int(recipient.get('amount', 0))
            dept      = recipient.get('department', 'General')
            narration = recipient.get('narration', batch_label)
            email     = recipient.get('email', '')

            # Initiate the B2C payment
            res = initiate_b2c_payment(phone, amount, narration)

            if res and 'error' not in res and res.get('ResponseCode') == '0':
                conv_id = res.get('OriginatorConversationID', f'CONV-{uuid_module.uuid4().hex[:8]}')
                status = 'Pending Verification'
                successful_count += 1
            else:
                conv_id = f"FAIL-{uuid_module.uuid4().hex[:8]}"
                status = 'Failed'
                failed_count += 1

            # Record individual payment under the batch
            entry = {
                'batch_id': batch_id,
                'employee_number': emp_num,
                'name': name,
                'phone': phone,
                'email': email,
                'amount': amount,
                'department': dept,
                'narration': narration,
                'status': status,
                'conversation_id': conv_id,
                'timestamp': str(datetime.datetime.now()),
                'initiated_by': initiated_by
            }
            db.reference(f'b2c_payments/history/{conv_id}').set(entry)

            results.append({
                'employee_number': emp_num,
                'name': name,
                'phone': phone,
                'amount': amount,
                'department': dept,
                'status': status,
                'conversation_id': conv_id
            })

        # Update batch summary with final stats
        db.reference(f'b2c_payments/batches/{batch_id}').update({
            'status': 'Completed' if failed_count == 0 else 'Completed with Errors',
            'successful_count': successful_count,
            'failed_count': failed_count,
            'completed_at': str(datetime.datetime.now())
        })

        return jsonify({
            "success": True,
            "batch_id": batch_id,
            "total_recipients": len(recipients),
            "total_amount": total_amount,
            "successful": successful_count,
            "failed": failed_count,
            "results": results
        })

    except Exception as e:
        print(f"[ERROR] Bulk Pay Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/bulk-batch-history', methods=['GET'])
def bulk_batch_history():
    """Returns a list of all bulk payment batches for the admin dashboard."""
    try:
        data = db.reference('b2c_payments/batches').get() or {}
        batches = []
        for batch_id, batch_data in data.items():
            if isinstance(batch_data, dict):
                batch_data['batch_id'] = batch_id
                batches.append(batch_data)
        # Sort newest first
        batches.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({"success": True, "batches": batches})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/bulk-batch-detail/<batch_id>', methods=['GET'])
def bulk_batch_detail(batch_id):
    """Returns all individual payment records for a specific batch."""
    try:
        all_history = db.reference('b2c_payments/history').get() or {}
        records = []
        for conv_id, record in all_history.items():
            if isinstance(record, dict) and record.get('batch_id') == batch_id:
                record['conversation_id'] = conv_id
                records.append(record)
        records.sort(key=lambda x: x.get('timestamp', ''), reverse=False)
        return jsonify({"success": True, "records": records})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/bulk-batch-csv/<batch_id>', methods=['GET'])
def bulk_batch_csv(batch_id):
    """Exports all individual payment records for a specific batch as CSV."""
    try:
        all_history = db.reference('b2c_payments/history').get() or {}
        batch_info = db.reference(f'b2c_payments/batches/{batch_id}').get() or {}

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow([
            'Batch ID', 'Batch Label', 'Employee No', 'Name', 'Phone', 'Email',
            'Amount (KSh)', 'Department', 'Narration', 'Status', 'Transaction ID', 'Timestamp', 'Initiated By'
        ])
        for conv_id, record in all_history.items():
            if isinstance(record, dict) and record.get('batch_id') == batch_id:
                cw.writerow([
                    batch_id,
                    batch_info.get('batch_label', ''),
                    record.get('employee_number', ''),
                    record.get('name', ''),
                    record.get('phone', ''),
                    record.get('email', ''),
                    record.get('amount', ''),
                    record.get('department', ''),
                    record.get('narration', ''),
                    record.get('status', ''),
                    conv_id,
                    record.get('timestamp', ''),
                    record.get('initiated_by', '')
                ])
        output = si.getvalue()
        safe_label = batch_info.get('batch_label', batch_id).replace(' ', '_')
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=bulk_payroll_{safe_label}_{batch_id}.csv"}
        )
    except Exception as e:
        return str(e), 500


@app.route('/admin/api/retry-failed-batch', methods=['POST'])
def retry_failed_batch():
    """Retries all failed payment entries in a given batch."""
    try:
        data = request.json
        batch_id = data.get('batch_id')
        initiated_by = data.get('initiated_by', 'System Admin')

        if not batch_id:
            return jsonify({"success": False, "error": "batch_id is required."}), 400

        all_history = db.reference('b2c_payments/history').get() or {}
        retried = 0

        for conv_id, record in all_history.items():
            if isinstance(record, dict) and record.get('batch_id') == batch_id and record.get('status') == 'Failed':
                phone  = record.get('phone', '')
                amount = record.get('amount', 0)
                reason = record.get('narration', 'Payroll Retry')
                name   = record.get('name', 'Unknown')
                
                res = initiate_b2c_payment(phone, amount, reason)
                if res and 'error' not in res and res.get('ResponseCode') == '0':
                    new_conv_id = res.get('OriginatorConversationID', f'RETRY-{uuid_module.uuid4().hex[:8]}')
                    # Create new entry
                    new_entry = dict(record)
                    new_entry.update({
                        'status': 'Pending Verification',
                        'conversation_id': new_conv_id,
                        'timestamp': str(datetime.datetime.now()),
                        'initiated_by': initiated_by,
                        'is_retry': True,
                        'original_conv_id': conv_id
                    })
                    db.reference(f'b2c_payments/history/{new_conv_id}').set(new_entry)
                    # Mark original as retried
                    db.reference(f'b2c_payments/history/{conv_id}').update({'status': 'Retried'})
                    retried += 1

        return jsonify({"success": True, "retried": retried})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/cron/run-schedules', methods=['GET'])
def b2c_scheduler_cron():
    """Endpoint for cPanel Cron Job to trigger scheduled B2C payments safely."""
    try:
        if not firebase_admin._apps:
            return jsonify({"status": "error", "message": "Firebase not initialized"}), 500
            
        schedules = db.reference('b2c_payments/schedules').get() or {}
        now = datetime.datetime.now()
        executed_count = 0
        
        for sched_id, sched in schedules.items():
            if sched.get('status') != 'Active': continue
            
            start_time_str = sched.get('start_time')
            if not start_time_str: continue
            
            try:
                start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
            except:
                continue
            
            if now >= start_time:
                freq = sched.get('frequency')
                last_run_str = sched.get('last_run')
                should_run = False
                
                if not last_run_str:
                    should_run = True
                else:
                    try:
                        last_run = datetime.datetime.strptime(last_run_str, "%Y-%m-%d %H:%M:%S")
                        delta = now - last_run
                        if freq == 'daily' and delta.days >= 1: should_run = True
                        elif freq == 'weekly' and delta.days >= 7: should_run = True
                        elif freq == 'monthly' and delta.days >= 30: should_run = True
                        elif freq == 'yearly' and delta.days >= 365: should_run = True
                    except:
                        should_run = True
                    
                if should_run:
                    print(f"Running scheduled B2C payment for {sched.get('name')}")
                    res = initiate_b2c_payment(sched.get('phone'), sched.get('amount'), sched.get('reason', 'Scheduled Salary'))
                    
                    hist_id = res.get("OriginatorConversationID") if res and res.get('ResponseCode') == '0' else f"ERR-{int(time.time())}"
                    status = 'Pending Verification' if res and res.get('ResponseCode') == '0' else 'Failed'
                    db.reference(f'b2c_payments/history/{hist_id}').set({
                        'name': sched.get('name'), 'phone': sched.get('phone'), 'amount': sched.get('amount'),
                        'reason': sched.get('reason', 'Scheduled Salary'), 'status': status,
                        'timestamp': str(now), 'schedule_id': sched_id
                    })
                    
                    db.reference(f'b2c_payments/schedules/{sched_id}').update({
                        'last_run': now.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    executed_count += 1
                    
        return jsonify({"status": "success", "executed": executed_count}), 200
        
    except Exception as e:
        print("Scheduler error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================================================================
# 7. RUN SERVER
# ==============================================================================
if __name__ == '__main__':
    # 'host=0.0.0.0' makes the server accessible on your local network/phone
    app.run(host='0.0.0.0', port=5000, debug=True)