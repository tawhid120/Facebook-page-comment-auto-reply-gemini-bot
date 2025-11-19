import os
from flask import Flask
from threading import Thread
# main.py থেকে run_bot_loop ইমপোর্ট করছি (এখন আর এরর দেবে না)
from main import run_bot_loop

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Powerful Gemini Bot is Running 24/7!"

def start_background_bot():
    try:
        run_bot_loop()
    except Exception as e:
        print(f"Bot Crash: {e}")

# সার্ভার অন হওয়ার সাথে সাথে ব্যাকগ্রাউন্ড থ্রেড চালু হবে
t = Thread(target=start_background_bot)
t.daemon = True
t.start()

if __name__ == "__main__":
    # Render এর পোর্ট লজিক
    port = int(os.environ.get("PORT", 10000))
    # host='0.0.0.0' দেওয়া বাধ্যতামূলক যাতে Render পোর্ট ডিটেক্ট করতে পারে
    app.run(host='0.0.0.0', port=port)

