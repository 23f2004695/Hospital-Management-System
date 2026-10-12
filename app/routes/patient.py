from datetime import date, timedelta

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from sqlalchemy import func

from app import db
from app.models import Patient, Doctor, Department, Appointment, DoctorAvailability
from app.utils import (FormError, role_required, field, email_field, phone_field, date_field, time_field,
                       int_arg, MIN_PASSWORD_LENGTH, BLOOD_GROUPS, GENDERS)

patient = Blueprint('patient', __name__)
patient_required = role_required('patient')

BOOKING_DAYS = 7


@patient.route('/dashboard')
@patient_required
def dashboard():
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == current_user.id,
        Appointment.appointment_date >= date.today(),
        Appointment.status == 'Booked',
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()

    recent_appointments = Appointment.query.filter_by(patient_id=current_user.id)\
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).limit(5).all()

    departments = Department.query.order_by(Department.name).all()
    doctor_counts = dict(db.session.query(Doctor.department_id, func.count(Doctor.id))
                         .filter(Doctor.is_available.is_(True)).group_by(Doctor.department_id).all())

    return render_template('patient/dashboard.html',
                           upcoming_appointments=upcoming_appointments,
                           recent_appointments=recent_appointments,
                           departments=departments,
                           doctor_counts=doctor_counts)


def _bookable_dates(doctor):
    today = date.today()
    rows = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date >= today,
        DoctorAvailability.date < today + timedelta(days=BOOKING_DAYS),
        DoctorAvailability.is_available.is_(True),
    ).order_by(DoctorAvailability.date).all()
    # Only offer days that still have a free slot
    return [r.date for r in rows if doctor.slots_for(r.date)]


@patient.route('/book-appointment', methods=['GET', 'POST'])
@patient_required
def book_appointment():
    if request.method == 'POST':
        try:
            doctor = db.session.get(Doctor, int_arg(request.form.get('doctor_id')) or 0)
            if not doctor or not doctor.is_available:
                raise FormError('That doctor is not taking appointments right now.')
            appt_date = date_field(request.form.get('appointment_date'), 'Date')
            appt_time = time_field(request.form.get('appointment_time'), 'Time')
            reason = field(request.form, 'reason', required=False, max_len=1000)

            if appt_time not in doctor.slots_for(appt_date):
                raise FormError('That time slot is no longer available. Please pick another one.')
            clash = Appointment.query.filter_by(patient_id=current_user.id, appointment_date=appt_date,
                                                appointment_time=appt_time, status='Booked').first()
            if clash:
                raise FormError(f'You already have an appointment with Dr. {clash.doctor.full_name} at that time.')
        except FormError as e:
            flash(str(e), 'error')
            return redirect(url_for('patient.book_appointment', **{
                k: v for k, v in (('department', request.form.get('department_id')),
                                  ('doctor', request.form.get('doctor_id')),
                                  ('date', request.form.get('appointment_date'))) if v
            }))

        db.session.add(Appointment(patient_id=current_user.id, doctor_id=doctor.id, appointment_date=appt_date,
                                   appointment_time=appt_time, reason=reason, status='Booked'))
        db.session.commit()
        flash(f'Appointment booked with Dr. {doctor.full_name} on {appt_date:%d %b} at {appt_time:%H:%M}!', 'success')
        return redirect(url_for('patient.appointments'))

    # GET: department -> doctor -> date -> time, each step narrowing the next
    departments = Department.query.order_by(Department.name).all()
    department = db.session.get(Department, int_arg(request.args.get('department')) or 0)
    doctors = Doctor.query.filter_by(department_id=department.id, is_available=True)\
        .order_by(Doctor.full_name).all() if department else []

    selected_doctor = db.session.get(Doctor, int_arg(request.args.get('doctor')) or 0)
    if selected_doctor not in doctors:
        selected_doctor = None

    available_dates, available_times, selected_date = [], [], None
    if selected_doctor:
        available_dates = _bookable_dates(selected_doctor)
        try:
            selected_date = date_field(request.args.get('date'), required=False)
        except FormError:
            selected_date = None
        if selected_date not in available_dates:
            selected_date = available_dates[0] if available_dates else None
        if selected_date:
            available_times = selected_doctor.slots_for(selected_date)

    return render_template('patient/book_appointment.html',
                           departments=departments, doctors=doctors,
                           department=department, selected_doctor=selected_doctor,
                           available_dates=available_dates, selected_date=selected_date,
                           available_times=available_times)


@patient.route('/appointments')
@patient_required
def appointments():
    appointments = Appointment.query.filter_by(patient_id=current_user.id)\
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    return render_template('patient/appointments.html', appointments=appointments)


@patient.route('/cancel-appointment/<int:appointment_id>', methods=['POST'])
@patient_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, patient_id=current_user.id).first_or_404()
    if appointment.status != 'Booked':
        flash('Can only cancel booked appointments!', 'error')
    else:
        appointment.status = 'Cancelled'
        db.session.commit()
        flash('Appointment cancelled successfully!', 'info')
    return redirect(request.referrer or url_for('patient.appointments'))


@patient.route('/profile', methods=['GET', 'POST'])
@patient_required
def profile():
    if request.method == 'POST':
        form = request.form
        try:
            full_name = field(form, 'full_name', 'Full name', max_len=100)
            email = email_field(form)
            phone = phone_field(form)
            emergency = phone_field(form, 'emergency_contact', 'Emergency contact', required=False)
            dob = date_field(form.get('date_of_birth'), 'Date of birth', required=False)
            gender = form.get('gender') or None
            blood_group = form.get('blood_group') or None
            address = field(form, 'address', required=False, max_len=500)
            medical_history = field(form, 'medical_history', 'Medical history', required=False, max_len=2000)

            if dob and dob > date.today():
                raise FormError('Date of birth cannot be in the future.')
            if gender and gender not in GENDERS:
                raise FormError('Please choose a gender from the list.')
            if blood_group and blood_group not in BLOOD_GROUPS:
                raise FormError('Please choose a blood group from the list.')
            if Patient.query.filter(func.lower(Patient.email) == email, Patient.id != current_user.id).first():
                raise FormError('Another account already uses that email.')

            new_password = form.get('new_password') or ''
            if new_password:
                if not current_user.check_password(form.get('current_password') or ''):
                    raise FormError('Your current password is incorrect.')
                if len(new_password) < MIN_PASSWORD_LENGTH:
                    raise FormError(f'New password must be at least {MIN_PASSWORD_LENGTH} characters.')
        except FormError as e:
            flash(str(e), 'error')
            return redirect(url_for('patient.profile'))

        current_user.full_name = full_name
        current_user.email = email
        current_user.phone = phone
        current_user.emergency_contact = emergency
        current_user.date_of_birth = dob
        current_user.gender = gender
        current_user.blood_group = blood_group
        current_user.address = address
        current_user.medical_history = medical_history
        if new_password:
            current_user.set_password(new_password)

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('patient.profile'))

    return render_template('patient/profile.html', blood_groups=BLOOD_GROUPS, genders=GENDERS,
                           today_iso=date.today().isoformat())


@patient.route('/treatment-history')
@patient_required
def treatment_history():
    appointments = Appointment.query.filter(
        Appointment.patient_id == current_user.id,
        Appointment.status == 'Completed',
        Appointment.treatments.any(),
    ).order_by(Appointment.appointment_date.desc()).all()
    return render_template('patient/treatment_history.html', appointments=appointments)
