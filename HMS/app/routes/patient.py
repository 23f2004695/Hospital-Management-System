from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from app.models import Patient, Doctor, Department, Appointment, DoctorAvailability, Treatment
from app import db
from datetime import datetime, date, timedelta, time
from sqlalchemy import and_, or_


patient = Blueprint('patient', __name__)


def patient_required(f):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or session.get('user_type') != 'patient':
            flash('Patient access required!', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@patient.route('/dashboard')
@login_required
@patient_required
def dashboard():
    upcoming_appointments = Appointment.query.filter(
        and_(Appointment.patient_id == current_user.id,
             Appointment.appointment_date >= date.today(),
             Appointment.status.in_(['Booked']))
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()

    recent_appointments = Appointment.query.filter_by(
        patient_id=current_user.id
    ).order_by(Appointment.appointment_date.desc()).limit(5).all()

    departments = Department.query.all()

    start_date = date.today()
    end_date = start_date + timedelta(days=7)

    available_doctors = db.session.query(Doctor).join(DoctorAvailability).filter(
        and_(DoctorAvailability.date >= start_date,
             DoctorAvailability.date <= end_date,
             DoctorAvailability.is_available == True,
             Doctor.is_available == True)
    ).distinct().all()

    return render_template(
        'patient/dashboard.html',
        upcoming_appointments=upcoming_appointments,
        recent_appointments=recent_appointments,
        departments=departments,
        available_doctors=available_doctors
    )


@patient.route('/book-appointment', methods=['GET', 'POST'])
@login_required
@patient_required
def book_appointment():
    # POST: actually book the appointment
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        reason = request.form.get('reason')

        try:
            appt_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            appt_time = datetime.strptime(appointment_time, '%H:%M').time()
        except ValueError:
            flash('Invalid date or time format!', 'error')
            return redirect(url_for('patient.book_appointment'))

        existing_appointment = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            status='Booked'
        ).first()

        if existing_appointment:
            flash('This time slot is already booked!', 'error')
            return redirect(url_for('patient.book_appointment'))

        doctor_availability = DoctorAvailability.query.filter_by(
            doctor_id=doctor_id,
            date=appt_date,
            is_available=True
        ).first()

        if not doctor_availability:
            flash('Doctor is not available on this date!', 'error')
            return redirect(url_for('patient.book_appointment'))

        if not (doctor_availability.start_time <= appt_time <= doctor_availability.end_time):
            flash('Selected time is outside doctor\'s available hours!', 'error')
            return redirect(url_for('patient.book_appointment'))

        appointment = Appointment(
            patient_id=current_user.id,
            doctor_id=doctor_id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            reason=reason,
            status='Booked'
        )

        db.session.add(appointment)
        db.session.commit()

        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('patient.appointments'))

    # GET: show booking form with dynamic options
    departments = Department.query.all()
    selected_department = request.args.get('department', '')
    selected_doctor = request.args.get('doctor', '')
    selected_date = request.args.get('date', '')

    doctors = []
    available_dates = []
    available_times = []

    # Step 1: load doctors for selected department
    if selected_department:
        doctors = Doctor.query.filter_by(
            department_id=int(selected_department),
            is_available=True
        ).all()

    # Step 2: load available dates for selected doctor (next 7 days)
    if selected_doctor:
        start_date = date.today()
        end_date = start_date + timedelta(days=7)

        availabilities = DoctorAvailability.query.filter(
            and_(DoctorAvailability.doctor_id == int(selected_doctor),
                 DoctorAvailability.date >= start_date,
                 DoctorAvailability.date <= end_date,
                 DoctorAvailability.is_available == True)
        ).order_by(DoctorAvailability.date).all()

        available_dates = list(
            set((avail.date, avail.date.strftime('%Y-%m-%d')) for avail in availabilities)
        )
        available_dates.sort()

        # If no date is selected yet but we have available dates, default to first one
        if available_dates and not selected_date:
            selected_date = available_dates[0][1]

    # Step 3: generate available time slots for selected date + doctor
    if selected_doctor and selected_date:
        try:
            selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

            doctor_availability = DoctorAvailability.query.filter_by(
                doctor_id=int(selected_doctor),
                date=selected_date_obj,
                is_available=True
            ).first()

            if doctor_availability:
                booked_appointments = Appointment.query.filter_by(
                    doctor_id=int(selected_doctor),
                    appointment_date=selected_date_obj,
                    status='Booked'
                ).all()

                booked_times = [appt.appointment_time for appt in booked_appointments]

                current_time = doctor_availability.start_time
                while current_time <= doctor_availability.end_time:
                    if current_time not in booked_times:
                        available_times.append(current_time.strftime('%H:%M'))

                    minutes = current_time.hour * 60 + current_time.minute
                    minutes += 30
                    if minutes < 24 * 60:
                        current_time = time(minutes // 60, minutes % 60)
                    else:
                        break
        except ValueError:
            pass

    return render_template(
        'patient/book_appointment.html',
        departments=departments,
        doctors=doctors,
        available_dates=available_dates,
        available_times=available_times,
        selected_department=selected_department,
        selected_doctor=selected_doctor,
        selected_date=selected_date
    )


@patient.route('/appointments')
@login_required
@patient_required
def appointments():
    appointments = Appointment.query.filter_by(
        patient_id=current_user.id
    ).order_by(Appointment.appointment_date.desc()).all()

    return render_template('patient/appointments.html', appointments=appointments)


@patient.route('/cancel-appointment/<int:appointment_id>')
@login_required
@patient_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        patient_id=current_user.id
    ).first_or_404()

    if appointment.status != 'Booked':
        flash('Can only cancel booked appointments!', 'error')
    else:
        appointment.status = 'Cancelled'
        db.session.commit()
        flash('Appointment cancelled successfully!', 'info')

    return redirect(url_for('patient.appointments'))


@patient.route('/profile', methods=['GET', 'POST'])
@login_required
@patient_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.email = request.form.get('email')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        current_user.blood_group = request.form.get('blood_group')
        current_user.emergency_contact = request.form.get('emergency_contact')

        date_of_birth = request.form.get('date_of_birth')
        if date_of_birth:
            current_user.date_of_birth = datetime.strptime(
                date_of_birth, '%Y-%m-%d'
            ).date()

        current_user.gender = request.form.get('gender')
        current_user.medical_history = request.form.get('medical_history')

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('patient.profile'))

    return render_template('patient/profile.html')


@patient.route('/treatment-history')
@login_required
@patient_required
def treatment_history():
    appointments = db.session.query(Appointment).join(Treatment).filter(
        Appointment.patient_id == current_user.id,
        Appointment.status == 'Completed'
    ).order_by(Appointment.appointment_date.desc()).all()

    return render_template('patient/treatment_history.html', appointments=appointments)
