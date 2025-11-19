import os
from flask import Flask
from threading import Thread
# আমরা main.py ফাইল থেকে run_bot_loop ফাংশনটি ইমপোর্ট করছি
from main import run_bot_loop

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Facebook Bot is Running 24/7!"

def start_bot_background():
    # ব্যাকগ্রাউন্ডে বট চালু করা
    try:
        run_bot_loop()
    except Exception as e:
        print(f"Bot Error: {e}")

# সার্ভার স্টার্ট হওয়ার আগেই থ্রেড চালু করে দিচ্ছি
# এটি নিশ্চিত করে যে Flask রান হওয়ার সাথে সাথে বটও চলতে শুরু করবে
t = Thread(target=start_bot_background)
t.daemon = True  # মেইন প্রোগ্রাম বন্ধ হলে থ্রেডও বন্ধ হবে
t.start()

if __name__ == "__main__":
    # Render যে পোর্ট দেয় সেটা ব্যবহার করবে
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
