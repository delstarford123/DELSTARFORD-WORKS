import os
import firebase_admin
from firebase_admin import credentials, auth, db
from datetime import datetime
from dotenv import load_dotenv

# ---------------------------------------------------------
# 0. LOAD ENVIRONMENT VARIABLES
# ---------------------------------------------------------
load_dotenv()  # This safely loads your .env file

# ---------------------------------------------------------
# 1. INITIALIZE FIREBASE ADMIN
# ---------------------------------------------------------
# Pointing to your specific JSON key file
cred = credentials.Certificate('service_account_key.json')

# Fetch the exact database URL from your .env file
database_url = os.getenv('DATABASE_URL')

# Safety check: make sure the URL was found
if not database_url:
    raise ValueError("❌ DATABASE_URL not found! Please check your .env file.")

# Initialize app using the dynamic URL
firebase_admin.initialize_app(cred, {
    'databaseURL': database_url
})

# ---------------------------------------------------------
# 2. ADMIN CREDENTIALS
# ---------------------------------------------------------
admin_email = "delstarfordisaiah@gmail.com"
admin_password = ".Delstarford123"
admin_name = "Delstarford Works Admin"

def create_admin():
    try:
        print(f"Attempting to create user: {admin_email}...")
        print(f"Connecting to Database: {database_url}...")
        
        # Step A: Create user in Firebase Authentication
        try:
            user = auth.create_user(
                email=admin_email,
                password=admin_password,
                display_name=admin_name
            )
            uid = user.uid
            print(f"✅ Successfully created Auth User with UID: {uid}")
        except auth.EmailAlreadyExistsError:
            print(f"⚠️ User {admin_email} already exists in Auth. Fetching UID to update database...")
            user = auth.get_user_by_email(admin_email)
            uid = user.uid
        
        # Step B: Set 'admin' role in Realtime Database
        print("Assigning 'admin' role in Realtime Database...")
        ref = db.reference(f'users/{uid}')
        
        ref.set({
            'name': admin_name,
            'email': admin_email,
            'role': 'admin',
            'joined_at': datetime.utcnow().isoformat() + "Z"
        })
        
        print("✅ Database updated successfully! You can now log into the Admin Dashboard.")

    except Exception as e:
        print(f"❌ Error occurred: {e}")

if __name__ == "__main__":
    create_admin()