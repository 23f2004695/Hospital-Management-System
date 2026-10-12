from datetime import datetime, date

from flask import Blueprint, render_template, request, flash, redirect, url_for
from sqlalchemy import or_, func

from app import db
from app.models import Doctor, Patient, Department, Appointment
from app.utils import (FormError, role_required, field, email_field, phone_field, password_field,
                       number_field, int_arg)

admin = Blueprint('admin', __name__)
admin_required = role_required('admin')

STATUSES = ('Booked', 'Completed', 'Cancelled')


@admin.route('/dashboard')
@admin_required
def dashboard():
    return render_template(
        'admin/dashboard.html',
        total_doctors=Doctor.query.count(),
        total_patients=Patient.query.count(),
        total_appointments=Appointment.query.count(),
        today_appointments=Appointment.query.filter_by(appointment_date=date.today()).count(),
        status_counts={s: Appointment.query.filter_by(status=s).count() for s in STATUSES},
        recent_appointments=Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all(),
        today_iso=date.today().isoformat(),
    )


@admin.route('/manage-doctors')
@admin_required
def manage_doctors():
    search = request.args.get('search', '').strip()
    query = Doctor.query
    if search:
        query = query.join(Department).filter(or_(
            Doctor.full_name.ilike(f'%{search}%'),
            Doctor.username.ilike(f'%{search}%'),
            Doctor.email.ilike(f'%{search}%'),
            Department.name.ilike(f'%{search}%'),
        ))
    doctors = query.order_by(Doctor.full_name).all()
    return render_template('admin/manage_doctors.html', doctors=doctors, search=search)


def _doctor_form(form, doctor=None):
    """Validate the add/edit doctor form and return the cleaned values."""
    data = {
        'full_name': field(form, 'full_name', 'Full name', max_len=100),
        'email': email_field(form),
        'phone': phone_field(form),
        'license_number': field(form, 'license_number', 'License number', max_len=50),
        'qualification': field(form, 'qualification', required=False),
        'experience_years': number_field(form, 'experience_years', 'Experience'),
        'consultation_fee': number_field(form, 'consultation_fee', 'Consultation fee', float, default=500.0),
    }
    department_id = int_arg(form.get('department_id'))
    if not department_id or not db.session.get(Department, department_id):
        raise FormError('Please choose a department.')
    data['department_id'] = department_id

    others = Doctor.query.filter(Doctor.id != doctor.id) if doctor else Doctor.query
    if others.filter(func.lower(Doctor.email) == data['email']).first():
        raise FormError('Email already exists!')
    if others.filter(Doctor.license_number == data['license_number']).first():
        raise FormError('Another doctor already has that license number.')
    return data


@admin.route('/add-doctor', methods=['GET', 'POST'])
@admin_required
def add_doctor():
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        try:
            username = field(request.form, 'username', max_len=80)
            password = password_field(request.form)
            if Doctor.query.filter(func.lower(Doctor.username) == username.lower()).first():
                raise FormError('Username already exists!')
            data = _doctor_form(request.form)
        except FormError as e:
            flash(str(e), 'error')
            return render_template('admin/add_doctor.html', departments=departments, form=request.form)

        db.session.add(Doctor(username=username, password=password, **data))
        db.session.commit()
        flash('Doctor added successfully!', 'success')
        return redirect(url_for('admin.manage_doctors'))

    return render_template('admin/add_doctor.html', departments=departments, form={})


@admin.route('/edit-doctor/<int:doctor_id>', methods=['GET', 'POST'])
@admin_required
def edit_doctor(doctor_id):
    doctor = db.get_or_404(Doctor, doctor_id)
    departments = Department.query.order_by(Department.name).all()

    if request.method == 'POST':
        try:
            data = _doctor_form(request.form, doctor)
        except FormError as e:
            flash(str(e), 'error')
            return render_template('admin/edit_doctor.html', doctor=doctor, departments=departments)

        for key, value in data.items():
            setattr(doctor, key, value)
        doctor.is_available = 'is_available' in request.form
        db.session.commit()
        flash('Doctor updated successfully!', 'success')
        return redirect(url_for('admin.manage_doctors'))

    return render_template('admin/edit_doctor.html', doctor=doctor, departments=departments)


@admin.route('/delete-doctor/<int:doctor_id>', methods=['POST'])
@admin_required
def delete_doctor(doctor_id):
    doctor = db.get_or_404(Doctor, doctor_id)
    if doctor.appointments:
        flash('This doctor has appointments, so they can only be marked unavailable, not deleted.', 'error')
    else:
        db.session.delete(doctor)
        db.session.commit()
        flash('Doctor deleted successfully!', 'success')
    return redirect(url_for('admin.manage_doctors'))


@admin.route('/manage-patients')
@admin_required
def manage_patients():
    search = request.args.get('search', '').strip()
    query = Patient.query
    if search:
        conditions = [
            Patient.full_name.ilike(f'%{search}%'),
            Patient.username.ilike(f'%{search}%'),
            Patient.email.ilike(f'%{search}%'),
            Patient.phone.ilike(f'%{search}%'),
        ]
        if search.isdigit():
            conditions.append(Patient.id == int(search))
        query = query.filter(or_(*conditions))
    patients = query.order_by(Patient.full_name).all()
    return render_template('admin/manage_patients.html', patients=patients, search=search)


@admin.route('/patient/<int:patient_id>')
@admin_required
def patient_detail(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient.id)\
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    return render_template('patient_history.html', patient=patient, appointments=appointments,
                           back_url=url_for('admin.manage_patients'))


@admin.route('/patient/<int:patient_id>/toggle', methods=['POST'])
@admin_required
def toggle_patient(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    patient.is_active = not patient.is_active
    db.session.commit()
    flash(f"{patient.full_name} has been {'re-activated' if patient.is_active else 'blocked from logging in'}.", 'success')
    return redirect(request.referrer or url_for('admin.manage_patients'))


@admin.route('/appointments')
@admin_required
def appointments():
    status_filter = request.args.get('status', '')
    date_filter = request.args.get('date', '')
    query = Appointment.query

    if status_filter in STATUSES:
        query = query.filter_by(status=status_filter)
    if date_filter:
        try:
            query = query.filter_by(appointment_date=datetime.strptime(date_filter, '%Y-%m-%d').date())
        except ValueError:
            flash('That date filter is not valid.', 'error')

    appointments = query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    return render_template('admin/appointments.html', appointments=appointments)


@admin.route('/appointments/<int:appointment_id>/cancel', methods=['POST'])
@admin_required
def cancel_appointment(appointment_id):
    appointment = db.get_or_404(Appointment, appointment_id)
    if appointment.status != 'Booked':
        flash('Only booked appointments can be cancelled.', 'error')
    else:
        appointment.status = 'Cancelled'
        db.session.commit()
        flash('Appointment cancelled.', 'info')
    return redirect(request.referrer or url_for('admin.appointments'))
