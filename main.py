import os
import time
import requests
from google import genai
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone

# --- লাইভ কনসোল লগের জন্য মেমোরি ---
bot_logs = []

def add_log(message):
    """লগ মেসেজ লিস্টে যোগ করার ফাংশন"""
    timestamp = time.strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    # কনসোলে সাথে সাথে প্রিন্ট করার জন্য flush=True দেওয়া হলো
    print(log_entry, flush=True) 
    
    bot_logs.insert(0, log_entry)
    if len(bot_logs) > 100:
        bot_logs.pop()

# --- কনফিগারেশন লোড ---
try:
    FACEBOOK_ACCESS_TOKEN = os.environ['FACEBOOK_ACCESS_TOKEN']
    PAGE_ID = os.environ['PAGE_ID']
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
    
    # Render Environment Variable থেকে MONGO_URI নিবে
    # আপনি Render এ MONGO_URI নামে ভেরিয়েবল সেট করবেন এবং আপনার লিংকটি ভ্যালু হিসেবে দিবেন
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
        # কানেকশন চেক
        client_mongo.server_info()
        add_log("✅ Connected to MongoDB successfully!")
    except Exception as e:
        add_log(f"❌ MongoDB Connection Error: {e}")
        db_collection = None
else:
    add_log("⚠️ Warning: MONGO_URI not found. Bot will use temporary memory.")

# --- মেমোরি ফাংশন ---
processed_memory_set = set() # মংগোডিবি না থাকলে এটি কাজ করবে

def is_comment_processed(comment_id):
    """চেক করবে এই কমেন্টে আগে রিপ্লাই দেওয়া হয়েছে কিনা"""
    if db_collection is not None:
        return db_collection.find_one({"_id": comment_id}) is not None
    else:
        return comment_id in processed_memory_set

def mark_comment_as_processed(comment_id):
    """কমেন্ট আইডি সেভ করবে"""
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

def generate_gemini_reply(comment_text):
    """Gemini 3 চেষ্টা করবে, না পারলে 2.0 Flash ব্যবহার করবে"""
    
    system_instruction = """You are a helpful AI assistant for a Facebook Page. 
Reply to this comment in Bengali. Be friendly, human-like, and keep it within 1-2 sentences.
If someone asks about price, politely say 'Please inbox us for pricing details'."""

    # প্রথমে Gemini 3.0 বা Experimental মডেল চেষ্টা করি
    try:
        # add_log("🤖 Trying Gemini 3...") 
        response = client.models.generate_content(
            model="gemini-2.0-flash-thinking-exp", # অথবা "gemini-3-pro-preview" যদি আপনার থাকে
            contents=f"{system_instruction}\nUser Comment: {comment_text}"
        )
        return response.text.strip()
    
    except Exception as e:
        # যদি ৩.০ ফেইল করে, তাহলে ২.০ ফ্ল্যাশ (সবচেয়ে স্টবল) ব্যবহার হবে
        # add_log(f"⚠️ Gemini 3 failed, switching to Flash: {e}")
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=f"{system_instruction}\nUser Comment: {comment_text}"
            )
            return response.text.strip()
        except Exception as e2:
            add_log(f"❌ All Gemini Models Failed: {e2}")
            return "ধন্যবাদ আপনার মন্তব্যের জন্য! 😊"

def post_reply_to_comment(comment_id, reply_text):
    """ফেসবুকে রিপ্লাই পোস্ট করা"""
    url = f"https://graph.facebook.com/v21.0/{comment_id}/comments"
    params = {
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "message": reply_text
    }
    try:
        response = requests.post(url, params=params)
        if response.status_code == 200:
            add_log(f"✅ Replied: {reply_text[:20]}...")
            return True
        else:
            add_log(f"❌ FB API Error: {response.text}")
            return False
    except Exception as e:
        add_log(f"Network Error: {e}")
        return False

def run_bot_loop():
    """মেইন লুপ"""
    if not FULL_POST_ID:
        add_log("⚠️ পোস্ট আইডি নেই, বট কাজ করবে না।")
        return

    add_log(f"🚀 Intelligent Bot Started! Monitoring: {FULL_POST_ID}")
    add_log("waiting for new comments...")
    
    while True:
        try:
            # ১. কমেন্ট আনা (সাধারণ অর্ডারে)
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
                    
                    # নিজের কমেন্ট হলে বাদ
                    if c_user == PAGE_ID:
                        continue
                    
                    # ডাটাবেজে চেক করুন রিপ্লাই দেওয়া হয়েছে কিনা
                    if is_comment_processed(c_id):
                        continue

                    # --- টেস্টিংয়ের জন্য টাইম ফিল্টার অফ রাখা হলো ---
                    # যাতে আপনি এখনই রিপ্লাই পান। প্রোডাকশনে পরে চালু করতে পারেন।
                    
                    add_log(f"✨ New Comment Found: {c_msg[:30]}...")
                    
                    # রিপ্লাই জেনারেট
                    reply = generate_gemini_reply(c_msg)
                    
                    # রিপ্লাই পোস্ট
                    if post_reply_to_comment(c_id, reply):
                        mark_comment_as_processed(c_id)
                        time.sleep(5) # সেফটি ডিলে
                    
            else:
                add_log(f"❌ Facebook API Error: {resp.text}")
                
        except Exception as e:
            add_log(f"⚠️ Loop Error: {e}")
            
        # ১০ সেকেন্ড অপেক্ষা (ফাস্ট রেসপন্সের জন্য সময় কমানো হলো)
        time.sleep(10)
