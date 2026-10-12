from datetime import date, time, timedelta

from app import db
from app.models import Appointment, Doctor, DoctorAvailability, Treatment
from conftest import TOMORROW


def test_complete_without_diagnosis_shows_error_instead_of_crashing(app, make, login):
    doctor_id = make.doctor()
    appt_id = make.appointment(make.patient(), doctor_id)
    res = login('drx', 'doctor').post(f'/doctor/complete-appointment/{appt_id}', data={}, follow_redirects=True)
    assert res.status_code == 200
    assert b'Diagnosis is required' in res.data
    with app.app_context():
        assert db.session.get(Appointment, appt_id).status == 'Booked'


def test_complete_records_treatment_once(app, make, login):
    doctor_id = make.doctor()
    appt_id = make.appointment(make.patient(), doctor_id)
    client = login('drx', 'doctor')
    data = {'diagnosis': 'Flu', 'prescription': 'Rest',
            'follow_up_date': (TOMORROW + timedelta(days=7)).isoformat()}
    client.post(f'/doctor/complete-appointment/{appt_id}', data=data)
    res = client.post(f'/doctor/complete-appointment/{appt_id}', data=data, follow_redirects=True)
    assert b'already completed' in res.data
    with app.app_context():
        assert Treatment.query.count() == 1
        t = Treatment.query.first()
        assert t.follow_up_required is True
        assert db.session.get(Appointment, appt_id).status == 'Completed'


def test_follow_up_must_be_after_the_visit(app, make, login):
    doctor_id = make.doctor()
    appt_id = make.appointment(make.patient(), doctor_id)
    res = login('drx', 'doctor').post(f'/doctor/complete-appointment/{appt_id}', data={
        'diagnosis': 'Flu', 'follow_up_date': TOMORROW.isoformat()}, follow_redirects=True)
    assert b'must be after' in res.data


def test_doctor_cannot_cancel_completed_appointment(app, make, login):
    doctor_id = make.doctor()
    appt_id = make.appointment(make.patient(), doctor_id, status='Completed')
    login('drx', 'doctor').post(f'/doctor/cancel-appointment/{appt_id}')
    with app.app_context():
        assert db.session.get(Appointment, appt_id).status == 'Completed'


def test_doctor_only_sees_history_of_own_patients(make, login):
    doctor_id = make.doctor('drx')
    make.doctor('dry')
    alice_id = make.patient('alice')
    make.appointment(alice_id, doctor_id)
    assert login('drx', 'doctor').get(f'/doctor/patient-history/{alice_id}').status_code == 200
    assert login('dry', 'doctor').get(f'/doctor/patient-history/{alice_id}').status_code == 403


def test_doctor_cannot_open_another_doctors_appointment(make, login):
    doctor_id = make.doctor('drx')
    make.doctor('dry')
    appt_id = make.appointment(make.patient(), doctor_id)
    assert login('dry', 'doctor').get(f'/doctor/appointment/{appt_id}').status_code == 404


def test_availability_rejects_end_before_start(app, make, login):
    make.doctor(available_on=None)
    key = TOMORROW.isoformat()
    res = login('drx', 'doctor').post('/doctor/availability', data={
        f'available_{key}': 'on', f'start_{key}': '17:00', f'end_{key}': '09:00'}, follow_redirects=True)
    assert b'end time must be after' in res.data
    with app.app_context():
        assert DoctorAvailability.query.count() == 0


def test_availability_saves_and_keeps_days_outside_the_window(app, make, login):
    doctor_id = make.doctor(available_on=None)
    day_eight = date.today() + timedelta(days=7)
    with app.app_context():
        db.session.add(DoctorAvailability(doctor_id=doctor_id, date=day_eight, start_time=time(9), end_time=time(10)))
        db.session.commit()

    key = TOMORROW.isoformat()
    login('drx', 'doctor').post('/doctor/availability', data={
        f'available_{key}': 'on', f'start_{key}': '10:00', f'end_{key}': '14:00'})
    with app.app_context():
        dates = sorted(a.date for a in DoctorAvailability.query.all())
    assert dates == [TOMORROW, day_eight]


def test_admin_add_doctor_validates(app, admin):
    base = {'username': 'drnew', 'password': 'secret123', 'full_name': 'Dr New', 'email': 'new@example.com',
            'phone': '9876543210', 'license_number': 'L-1', 'department_id': '1'}
    assert b'choose a department' in admin.post('/admin/add-doctor', data={**base, 'department_id': ''}).data
    assert b'must be a number' in admin.post('/admin/add-doctor', data={**base, 'experience_years': 'ten'}).data
    assert admin.post('/admin/add-doctor', data=base).status_code == 302
    res = admin.post('/admin/add-doctor', data={**base, 'username': 'other', 'email': 'o@example.com'})
    assert b'license number' in res.data
    with app.app_context():
        assert Doctor.query.count() == 1


def test_admin_edit_doctor_validates(app, make, admin):
    make.doctor('drx')
    make.doctor('dry')
    data = {'full_name': 'Dr X', 'email': 'dry@example.com', 'phone': '9876543210', 'license_number': 'LIC-drx',
            'department_id': '2', 'experience_years': '5', 'consultation_fee': '700'}
    assert b'Email already exists' in admin.post('/admin/edit-doctor/1', data=data).data
    assert admin.post('/admin/edit-doctor/1', data={**data, 'email': 'drx@example.com'}).status_code == 302
    with app.app_context():
        d = db.session.get(Doctor, 1)
        assert (d.department_id, d.experience_years, d.consultation_fee, d.is_available) == (2, 5, 700.0, False)


def test_admin_delete_doctor(app, make, admin):
    busy = make.doctor('busy')
    free = make.doctor('free')
    make.appointment(make.patient(), busy)

    assert admin.get(f'/admin/delete-doctor/{free}').status_code == 405
    admin.post(f'/admin/delete-doctor/{busy}')
    admin.post(f'/admin/delete-doctor/{free}')
    with app.app_context():
        assert [d.username for d in Doctor.query.all()] == ['busy']
        assert DoctorAvailability.query.count() == 1  # the deleted doctor's slots went with them


def test_admin_search_and_patient_history(make, admin):
    alice_id = make.patient('alice')
    make.patient('bob')
    assert 'Alice' in admin.get(f'/admin/manage-patients?search={alice_id}').get_data(as_text=True)
    page = admin.get('/admin/manage-patients?search=ali').get_data(as_text=True)
    assert 'Alice' in page and 'Bob' not in page
    assert admin.get(f'/admin/patient/{alice_id}').status_code == 200


def test_admin_dashboard_counts(make, admin):
    doctor_id = make.doctor()
    make.appointment(make.patient(), doctor_id, day=date.today(), at=time(23, 30))
    page = admin.get('/admin/dashboard').get_data(as_text=True)
    assert "Today&#39;s appointments" in page or "Today's appointments" in page
