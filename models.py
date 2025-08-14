from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(100), unique=True, nullable=False)
    employee_id = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    date_joined = db.Column(db.Date, nullable=False)
    salary = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with attendance logs
    attendance_logs = db.relationship('AttendanceLog', backref='employee', lazy=True)

class AttendanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    log_type = db.Column(db.String(10), nullable=False)  # 'IN' or 'OUT'
    similarity_score = db.Column(db.Float)
    confidence_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FaceImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    image_id = db.Column(db.String(100), unique=True, nullable=False)  # CompreFace image ID
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='face_images')