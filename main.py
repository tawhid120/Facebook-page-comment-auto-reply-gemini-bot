import os
import time
import requests
from google import genai
from pymongo import MongoClient
from datetime import datetime, timedelta

# --- লাইভ কনসোল লগের জন্য মেমোরি ---
bot_logs = []

def add_log(message):
    """লগ মেসেজ লিস্টে যোগ করার ফাংশন"""
    timestamp = time.strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    bot_logs.insert(0, log_entry)
    if len(bot_logs) > 100:
        bot_logs.pop()

# --- কনফিগারেশন লোড ---
try:
    FACEBOOK_ACCESS_TOKEN = os.environ['FACEBOOK_ACCESS_TOKEN']
    PAGE_ID = os.environ['PAGE_ID']
    RAW_POST_ID = os.environ['POST_ID']
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
    MONGO_URI = os.environ['MONGO_URI'] # Render এ এই ভেরিয়েবলটি সেট করুন

    # পোস্ট আইডি ঠিক করা
    if "_" not in RAW_POST_ID:
        FULL_POST_ID = f"{PAGE_ID}_{RAW_POST_ID}"
    else:
        FULL_POST_ID = RAW_POST_ID
        
except KeyError as e:
    add_log(f"❌ Error: Environment Variable {e} missing!")
    FULL_POST_ID = None
    MONGO_URI = None

# --- MongoDB সেটআপ (স্থায়ী মেমোরির জন্য) ---
db_collection = None
if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI)
        db = client['facebook_bot_db']  # ডাটাবেজ নাম
        db_collection = db['replied_comments'] # কালেকশন নাম
        add_log("✅ Connected to MongoDB successfully!")
    except Exception as e:
        add_log(f"❌ MongoDB Connection Error: {e}")

def is_comment_processed(comment_id):
    """চেক করবে এই কমেন্টে আগে রিপ্লাই দেওয়া হয়েছে কিনা"""
    if db_collection is not None:
        return db_collection.find_one({"_id": comment_id}) is not None
    return False

def mark_comment_as_processed(comment_id):
    """কমেন্ট আইডি ডাটাবেজে সেভ করে রাখবে"""
    if db_collection is not None:
        try:
            db_collection.insert_one({
                "_id": comment_id,
                "processed_at": datetime.utcnow()
            })
        except Exception:
            pass # অলরেডি থাকলে ইগনোর করবে

# --- Gemini 3 / 2.0 Client সেটআপ ---
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    add_log(f"❌ Gemini Client Error: {e}")

def generate_gemini_reply(comment_text):
    """Gemini 3 (Preview) বা Flash দিয়ে রিপ্লাই তৈরি"""
    try:
        prompt = f"""You are a helpful AI assistant for a Facebook Page. 
Reply to this comment in Bengali, be friendly, short and concise.
If asking for price, say 'Please inbox us'.
User Comment: {comment_text}"""
        
        # এখানে Gemini 3 মডেল ব্যবহার করা হয়েছে যেমনটা আপনি চেয়েছেন
        # যদি 3-pro-preview আপনার অ্যাকাউন্টে চালু না থাকে, তবে এটি অটোমেটিক ফলব্যাক করবে বা এরর দিবে।
        # সেই ক্ষেত্রে 'gemini-2.0-flash' ব্যবহার করা নিরাপদ।
        response = client.models.generate_content(
            model="gemini-3-pro-preview", # অথবা "gemini-3-pro-preview" যদি আপনার এক্সেস থাকে
            contents=prompt
        )
        return response.text.strip()
    
    except Exception as e:
        add_log(f"❌ Gemini AI Error: {e}")
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
            add_log(f"✅ Replied to {comment_id}")
            return True
        else:
            add_log(f"❌ FB API Error: {response.text}")
            return False
    except Exception as e:
        add_log(f"Network Error: {e}")
        return False

def run_bot_loop():
    """মেইন লুপ যা app.py থেকে কল করা হবে"""
    if not FULL_POST_ID or not db_collection:
        add_log("⚠️ পোস্ট আইডি বা ডাটাবেজ নেই, বট কাজ করবে না।")
        return

    add_log(f"🚀 Gemini 3 Bot Logic Started! Monitoring: {FULL_POST_ID}")
    
    while True:
        try:
            # ১. কমেন্ট আনা (Reverse Order যাতে নতুন কমেন্ট আগে প্রসেস না হয়)
            url = f"https://graph.facebook.com/v21.0/{FULL_POST_ID}/comments"
            params = {
                "access_token": FACEBOOK_ACCESS_TOKEN,
                "fields": "id,message,from,created_time",
                "limit": 25,
                "order": "reverse_chronological"
            }
            
            resp = requests.get(url, params=params)
            
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                
                for comment in data:
                    c_id = comment.get('id')
                    c_msg = comment.get('message', '')
                    c_user = comment.get('from', {}).get('id')
                    c_time_str = comment.get('created_time') # e.g., 2023-10-27T10:00:00+0000
                    
                    # নিজের কমেন্ট হলে বাদ
                    if c_user == PAGE_ID:
                        continue
                    
                    # ডাটাবেজে চেক করুন রিপ্লাই দেওয়া হয়েছে কিনা
                    if is_comment_processed(c_id):
                        continue

                    # --- পুরনো মেসেজ ফিল্টার (অতিরিক্ত সুরক্ষা) ---
                    # যদি কমেন্ট ১ ঘন্টার বেশি পুরনো হয় এবং আগে রিপ্লাই না দিয়ে থাকি,
                    # তাহলে এখন আর রিপ্লাই দিবো না, শুধু ডাটাবেজে সেভ করে রাখবো।
                    # এতে করে সার্ভার রিস্টার্ট দিলে পুরনো কমেন্টে রিপ্লাই যাবে না।
                    try:
                        # টাইম ফরম্যাট পার্স করা (FB time format)
                        c_time = datetime.strptime(c_time_str, "%Y-%m-%dT%H:%M:%S%z")
                        # বর্তমান সময় (UTC)
                        now = datetime.now(c_time.tzinfo)
                        
                        # যদি কমেন্ট ২ ঘন্টার বেশি পুরনো হয়
                        if (now - c_time) > timedelta(hours=2):
                            add_log(f"⏩ Skipping old comment: {c_msg[:20]}...")
                            mark_comment_as_processed(c_id)
                            continue
                    except Exception as e:
                        # টাইম পার্স করতে সমস্যা হলে সাধারণ নিয়মে প্রসেস হবে
                        pass

                    add_log(f"✨ New Comment Found: {c_msg[:30]}...")
                    
                    # রিপ্লাই জেনারেট
                    reply = generate_gemini_reply(c_msg)
                    
                    # রিপ্লাই পোস্ট
                    if post_reply_to_comment(c_id, reply):
                        # সফল হলে ডাটাবেজে সেভ করুন
                        mark_comment_as_processed(c_id)
                        time.sleep(5) # সেফটি ডিলে
                    
            else:
                add_log(f"❌ Facebook API Error: {resp.text}")
                
        except Exception as e:
            add_log(f"⚠️ Loop Error: {e}")
            
        # ৩০ সেকেন্ড অপেক্ষা
        time.sleep(30)

