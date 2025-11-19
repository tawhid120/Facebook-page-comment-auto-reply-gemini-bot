import os
from flask import Flask, render_template, jsonify
from threading import Thread
# main.py থেকে run_bot_loop এবং bot_logs ইমপোর্ট করছি
from main import run_bot_loop, bot_logs

app = Flask(__name__, template_folder='templates')

@app.route('/')
def home():
    page_id = os.environ.get('PAGE_ID', '#')
    return render_template('index.html', page_id=page_id)

# লাইভ কনসোল আপডেট করার জন্য API
@app.route('/api/logs')
def get_logs():
    return jsonify(bot_logs)

def start_background_bot():
    try:
        run_bot_loop()
    except Exception as e:
        print(f"Bot Crash: {e}")

# সার্ভার চালু হওয়ার সাথে সাথে ব্যাকগ্রাউন্ডে বট চালু হবে
t = Thread(target=start_background_bot)
t.daemon = True
t.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)


