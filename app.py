import os
from flask import Flask, render_template
from threading import Thread
from main import run_bot_loop

# Flask অ্যাপ তৈরি, টেমপ্লেট ফোল্ডার দেখিয়ে দেওয়া হলো
app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    # পরিবেশ ভেরিয়েবল থেকে পেজ আইডি নিয়ে HTML-এ পাঠাবে
    page_id = os.environ.get('PAGE_ID', 'YOUR_PAGE_ID')
    return render_template('index.html', page_id=page_id)

def start_background_bot():
    try:
        run_bot_loop()
    except Exception as e:
        print(f"Bot Crash: {e}")

# সার্ভার চালু হওয়ার সাথে সাথে বট ব্যাকগ্রাউন্ডে চলবে
t = Thread(target=start_background_bot)
t.daemon = True
t.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)


