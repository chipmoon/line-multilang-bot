import os
import sys
from dotenv import load_dotenv

load_dotenv()

def check_env():
    print(f"--- Environment Check ---")
    print(f"Python Version: {sys.version}")
    
    # Check dependencies
    try:
        import flask
        import linebot
        import google.cloud.vision as vision
        import pypinyin
        import cloudinary
        import dotenv
        print("✅ Core dependencies imported successfully.")
        
        from linebot.v3 import WebhookHandler
        print("✅ line-bot-sdk v3 verified.")
    except ImportError as e:
        print(f"❌ Dependency Error: {e}")
        return

    # Check .env variables
    keys = [
        'LINE_CHANNEL_ACCESS_TOKEN', 
        'LINE_CHANNEL_SECRET', 
        'CLOUDINARY_NAME', 
        'CLOUDINARY_API_KEY', 
        'CLOUDINARY_API_SECRET',
        'GOOGLE_APPLICATION_CREDENTIALS'
    ]
    missing = []
    for k in keys:
        if not os.getenv(k):
            missing.append(k)
    
    if missing:
        print(f"❌ Missing Env Vars: {', '.join(missing)}")
    else:
        print("✅ All required Env Vars present.")

    # Check Google Credentials file
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')
    if not os.path.exists(creds_path):
        print(f"❌ Google Credentials file not found: {creds_path}")
    else:
        print(f"✅ Google Credentials file found: {creds_path}")

    # Check Static folder
    if not os.path.exists('static'):
        print("⚠️ 'static' folder missing (will be created by app.py)")
    else:
        print("✅ 'static' folder exists.")

if __name__ == "__main__":
    check_env()
