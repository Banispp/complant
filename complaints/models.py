import re
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


class AcademicClass(models.Model):
    name = models.CharField(max_length=100, unique=True)  # e.g., 'BCA S3', 'B.Tech CSE S5'
    department = models.CharField(max_length=100)          # e.g., 'Computer Applications'
    mentor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='mentored_classes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Academic Class'
        verbose_name_plural = 'Academic Classes'
        ordering = ['name']

    def __str__(self):
        mentor_name = self.mentor.get_full_name() or self.mentor.username if self.mentor else "No Mentor"
        return f"{self.name} ({self.department}) - Mentor: {mentor_name}"


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('STUDENT', 'Student'),
        ('CLASS_MENTOR', 'Class Mentor'),
        ('HOD', 'Head of Department (HOD)'),
        ('PRINCIPAL', 'Principal'),
        ('ADMIN', 'System Administrator'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STUDENT')
    academic_class = models.ForeignKey(
        AcademicClass,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='students'
    )
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_admin(self):
        return self.role in ['ADMIN', 'PRINCIPAL'] or self.user.is_superuser

    def is_principal(self):
        return self.role in ['PRINCIPAL', 'ADMIN'] or self.user.is_superuser

    def is_hod(self):
        return self.role in ['HOD', 'PRINCIPAL', 'ADMIN'] or self.user.is_superuser

    def is_mentor(self):
        return self.role in ['CLASS_MENTOR', 'MENTOR', 'HOD', 'PRINCIPAL', 'ADMIN'] or self.user.is_superuser

    def is_student(self):
        return self.role in ['STUDENT', 'USER'] and not self.can_manage_complaints()

    def can_manage_complaints(self):
        return self.role in ['CLASS_MENTOR', 'MENTOR', 'HOD', 'PRINCIPAL', 'ADMIN'] or self.user.is_staff or self.user.is_superuser

    def get_role_badge_class(self):
        mapping = {
            'STUDENT': 'bg-secondary-subtle text-secondary border',
            'USER': 'bg-secondary-subtle text-secondary border',
            'CLASS_MENTOR': 'bg-info-subtle text-info-emphasis border border-info-subtle',
            'MENTOR': 'bg-info-subtle text-info-emphasis border border-info-subtle',
            'HOD': 'bg-warning-subtle text-warning-emphasis border border-warning-subtle',
            'PRINCIPAL': 'bg-danger-subtle text-danger-emphasis border border-danger-subtle',
            'ADMIN': 'bg-primary-subtle text-primary border border-primary-subtle',
        }
        return mapping.get(self.role, 'bg-light text-dark')

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        role = 'ADMIN' if instance.is_superuser else 'STUDENT'
        UserProfile.objects.create(user=instance, role=role)
    else:
        if hasattr(instance, 'profile'):
            if instance.is_superuser and instance.profile.role in ['STUDENT', 'USER']:
                instance.profile.role = 'ADMIN'
                instance.profile.save()


class ComplaintCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Complaint Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Complaint(models.Model):
    PRIORITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    )

    LEVEL_CHOICES = (
        ('MENTOR', 'Class Mentor Level'),
        ('HOD', 'HOD Level'),
        ('PRINCIPAL', 'Principal Level'),
    )

    STATUS_CHOICES = (
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('IN_PROGRESS', 'In Progress'),
        ('ESCALATED_HOD', 'Escalated to HOD'),
        ('ESCALATED_PRINCIPAL', 'Escalated to Principal'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('REJECTED', 'Rejected'),
        ('REOPENED', 'Reopened'),
    )

    ALLOWED_TRANSITIONS = {
        'SUBMITTED': ['UNDER_REVIEW', 'IN_PROGRESS', 'ESCALATED_HOD', 'RESOLVED', 'REJECTED'],
        'UNDER_REVIEW': ['IN_PROGRESS', 'ESCALATED_HOD', 'ESCALATED_PRINCIPAL', 'RESOLVED', 'REJECTED'],
        'IN_PROGRESS': ['ESCALATED_HOD', 'ESCALATED_PRINCIPAL', 'RESOLVED', 'REJECTED'],
        'ESCALATED_HOD': ['UNDER_REVIEW', 'IN_PROGRESS', 'ESCALATED_PRINCIPAL', 'RESOLVED', 'REJECTED'],
        'ESCALATED_PRINCIPAL': ['UNDER_REVIEW', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'REJECTED'],
        'RESOLVED': ['CLOSED', 'REOPENED'],
        'REOPENED': ['IN_PROGRESS', 'ESCALATED_HOD', 'ESCALATED_PRINCIPAL', 'RESOLVED', 'REJECTED'],
        'CLOSED': ['REOPENED'],
        'REJECTED': [],
    }

    complaint_id = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaints')
    category = models.ForeignKey(ComplaintCategory, on_delete=models.PROTECT, related_name='complaints')
    title = models.CharField(max_length=150)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM', blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='SUBMITTED')
    current_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='MENTOR')
    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_complaints'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.complaint_id} - {self.title}"

    def can_transition_to(self, new_status):
        if self.status == new_status:
            return True
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_status(self, new_status, changed_by, comment=""):
        if self.status == new_status:
            return self

        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Invalid status transition from {self.get_status_display()} to {dict(self.STATUS_CHOICES).get(new_status, new_status)}."
            )

        old_status = self.status
        self.status = new_status
        now = timezone.now()

        if new_status == 'RESOLVED':
            self.resolved_at = now
        elif new_status == 'CLOSED':
            self.closed_at = now
        elif new_status == 'REOPENED':
            self.closed_at = None
        elif new_status == 'ESCALATED_HOD':
            self.current_level = 'HOD'
        elif new_status == 'ESCALATED_PRINCIPAL':
            self.current_level = 'PRINCIPAL'

        self.save()

        old_status_display = dict(self.STATUS_CHOICES).get(old_status, old_status)
        new_status_display = dict(self.STATUS_CHOICES).get(new_status, new_status)
        audit_comment = comment.strip() if comment else f"Status changed from {old_status_display} to {new_status_display}."

        ComplaintStatusHistory.objects.create(
            complaint=self,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            comment=audit_comment
        )
        return self

    def escalate_to_hod(self, escalated_by, reason, assign_to=None):
        old_status = self.status
        self.status = 'ESCALATED_HOD'
        self.current_level = 'HOD'
        if assign_to:
            self.assigned_to = assign_to
        else:
            self.assigned_to = None
        self.save()

        ComplaintStatusHistory.objects.create(
            complaint=self,
            old_status=old_status,
            new_status='ESCALATED_HOD',
            changed_by=escalated_by,
            comment=f"ESCALATION TO HOD: {reason.strip()}"
        )
        return self

    def escalate_to_principal(self, escalated_by, reason, assign_to=None):
        old_status = self.status
        self.status = 'ESCALATED_PRINCIPAL'
        self.current_level = 'PRINCIPAL'
        if assign_to:
            self.assigned_to = assign_to
        else:
            self.assigned_to = None
        self.save()

        ComplaintStatusHistory.objects.create(
            complaint=self,
            old_status=old_status,
            new_status='ESCALATED_PRINCIPAL',
            changed_by=escalated_by,
            comment=f"ESCALATION TO PRINCIPAL: {reason.strip()}"
        )
        return self

    def clean(self):
        super().clean()
        if not self.pk and self.category_id:
            try:
                category = ComplaintCategory.objects.get(pk=self.category_id)
                if not category.is_active:
                    raise ValidationError({'category': 'Inactive categories cannot be selected for new complaints.'})
            except ComplaintCategory.DoesNotExist:
                pass

    def save(self, *args, **kwargs):
        is_new = not self.pk
        if not self.complaint_id:
            with transaction.atomic():
                last_complaint = Complaint.objects.select_for_update().order_by('-id').first()
                if last_complaint and last_complaint.complaint_id:
                    match = re.search(r'\d+', last_complaint.complaint_id)
                    next_number = int(match.group(0)) + 1 if match else 1
                else:
                    next_number = 1
                
                candidate_id = f"CMP-{next_number:05d}"
                while Complaint.objects.filter(complaint_id=candidate_id).exists():
                    next_number += 1
                    candidate_id = f"CMP-{next_number:05d}"
                self.complaint_id = candidate_id

                # Auto-assign to Class Mentor if student belongs to a mentored class
                if is_new and not self.assigned_to and hasattr(self.user, 'profile') and self.user.profile.academic_class:
                    if self.user.profile.academic_class.mentor:
                        self.assigned_to = self.user.profile.academic_class.mentor

                super().save(*args, **kwargs)
        else:
            if is_new and not self.assigned_to and hasattr(self.user, 'profile') and self.user.profile.academic_class:
                if self.user.profile.academic_class.mentor:
                    self.assigned_to = self.user.profile.academic_class.mentor
            super().save(*args, **kwargs)


class ComplaintResponse(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='responses')
    responder = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaint_responses')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Response by {self.responder.username} on {self.complaint.complaint_id}"


class ComplaintStatusHistory(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=30)
    new_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='status_changes')
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.complaint.complaint_id}: {self.old_status} -> {self.new_status}"
