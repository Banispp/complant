from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from complaints.models import AcademicClass, Complaint, ComplaintResponse, ComplaintStatusHistory, UserProfile


class Command(BaseCommand):
    help = 'Clears all dummy/test complaints and users, keeping only the main administrator account.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Clearing all test complaints, responses, and non-admin users..."))

        # 1. Delete all complaint activity and complaints
        resp_count, _ = ComplaintResponse.objects.all().delete()
        hist_count, _ = ComplaintStatusHistory.objects.all().delete()
        comp_count, _ = Complaint.objects.all().delete()
        self.stdout.write(f"Deleted {comp_count} complaints, {resp_count} responses, {hist_count} history records.")

        # 2. Reset mentor on AcademicClasses
        AcademicClass.objects.all().update(mentor=None)

        # 3. Delete all non-admin users
        non_admin_users = User.objects.exclude(username='admin')
        user_count = non_admin_users.count()
        deleted_usernames = list(non_admin_users.values_list('username', flat=True))
        non_admin_users.delete()

        # 4. Ensure admin exists and is set properly
        admin_user, created = User.objects.get_or_create(
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
        admin_profile.academic_class = None
        admin_profile.save()

        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {user_count} users: {deleted_usernames}"))
        self.stdout.write(self.style.SUCCESS("Database is now clean! Main Admin account kept: username 'admin' | password 'admin12345'"))
