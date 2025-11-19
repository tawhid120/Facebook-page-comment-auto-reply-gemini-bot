# ১. পাইথনের হালকা ভার্সন ব্যবহার করছি (Size কম হবে)
FROM python:3.10-slim

# ২. কন্টেইনারের ভেতরে কাজের ফোল্ডার ঠিক করা
WORKDIR /app

# ৩. প্রয়োজনীয় ফাইলগুলো কপি করা এবং ইন্সটল করা
# প্রথমে requirements.txt কপি করছি যাতে ক্যাশ সুবিধা পাওয়া যায়
COPY requirements.txt .

# লাইব্রেরিগুলো ইন্সটল করা
RUN pip install --no-cache-dir -r requirements.txt

# ৪. বাকি সব কোড (main.py, app.py) কপি করা
COPY . .

# ৫. পোর্ট এক্সপোজ করা (Render বা অন্য সার্ভার যাতে এটা দেখতে পায়)
EXPOSE 5000

# ৬. এনভায়রনমেন্ট ভেরিয়েবল (লগ ঠিকমতো দেখার জন্য)
ENV PYTHONUNBUFFERED=1

# ৭. কন্টেইনার চালু হলে যে কমান্ড রান হবে
CMD ["python", "app.py"]
