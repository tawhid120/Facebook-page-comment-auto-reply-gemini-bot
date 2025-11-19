# ১. নতুন পাইথন ভার্সন (ওয়ার্নিং ফিক্স)
FROM python:3.11-slim

# ২. কাজের ফোল্ডার
WORKDIR /app

# ৩. লাইব্রেরি ইনস্টল
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ৪. সব ফাইল কপি
COPY . .

# ৫. পোর্ট ওপেন করা (Render এর জন্য জরুরি)
EXPOSE 10000

# ৬. সার্ভার রান করা
# আমরা সরাসরি python app.py চালাব কারণ এটিই থ্রেডিং হ্যান্ডেল করছে
CMD ["python", "app.py"]

