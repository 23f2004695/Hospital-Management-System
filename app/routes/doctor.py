from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user
from sqlalchemy import and_

from app import db
from app.models import Patient, Appointment, Treatment, DoctorAvailability
from app.utils import FormError, role_required, field, date_field, time_field

doctor = Blueprint('doctor', __name__)
doctor_required = role_required('doctor')

AVAILABILITY_DAYS = 7


def _my_appointment(appointment_id):
    return Appointment.query.filter_by(id=appointment_id, doctor_id=current_user.id).first_or_404()


@doctor.route('/dashboard')
@doctor_required
def dashboard():
    today = date.today()
    today_appointments = Appointment.query.filter_by(doctor_id=current_user.id, appointment_date=today)\
        .order_by(Appointment.appointment_time).all()

    week_start = today - timedelta(days=today.weekday())
    week_appointments = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_date >= week_start,
        Appointment.appointment_date <= week_start + timedelta(days=6),
        Appointment.status != 'Cancelled',
    ).count()

    upcoming = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_date > today,
        Appointment.status == 'Booked',
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).limit(5).all()

    patient_count = db.session.query(Appointment.patient_id).filter_by(doctor_id=current_user.id).distinct().count()

    return render_template('doctor/dashboard.html',
                           today_appointments=today_appointments,
                           week_appointments=week_appointments,
                           upcoming=upcoming,
                           patient_count=patient_count)


@doctor.route('/appointments')
@doctor_required
def appointments():
    status_filter = request.args.get('status', '')
    date_filter = request.args.get('date', '')
    query = Appointment.query.filter_by(doctor_id=current_user.id)

    if status_filter in ('Booked', 'Completed', 'Cancelled'):
        query = query.filter_by(status=status_filter)
    if date_filter:
        try:
            query = query.filter_by(appointment_date=datetime.strptime(date_filter, '%Y-%m-%d').date())
        except ValueError:
            flash('That date filter is not valid.', 'error')

    appointments = query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    return render_template('doctor/appointments.html', appointments=appointments)


@doctor.route('/appointment/<int:appointment_id>')
@doctor_required
def appointment_detail(appointment_id):
    appointment = _my_appointment(appointment_id)
    return render_template('doctor/appointment_detail.html', appointment=appointment,
                           follow_up_min=appointment.appointment_date + timedelta(days=1))


@doctor.route('/complete-appointment/<int:appointment_id>', methods=['POST'])
@doctor_required
def complete_appointment(appointment_id):
    appointment = _my_appointment(appointment_id)
    if appointment.status != 'Booked':
        flash(f'This appointment is already {appointment.status.lower()}.', 'error')
        return redirect(url_for('doctor.appointment_detail', appointment_id=appointment.id))

    try:
        diagnosis = field(request.form, 'diagnosis', max_len=2000)
        prescription = field(request.form, 'prescription', required=False, max_len=2000)
        notes = field(request.form, 'treatment_notes', 'Treatment notes', required=False, max_len=2000)
        follow_up_required = 'follow_up_required' in request.form
        follow_up_date = date_field(request.form.get('follow_up_date'), 'Follow-up date', required=False)
        if follow_up_date and follow_up_date <= appointment.appointment_date:
            raise FormError('Follow-up date must be after the appointment.')
        if follow_up_date:
            follow_up_required = True
    except FormError as e:
        flash(str(e), 'error')
        return redirect(url_for('doctor.appointment_detail', appointment_id=appointment.id))

    db.session.add(Treatment(
        appointment_id=appointment.id,
        diagnosis=diagnosis,
        prescription=prescription,
        treatment_notes=notes,
        follow_up_required=follow_up_required,
        follow_up_date=follow_up_date,
    ))
    appointment.status = 'Completed'
    db.session.commit()

    flash('Appointment completed and treatment recorded!', 'success')
    return redirect(url_for('doctor.appointments'))


@doctor.route('/cancel-appointment/<int:appointment_id>', methods=['POST'])
@doctor_required
def cancel_appointment(appointment_id):
    appointment = _my_appointment(appointment_id)
    if appointment.status != 'Booked':
        flash(f'This appointment is already {appointment.status.lower()}.', 'error')
    else:
        appointment.status = 'Cancelled'
        db.session.commit()
        flash('Appointment cancelled!', 'info')
    return redirect(url_for('doctor.appointments'))


@doctor.route('/patient-history/<int:patient_id>')
@doctor_required
def patient_history(patient_id):
    patient = db.get_or_404(Patient, patient_id)

    # Doctors can only open the records of patients who have booked with them
    if not Appointment.query.filter_by(patient_id=patient.id, doctor_id=current_user.id).first():
        abort(403)

    appointments = Appointment.query.filter_by(patient_id=patient.id)\
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    return render_template('patient_history.html', patient=patient, appointments=appointments,
                           back_url=url_for('doctor.dashboard'))


def _next_days():
    today = date.today()
    return [today + timedelta(days=i) for i in range(AVAILABILITY_DAYS)]


@doctor.route('/availability', methods=['GET', 'POST'])
@doctor_required
def availability():
    days = _next_days()

    if request.method == 'POST':
        new_slots = []
        try:
            for day in days:
                key = day.isoformat()
                if f'available_{key}' not in request.form:
                    continue
                label = day.strftime('%A %d %b')
                start = time_field(request.form.get(f'start_{key}'), f'Start time for {label}')
                end = time_field(request.form.get(f'end_{key}'), f'End time for {label}')
                if end <= start:
                    raise FormError(f'On {label} the end time must be after the start time.')
                new_slots.append(DoctorAvailability(doctor_id=current_user.id, date=day,
                                                    start_time=start, end_time=end, is_available=True))
        except FormError as e:
            flash(str(e), 'error')
            return redirect(url_for('doctor.availability'))

        DoctorAvailability.query.filter(and_(
            DoctorAvailability.doctor_id == current_user.id,
            DoctorAvailability.date >= days[0],
            DoctorAvailability.date <= days[-1],
        )).delete()
        db.session.add_all(new_slots)
        db.session.commit()
        flash('Availability updated successfully!', 'success')
        return redirect(url_for('doctor.availability'))

    existing = {
        a.date: a for a in DoctorAvailability.query.filter(
            DoctorAvailability.doctor_id == current_user.id,
            DoctorAvailability.date >= days[0],
            DoctorAvailability.date <= days[-1],
        )
    }
    booked = {
        day: Appointment.query.filter_by(doctor_id=current_user.id, appointment_date=day, status='Booked').count()
        for day in days
    }
    return render_template('doctor/availability.html', days=days, existing=existing, booked=booked)
