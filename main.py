import os
import time
import requests
from google import genai
from pymongo import MongoClient
from datetime import datetime, timezone

# --- লাইভ কনসোল লগের জন্য মেমোরি ---
bot_logs = []

def add_log(message):
    """লগ মেসেজ লিস্টে যোগ করার ফাংশন"""
    timestamp = time.strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry, flush=True) 
    
    bot_logs.insert(0, log_entry)
    if len(bot_logs) > 100:
        bot_logs.pop()

# --- কনফিগারেশন লোড ---
try:
    FACEBOOK_ACCESS_TOKEN = os.environ['FACEBOOK_ACCESS_TOKEN']
    PAGE_ID = os.environ['PAGE_ID']
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
    MONGO_URI = os.environ.get('MONGO_URI') 
    
    RAW_POST_ID = os.environ['POST_ID']
    if "_" not in RAW_POST_ID:
        FULL_POST_ID = f"{PAGE_ID}_{RAW_POST_ID}"
    else:
        FULL_POST_ID = RAW_POST_ID
        
except KeyError as e:
    add_log(f"❌ Error: Environment Variable {e} missing!")
    FULL_POST_ID = None
    MONGO_URI = None

# --- MongoDB সেটআপ ---
db_collection = None
if MONGO_URI:
    try:
        client_mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client_mongo['facebook_bot_db']
        db_collection = db['replied_comments']
        client_mongo.server_info()
        add_log("✅ Connected to MongoDB successfully!")
    except Exception as e:
        add_log(f"❌ MongoDB Connection Error: {e}")
        db_collection = None
else:
    add_log("⚠️ Warning: MONGO_URI not found. Bot will use temporary memory.")

# --- মেমোরি ফাংশন ---
processed_memory_set = set()

def is_comment_processed(comment_id):
    if db_collection is not None:
        return db_collection.find_one({"_id": comment_id}) is not None
    else:
        return comment_id in processed_memory_set

def mark_comment_as_processed(comment_id):
    if db_collection is not None:
        try:
            db_collection.insert_one({
                "_id": comment_id,
                "processed_at": datetime.now(timezone.utc)
            })
        except Exception:
            pass
    else:
        processed_memory_set.add(comment_id)

# --- Gemini Client সেটআপ ---
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    add_log(f"❌ Gemini Client Error: {e}")

# --- মডেলের লিস্ট (শক্তিশালী থেকে সাধারণ) ---
MODEL_HIERARCHY = [
    "gemini-3-pro-preview",         # 1. সবচেয়ে শক্তিশালী (Gemini 3)
    "gemini-2.5-pro-preview-06-05", # 2. দ্বিতীয় শক্তিশালী (Gemini 2.5 Pro)
    "gemini-2.0-pro-exp-02-05",     # 3. তৃতীয় শক্তিশালী (Gemini 2.0 Pro)
    "gemini-2.0-flash"              # 4. ফলব্যাক/দ্রুত (Gemini 2.0 Flash)
]

def generate_gemini_reply(comment_text):
    """
    ধারাবাহিকভাবে ৪টি মডেল চেষ্টা করবে।
    রিটার্ন করবে: (reply_text, model_name)
    """
    
    system_instruction = """You are a helpful AI assistant for a Facebook Page. 
Reply to this comment in Bengali. Be friendly, human-like, and keep it concise (1-2 sentences).
If someone asks about price, politely say 'Please inbox us for pricing details'."""

    last_error = ""

    # লুপের মাধ্যমে একটার পর একটা মডেল ট্রাই করবে
    for model_name in MODEL_HIERARCHY:
        try:
            # add_log(f"🔄 Trying model: {model_name}...") # (অপশনাল লগ, চাইলে চালু করতে পারেন)
            
            response = client.models.generate_content(
                model=model_name,
                contents=f"{system_instruction}\nUser Comment: {comment_text}"
            )
            
            if response.text:
                # সফল হলে লুপ ব্রেক করে রিপ্লাই রিটার্ন করবে
                return response.text.strip(), model_name
            
        except Exception as e:
            # ফেইল করলে লগ রেখে পরের মডেলে যাবে
            last_error = str(e)
            add_log(f"⚠️ {model_name} Failed. Switching to next...")
            continue

    # যদি ৪টা মডেলই ফেইল করে
    add_log(f"❌ All 4 Models Failed! Last Error: {last_error}")
    return "ধন্যবাদ আপনার মন্তব্যের জন্য! 😊", "System-Fallback"

def post_reply_to_comment(comment_id, reply_text):
    url = f"https://graph.facebook.com/v21.0/{comment_id}/comments"
    params = {
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "message": reply_text
    }
    try:
        response = requests.post(url, params=params)
        if response.status_code == 200:
            return True
        else:
            add_log(f"❌ FB API Error: {response.text}")
            return False
    except Exception as e:
        add_log(f"Network Error: {e}")
        return False

def run_bot_loop():
    if not FULL_POST_ID:
        add_log("⚠️ পোস্ট আইডি নেই, বট কাজ করবে না।")
        return

    add_log(f"🚀 Intelligent Multi-Model Bot Started! Monitoring: {FULL_POST_ID}")
    add_log(f"🧠 Active Models Hierarchy: {MODEL_HIERARCHY}")
    
    while True:
        try:
            url = f"https://graph.facebook.com/v21.0/{FULL_POST_ID}/comments"
            params = {
                "access_token": FACEBOOK_ACCESS_TOKEN,
                "fields": "id,message,from,created_time",
                "limit": 25
            }
            
            resp = requests.get(url, params=params)
            
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                
                for comment in data:
                    c_id = comment.get('id')
                    c_msg = comment.get('message', '')
                    c_user = comment.get('from', {}).get('id')
                    
                    if c_user == PAGE_ID:
                        continue
                    
                    if is_comment_processed(c_id):
                        continue
                    
                    add_log(f"✨ New Comment: {c_msg[:30]}...")
                    
                    # রিপ্লাই এবং মডেলের নাম রিসিভ করছি
                    reply_text, used_model = generate_gemini_reply(c_msg)
                    
                    if post_reply_to_comment(c_id, reply_text):
                        # কনসোলে মডেলের নামসহ লগ দেখাবে (যেমন: [gemini-3-pro-preview] Replied...)
                        add_log(f"✅ [{used_model}] Replied: {reply_text[:30]}...")
                        mark_comment_as_processed(c_id)
                        time.sleep(5) # স্প্যামিং এড়াতে বিরতি
                    
            else:
                add_log(f"❌ Facebook API Error: {resp.text}")
                
        except Exception as e:
            add_log(f"⚠️ Loop Error: {e}")
            
        time.sleep(10)
