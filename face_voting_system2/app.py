from flask import Flask, render_template, request, redirect, session, Response, send_file
import cv2
import os
import sqlite3
import numpy as np
import base64
from gtts import gTTS

app = Flask(__name__)
app.secret_key = "secret"

# Load face cascade globally for better performance
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Cache for user face histograms to improve performance
user_cache = {}

def get_user_histograms():
    """Cache user face histograms for faster recognition"""
    global user_cache
    if 'users' not in user_cache:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT id, name, face_path FROM users")
        users = c.fetchall()
        conn.close()

        user_cache['users'] = []
        for user in users:
            face_path = user[2]
            if not face_path or not os.path.exists(face_path):
                continue

            stored_img = cv2.imread(face_path, cv2.IMREAD_GRAYSCALE)
            if stored_img is None:
                continue

            stored_img = cv2.resize(stored_img, (200, 200))
            stored_img = cv2.equalizeHist(stored_img)
            hist = cv2.calcHist([stored_img], [0], None, [256], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            user_cache['users'].append((user[0], user[1], hist))
    return user_cache['users']

def clear_user_cache():
    """Clear cache when users are added/removed"""
    global user_cache
    user_cache = {}
@app.route('/information')
def information():
    return render_template('information.html')
# ---------------- SPEECH ---------------- #
@app.route('/speak')
def speak():
    text = request.args.get('text')
    lang = request.args.get('lang', 'en')

    tts = gTTS(text=text, lang=lang)
    file_path = "speech.mp3"
    tts.save(file_path)

    return send_file(file_path, as_attachment=False)

# ---------------- DATABASE INIT ---------------- #
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    face_path TEXT,
                    voted INTEGER DEFAULT 0
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate TEXT
                )''')

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ---------------- #
@app.route('/')
def index():
    return render_template('index.html')

# ---------------- REGISTER PAGE ---------------- #
@app.route('/register')
def register_page():
    return render_template('register.html')

# ---------------- VIDEO ---------------- #
def get_camera():
    """Try to get camera with fallback options"""
    for camera_index in [0, 1, -1]:  # Try default, secondary, and auto-detect
        try:
            camera = cv2.VideoCapture(camera_index)
            if camera is not None and camera.isOpened():
                # Set camera properties for better performance
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                camera.set(cv2.CAP_PROP_FPS, 30)
                return camera
            camera.release()
        except Exception as e:
            print(f"Camera index {camera_index} failed: {e}")
            continue
    return None

def gen_frames():
    camera = get_camera()
    if camera is None:
        print("ERROR: Camera not available")
        return
    
    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Error: Failed to read frame from camera")
                break
            else:
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        camera.release()

@app.route('/video')
def video():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ---------------- SAVE FACE ---------------- #
@app.route('/save_face', methods=['POST'])
def save_face():
    data = request.get_json()

    if not data or 'name' not in data or 'image' not in data:
        return "Invalid data"

    name = data['name']
    image_data = data['image'].split(',')[1]

    img_bytes = base64.b64decode(image_data)

    os.makedirs('faces', exist_ok=True)

    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return "No face detected"

    (x, y, w, h) = faces[0]
    face_img = img[y:y+h, x:x+w]
    face_img = cv2.resize(face_img, (200, 200))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Insert with empty path first, then update with unique ID-based path
    c.execute(
        "INSERT INTO users (name, face_path, voted) VALUES (?, ?, 0)",
        (name, "")
    )
    user_id = c.lastrowid
    file_path = f'faces/{user_id}.jpg'

    cv2.imwrite(file_path, face_img)

    c.execute(
        "UPDATE users SET face_path = ? WHERE id = ?",
        (file_path, user_id)
    )

    conn.commit()
    conn.close()

    # Clear cache to include new user
    clear_user_cache()

    return "Face Registered Successfully!"

# ---------------- LOGIN ---------------- #
@app.route('/login')
def login():
    return render_template('login.html')

# ---------------- AUTHENTICATE ---------------- #
@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.get_json()
    if not data or 'image' not in data:
        return {"success": False, "message": "No image provided"}

    image_data = data['image'].split(',')[1]
    img_bytes = base64.b64decode(image_data)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {"success": False, "message": "Invalid image"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=4, minSize=(50, 50))

    if len(faces) == 0:
        return {"success": False, "message": "No face detected. Please ensure your face is clearly visible."}

    # Take the largest face
    faces = sorted(faces, key=lambda x: x[2] * x[3], reverse=True)
    (x, y, w, h) = faces[0]

    captured_face = gray[y:y+h, x:x+w]
    captured_face = cv2.resize(captured_face, (200, 200))
    captured_face = cv2.equalizeHist(captured_face)

    # Get cached user histograms
    users = get_user_histograms()

    if len(users) == 0:
        return {"success": False, "message": "No registered faces found. Please register first."}

    best_match = None
    highest_score = -1.0

    # Calculate histogram for captured face
    hist1 = cv2.calcHist([captured_face], [0], None, [256], [0, 256])
    hist1 = cv2.normalize(hist1, hist1).flatten()

    for user_id, name, hist2 in users:
        score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

        if score > highest_score:  # Higher correlation is better
            highest_score = score
            best_match = (user_id, name)

    if best_match and highest_score > 0.5:  # Lowered threshold for better recognition
        session['user_id'] = best_match[0]
        session['name'] = best_match[1]
        return {"success": True, "message": f"Welcome {best_match[1]}!", "redirect": "/vote_page"}

    return {"success": False, "message": "Face not recognized"}
# ---------------- VOTE ---------------- #
@app.route('/vote_page')
def vote_page():
    return render_template('vote.html')
@app.route('/leader')
def leader():
    return render_template('leader.html')
@app.route('/vote/<candidate>')
def vote(candidate):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # For now, we'll use a simple approach: each IP can vote once
    # You can enhance this with session-based tracking if needed
    
    c.execute("INSERT INTO votes (candidate) VALUES (?)", (candidate,))

    conn.commit()
    conn.close()

    return f"""
<html>
<head>
    <title>Vote Success</title>
</head>
<body style="text-align:center; font-family:Poppins; margin-top:100px;">

    <h1 style="color:green;">✅ Vote given to {candidate}</h1>
    <p>Redirecting to home page in 5 seconds...</p>

    <script>
        setTimeout(function() {{
            window.location.href = "/";
        }}, 5000);
    </script>

</body>
</html>
"""

# ---------------- PARTY INFO ---------------- #
@app.route('/party/<name>')
def party(name):
    return render_template(f"{name}.html")

# ---------------- ADMIN ---------------- #
@app.route('/admin')
def admin():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT candidate, COUNT(*) FROM votes GROUP BY candidate")
    results = c.fetchall()

    conn.close()
    return render_template('admin.html', results=results)

# ---------------- LOGOUT ---------------- #
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- RUN ---------------- #
if __name__ == '__main__':
    app.run(debug=True)