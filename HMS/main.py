from app import create_app, db
from app.models import Admin, Doctor, Patient, Department, Appointment, Treatment

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Create all database tables
        db.create_all()

        # Create default admin if not exists
        if not Admin.query.first():
            admin = Admin(
                username='admin',
                email='admin@hospital.com', 
                password='admin123',
                full_name='Hospital Administrator',
                phone='1234567890'
            )
            db.session.add(admin)

            # Create default departments
            departments = [
                ('Cardiology', 'Heart and cardiovascular system care'),
                ('Neurology', 'Brain and nervous system disorders'),
                ('Oncology', 'Cancer treatment and care'),
                ('Pediatrics', 'Medical care for children'),
                ('Orthopedics', 'Bone and muscle disorders'),
                ('Dermatology', 'Skin and related conditions'),
                ('General Medicine', 'General health and wellness'),
                ('Emergency', 'Emergency medical services')
            ]

            for dept_name, description in departments:
                dept = Department(name=dept_name, description=description)
                db.session.add(dept)

            db.session.commit()
            print("✅ Database initialized with default admin and departments!")

    app.run(debug=True, host='0.0.0.0', port=5001)
