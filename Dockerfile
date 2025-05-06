# Gunakan image Python sebagai base
FROM python:3.10.6-slim

# Set working directory di dalam container
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file ke dalam container
COPY . /app/

# Set environment variable untuk Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Expose port yang digunakan Flask
EXPOSE 5000

# Perintah untuk menjalankan Flask menggunakan gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
