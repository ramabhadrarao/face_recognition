from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import requests
import base64
import json
from werkzeug.security import check_password_hash, generate_password_hash
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple User class
class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    if user_id in Config.USERS:
        return User(user_id)
    return None

# CompreFace API endpoints
COMPREFACE_BASE_URL = f"{Config.COMPREFACE_URL}/api/v1"
HEADERS = {
    'x-api-key': Config.COMPREFACE_API_KEY
}

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in Config.USERS and Config.USERS[username] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get all subjects from CompreFace
    try:
        response = requests.get(
            f"{COMPREFACE_BASE_URL}/recognition/subjects",
            headers=HEADERS,
            timeout=10
        )
        print(f"Dashboard - Status Code: {response.status_code}")
        print(f"Dashboard - Response: {response.text}")
        
        if response.status_code == 200:
            subjects = response.json().get('subjects', [])
        else:
            subjects = []
            flash(f'CompreFace API error: {response.status_code}', 'warning')
    except requests.exceptions.RequestException as e:
        subjects = []
        flash(f'Could not connect to CompreFace: {str(e)}', 'warning')
        print(f"Dashboard Error: {str(e)}")
    
    return render_template('dashboard.html', subjects=subjects)

@app.route('/add_subject', methods=['GET', 'POST'])
@login_required
def add_subject():
    if request.method == 'POST':
        subject_name = request.form.get('subject_name')
        image_data = request.form.get('image_data')
        
        if not subject_name or not image_data:
            flash('Please provide both name and image', 'danger')
            return render_template('add_subject.html')
        
        try:
            # Remove data URL prefix
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            # Decode base64 to binary
            image_binary = base64.b64decode(image_data)
            
            # First, detect faces to check how many are in the image
            detect_response = requests.post(
                f"{COMPREFACE_BASE_URL}/detection/detect",
                headers=HEADERS,
                params={'face_plugins': 'landmarks,gender,age', 'det_prob_threshold': 0.8},
                files={'file': ('image.jpg', image_binary, 'image/jpeg')},
                timeout=30
            )
            
            if detect_response.status_code == 200:
                faces = detect_response.json().get('result', [])
                
                if len(faces) == 0:
                    flash('No face detected in the image. Please ensure your face is clearly visible.', 'warning')
                    return render_template('add_subject.html')
                elif len(faces) > 1:
                    flash(f'Multiple faces detected ({len(faces)} faces). Please ensure only one person is in the frame.', 'warning')
                    return render_template('add_subject.html')
            
            # If we get here, we have exactly one face - proceed with adding
            response = requests.post(
                f"{COMPREFACE_BASE_URL}/recognition/faces",
                headers=HEADERS,
                params={'subject': subject_name, 'det_prob_threshold': 0.8},
                files={'file': ('image.jpg', image_binary, 'image/jpeg')},
                timeout=30
            )
            
            print(f"Add Subject - Status Code: {response.status_code}")
            print(f"Add Subject - Response: {response.text}")
            
            if response.status_code == 201:
                flash(f'Successfully added {subject_name}', 'success')
                return redirect(url_for('dashboard'))
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', 'Unknown error')
                except:
                    error_msg = response.text
                
                flash(f'Failed to add subject: {error_msg}', 'danger')
                
        except Exception as e:
            flash(f'Error processing image: {str(e)}', 'danger')
            print(f"Exception: {str(e)}")
    
    return render_template('add_subject.html')

@app.route('/recognize')
@login_required
def recognize():
    return render_template('recognize.html')

@app.route('/api/recognize', methods=['POST'])
@login_required
def api_recognize():
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        
        # Remove data URL prefix
        image_data = image_data.split(',')[1]
        image_binary = base64.b64decode(image_data)
        
        # Send to CompreFace for recognition
        response = requests.post(
            f"{COMPREFACE_BASE_URL}/recognition/recognize",
            headers=HEADERS,
            params={'limit': 1, 'det_prob_threshold': 0.8},
            files={'file': ('face.jpg', image_binary, 'image/jpeg')},
            timeout=30
        )
        
        print(f"Recognize - Status Code: {response.status_code}")
        print(f"Recognize - Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            return jsonify(result)
        else:
            return jsonify({'error': f'Recognition failed: {response.text}'}), 400
            
    except Exception as e:
        print(f"Recognition Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_subject/<subject_name>', methods=['DELETE'])
@login_required
def delete_subject(subject_name):
    try:
        response = requests.delete(
            f"{COMPREFACE_BASE_URL}/recognition/subjects/{subject_name}",
            headers=HEADERS,
            timeout=10
        )
        
        print(f"Delete - Status Code: {response.status_code}")
        print(f"Delete - Response: {response.text}")
        
        if response.status_code == 200:
            return jsonify({'success': True})
        else:
            return jsonify({'error': f'Failed to delete: {response.text}'}), 400
            
    except Exception as e:
        print(f"Delete Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',  # listens on all network interfaces
        port=5999,       # your custom port
        threaded=True    # enable multi-threaded handling
    )
    # app.run(debug=True, host='0.0.0.0', port=5999, threaded=True)  # Enable SSL with your certificate and key files

