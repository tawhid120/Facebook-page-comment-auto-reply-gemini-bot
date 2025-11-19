import os
import time
import requests
from google import genai 

# --- কনফিগারেশন ---
try:
    FACEBOOK_ACCESS_TOKEN = os.environ['FACEBOOK_ACCESS_TOKEN']
    PAGE_ID = os.environ['PAGE_ID']
    
    # পোস্ট আইডি ঠিক করা (PAGE_ID_POST_ID ফরম্যাট)
    RAW_POST_ID = os.environ['POST_ID']
    if "_" not in RAW_POST_ID:
        FULL_POST_ID = f"{PAGE_ID}_{RAW_POST_ID}"
    else:
        FULL_POST_ID = RAW_POST_ID
        
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
except KeyError as e:
    print(f"❌ Error: Environment Variable {e} পাওয়া যাচ্ছে না!")
    FULL_POST_ID = None

# --- Gemini 2.0 সেটআপ (সবচেয়ে শক্তিশালী) ---
# নতুন SDK ব্যবহার করছি যাতে ফিউচার প্রুফ হয়
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_gemini_reply(comment_text):
    """Gemini 2.0 দিয়ে রিপ্লাই তৈরি"""
    try:
        prompt = f"""You are a helpful AI assistant for a Facebook Page. 
Reply to this comment in Bengali, be friendly and concise.
If someone asks about price, say 'Please inbox us for pricing details'.
Do not reply to offensive comments.

User Comment: {comment_text}"""
        
        # gemini-2.0-flash মডেল ব্যবহার করা হচ্ছে
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt
        )
        return response.text.strip()
    
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
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
            print(f"✅ Successfully replied to {comment_id}")
            return True
        else:
            print(f"❌ Failed to reply: {response.text}")
            return False
    except Exception as e:
        print(f"Network Error: {e}")
        return False

# --- প্রসেসড কমেন্ট ট্র্যাক করার সেট ---
processed_comment_ids = set()

def run_bot_loop():
    """এই ফাংশনটিই app.py চালাবে"""
    if not FULL_POST_ID:
        print("⚠️ পোস্ট আইডি নেই, বট কাজ করবে না।")
        return

    print(f"🚀 Facebook Gemini Bot Started! Monitoring: {FULL_POST_ID}")
    
    while True:
        try:
            # ১. কমেন্ট আনা
            url = f"https://graph.facebook.com/v21.0/{FULL_POST_ID}/comments"
            params = {
                "access_token": FACEBOOK_ACCESS_TOKEN,
                "fields": "id,message,from",
                "limit": 25
            }
            
            resp = requests.get(url, params=params)
            
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                print(f"🔍 Checking... Found {len(data)} comments")
                
                for comment in data:
                    c_id = comment.get('id')
                    c_msg = comment.get('message', '')
                    c_user = comment.get('from', {}).get('id')
                    
                    # নিজের কমেন্ট এবং আগের রিপ্লাই দেওয়া কমেন্ট বাদ
                    if c_id in processed_comment_ids or c_user == PAGE_ID:
                        continue
                        
                    print(f"✨ New Comment: {c_msg[:30]}...")
                    
                    # রিপ্লাই জেনারেট এবং পোস্ট
                    reply = generate_gemini_reply(c_msg)
                    if post_reply_to_comment(c_id, reply):
                        processed_comment_ids.add(c_id)
                    
                    time.sleep(2) # স্প্যামিং এড়াতে
            else:
                print(f"❌ Facebook API Error: {resp.text}")
                
        except Exception as e:
            print(f"⚠️ Loop Error: {e}")
            
        # ৩০ সেকেন্ড অপেক্ষা
        time.sleep(30)

