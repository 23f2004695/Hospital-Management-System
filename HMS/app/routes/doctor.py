from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from app.models import Doctor, Patient, Appointment, Treatment, DoctorAvailability
from app import db
from datetime import datetime, date, timedelta, time
from sqlalchemy import and_

doctor = Blueprint('doctor', __name__)

def doctor_required(f):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or session.get('user_type') != 'doctor':
            flash('Doctor access required!', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@doctor.route('/dashboard')
@login_required
@doctor_required
def dashboard():
    today = date.today()
    today_appointments = Appointment.query.filter_by(
        doctor_id=current_user.id,
        appointment_date=today
    ).order_by(Appointment.appointment_time).all()

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_appointments = Appointment.query.filter(
        and_(Appointment.doctor_id == current_user.id,
             Appointment.appointment_date >= week_start,
             Appointment.appointment_date <= week_end)
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()

    patient_count = db.session.query(Appointment.patient_id).filter_by(doctor_id=current_user.id).distinct().count()

    return render_template('doctor/dashboard.html',
                         today_appointments=today_appointments,
                         week_appointments=week_appointments,
                         patient_count=patient_count)

@doctor.route('/appointments', methods=['GET', 'POST'])
@login_required
@doctor_required
def appointments():
    status_filter = request.args.get('status', '')
    date_filter = request.args.get('date', '')

    query = Appointment.query.filter_by(doctor_id=current_user.id)

    if status_filter:
        query = query.filter_by(status=status_filter)

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(appointment_date=filter_date)
        except ValueError:
            pass

    appointments = query.order_by(Appointment.appointment_date.desc()).all()
    return render_template('doctor/appointments.html', appointments=appointments)

@doctor.route('/appointment/<int:appointment_id>')
@login_required
@doctor_required
def appointment_detail(appointment_id):
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        doctor_id=current_user.id
    ).first_or_404()

    return render_template('doctor/appointment_detail.html', appointment=appointment)

@doctor.route('/complete-appointment/<int:appointment_id>', methods=['POST'])
@login_required
@doctor_required
def complete_appointment(appointment_id):
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        doctor_id=current_user.id
    ).first_or_404()

    diagnosis = request.form.get('diagnosis')
    prescription = request.form.get('prescription')
    treatment_notes = request.form.get('treatment_notes')
    follow_up_required = 'follow_up_required' in request.form
    follow_up_date = request.form.get('follow_up_date')

    appointment.status = 'Completed'

    treatment = Treatment(
        appointment_id=appointment.id,
        diagnosis=diagnosis,
        prescription=prescription,
        treatment_notes=treatment_notes,
        follow_up_required=follow_up_required
    )

    if follow_up_date:
        treatment.follow_up_date = datetime.strptime(follow_up_date, '%Y-%m-%d').date()

    db.session.add(treatment)
    db.session.commit()

    flash('Appointment completed and treatment recorded!', 'success')
    return redirect(url_for('doctor.appointments'))

@doctor.route('/cancel-appointment/<int:appointment_id>')
@login_required
@doctor_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        doctor_id=current_user.id
    ).first_or_404()

    appointment.status = 'Cancelled'
    db.session.commit()

    flash('Appointment cancelled!', 'info')
    return redirect(url_for('doctor.appointments'))

@doctor.route('/patient-history/<int:patient_id>')
@login_required
@doctor_required
def patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)

    appointments = Appointment.query.filter_by(
        patient_id=patient_id,
        doctor_id=current_user.id
    ).order_by(Appointment.appointment_date.desc()).all()

    return render_template('doctor/patient_history.html', 
                         patient=patient, 
                         appointments=appointments)

@doctor.route('/availability', methods=['GET', 'POST'])
@login_required
@doctor_required
def availability():
    if request.method == 'POST':
        start_date = date.today()
        end_date = start_date + timedelta(days=7)

        DoctorAvailability.query.filter(
            and_(DoctorAvailability.doctor_id == current_user.id,
                 DoctorAvailability.date >= start_date,
                 DoctorAvailability.date <= end_date)
        ).delete()

        for i in range(7):
            current_date = start_date + timedelta(days=i)
            day_name = current_date.strftime('%A').lower()

            is_available = f'{day_name}_available' in request.form

            if is_available:
                start_time_str = request.form.get(f'{day_name}_start')
                end_time_str = request.form.get(f'{day_name}_end')

                if start_time_str and end_time_str:
                    availability_obj = DoctorAvailability(
                        doctor_id=current_user.id,
                        date=current_date,
                        start_time=datetime.strptime(start_time_str, '%H:%M').time(),
                        end_time=datetime.strptime(end_time_str, '%H:%M').time(),
                        is_available=True
                    )
                    db.session.add(availability_obj)

        db.session.commit()
        flash('Availability updated successfully!', 'success')
        return redirect(url_for('doctor.availability'))

    start_date = date.today()
    end_date = start_date + timedelta(days=7)

    availability_list = DoctorAvailability.query.filter(
        and_(DoctorAvailability.doctor_id == current_user.id,
             DoctorAvailability.date >= start_date,
             DoctorAvailability.date <= end_date)
    ).all()

    availability_dict = {}
    for avail in availability_list:
        day_name = avail.date.strftime('%A').lower()
        availability_dict[day_name] = {
            'date': avail.date,
            'available': avail.is_available,
            'start_time': avail.start_time.strftime('%H:%M') if avail.start_time else '',
            'end_time': avail.end_time.strftime('%H:%M') if avail.end_time else ''
        }

    return render_template('doctor/availability.html', availability=availability_dict)
