from flask import Flask, render_template, request, redirect, url_for, send_file, session, Response
from pyzbar.pyzbar import decode
from ecdsa import SigningKey, VerifyingKey, NIST384p
import cv2
import csv
import hashlib
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# Konfigurasi Sistem
USERS = {'admin': 'admin123', 'teacher': 'teacher123'}
CLASSES = ['Matematika', 'Fisika', 'Kimia']
ATTENDANCE_FILE = 'attendance.csv'

# 1. Kelas Blockchain
class Block:
    def __init__(self, index, timestamp, data, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = 0
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def mine_block(self, difficulty):
        while self.hash[:difficulty] != '0' * difficulty:
            self.nonce += 1
            self.hash = self.calculate_hash()

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.difficulty = 2

    def create_genesis_block(self):
        return Block(0, str(datetime.now()), "Genesis Block", "0")

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, new_block):
        new_block.previous_hash = self.get_latest_block().hash
        new_block.mine_block(self.difficulty)
        self.chain.append(new_block)

# 2. Sistem Tokenisasi ECDSA
class TokenizerECDSA:
    def __init__(self):
        self.private_key = SigningKey.generate(curve=NIST384p)
        self.public_key = self.private_key.get_verifying_key()

    def sign_data(self, data):
        data_bytes = json.dumps(data, sort_keys=True).encode()
        signature = self.private_key.sign(data_bytes)
        return signature.hex()

    def verify_signature(self, data, signature_hex):
        data_bytes = json.dumps(data, sort_keys=True).encode()
        signature = bytes.fromhex(signature_hex)
        try:
            return self.public_key.verify(signature, data_bytes)
        except:
            return False

# 3. Integrasi Blockchain dengan Presensi
class AttendanceSystem:
    def __init__(self):
        self.blockchain = Blockchain()
        self.tokenizer = TokenizerECDSA()
    
    def record_attendance(self, student_id, class_name):
        attendance_data = {
            'student_id': student_id,
            'class': class_name,
            'timestamp': str(datetime.now())
        }
        
        # Tokenisasi data
        signature = self.tokenizer.sign_data(attendance_data)
        
        # Membuat blok baru
        new_block = Block(
            index=len(self.blockchain.chain),
            timestamp=str(datetime.now()),
            data={
                'attendance': attendance_data,
                'signature': signature,
                'public_key': self.tokenizer.public_key.to_pem().hex()
            },
            previous_hash=self.blockchain.get_latest_block().hash
        )
        
        # Menambahkan ke blockchain
        self.blockchain.add_block(new_block)
        
        # Menyimpan ke CSV
        with open(ATTENDANCE_FILE, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                attendance_data['timestamp'],
                class_name,
                student_id,
                'Hadir',
                signature,
                new_block.hash
            ])
        
        return new_block.hash

# Inisialisasi sistem
attendance_system = AttendanceSystem()

# 4. Fungsi Validasi dan Pemrosesan QR
def validate_qr(data):
    try:
        parts = data.split('|')
        if len(parts) != 3:
            return False
            
        class_name = parts[0].split(':')[1]
        qr_date = datetime.strptime(parts[1].split(':')[1], '%Y-%m-%d')
        student_id = parts[2].split(':')[1]
        
        return (
            class_name in CLASSES and
            (datetime.now().date() - qr_date.date()).days < 1
        )
    except:
        return False

def draw_validation(frame):
    cv2.putText(frame, "✅ QR Valid", (50, 50), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.rectangle(frame, (10, 10), 
                 (frame.shape[1]-10, frame.shape[0]-10), 
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
                    parts = data.split('|')
                    class_name = parts[0].split(':')[1]
                    student_id = parts[2].split(':')[1]
                    attendance_system.record_attendance(student_id, class_name)
                    frame = draw_validation(frame)
            
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


@app.route('/verify')
def verify_attendance():
    df = pd.read_csv(ATTENDANCE_FILE)
    
    # Verifikasi blockchain
    hashes = df['Block Hash'].tolist()
    blockchain_valid = all(
        attendance_system.blockchain.chain[i].hash == hashes[i] 
        for i in range(len(hashes))
    )
    
    # Verifikasi tanda tangan
    signatures_valid = []
    for _, row in df.iterrows():
        data = {
            'student_id': row['Siswa'],
            'class': row['Kelas'],
            'timestamp': row['Tanggal']
        }
        signatures_valid.append(
            attendance_system.tokenizer.verify_signature(data, row['Signature'])
        )
    
    return render_template('verification.html',
                         blockchain_valid=blockchain_valid,
                         signatures_valid=sum(signatures_valid))


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