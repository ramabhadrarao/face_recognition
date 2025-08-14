from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import requests
import base64
import json
from werkzeug.security import check_password_hash, generate_password_hash
from config import Config
from models import db, Employee, AttendanceLog, FaceImage
from datetime import datetime, timedelta, date
from sqlalchemy import func, and_, extract
import uuid
import pytz

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create tables
with app.app_context():
    db.create_all()

# Timezone helper functions
def get_ist_time():
    """Get current time in IST"""
    return datetime.now(Config.TIMEZONE)

def utc_to_ist(utc_dt):
    """Convert UTC datetime to IST"""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    return utc_dt.astimezone(Config.TIMEZONE)

def ist_to_utc(ist_dt):
    """Convert IST datetime to UTC for database storage"""
    if ist_dt is None:
        return None
    if ist_dt.tzinfo is None:
        ist_dt = Config.TIMEZONE.localize(ist_dt)
    return ist_dt.astimezone(pytz.UTC).replace(tzinfo=None)

# Add timezone filter for templates
@app.template_filter('to_ist')
def to_ist_filter(dt):
    """Template filter to convert UTC to IST"""
    if dt:
        return utc_to_ist(dt)
    return dt

@app.template_filter('ist_format')
def ist_format_filter(dt, format='%d %b %Y %I:%M %p'):
    """Template filter to format datetime in IST"""
    if dt:
        ist_time = utc_to_ist(dt)
        return ist_time.strftime(format)
    return ''

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
    # Get all employees from database
    employees = Employee.query.filter_by(is_active=True).all()
    
    # Get today's attendance summary in IST
    today_ist = get_ist_time().date()
    today_start_utc = ist_to_utc(datetime.combine(today_ist, datetime.min.time()))
    today_end_utc = ist_to_utc(datetime.combine(today_ist, datetime.max.time()))
    
    attendance_summary = db.session.query(
        Employee.full_name,
        func.min(AttendanceLog.timestamp).label('first_in'),
        func.max(AttendanceLog.timestamp).label('last_out')
    ).join(
        AttendanceLog
    ).filter(
        AttendanceLog.timestamp >= today_start_utc,
        AttendanceLog.timestamp <= today_end_utc
    ).group_by(Employee.id).all()
    
    return render_template('dashboard.html', 
                         employees=employees, 
                         attendance_summary=attendance_summary)

