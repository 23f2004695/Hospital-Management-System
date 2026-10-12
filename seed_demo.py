"""Fill the database with demo doctors, patients, availability and visits.

    python seed_demo.py

Every demo doctor and patient uses the password "demo123". Safe to run more than once.
"""
from datetime import date, time, timedelta

from app import create_app, db
from app.models import Doctor, Patient, Department, DoctorAvailability, Appointment, Treatment

PASSWORD = 'demo123'

DOCTORS = [
    # username, name, department, qualification, years, fee
    ('dr.mehta', 'Anika Mehta', 'Cardiology', 'MBBS, MD, DM (Cardiology)', 12, 900),
    ('dr.sharma', 'Rohan Sharma', 'Orthopedics', 'MBBS, MS (Ortho)', 8, 700),
    ('dr.iyer', 'Kavya Iyer', 'Pediatrics', 'MBBS, DCH', 6, 500),
    ('dr.khan', 'Imran Khan', 'Dermatology', 'MBBS, MD (Dermatology)', 10, 600),
    ('dr.gill', 'Harpreet Gill', 'General Medicine', 'MBBS, MD (Medicine)', 15, 400),
    ('dr.nair', 'Arjun Nair', 'Neurology', 'MBBS, DM (Neurology)', 9, 1000),
]

PATIENTS = [
    # username, name, gender, blood group, date of birth
    ('rahul', 'Rahul Verma', 'Male', 'B+', date(1994, 3, 12)),
    ('sneha', 'Sneha Kapoor', 'Female', 'O+', date(1999, 7, 25)),
    ('amit', 'Amit Joshi', 'Male', 'A-', date(1987, 11, 2)),
    ('priya', 'Priya Das', 'Female', 'AB+', date(2001, 1, 18)),
]

PAST_VISITS = [
    # patient, doctor, days ago, diagnosis, prescription
    ('rahul', 'dr.gill', 20, 'Viral fever', 'Paracetamol 650mg twice a day for 3 days, plenty of fluids'),
    ('rahul', 'dr.mehta', 9, 'Mild hypertension', 'Amlodipine 5mg once daily, reduce salt intake'),
    ('sneha', 'dr.khan', 14, 'Contact dermatitis', 'Hydrocortisone cream 1% twice daily for a week'),
    ('amit', 'dr.sharma', 6, 'Grade 1 ankle sprain', 'Rest, ice, compression. Ibuprofen 400mg if needed'),
    ('priya', 'dr.nair', 3, 'Tension-type headache', 'Regular sleep, screen breaks, Naproxen 250mg if needed'),
]

UPCOMING = [
    # patient, doctor, days ahead, time, reason
    ('rahul', 'dr.mehta', 1, time(10, 0), 'Blood pressure follow-up'),
    ('sneha', 'dr.iyer', 2, time(11, 30), 'Vaccination schedule for my nephew'),
    ('amit', 'dr.sharma', 3, time(15, 0), 'Ankle still swells after running'),
    ('priya', 'dr.gill', 1, time(16, 30), 'Annual check-up'),
]


def phone_for(username):
    return '98' + str(sum(ord(c) * 7919 for c in username) % 10**8).zfill(8)


def seed():
    today = date.today()

    doctors = {}
    for i, (username, name, dept_name, qual, years, fee) in enumerate(DOCTORS, start=1):
        doctor = Doctor.query.filter_by(username=username).first()
        if not doctor:
            dept = Department.query.filter_by(name=dept_name).first()
            doctor = Doctor(username=username, email=f'{username}@example.com', password=PASSWORD,
                            full_name=name, phone=phone_for(username), license_number=f'MCI-{2010 + i}-{4321 + i}',
                            department_id=dept.id, qualification=qual, experience_years=years,
                            consultation_fee=fee)
            db.session.add(doctor)
            db.session.flush()
        doctors[username] = doctor

    patients = {}
    for username, name, gender, blood, dob in PATIENTS:
        patient = Patient.query.filter_by(username=username).first()
        if not patient:
            patient = Patient(username=username, email=f'{username}@example.com', password=PASSWORD,
                              full_name=name, phone=phone_for(username), gender=gender, blood_group=blood,
                              date_of_birth=dob, address='Chennai, Tamil Nadu')
            db.session.add(patient)
            db.session.flush()
        patients[username] = patient

    # Every doctor works 09:00-17:00 for the next week, except Sundays
    for doctor in doctors.values():
        for offset in range(7):
            day = today + timedelta(days=offset)
            if day.weekday() == 6:
                continue
            if not DoctorAvailability.query.filter_by(doctor_id=doctor.id, date=day).first():
                db.session.add(DoctorAvailability(doctor_id=doctor.id, date=day, start_time=time(9), end_time=time(17)))

    for p, d, days_ago, diagnosis, prescription in PAST_VISITS:
        day = today - timedelta(days=days_ago)
        if Appointment.query.filter_by(patient_id=patients[p].id, doctor_id=doctors[d].id, appointment_date=day).first():
            continue
        appt = Appointment(patient_id=patients[p].id, doctor_id=doctors[d].id, appointment_date=day,
                           appointment_time=time(10, 30), status='Completed', reason='Consultation')
        db.session.add(appt)
        db.session.flush()
        db.session.add(Treatment(appointment_id=appt.id, diagnosis=diagnosis, prescription=prescription,
                                 treatment_notes='Advised to come back if symptoms persist.'))

    for p, d, days_ahead, at, reason in UPCOMING:
        day = today + timedelta(days=days_ahead)
        if day.weekday() == 6:
            day += timedelta(days=1)
        if not Appointment.query.filter_by(doctor_id=doctors[d].id, appointment_date=day, appointment_time=at).first():
            db.session.add(Appointment(patient_id=patients[p].id, doctor_id=doctors[d].id, appointment_date=day,
                                       appointment_time=at, status='Booked', reason=reason))

    db.session.commit()
    print(f'Demo data ready. Doctors and patients below all use the password "{PASSWORD}":')
    print('  doctors :', ', '.join(doctors))
    print('  patients:', ', '.join(patients))


if __name__ == '__main__':
    with create_app().app_context():
        seed()
