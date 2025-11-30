from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from app.models import Admin, Doctor, Patient, Department, Appointment, Treatment
from app import db
from datetime import datetime, date
from sqlalchemy import or_, and_

admin = Blueprint('admin', __name__)

def admin_required(f):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or session.get('user_type') != 'admin':
            flash('Admin access required!', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_doctors = Doctor.query.count()
    total_patients = Patient.query.count()
    total_appointments = Appointment.query.count()
    today_appointments = Appointment.query.filter_by(appointment_date=date.today()).count()
    recent_appointments = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                         total_doctors=total_doctors,
                         total_patients=total_patients,
                         total_appointments=total_appointments,
                         today_appointments=today_appointments,
                         recent_appointments=recent_appointments)

@admin.route('/manage-doctors', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_doctors():
    search = request.args.get('search', '')
    if search:
        doctors = Doctor.query.filter(
            or_(Doctor.full_name.contains(search),
                Doctor.username.contains(search),
                Doctor.email.contains(search))
        ).all()
    else:
        doctors = Doctor.query.all()

    departments = Department.query.all()
    return render_template('admin/manage_doctors.html', doctors=doctors, departments=departments)

@admin.route('/add-doctor', methods=['GET', 'POST'])
@login_required
@admin_required
def add_doctor():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        license_number = request.form.get('license_number')
        department_id = request.form.get('department_id')
        experience_years = request.form.get('experience_years', 0)
        qualification = request.form.get('qualification')
        consultation_fee = request.form.get('consultation_fee', 500)

        if Doctor.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return render_template('admin/add_doctor.html', departments=Department.query.all())

        if Doctor.query.filter_by(email=email).first():
            flash('Email already exists!', 'error')
            return render_template('admin/add_doctor.html', departments=Department.query.all())

        doctor = Doctor(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
            license_number=license_number,
            department_id=int(department_id),
            experience_years=int(experience_years) if experience_years else 0,
            qualification=qualification,
            consultation_fee=float(consultation_fee) if consultation_fee else 500.0
        )

        db.session.add(doctor)
        db.session.commit()

        flash('Doctor added successfully!', 'success')
        return redirect(url_for('admin.manage_doctors'))

    departments = Department.query.all()
    return render_template('admin/add_doctor.html', departments=departments)

@admin.route('/edit-doctor/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)

    if request.method == 'POST':
        doctor.full_name = request.form.get('full_name')
        doctor.email = request.form.get('email')
        doctor.phone = request.form.get('phone')
        doctor.license_number = request.form.get('license_number')
        doctor.department_id = int(request.form.get('department_id'))
        doctor.experience_years = int(request.form.get('experience_years', 0))
        doctor.qualification = request.form.get('qualification')
        doctor.consultation_fee = float(request.form.get('consultation_fee', 500))
        doctor.is_available = 'is_available' in request.form

        db.session.commit()
        flash('Doctor updated successfully!', 'success')
        return redirect(url_for('admin.manage_doctors'))

    departments = Department.query.all()
    return render_template('admin/edit_doctor.html', doctor=doctor, departments=departments)

@admin.route('/delete-doctor/<int:doctor_id>')
@login_required
@admin_required
def delete_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)

    if doctor.appointments:
        flash('Cannot delete doctor with existing appointments!', 'error')
    else:
        db.session.delete(doctor)
        db.session.commit()
        flash('Doctor deleted successfully!', 'success')

    return redirect(url_for('admin.manage_doctors'))

@admin.route('/manage-patients', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_patients():
    search = request.args.get('search', '')
    if search:
        patients = Patient.query.filter(
            or_(Patient.full_name.contains(search),
                Patient.username.contains(search),
                Patient.email.contains(search),
                Patient.phone.contains(search))
        ).all()
    else:
        patients = Patient.query.all()

    return render_template('admin/manage_patients.html', patients=patients)

@admin.route('/appointments', methods=['GET', 'POST'])
@login_required
@admin_required
def appointments():
    status_filter = request.args.get('status', '')
    date_filter = request.args.get('date', '')

    query = Appointment.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(appointment_date=filter_date)
        except ValueError:
            pass

    appointments = query.order_by(Appointment.appointment_date.desc()).all()
    return render_template('admin/appointments.html', appointments=appointments)
