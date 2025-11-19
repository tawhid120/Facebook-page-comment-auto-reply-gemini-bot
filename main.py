
import os
import sys
import time
import requests
import google.generativeai as genai

# --- Load credentials from Replit Secrets ---
try:
    FACEBOOK_ACCESS_TOKEN = os.environ['FACEBOOK_ACCESS_TOKEN']
    PAGE_ID = os.environ['PAGE_ID']
    POST_ID_NUMBER = os.environ['POST_ID']
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
except KeyError as e:
    print(f"❌ Error: Missing secret {e}. Please add it in the Secrets tab.")
    sys.exit(1)

# Create full post ID (Facebook requires PAGE_ID_POST_ID format)
FULL_POST_ID = f"{PAGE_ID}_{POST_ID_NUMBER}"

# --- Configure Gemini AI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")


# Track processed comment IDs
processed_comment_ids = set()

def get_post_comments():
    """Fetch comments from a specific Facebook post"""
    url = f"https://graph.facebook.com/v21.0/{FULL_POST_ID}/comments"
    params = {
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "fields": "id,message,from",
        "limit": 25
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"❌ Facebook API Error: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        return data.get('data', [])
    
    except Exception as e:
        print(f"❌ Error fetching comments: {e}")
        return []

def generate_gemini_reply(comment_text):
    """Generate a reply using Gemini AI"""
    try:
        prompt = f"""You are a helpful AI assistant for a Facebook Page. 
Reply to this comment in Bengali, be friendly and concise.
If someone asks about price, say 'Please inbox us for pricing details'.
Do not reply to offensive comments.

User Comment: {comment_text}

Your Reply:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return "ধন্যবাদ আপনার মন্তব্যের জন্য! 😊"

def post_reply_to_comment(comment_id, reply_text):
    """Post a reply to a Facebook comment"""
    url = f"https://graph.facebook.com/v21.0/{comment_id}/comments"
    params = {
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "message": reply_text
    }
    
    try:
        response = requests.post(url, params=params)
        if response.status_code == 200:
            print(f"✅ Successfully replied to comment {comment_id}")
            return True
        else:
            print(f"❌ Failed to post reply: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        print(f"❌ Error posting reply: {e}")
        return False

def main():
    print("🤖 Facebook Gemini Bot Started!")
    print(f"📍 Monitoring Post ID: {FULL_POST_ID}")
    print("Press Ctrl+C to stop\n")
    print("-" * 60)
    
    while True:
        try:
            print(f"\n🔍 Checking for new comments... ({time.strftime('%Y-%m-%d %H:%M:%S')})")
            
            comments = get_post_comments()
            
            if not comments:
                print("💤 No comments found or error occurred")
            else:
                print(f"📨 Found {len(comments)} total comments")
                
                new_comments = 0
                for comment in comments:
                    comment_id = comment.get('id')
                    comment_text = comment.get('message', '')
                    commenter_id = comment.get('from', {}).get('id')
                    
                    # Skip if already processed or if it's from the page itself
                    if comment_id in processed_comment_ids or commenter_id == PAGE_ID:
                        continue
                    
                    # New comment found!
                    new_comments += 1
                    print(f"\n✨ New Comment Found!")
                    print(f"   ID: {comment_id}")
                    print(f"   Text: {comment_text[:50]}...")
                    
                    # Generate AI reply
                    print("   🤖 Generating Gemini reply...")
                    ai_reply = generate_gemini_reply(comment_text)
                    print(f"   💬 Reply: {ai_reply[:50]}...")
                    
                    # Post the reply
                    if post_reply_to_comment(comment_id, ai_reply):
                        processed_comment_ids.add(comment_id)
                    
                    # Small delay to avoid rate limiting
                    time.sleep(2)
                
                if new_comments == 0:
                    print("✓ No new comments to process")
            
            # Wait 30 seconds before next check
            print(f"\n⏳ Waiting 30 seconds before next check...")
            time.sleep(30)
        
        except KeyboardInterrupt:
            print("\n\n👋 Bot stopped by user. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            print("⏳ Retrying in 30 seconds...")
            time.sleep(30)

if __name__ == "__main__":
    main()
