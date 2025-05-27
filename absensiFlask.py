from flask import Flask, render_template, request, redirect, url_for, send_file, session, Response
from pyzbar.pyzbar import decode
import cv2
import csv
# import os
# import qrcode
# from PIL import Image
import matplotlib.pyplot as plt
# from io import BytesIO
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# Database sederhana
USERS = {
    'admin': 'admin123',  # Hak akses penuh
    'teacher': 'teacher123'  # Akses terbatas
}
CLASSES = ['Matematika', 'Fisika', 'Kimia']
ATTENDANCE_FILE = 'attendance.csv'

# Fungsi validasi visual
def draw_validation(frame):
    # Menambahkan teks validasi
    cv2.putText(frame, "QR Valid", (50, 50), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    # Menambahkan border hijau
    height, width = frame.shape[:2]
    cv2.rectangle(frame, (10, 10), 
                 (width-10, height-10), 
                 (0, 255, 0), 3)
    return frame

def gen_frames():
    camera = cv2.VideoCapture(0)
    while True:
        success, frame = camera.read()
        if success:
            decoded_objects = decode(frame)
            for obj in decoded_objects:
                data = obj.data.decode('utf-8')
                if validate_qr(data):
                    update_attendance(data)
                    frame = draw_validation(frame)  # Panggil fungsi validasi visual
            
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# Fungsi validasi QR
def validate_qr(data):
    try:
        class_part, date_part = data.split('|')
        class_name = class_part.split(':')[1]
        qr_date = datetime.strptime(date_part.split(':')[1], '%Y-%m-%d')
        
        return (
            class_name in CLASSES and
            (datetime.now() - qr_date).days < 1
        )
    except:
        return False

# Fungsi update data kehadiran
def update_attendance(data):
    with open(ATTENDANCE_FILE, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            data.split('|')[0].split(':')[1],  # Ambil nama kelas
            'NIM_SISWA',  # Ganti dengan ID siswa aktual
            'Hadir'
        ])

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), 
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/results')
def results():
    df = pd.read_csv(ATTENDANCE_FILE)
    
    # Generate pie chart
    plt.figure(figsize=(8,6))
    df['Status'].value_counts().plot.pie(autopct='%1.1f%%')
    plt.title('Distribusi Kehadiran')
    plt.savefig('static/attendance_pie.png')
    
    # Generate trend line chart
    plt.figure(figsize=(10,6))
    df['Tanggal'] = pd.to_datetime(df['Tanggal'])
    daily_attendance = df.groupby(df['Tanggal'].dt.date).size()
    daily_attendance.plot(kind='line', marker='o')
    plt.title('Trend Harian Kehadiran')
    plt.xlabel('Tanggal')
    plt.ylabel('Jumlah Siswa')
    plt.grid(True)
    plt.savefig('static/attendance_trend.png')
    
    return render_template('results.html', 
                         pie_chart='attendance_pie.png',
                         trend_chart='attendance_trend.png')

"""
login.html:
<!-- Form login sederhana 

dashboard.html:
<!-- Menu utama dengan navigasi dan form pengaturan 

scanner.html:
<!-- Antarmuka pemindai QR real-time 
<img src="{{ url_for('video_feed') }}">

results.html:
<!-- Tampilan statistik dengan dropdown kelas 
<img src="{{ url_for('static', filename=stats_image) }}">

├── absensiFlask.py
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   ├── scanner.html
│   └── results.html
├── static/
│   ├── styles.css
│   └── images/
├── attendance.csv
└── requirements.txt
"""
if __name__ == '__main__':
    app.run(debug=True)


