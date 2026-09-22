from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from complaints.models import AcademicClass, UserProfile, ComplaintCategory, Complaint, ComplaintResponse, ComplaintStatusHistory


class Command(BaseCommand):
    help = 'Seeds database with College Hierarchy (Student -> Class Mentor -> HOD), classes, demo users, and complaints.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Seeding Complaint Management System: Student -> Class Mentor -> HOD hierarchy..."))

        # 1. System Administrator
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'System',
                'last_name': 'Administrator',
                'email': 'admin@institution.edu',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('admin12345')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        admin_profile, _ = UserProfile.objects.get_or_create(user=admin_user)
        admin_profile.role = 'ADMIN'
        admin_profile.department = 'Central IT'
        admin_profile.phone = '+1 555-0100'
        admin_profile.save()

        # 2. HOD - Head of Department
        hod_user, _ = User.objects.get_or_create(
            username='hod_cs',
            defaults={
                'first_name': 'Prof. Rajesh',
                'last_name': 'Menon',
                'email': 'hod.cs@institution.edu',
                'is_staff': True,
                'is_superuser': False,
            }
        )
        hod_user.set_password('hod12345')
        hod_user.is_staff = True
        hod_user.save()
        hod_profile, _ = UserProfile.objects.get_or_create(user=hod_user)
        hod_profile.role = 'HOD'
        hod_profile.department = 'Computer Science & Engineering'
        hod_profile.phone = '+1 555-0120'
        hod_profile.save()

        # 3. Class Mentor 1: John (Mentors BCA S3)
        mentor_john, _ = User.objects.get_or_create(
            username='mentor_john',
            defaults={
                'first_name': 'John',
                'last_name': 'Mathews',
                'email': 'john.mentor@institution.edu',
                'is_staff': True,
                'is_superuser': False,
            }
        )
        mentor_john.set_password('mentor12345')
        mentor_john.is_staff = True
        mentor_john.save()
        john_profile, _ = UserProfile.objects.get_or_create(user=mentor_john)
        john_profile.role = 'CLASS_MENTOR'
        john_profile.department = 'Computer Applications'
        john_profile.phone = '+1 555-0131'
        john_profile.save()

        # 4. Class Mentor 2: Sarah (Mentors B.Tech CSE S5)
        mentor_sarah, _ = User.objects.get_or_create(
            username='mentor_sarah',
            defaults={
                'first_name': 'Dr. Sarah',
                'last_name': 'Jenkins',
                'email': 'sarah.mentor@institution.edu',
                'is_staff': True,
                'is_superuser': False,
            }
        )
        mentor_sarah.set_password('mentor12345')
        mentor_sarah.is_staff = True
        mentor_sarah.save()
        sarah_profile, _ = UserProfile.objects.get_or_create(user=mentor_sarah)
        sarah_profile.role = 'CLASS_MENTOR'
        sarah_profile.department = 'Computer Science & Engineering'
        sarah_profile.phone = '+1 555-0132'
        sarah_profile.save()

        # 5. Academic Classes
        class_bca, _ = AcademicClass.objects.get_or_create(
            name='BCA S3',
            defaults={
                'department': 'Computer Applications',
                'mentor': mentor_john
            }
        )
        class_bca.mentor = mentor_john
        class_bca.department = 'Computer Applications'
        class_bca.save()

        class_cse, _ = AcademicClass.objects.get_or_create(
            name='B.Tech CSE S5',
            defaults={
                'department': 'Computer Science & Engineering',
                'mentor': mentor_sarah
            }
        )
        class_cse.mentor = mentor_sarah
        class_cse.department = 'Computer Science & Engineering'
        class_cse.save()

        # 6. Students
        # Student A (BCA S3)
        student_a, _ = User.objects.get_or_create(
            username='student_a',
            defaults={
                'first_name': 'Rahul',
                'last_name': 'Nair',
                'email': 'student.a@institution.edu',
                'is_staff': False,
                'is_superuser': False,
            }
        )
        student_a.set_password('student12345')
        student_a.save()
        profile_a, _ = UserProfile.objects.get_or_create(user=student_a)
        profile_a.role = 'STUDENT'
        profile_a.academic_class = class_bca
        profile_a.department = class_bca.department
        profile_a.save()

        # Student B (BCA S3)
        student_b, _ = User.objects.get_or_create(
            username='student_b',
            defaults={
                'first_name': 'Ananya',
                'last_name': 'Sharma',
                'email': 'student.b@institution.edu',
                'is_staff': False,
                'is_superuser': False,
            }
        )
        student_b.set_password('student12345')
        student_b.save()
        profile_b, _ = UserProfile.objects.get_or_create(user=student_b)
        profile_b.role = 'STUDENT'
        profile_b.academic_class = class_bca
        profile_b.department = class_bca.department
        profile_b.save()

        # Student C (B.Tech CSE S5)
        student_c, _ = User.objects.get_or_create(
            username='student_c',
            defaults={
                'first_name': 'Kavya',
                'last_name': 'Pillai',
                'email': 'student.c@institution.edu',
                'is_staff': False,
                'is_superuser': False,
            }
        )
        student_c.set_password('student12345')
        student_c.save()
        profile_c, _ = UserProfile.objects.get_or_create(user=student_c)
        profile_c.role = 'STUDENT'
        profile_c.academic_class = class_cse
        profile_c.department = class_cse.department
        profile_c.save()

        # 7. Categories
        categories_data = [
            ('Academic & Curriculum', 'Issues relating to syllabus, lectures, faculty guidance, and lab sessions.'),
            ('Laboratory Equipment', 'Hardware malfunction, computer systems, oscilloscopes, and lab safety.'),
            ('Hostel & Accommodation', 'Room maintenance, hot water, electrical supply, and cleanliness.'),
            ('Internet & WiFi', 'Campus WiFi signal coverage, high-speed access, and student portal connectivity.'),
            ('Canteen & Food Quality', 'Hygiene standards, drinking water, and meal service concerns.'),
            ('Transport & Bus Service', 'College bus schedules, bus passes, and route coverage.'),
            ('Administration & Fees', 'Tuition payments, scholarship verifications, and ID cards.'),
        ]

        cat_objs = {}
        for name, desc in categories_data:
            cat, _ = ComplaintCategory.objects.get_or_create(
                name=name,
                defaults={'description': desc, 'is_active': True}
            )
            cat_objs[name] = cat

        now = timezone.now()

        # 8. Seed Sample Complaints Demonstrating Hierarchy & Scoping
        # Complaint 1: student_a (BCA S3) -> Auto assigned to mentor_john (Submitted, Mentor Level)
        c1 = Complaint.objects.filter(title='WiFi router in Lab 3 keeps dropping connectivity').first()
        if not c1:
            c1 = Complaint.objects.create(
                user=student_a,
                category=cat_objs['Internet & WiFi'],
                title='WiFi router in Lab 3 keeps dropping connectivity',
                description='During practical coding sessions, the wireless access point in Lab 3 disconnects every 10 minutes.',
                priority='MEDIUM',
                status='SUBMITTED',
                current_level='MENTOR',
                assigned_to=mentor_john
            )
            ComplaintStatusHistory.objects.create(
                complaint=c1,
                old_status='NONE',
                new_status='SUBMITTED',
                changed_by=student_a,
                comment='Complaint submitted by student Rahul (BCA S3). Auto-assigned to Class Mentor John.',
                created_at=now - timedelta(hours=5)
            )

        # Complaint 2: student_b (BCA S3) -> Escalated by mentor_john to HOD
        c2 = Complaint.objects.filter(title='Digital Electronics trainer kits not functional in hardware lab').first()
        if not c2:
            c2 = Complaint.objects.create(
                user=student_b,
                category=cat_objs['Laboratory Equipment'],
                title='Digital Electronics trainer kits not functional in hardware lab',
                description='Five trainer kits have broken IC sockets and power supplies. IC logic testing cannot be conducted.',
                priority='HIGH',
                status='ESCALATED_HOD',
                current_level='HOD',
                assigned_to=hod_user
            )
            ComplaintStatusHistory.objects.create(
                complaint=c2,
                old_status='NONE',
                new_status='SUBMITTED',
                changed_by=student_b,
                comment='Submitted by student Ananya (BCA S3). Auto-assigned to Class Mentor John.',
                created_at=now - timedelta(days=2)
            )
            ComplaintStatusHistory.objects.create(
                complaint=c2,
                old_status='SUBMITTED',
                new_status='UNDER_REVIEW',
                changed_by=mentor_john,
                comment='Mentor John inspected hardware lab setup and confirmed kit failure.',
                created_at=now - timedelta(days=1, hours=18)
            )
            ComplaintResponse.objects.create(
                complaint=c2,
                responder=mentor_john,
                message='I have inspected the trainer kits. Since component replacement requires departmental budget approval, I am escalating this ticket directly to HOD.',
                created_at=now - timedelta(days=1, hours=10)
            )
            ComplaintStatusHistory.objects.create(
                complaint=c2,
                old_status='UNDER_REVIEW',
                new_status='ESCALATED_HOD',
                changed_by=mentor_john,
                comment='ESCALATION TO HOD: Requires departmental lab equipment replacement budget approval from HOD.',
                created_at=now - timedelta(days=1)
            )

        # Complaint 3: student_c (B.Tech CSE S5) -> Mentor Sarah reviewing (In Progress)
        c3 = Complaint.objects.filter(title='Projector not displaying HDMI signal in Room 302').first()
        if not c3:
            c3 = Complaint.objects.create(
                user=student_c,
                category=cat_objs['Academic & Curriculum'],
                title='Projector not displaying HDMI signal in Room 302',
                description='The ceiling mounted projector shows no signal error when connected to faculty or student laptops via HDMI cable.',
                priority='LOW',
                status='IN_PROGRESS',
                current_level='MENTOR',
                assigned_to=mentor_sarah
            )
            ComplaintStatusHistory.objects.create(
                complaint=c3,
                old_status='NONE',
                new_status='SUBMITTED',
                changed_by=student_c,
                comment='Submitted by Kavya (B.Tech CSE S5). Auto-assigned to Class Mentor Dr. Sarah.',
                created_at=now - timedelta(days=1)
            )
            ComplaintStatusHistory.objects.create(
                complaint=c3,
                old_status='SUBMITTED',
                new_status='IN_PROGRESS',
                changed_by=mentor_sarah,
                comment='Mentor Sarah logged service call with AV maintenance technician.',
                created_at=now - timedelta(hours=3)
            )

        # Complaint 4: student_a (BCA S3) -> Resolved by mentor_john
        c4 = Complaint.objects.filter(title='Library ID card barcode not scanning at gate').first()
        if not c4:
            c4 = Complaint.objects.create(
                user=student_a,
                category=cat_objs['Administration & Fees'],
                title='Library ID card barcode not scanning at gate',
                description='The laminated barcode on my ID card has smudged ink and cannot be read by the optical turnstile scanner.',
                priority='LOW',
                status='RESOLVED',
                current_level='MENTOR',
                assigned_to=mentor_john,
                resolved_at=now - timedelta(hours=2)
            )
            ComplaintStatusHistory.objects.create(
                complaint=c4,
                old_status='NONE',
                new_status='SUBMITTED',
                changed_by=student_a,
                comment='Submitted by student Rahul (BCA S3).',
                created_at=now - timedelta(days=3)
            )
            ComplaintStatusHistory.objects.create(
                complaint=c4,
                old_status='SUBMITTED',
                new_status='RESOLVED',
                changed_by=mentor_john,
                comment='Issued replacement barcode sticker from administration desk. Tested and verified at library gate.',
                created_at=now - timedelta(hours=2)
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded Student -> Class Mentor -> HOD hierarchy!"))
        self.stdout.write(self.style.SUCCESS("=================================================================="))
        self.stdout.write(self.style.SUCCESS("DEMO ACCOUNTS:"))
        self.stdout.write(self.style.SUCCESS("1. STUDENT A (BCA S3):     username: student_a    | password: student12345"))
        self.stdout.write(self.style.SUCCESS("2. STUDENT B (BCA S3):     username: student_b    | password: student12345"))
        self.stdout.write(self.style.SUCCESS("3. STUDENT C (CSE S5):     username: student_c    | password: student12345"))
        self.stdout.write(self.style.SUCCESS("4. CLASS MENTOR (BCA S3):  username: mentor_john  | password: mentor12345"))
        self.stdout.write(self.style.SUCCESS("5. CLASS MENTOR (CSE S5):  username: mentor_sarah | password: mentor12345"))
        self.stdout.write(self.style.SUCCESS("6. HOD (CSE / Dept):       username: hod_cs       | password: hod12345"))
        self.stdout.write(self.style.SUCCESS("7. ADMINISTRATOR:          username: admin        | password: admin12345"))
        self.stdout.write(self.style.SUCCESS("=================================================================="))