@app.route('/add_employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        # Get form data
        employee_id = request.form.get('employee_id')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        department = request.form.get('department')
        designation = request.form.get('designation')
        date_joined = datetime.strptime(request.form.get('date_joined'), '%Y-%m-%d').date()
        salary = float(request.form.get('salary', 0))
        image_data = request.form.get('image_data')
        
        # Generate subject name for CompreFace
        subject_name = f"emp_{employee_id}"
        
        print(f"Creating employee with subject name: {subject_name}")  # Debug log
        
        if not image_data:
            flash('Please capture at least one photo', 'danger')
            return render_template('add_employee.html')
        
        try:
            # Check if employee already exists
            existing = Employee.query.filter(
                (Employee.employee_id == employee_id) | 
                (Employee.email == email)
            ).first()
            
            if existing:
                flash('Employee with this ID or email already exists', 'danger')
                return render_template('add_employee.html')
            
            # Create employee record
            employee = Employee(
                subject_name=subject_name,
                employee_id=employee_id,
                full_name=full_name,
                email=email,
                phone=phone,
                department=department,
                designation=designation,
                date_joined=date_joined,
                salary=salary
            )
            db.session.add(employee)
            db.session.flush()  # Get the ID without committing
            
            # Process and add face to CompreFace
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_binary = base64.b64decode(image_data)
            
            # Add face to CompreFace
            response = requests.post(
                f"{COMPREFACE_BASE_URL}/recognition/faces",
                headers=HEADERS,
                params={'subject': subject_name, 'det_prob_threshold': 0.8},
                files={'file': ('image.jpg', image_binary, 'image/jpeg')},
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                image_id = result.get('image_id')
                
                # Store face image reference
                face_image = FaceImage(
                    employee_id=employee.id,
                    image_id=image_id,
                    is_primary=True
                )
                db.session.add(face_image)
                db.session.commit()
                
                flash(f'Successfully added employee: {full_name}', 'success')
                return redirect(url_for('dashboard'))
            else:
                db.session.rollback()
                flash(f'Failed to add face to recognition system', 'danger')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding employee: {str(e)}', 'danger')
            print(f"Exception: {str(e)}")
    
    return render_template('add_employee.html')

@app.route('/add_face/<int:employee_id>', methods=['GET', 'POST'])
@login_required
def add_face(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    if request.method == 'POST':
        image_data = request.form.get('image_data')
        
        if not image_data:
            flash('Please capture a photo', 'danger')
            return render_template('add_face.html', employee=employee)
        
        try:
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_binary = base64.b64decode(image_data)
            
            # Add additional face to CompreFace
            response = requests.post(
                f"{COMPREFACE_BASE_URL}/recognition/faces",
                headers=HEADERS,
                params={'subject': employee.subject_name, 'det_prob_threshold': 0.8},
                files={'file': ('image.jpg', image_binary, 'image/jpeg')},
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                image_id = result.get('image_id')
                
                # Store face image reference
                face_image = FaceImage(
                    employee_id=employee.id,
                    image_id=image_id,
                    is_primary=False
                )
                db.session.add(face_image)
                db.session.commit()
                
                flash(f'Successfully added face for {employee.full_name}', 'success')
                return redirect(url_for('employee_details', employee_id=employee.id))
            else:
                flash('Failed to add face', 'danger')
                
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('add_face.html', employee=employee)

@app.route('/employee/<int:employee_id>')
@login_required
def employee_details(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    # Get attendance logs for current month
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    logs = AttendanceLog.query.filter(
        AttendanceLog.employee_id == employee_id,
        extract('month', AttendanceLog.timestamp) == current_month,
        extract('year', AttendanceLog.timestamp) == current_year
    ).order_by(AttendanceLog.timestamp.desc()).all()
    
    # Calculate working hours
    working_days = {}
    for log in logs:
        date_key = log.timestamp.date()
        if date_key not in working_days:
            working_days[date_key] = {'in': None, 'out': None, 'logs': []}
        
        working_days[date_key]['logs'].append(log)
        
        if log.log_type == 'IN' and not working_days[date_key]['in']:
            working_days[date_key]['in'] = log.timestamp
        elif log.log_type == 'OUT':
            working_days[date_key]['out'] = log.timestamp
    
    # Calculate total hours and salary with overtime
    total_regular_hours = 0
    total_overtime_hours = 0
    total_days_worked = 0
    today_ist = get_ist_time().date()
    
    # Detailed calculation for each day
    daily_calculations = {}
    
    for day, times in working_days.items():
        daily_calc = {
            'regular_hours': 0,
            'overtime_hours': 0,
            'total_hours': 0,
            'status': 'absent'
        }
        
        if times['in'] and times['out']:
            # Full day with both IN and OUT
            hours_worked = (times['out'] - times['in']).total_seconds() / 3600
            
            if hours_worked >= Config.WORKING_HOURS_PER_DAY:
                # Full day + overtime
                daily_calc['regular_hours'] = Config.WORKING_HOURS_PER_DAY
                daily_calc['overtime_hours'] = hours_worked - Config.WORKING_HOURS_PER_DAY
                daily_calc['status'] = 'present_ot'
                total_days_worked += 1
            elif hours_worked >= Config.MINIMUM_HOURS_FOR_FULL_DAY:
                # Full day, no overtime
                daily_calc['regular_hours'] = hours_worked
                daily_calc['status'] = 'present'
                total_days_worked += 1
            else:
                # Less than minimum hours - half day
                daily_calc['regular_hours'] = hours_worked
                daily_calc['status'] = 'half_day'
                total_days_worked += 0.5
                
            daily_calc['total_hours'] = hours_worked
            total_regular_hours += daily_calc['regular_hours']
            total_overtime_hours += daily_calc['overtime_hours']
            
        elif times['in'] and not times['out']:
            # Only clocked IN
            if day == today_ist:
                # Today - calculate hours until now
                now_ist = get_ist_time()
                in_time_ist = utc_to_ist(times['in'])
                hours_till_now = (now_ist - in_time_ist).total_seconds() / 3600
                
                daily_calc['regular_hours'] = min(hours_till_now, Config.WORKING_HOURS_PER_DAY)
                if hours_till_now > Config.WORKING_HOURS_PER_DAY:
                    daily_calc['overtime_hours'] = hours_till_now - Config.WORKING_HOURS_PER_DAY
                daily_calc['total_hours'] = hours_till_now
                daily_calc['status'] = 'ongoing'
                
                # Don't count as full day yet
                if hours_till_now >= Config.MINIMUM_HOURS_FOR_FULL_DAY:
                    total_days_worked += 1
                else:
                    total_days_worked += 0.5
                    
                total_regular_hours += daily_calc['regular_hours']
                total_overtime_hours += daily_calc['overtime_hours']
            else:
                # Past date with only IN - based on policy
                if Config.INCOMPLETE_DAY_POLICY == 'NO_PAY':
                    daily_calc['status'] = 'incomplete'
                elif Config.INCOMPLETE_DAY_POLICY == 'HALF_DAY':
                    daily_calc['regular_hours'] = Config.WORKING_HOURS_PER_DAY / 2
                    daily_calc['status'] = 'half_day'
                    total_days_worked += 0.5
                    total_regular_hours += daily_calc['regular_hours']
                elif Config.INCOMPLETE_DAY_POLICY == 'FULL_DAY':
                    daily_calc['regular_hours'] = Config.WORKING_HOURS_PER_DAY
                    daily_calc['status'] = 'assumed_full'
                    total_days_worked += 1
                    total_regular_hours += daily_calc['regular_hours']
                    
        daily_calculations[day] = daily_calc
    
    # Salary calculation with overtime
    daily_salary = employee.salary / Config.WORKING_DAYS_PER_MONTH
    hourly_salary = daily_salary / Config.WORKING_HOURS_PER_DAY
    
    # Calculate components
    basic_salary = daily_salary * total_days_worked
    overtime_pay = total_overtime_hours * (hourly_salary * Config.OVERTIME_MULTIPLIER)
    total_salary = basic_salary + overtime_pay
    
    # Add daily calculations to working_days for template
    for day in working_days:
        working_days[day]['calc'] = daily_calculations.get(day, {})
    
    return render_template('employee_details.html', 
                         employee=employee,
                         logs=logs,
                         working_days=working_days,
                         total_regular_hours=total_regular_hours,
                         total_overtime_hours=total_overtime_hours,
                         total_days_worked=total_days_worked,
                         basic_salary=basic_salary,
                         overtime_pay=overtime_pay,
                         total_salary=total_salary,
                         daily_salary=daily_salary,
                         hourly_salary=hourly_salary,
                         datetime=datetime,
                         date=date)

@app.route('/attendance')
@login_required
def attendance():
    return render_template('attendance.html')

@app.route('/api/clock', methods=['POST'])
@login_required
def api_clock():
    try:
        data = request.get_json()
        image_data = data.get('image')
        log_type = data.get('type', 'IN')  # IN or OUT
        
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
        
        if response.status_code == 200:
            result = response.json()
            print(f"Recognition result: {json.dumps(result, indent=2)}")
            
            if result.get('result') and len(result['result']) > 0:
                face = result['result'][0]
                
                if face.get('subjects') and len(face['subjects']) > 0:
                    subject = face['subjects'][0]
                    similarity = subject.get('similarity', 0)
                    subject_name = subject.get('subject', '')
                    
                    print(f"Recognized: {subject_name} with similarity {similarity}")
                    
                    # Check if similarity meets threshold
                    if similarity < Config.SIMILARITY_THRESHOLD:
                        return jsonify({
                            'success': False,
                            'message': f'Face not recognized with sufficient confidence (similarity: {similarity:.2%})'
                        }), 200
                    
                    # Find employee by subject name
                    employee = Employee.query.filter_by(
                        subject_name=subject_name
                    ).first()
                    
                    if not employee:
                        print(f"Employee not found for subject: {subject_name}")
                        # Try to find by partial match if exact match fails
                        all_employees = Employee.query.filter_by(is_active=True).all()
                        for emp in all_employees:
                            if emp.subject_name == subject_name:
                                employee = emp
                                break
                        
                        if not employee:
                            return jsonify({
                                'success': False,
                                'message': f'Employee not found in database for subject: {subject_name}'
                            }), 200
                    
                    # Check for recent logs to prevent duplicates
                    current_time_utc = datetime.utcnow()
                    recent_threshold = current_time_utc - timedelta(
                        minutes=Config.MINIMUM_INTERVAL_MINUTES
                    )
                    
                    recent_log = AttendanceLog.query.filter(
                        AttendanceLog.employee_id == employee.id,
                        AttendanceLog.timestamp > recent_threshold,
                        AttendanceLog.log_type == log_type
                    ).first()
                    
                    if recent_log:
                        return jsonify({
                            'success': False,
                            'message': f'Already clocked {log_type.lower()} recently. Please wait {Config.MINIMUM_INTERVAL_MINUTES} minutes.'
                        }), 200
                    
                    # Create attendance log with current UTC time (will be converted to IST for display)
                    attendance_log = AttendanceLog(
                        employee_id=employee.id,
                        log_type=log_type,
                        similarity_score=similarity,
                        confidence_score=face.get('det_probability', 0.0),
                        timestamp=current_time_utc
                    )
                    db.session.add(attendance_log)
                    db.session.commit()
                    
                    # Return IST time for display
                    ist_time = utc_to_ist(attendance_log.timestamp)
                    
                    return jsonify({
                        'success': True,
                        'employee': {
                            'name': employee.full_name,
                            'id': employee.employee_id,
                            'department': employee.department
                        },
                        'log_type': log_type,
                        'timestamp': ist_time.strftime('%Y-%m-%d %I:%M:%S %p IST'),
                        'similarity': f"{similarity * 100:.2f}%"
                    }), 200
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Face detected but not recognized. Please ensure you are registered in the system.'
                    }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'No face detected in the image. Please ensure your face is clearly visible.'
                }), 200
        else:
            print(f"CompreFace error: {response.status_code} - {response.text}")
            return jsonify({'error': f'Recognition failed: {response.text}'}), 400
            
    except Exception as e:
        print(f"Clock Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/reports')
@login_required
def reports():
    # Get month and policy from query parameters
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    policy = request.args.get('policy', 'NO_PAY')  # Default to NO_PAY
    year, month = map(int, month_str.split('-'))
    
    # Get all employees with their attendance data
    employees_data = []
    
    employees = Employee.query.filter_by(is_active=True).all()
    
    for employee in employees:
        # Get all logs for this month
        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id == employee.id,
            extract('month', AttendanceLog.timestamp) == month,
            extract('year', AttendanceLog.timestamp) == year
        ).order_by(AttendanceLog.timestamp).all()
        
        print(f"\nProcessing {employee.full_name} with policy: {policy}")
        print(f"Found {len(logs)} logs for this month")
        
        # Process logs to calculate working days and hours
        working_days = {}
        for log in logs:
            date_key = log.timestamp.date()
            if date_key not in working_days:
                working_days[date_key] = {'in': None, 'out': None}
            
            if log.log_type == 'IN' and not working_days[date_key]['in']:
                working_days[date_key]['in'] = log.timestamp
            elif log.log_type == 'OUT':
                working_days[date_key]['out'] = log.timestamp
        
        print(f"Working days: {len(working_days)}")
        
        # Calculate totals with overtime based on selected policy
        total_days = 0
        total_regular_hours = 0
        total_overtime_hours = 0
        total_actual_hours = 0
        
        for day, times in working_days.items():
            if times['in'] and times['out']:
                # Complete day
                hours_worked = (times['out'] - times['in']).total_seconds() / 3600
                total_actual_hours += hours_worked
                
                if hours_worked >= Config.WORKING_HOURS_PER_DAY:
                    # Full day + overtime
                    regular_hours = Config.WORKING_HOURS_PER_DAY
                    overtime_hours = hours_worked - Config.WORKING_HOURS_PER_DAY
                    total_days += 1
                elif hours_worked >= Config.MINIMUM_HOURS_FOR_FULL_DAY:
                    # Full day, no overtime
                    regular_hours = hours_worked
                    overtime_hours = 0
                    total_days += 1
                else:
                    # Less than minimum - apply policy
                    if policy == 'ACTUAL_HOURS':
                        regular_hours = hours_worked
                        overtime_hours = 0
                        total_days += hours_worked / Config.WORKING_HOURS_PER_DAY
                    else:
                        regular_hours = hours_worked
                        overtime_hours = 0
                        total_days += 0.5  # Half day
                
                total_regular_hours += regular_hours
                total_overtime_hours += overtime_hours
                
            elif times['in'] and not times['out']:
                # Incomplete day
                if day == date.today():
                    # Today - calculate hours until now
                    current_time = get_ist_time()
                    in_time_ist = utc_to_ist(times['in'])
                    hours_till_now = (current_time - in_time_ist).total_seconds() / 3600
                    total_actual_hours += hours_till_now
                    regular_hours = min(hours_till_now, Config.WORKING_HOURS_PER_DAY)
                    overtime_hours = max(0, hours_till_now - Config.WORKING_HOURS_PER_DAY)
                    
                    if policy == 'ACTUAL_HOURS':
                        total_days += hours_till_now / Config.WORKING_HOURS_PER_DAY
                    elif hours_till_now >= Config.MINIMUM_HOURS_FOR_FULL_DAY:
                        total_days += 1
                    else:
                        total_days += 0.5
                        
                    total_regular_hours += regular_hours
                    total_overtime_hours += overtime_hours
                else:
                    # Past day with only IN - apply selected policy
                    print(f"  Incomplete day {day}: applying policy {policy}")
                    
                    if policy == 'NO_PAY':
                        # No payment for incomplete days
                        print(f"    NO_PAY: No hours/days added")
                        pass
                    elif policy == 'HALF_DAY':
                        total_regular_hours += Config.WORKING_HOURS_PER_DAY / 2
                        total_days += 0.5
                        print(f"    HALF_DAY: Added 4 hours and 0.5 days")
                    elif policy == 'FULL_DAY':
                        total_regular_hours += Config.WORKING_HOURS_PER_DAY
                        total_days += 1
                        print(f"    FULL_DAY: Added 8 hours and 1 day")
                    elif policy == 'ACTUAL_HOURS':
                        # Assume minimum hours for past incomplete days
                        assumed_hours = 4  # Assume 4 hours if no clock out
                        total_regular_hours += assumed_hours
                        total_actual_hours += assumed_hours
                        total_days += assumed_hours / Config.WORKING_HOURS_PER_DAY
                        print(f"    ACTUAL_HOURS: Added {assumed_hours} hours")
        
        # Calculate salary based on selected policy
        daily_salary = employee.salary / Config.WORKING_DAYS_PER_MONTH
        hourly_salary = daily_salary / Config.WORKING_HOURS_PER_DAY
        
        if policy == 'ACTUAL_HOURS':
            # Pay based on actual hours worked
            basic_salary = total_regular_hours * hourly_salary
            overtime_pay = total_overtime_hours * (hourly_salary * Config.OVERTIME_MULTIPLIER)
            print(f"\nACTUAL_HOURS calculation:")
            print(f"  Regular hours: {total_regular_hours} × ₹{hourly_salary:.2f} = ₹{basic_salary:.2f}")
        else:
            # Pay based on days worked
            basic_salary = daily_salary * total_days
            overtime_pay = total_overtime_hours * (hourly_salary * Config.OVERTIME_MULTIPLIER)
            print(f"\n{policy} calculation:")
            print(f"  Days worked: {total_days} × ₹{daily_salary:.2f} = ₹{basic_salary:.2f}")
        
        total_salary = basic_salary + overtime_pay
        
        print(f"  Overtime: {total_overtime_hours} hrs × ₹{hourly_salary * Config.OVERTIME_MULTIPLIER:.2f} = ₹{overtime_pay:.2f}")
        print(f"  Total salary: ₹{total_salary:.2f}")
        
        employees_data.append({
            'employee': employee,
            'total_days': total_days,
            'total_regular_hours': round(total_regular_hours, 2),
            'total_overtime_hours': round(total_overtime_hours, 2),
            'total_actual_hours': round(total_actual_hours, 2),
            'basic_salary': round(basic_salary, 2),
            'overtime_pay': round(overtime_pay, 2),
            'total_salary': round(total_salary, 2)
        })
    
    return render_template('reports.html', 
                         employees_data=employees_data,
                         month=month_str,
                         policy=policy)

@app.route('/api/delete_employee/<int:employee_id>', methods=['DELETE'])
@login_required
def delete_employee(employee_id):
    try:
        employee = Employee.query.get_or_404(employee_id)
        
        # Delete from CompreFace
        response = requests.delete(
            f"{COMPREFACE_BASE_URL}/recognition/subjects/{employee.subject_name}",
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            # Soft delete - just mark as inactive
            employee.is_active = False
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to delete from recognition system'}), 400
            
    except Exception as e:
        print(f"Delete Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/subjects')
@login_required
def debug_subjects():
    try:
        # Get subjects from CompreFace
        response = requests.get(
            f"{COMPREFACE_BASE_URL}/recognition/subjects",
            headers=HEADERS,
            timeout=10
        )
        
        compreface_subjects = []
        if response.status_code == 200:
            compreface_subjects = response.json().get('subjects', [])
        
        # Get employees from database
        db_employees = Employee.query.filter_by(is_active=True).all()
        
        return jsonify({
            'compreface_subjects': compreface_subjects,
            'database_employees': [
                {
                    'id': e.id,
                    'employee_id': e.employee_id,
                    'name': e.full_name,
                    'subject_name': e.subject_name
                } for e in db_employees
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5999, threaded=True)