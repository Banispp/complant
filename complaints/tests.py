from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import AcademicClass, UserProfile, ComplaintCategory, Complaint, ComplaintResponse, ComplaintStatusHistory


class ComplaintManagementSystemTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='AdminPassword123!',
            is_staff=True,
            is_superuser=True
        )
        self.admin_user.profile.role = 'ADMIN'
        self.admin_user.profile.save()

        # Class Mentor 1 (BCA S3)
        self.mentor_1 = User.objects.create_user(
            username='mentor_john',
            email='john@test.com',
            password='MentorPassword123!',
            is_staff=True
        )
        self.mentor_1.profile.role = 'CLASS_MENTOR'
        self.mentor_1.profile.department = 'Computer Applications'
        self.mentor_1.profile.save()

        # Class Mentor 2 (B.Tech CSE S5)
        self.mentor_2 = User.objects.create_user(
            username='mentor_sarah',
            email='sarah@test.com',
            password='MentorPassword123!',
            is_staff=True
        )
        self.mentor_2.profile.role = 'CLASS_MENTOR'
        self.mentor_2.profile.department = 'Computer Science'
        self.mentor_2.profile.save()

        # HOD User
        self.hod_user = User.objects.create_user(
            username='hod_test',
            email='hod@test.com',
            password='HodPassword123!',
            is_staff=True
        )
        self.hod_user.profile.role = 'HOD'
        self.hod_user.profile.department = 'Computer Applications'
        self.hod_user.profile.save()

        # Principal User
        self.principal_user = User.objects.create_user(
            username='principal_test',
            email='principal@test.com',
            password='PrincipalPassword123!',
            is_staff=True
        )
        self.principal_user.profile.role = 'PRINCIPAL'
        self.principal_user.profile.save()

        # Academic Classes
        self.class_bca = AcademicClass.objects.create(
            name='BCA S3',
            department='Computer Applications',
            mentor=self.mentor_1
        )
        self.class_cse = AcademicClass.objects.create(
            name='B.Tech CSE S5',
            department='Computer Science',
            mentor=self.mentor_2
        )

        # Student 1 (in BCA S3 -> mentored by mentor_1)
        self.student_1 = User.objects.create_user(
            username='student_one',
            email='student1@test.com',
            password='StudentPassword123!'
        )
        self.student_1.profile.role = 'STUDENT'
        self.student_1.profile.academic_class = self.class_bca
        self.student_1.profile.department = self.class_bca.department
        self.student_1.profile.save()

        # Student 2 (in B.Tech CSE S5 -> mentored by mentor_2)
        self.student_2 = User.objects.create_user(
            username='student_two',
            email='student2@test.com',
            password='StudentPassword123!'
        )
        self.student_2.profile.role = 'STUDENT'
        self.student_2.profile.academic_class = self.class_cse
        self.student_2.profile.department = self.class_cse.department
        self.student_2.profile.save()

        # Categories
        self.cat_active = ComplaintCategory.objects.create(name='Internet', description='Network issues', is_active=True)
        self.cat_inactive = ComplaintCategory.objects.create(name='Old Category', description='Decommissioned', is_active=False)

    # 1. User registration with AcademicClass
    def test_01_user_registration(self):
        url = reverse('register')
        data = {
            'first_name': 'New',
            'last_name': 'Student',
            'username': 'newstudent',
            'email': 'newstudent@test.com',
            'academic_class': self.class_bca.id,
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='newstudent')
        self.assertEqual(new_user.profile.role, 'STUDENT')
        self.assertEqual(new_user.profile.academic_class, self.class_bca)
        self.assertFalse(new_user.is_staff)

    # 2. Student login redirects to user_dashboard
    def test_02_student_login(self):
        login_url = reverse('login')
        response = self.client.post(login_url, {'username': 'student_one', 'password': 'StudentPassword123!'})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('user_dashboard'))

    # 3. Admin / Staff login redirects to admin_dashboard
    def test_03_admin_login(self):
        login_url = reverse('login')
        response = self.client.post(login_url, {'username': 'admin_test', 'password': 'AdminPassword123!'})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin_dashboard'))

    # 4. Student cannot access admin pages
    def test_04_student_cannot_access_admin_pages(self):
        self.client.login(username='student_one', password='StudentPassword123!')
        admin_urls = [
            reverse('admin_dashboard'),
            reverse('category_list'),
            reverse('category_create'),
            reverse('user_list'),
            reverse('reports'),
        ]
        for url in admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    # 5. Student can create complaint and it auto-assigns to their Class Mentor
    def test_05_student_create_complaint_auto_assigns_mentor(self):
        self.client.login(username='student_one', password='StudentPassword123!')
        url = reverse('complaint_create')
        data = {
            'category': self.cat_active.id,
            'title': 'Broken network switch in BCA lab',
            'description': 'The network switch in room 204 has completely failed and port lights are dark.'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        complaint = Complaint.objects.get(title='Broken network switch in BCA lab')
        self.assertEqual(complaint.user, self.student_1)
        self.assertEqual(complaint.current_level, 'MENTOR')
        self.assertEqual(complaint.status, 'SUBMITTED')
        # Student 1 is in BCA S3 -> assigned_to is automatically mentor_1
        self.assertEqual(complaint.assigned_to, self.mentor_1)

    # 6. Complaint automatically gets unique ID (e.g. CMP-00001)
    def test_06_complaint_automatically_gets_unique_id(self):
        c1 = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='Auto ID test 1',
            description='Detailed test description for unique id generator testing.'
        )
        c2 = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='Auto ID test 2',
            description='Detailed test description for unique id generator testing 2.'
        )
        self.assertTrue(c1.complaint_id.startswith('CMP-'))
        self.assertTrue(c2.complaint_id.startswith('CMP-'))
        self.assertNotEqual(c1.complaint_id, c2.complaint_id)

    # 7. Student can only view own complaints
    def test_07_student_can_only_view_own_complaints(self):
        c1 = Complaint.objects.create(user=self.student_1, category=self.cat_active, title='Student 1 only', description='Student 1 desc')
        c2 = Complaint.objects.create(user=self.student_2, category=self.cat_active, title='Student 2 only', description='Student 2 desc')

        self.client.login(username='student_one', password='StudentPassword123!')
        response = self.client.get(reverse('complaint_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, c1.complaint_id)
        self.assertNotContains(response, c2.complaint_id)

        # Accessing student 2's complaint directly via URL is 403 Forbidden
        detail_response = self.client.get(reverse('complaint_detail', kwargs={'complaint_id': c2.complaint_id}))
        self.assertEqual(detail_response.status_code, 403)

    # 8. Class Mentor ONLY sees complaints from students in their mentored class
    def test_08_class_mentor_isolation_by_class(self):
        # c1 belongs to student_1 in BCA S3 (mentored by mentor_1)
        c1 = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='BCA S3 Complaint',
            description='Issue in BCA lab'
        )
        # c2 belongs to student_2 in CSE S5 (mentored by mentor_2)
        c2 = Complaint.objects.create(
            user=self.student_2,
            category=self.cat_active,
            title='CSE S5 Complaint',
            description='Issue in CSE lab'
        )

        # Log in as mentor_1 (John - BCA S3)
        self.client.login(username='mentor_john', password='MentorPassword123!')
        response = self.client.get(reverse('complaint_list'))
        self.assertEqual(response.status_code, 200)
        # mentor_1 must see c1
        self.assertContains(response, c1.complaint_id)
        # mentor_1 must NOT see c2
        self.assertNotContains(response, c2.complaint_id)

        # mentor_1 attempting to view c2 directly via URL must get 403 Forbidden
        detail_resp = self.client.get(reverse('complaint_detail', kwargs={'complaint_id': c2.complaint_id}))
        self.assertEqual(detail_resp.status_code, 403)

        # mentor_1 attempting to escalate or update c2 directly must get 403 Forbidden
        update_resp = self.client.post(reverse('complaint_status_update', kwargs={'complaint_id': c2.complaint_id}), {'new_status': 'UNDER_REVIEW'})
        self.assertEqual(update_resp.status_code, 403)

    # 9. Class Mentor can update status and resolve complaints in their class
    def test_09_class_mentor_can_resolve_class_complaint(self):
        c = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='Class issue to resolve',
            description='Issue resolved by mentor',
            status='UNDER_REVIEW'
        )
        self.client.login(username='mentor_john', password='MentorPassword123!')
        url = reverse('complaint_status_update', kwargs={'complaint_id': c.complaint_id})
        response = self.client.post(url, {'new_status': 'RESOLVED', 'comment': 'Resolved by Class Mentor John.'})
        self.assertEqual(response.status_code, 302)

        c.refresh_from_db()
        self.assertEqual(c.status, 'RESOLVED')
        self.assertIsNotNone(c.resolved_at)

    # 10. Class Mentor can escalate to HOD with mandatory reason
    def test_10_class_mentor_escalates_to_hod_with_reason(self):
        c = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='Escalation to HOD Test',
            description='Test description for mentor forwarding issue to HOD.',
            current_level='MENTOR',
            status='UNDER_REVIEW'
        )
        self.client.login(username='mentor_john', password='MentorPassword123!')
        url = reverse('complaint_escalate', kwargs={'complaint_id': c.complaint_id})
        response = self.client.post(url, {
            'escalation_reason': 'Issue requires departmental budgetary approval from HOD.'
        })
        self.assertEqual(response.status_code, 302)

        c.refresh_from_db()
        self.assertEqual(c.current_level, 'HOD')
        self.assertEqual(c.status, 'ESCALATED_HOD')

        # Verify audit history note
        history = ComplaintStatusHistory.objects.filter(complaint=c, new_status='ESCALATED_HOD').first()
        self.assertIsNotNone(history)
        self.assertIn('ESCALATION TO HOD', history.comment)

    # 11. HOD can view and resolve escalated complaint
    def test_11_hod_can_view_and_resolve_escalated_complaint(self):
        c = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='HOD Resolution Test',
            description='Issue escalated to HOD.',
            current_level='HOD',
            status='ESCALATED_HOD'
        )
        self.client.login(username='hod_test', password='HodPassword123!')

        # HOD can view in complaint list
        list_response = self.client.get(reverse('complaint_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, c.complaint_id)

        # HOD can resolve the ticket
        url = reverse('complaint_status_update', kwargs={'complaint_id': c.complaint_id})
        response = self.client.post(url, {
            'new_status': 'RESOLVED',
            'comment': 'Approved and resolved by HOD.'
        })
        self.assertEqual(response.status_code, 302)

        c.refresh_from_db()
        self.assertEqual(c.status, 'RESOLVED')
        self.assertIsNotNone(c.resolved_at)

    # 12. Student cannot escalate complaint directly
    def test_12_student_cannot_escalate_complaint(self):
        c = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='Student Escalation Attempt',
            description='Testing unauthorized escalation.'
        )
        self.client.login(username='student_one', password='StudentPassword123!')
        url = reverse('complaint_escalate', kwargs={'complaint_id': c.complaint_id})
        response = self.client.post(url, {'escalation_reason': 'Unauthorized escalation.'})
        self.assertEqual(response.status_code, 403)

    # 13. Admin can view all complaints across all classes and departments
    def test_13_admin_can_view_all_complaints(self):
        c1 = Complaint.objects.create(user=self.student_1, category=self.cat_active, title='BCA complaint', description='Desc 1')
        c2 = Complaint.objects.create(user=self.student_2, category=self.cat_active, title='CSE complaint', description='Desc 2')

        self.client.login(username='admin_test', password='AdminPassword123!')
        response = self.client.get(reverse('complaint_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, c1.complaint_id)
        self.assertContains(response, c2.complaint_id)

    # 14. Invalid status transition is rejected
    def test_14_invalid_status_transition_is_rejected(self):
        c = Complaint.objects.create(user=self.student_1, category=self.cat_active, title='Transition rule test', description='Desc', status='CLOSED')
        with self.assertRaises(ValidationError):
            c.transition_status('IN_PROGRESS', changed_by=self.admin_user)

    # 15. Student can request reopening on resolved complaint
    def test_15_student_can_request_reopen_on_resolved(self):
        c = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='Reopen test ticket',
            description='Desc',
            status='RESOLVED'
        )
        self.client.login(username='student_one', password='StudentPassword123!')
        url = reverse('complaint_reopen', kwargs={'complaint_id': c.complaint_id})
        response = self.client.post(url, {'comment': 'Issue has reoccurred today.'})
        self.assertEqual(response.status_code, 302)

        c.refresh_from_db()
        self.assertEqual(c.status, 'REOPENED')

    # 16. HOD can escalate to Principal with mandatory reason
    def test_16_hod_escalates_to_principal_with_reason(self):
        c = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='Escalation to Principal Test',
            description='Issue that HOD cannot resolve and forwards to Principal.',
            current_level='HOD',
            status='ESCALATED_HOD'
        )
        self.client.login(username='hod_test', password='HodPassword123!')
        url = reverse('complaint_escalate', kwargs={'complaint_id': c.complaint_id})
        response = self.client.post(url, {
            'escalation_reason': 'Requires institutional-level policy decision by Principal.'
        })
        self.assertEqual(response.status_code, 302)

        c.refresh_from_db()
        self.assertEqual(c.current_level, 'PRINCIPAL')
        self.assertEqual(c.status, 'ESCALATED_PRINCIPAL')

        # Verify audit history note
        history = ComplaintStatusHistory.objects.filter(complaint=c, new_status='ESCALATED_PRINCIPAL').first()
        self.assertIsNotNone(history)
        self.assertIn('ESCALATION TO PRINCIPAL', history.comment)

    # 17. Principal can view and resolve escalated complaint
    def test_17_principal_can_view_and_resolve_escalated_complaint(self):
        c = Complaint.objects.create(
            user=self.student_1,
            category=self.cat_active,
            title='Principal Resolution Test',
            description='Issue escalated all the way to Principal.',
            current_level='PRINCIPAL',
            status='ESCALATED_PRINCIPAL'
        )
        self.client.login(username='principal_test', password='PrincipalPassword123!')

        # Principal can view in complaint list
        list_response = self.client.get(reverse('complaint_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, c.complaint_id)

        # Principal can resolve the complaint
        url = reverse('complaint_status_update', kwargs={'complaint_id': c.complaint_id})
        response = self.client.post(url, {
            'new_status': 'RESOLVED',
            'comment': 'Reviewed and resolved by College Principal.'
        })
        self.assertEqual(response.status_code, 302)

        c.refresh_from_db()
        self.assertEqual(c.status, 'RESOLVED')
        self.assertIsNotNone(c.resolved_at)

    # 18. Priority is removed from Complaint Create form
    def test_18_priority_removed_from_create_form(self):
        self.client.login(username='student_one', password='StudentPassword123!')
        response = self.client.get(reverse('complaint_create'))
        self.assertEqual(response.status_code, 200)
        # Form must not contain priority field
        self.assertNotContains(response, 'id_priority')
        self.assertNotContains(response, 'Priority Level')

    # 19. Full 4-Tier College Hierarchy End-to-End
    def test_19_full_four_tier_hierarchy_end_to_end(self):
        # Step 1: Student submits complaint
        self.client.login(username='student_one', password='StudentPassword123!')
        create_resp = self.client.post(reverse('complaint_create'), {
            'category': self.cat_active.id,
            'title': 'End to end college workflow complaint',
            'description': 'End to end test of Student -> Mentor -> HOD -> Principal'
        })
        self.assertEqual(create_resp.status_code, 302)
        c = Complaint.objects.get(title='End to end college workflow complaint')
        self.assertEqual(c.current_level, 'MENTOR')
        self.assertEqual(c.status, 'SUBMITTED')

        # Step 2: Class Mentor reviews and escalates to HOD
        self.client.login(username='mentor_john', password='MentorPassword123!')
        esc1_resp = self.client.post(reverse('complaint_escalate', kwargs={'complaint_id': c.complaint_id}), {
            'escalation_reason': 'Mentor cannot fix, passing to HOD.'
        })
        self.assertEqual(esc1_resp.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.current_level, 'HOD')
        self.assertEqual(c.status, 'ESCALATED_HOD')

        # Step 3: HOD reviews and escalates to Principal
        self.client.login(username='hod_test', password='HodPassword123!')
        esc2_resp = self.client.post(reverse('complaint_escalate', kwargs={'complaint_id': c.complaint_id}), {
            'escalation_reason': 'HOD cannot fix, passing to Principal.'
        })
        self.assertEqual(esc2_resp.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.current_level, 'PRINCIPAL')
        self.assertEqual(c.status, 'ESCALATED_PRINCIPAL')

        # Step 4: Principal reviews and finalizes resolution
        self.client.login(username='principal_test', password='PrincipalPassword123!')
        res_resp = self.client.post(reverse('complaint_status_update', kwargs={'complaint_id': c.complaint_id}), {
            'new_status': 'RESOLVED',
            'comment': 'Final resolution provided by Principal.'
        })
        self.assertEqual(res_resp.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.status, 'RESOLVED')
        self.assertIsNotNone(c.resolved_at)
