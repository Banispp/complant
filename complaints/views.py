import csv
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q
from django.http import HttpResponse, Http404
from django.utils import timezone

from .models import Complaint, ComplaintCategory, ComplaintResponse, ComplaintStatusHistory, UserProfile, AcademicClass
from .forms import (
    UserRegistrationForm,
    UserLoginForm,
    UserProfileUpdateForm,
    ComplaintCreateForm,
    ComplaintStatusUpdateForm,
    ComplaintAssignForm,
    ComplaintPriorityUpdateForm,
    ComplaintResponseForm,
    ComplaintReopenForm,
    ComplaintEscalateForm,
    CategoryForm,
    AdminUserCreateForm,
)
from .decorators import admin_required, staff_or_authority_required, active_user_required


def get_user_scoped_complaints(user):
    """
    Returns queryset of complaints visible to the given user based on their role:
    - Student: only their own complaints (user=user)
    - Class Mentor: complaints from students in classes mentored by this user, OR assigned to this mentor.
      A mentor cannot see complaints from students in classes mentored by other mentors.
    - HOD: complaints belonging to this HOD's department, or escalated to HOD/Principal level, or assigned to this HOD.
    - Principal: institutional scope (all complaints across all departments).
    - System Administrator / Superuser: full visibility across all classes and departments.
    """
    if user.is_superuser or (hasattr(user, 'profile') and user.profile.role in ['ADMIN', 'PRINCIPAL']):
        return Complaint.objects.select_related('user', 'category', 'assigned_to', 'user__profile', 'user__profile__academic_class').all()

    if not hasattr(user, 'profile'):
        return Complaint.objects.none()

    profile = user.profile
    if profile.role in ['CLASS_MENTOR', 'MENTOR']:
        return Complaint.objects.filter(
            Q(user__profile__academic_class__mentor=user) | Q(assigned_to=user) | Q(user=user)
        ).select_related('user', 'category', 'assigned_to', 'user__profile', 'user__profile__academic_class').distinct()

    elif profile.role == 'HOD':
        hod_dept = profile.department.strip() if profile.department else ''
        if hod_dept:
            return Complaint.objects.filter(
                Q(user__profile__department__iexact=hod_dept) |
                Q(user__profile__academic_class__department__iexact=hod_dept) |
                Q(current_level__in=['HOD', 'PRINCIPAL']) |
                Q(status__in=['ESCALATED_HOD', 'ESCALATED_PRINCIPAL']) |
                Q(assigned_to=user) | Q(user=user)
            ).select_related('user', 'category', 'assigned_to', 'user__profile', 'user__profile__academic_class').distinct()
        else:
            return Complaint.objects.filter(
                Q(current_level__in=['HOD', 'PRINCIPAL']) |
                Q(status__in=['ESCALATED_HOD', 'ESCALATED_PRINCIPAL']) |
                Q(assigned_to=user) | Q(user=user)
            ).select_related('user', 'category', 'assigned_to', 'user__profile', 'user__profile__academic_class').distinct()

    else:  # Student / standard user
        return Complaint.objects.filter(user=user).select_related('user', 'category', 'assigned_to', 'user__profile', 'user__profile__academic_class')


# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Account created successfully for {user.username}! Please log in.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegistrationForm()

    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data.get('username').strip()
            password = form.cleaned_data.get('password')

            # Authenticate by username or email
            user_obj = None
            user_match = User.objects.filter(Q(username__iexact=username_or_email) | Q(email__iexact=username_or_email)).first()
            if user_match:
                user_obj = authenticate(request, username=user_match.username, password=password)
            else:
                user_obj = authenticate(request, username=username_or_email, password=password)

            if user_obj is not None:
                if not user_obj.is_active:
                    messages.error(request, "Your account has been deactivated. Please contact an administrator.")
                else:
                    login(request, user_obj)
                    role_name = user_obj.profile.get_role_display() if hasattr(user_obj, 'profile') else "User"
                    messages.success(request, f"Welcome, {user_obj.get_full_name() or user_obj.username}! ({role_name})")
                    next_url = request.GET.get('next')
                    if next_url:
                        return redirect(next_url)

                    can_manage = (
                        user_obj.is_superuser or 
                        user_obj.is_staff or 
                        (hasattr(user_obj, 'profile') and user_obj.profile.can_manage_complaints())
                    )
                    if can_manage:
                        return redirect('admin_dashboard')
                    return redirect('user_dashboard')
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = UserLoginForm()

    return render(request, 'auth/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


# ==============================================================================
# DASHBOARD VIEWS
# ==============================================================================

@login_required
@active_user_required
def dashboard_view(request):
    can_manage = (
        request.user.is_superuser or 
        request.user.is_staff or 
        (hasattr(request.user, 'profile') and request.user.profile.can_manage_complaints())
    )
    if can_manage:
        return redirect('admin_dashboard')
    return redirect('user_dashboard')


@login_required
@staff_or_authority_required
def admin_dashboard_view(request):
    all_complaints = get_user_scoped_complaints(request.user)

    total_count = all_complaints.count()
    submitted_count = all_complaints.filter(status='SUBMITTED').count()
    under_review_count = all_complaints.filter(status='UNDER_REVIEW').count()
    in_progress_count = all_complaints.filter(status='IN_PROGRESS').count()
    escalated_hod_count = all_complaints.filter(status='ESCALATED_HOD').count()
    escalated_principal_count = all_complaints.filter(status='ESCALATED_PRINCIPAL').count()
    resolved_count = all_complaints.filter(status='RESOLVED').count()
    closed_count = all_complaints.filter(status='CLOSED').count()
    reopened_count = all_complaints.filter(status='REOPENED').count()
    # Escalated tickets lists based on role
    profile_role = request.user.profile.role if hasattr(request.user, 'profile') else 'ADMIN'
    is_admin_user = request.user.is_superuser or request.user.is_staff or profile_role == 'ADMIN'
    
    if profile_role == 'HOD' or is_admin_user:
        escalated_hod_complaints = all_complaints.filter(status='ESCALATED_HOD').order_by('-updated_at')[:8]
    else:
        escalated_hod_complaints = None

    if profile_role == 'PRINCIPAL' or is_admin_user:
        escalated_principal_complaints = all_complaints.filter(status='ESCALATED_PRINCIPAL').order_by('-updated_at')[:8]
    else:
        escalated_principal_complaints = None

    recent_complaints = all_complaints.order_by('-created_at')[:5]
    
    # Unassigned relevant to role
    unassigned_qs = all_complaints.filter(assigned_to__isnull=True).exclude(status__in=['RESOLVED', 'CLOSED', 'REJECTED'])
    if profile_role == 'CLASS_MENTOR' or profile_role == 'MENTOR':
        unassigned_qs = unassigned_qs.filter(current_level='MENTOR')
    elif profile_role == 'HOD':
        unassigned_qs = unassigned_qs.filter(current_level='HOD')
    elif profile_role == 'PRINCIPAL':
        unassigned_qs = unassigned_qs.filter(current_level='PRINCIPAL')
    
    unassigned_count = unassigned_qs.count()
    unassigned_complaints = unassigned_qs.order_by('-created_at')[:5]

    # Status breakdown
    status_stats = (
        all_complaints.values('status')
        .annotate(total=Count('id'))
        .order_by('status')
    )
    status_labels = [dict(Complaint.STATUS_CHOICES).get(s['status'], s['status']) for s in status_stats]
    status_data = [s['total'] for s in status_stats]

    # Category breakdown
    category_stats = (
        all_complaints.values('category__name')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    cat_labels = [c['category__name'] or 'Uncategorized' for c in category_stats]
    cat_data = [c['total'] for c in category_stats]

    # Tier breakdown (replaces priority)
    level_stats = (
        all_complaints.values('current_level')
        .annotate(total=Count('id'))
        .order_by('current_level')
    )
    level_labels = [dict(Complaint.LEVEL_CHOICES).get(l['current_level'], l['current_level']) for l in level_stats]
    level_data = [l['total'] for l in level_stats]

    context = {
        'total_count': total_count,
        'submitted_count': submitted_count,
        'under_review_count': under_review_count,
        'in_progress_count': in_progress_count,
        'escalated_hod_count': escalated_hod_count,
        'escalated_principal_count': escalated_principal_count,
        'resolved_count': resolved_count,
        'closed_count': closed_count,
        'reopened_count': reopened_count,
        'unassigned_count': unassigned_count,
        'escalated_complaints': escalated_hod_complaints,
        'escalated_principal_complaints': escalated_principal_complaints,
        'recent_complaints': recent_complaints,
        'unassigned_complaints': unassigned_complaints,
        'status_labels': status_labels,
        'status_data': status_data,
        'cat_labels': cat_labels,
        'cat_data': cat_data,
        'level_labels': level_labels,
        'level_data': level_data,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
@active_user_required
def user_dashboard_view(request):
    can_manage = (
        request.user.is_superuser or 
        request.user.is_staff or 
        (hasattr(request.user, 'profile') and request.user.profile.can_manage_complaints())
    )
    if can_manage:
        return redirect('admin_dashboard')

    user_complaints = Complaint.objects.filter(user=request.user).select_related('category', 'assigned_to')

    total_count = user_complaints.count()
    pending_count = user_complaints.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).count()
    in_progress_count = user_complaints.filter(status__in=['IN_PROGRESS', 'ESCALATED_HOD', 'ESCALATED_PRINCIPAL', 'REOPENED']).count()
    resolved_count = user_complaints.filter(status='RESOLVED').count()
    closed_count = user_complaints.filter(status='CLOSED').count()
    recent_complaints = user_complaints.order_by('-created_at')[:5]

    context = {
        'total_count': total_count,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'closed_count': closed_count,
        'recent_complaints': recent_complaints,
    }
    return render(request, 'dashboard/user_dashboard.html', context)


# ==============================================================================
# COMPLAINT MANAGEMENT VIEWS
# ==============================================================================

@login_required
@active_user_required
def complaint_list_view(request):
    can_manage = (
        request.user.is_superuser or 
        request.user.is_staff or 
        (hasattr(request.user, 'profile') and request.user.profile.can_manage_complaints())
    )

    complaints = get_user_scoped_complaints(request.user)

    # Search
    search_query = request.GET.get('q', '').strip()
    if search_query:
        if can_manage:
            complaints = complaints.filter(
                Q(complaint_id__icontains=search_query) |
                Q(title__icontains=search_query) |
                Q(user__username__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query)
            )
        else:
            complaints = complaints.filter(
                Q(complaint_id__icontains=search_query) |
                Q(title__icontains=search_query)
            )

    # Filters
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        complaints = complaints.filter(status=status_filter)

    category_filter = request.GET.get('category', '').strip()
    if category_filter:
        complaints = complaints.filter(category_id=category_filter)

    level_filter = request.GET.get('level', '').strip()
    if level_filter:
        complaints = complaints.filter(current_level=level_filter)

    if can_manage:
        assigned_filter = request.GET.get('assigned_to', '').strip()
        if assigned_filter == 'unassigned':
            complaints = complaints.filter(assigned_to__isnull=True)
        elif assigned_filter:
            complaints = complaints.filter(assigned_to_id=assigned_filter)

    date_from = request.GET.get('date_from', '').strip()
    if date_from:
        complaints = complaints.filter(created_at__date__gte=date_from)

    date_to = request.GET.get('date_to', '').strip()
    if date_to:
        complaints = complaints.filter(created_at__date__lte=date_to)

    # Pagination
    paginator = Paginator(complaints, 10)
    page = request.GET.get('page')
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    categories = ComplaintCategory.objects.all()
    admins = User.objects.filter(
        is_active=True
    ).filter(
        Q(is_staff=True) | Q(is_superuser=True) | Q(profile__role__in=['CLASS_MENTOR', 'MENTOR', 'HOD', 'PRINCIPAL', 'ADMIN'])
    ).distinct() if can_manage else None

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'level_filter': level_filter,
        'assigned_filter': request.GET.get('assigned_to', ''),
        'date_from': date_from,
        'date_to': date_to,
        'categories': categories,
        'admins': admins,
        'is_admin': can_manage,
        'status_choices': Complaint.STATUS_CHOICES,
        'level_choices': Complaint.LEVEL_CHOICES,
    }
    return render(request, 'complaints/complaint_list.html', context)


@login_required
@active_user_required
def complaint_create_view(request):
    show_duplicate_warning = False

    if request.method == 'POST':
        form = ComplaintCreateForm(request.POST)
        if form.is_valid():
            category = form.cleaned_data['category']
            title = form.cleaned_data['title']
            confirm_duplicate = form.cleaned_data.get('confirm_duplicate', False)

            fifteen_mins_ago = timezone.now() - timedelta(minutes=15)
            recent_duplicate = Complaint.objects.filter(
                user=request.user,
                category=category,
                title__iexact=title,
                created_at__gte=fifteen_mins_ago
            ).first()

            if recent_duplicate and not confirm_duplicate:
                show_duplicate_warning = True
                messages.warning(request, f"A similar complaint '{recent_duplicate.complaint_id}' was submitted {recent_duplicate.created_at.strftime('%H:%M')} today. If this is a distinct issue, please confirm to proceed.")
                return render(request, 'complaints/complaint_form.html', {
                    'form': form,
                    'show_duplicate_warning': True,
                    'duplicate_complaint': recent_duplicate
                })

            complaint = form.save(commit=False)
            complaint.user = request.user
            complaint.status = 'SUBMITTED'
            complaint.current_level = 'MENTOR'
            complaint.save()

            # Record initial status in history
            ComplaintStatusHistory.objects.create(
                complaint=complaint,
                old_status='NONE',
                new_status='SUBMITTED',
                changed_by=request.user,
                comment='Complaint submitted by student. Assigned to Mentor Review level.'
            )

            messages.success(request, f"Complaint {complaint.complaint_id} submitted successfully.")
            return redirect('complaint_detail', complaint_id=complaint.complaint_id)
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = ComplaintCreateForm()

    return render(request, 'complaints/complaint_form.html', {
        'form': form,
        'show_duplicate_warning': show_duplicate_warning
    })


@login_required
@active_user_required
def complaint_detail_view(request, complaint_id):
    complaint = get_object_or_404(
        Complaint.objects.select_related('user', 'category', 'assigned_to', 'user__profile', 'user__profile__academic_class'),
        complaint_id=complaint_id
    )

    can_manage = (
        request.user.is_superuser or 
        request.user.is_staff or 
        (hasattr(request.user, 'profile') and request.user.profile.can_manage_complaints())
    )

    # Scoped authorization check:
    # Student can only view own complaint.
    # Class Mentor can only view complaints from students in classes they mentor or assigned to them.
    # HOD can view complaints in their department or escalated to HOD.
    # Admin can view all.
    scoped_qs = get_user_scoped_complaints(request.user)
    if not scoped_qs.filter(id=complaint.id).exists():
        raise PermissionDenied("You do not have permission to view this complaint.")

    # Timeline activities: status changes & responses merged chronologically
    status_history = list(complaint.status_history.select_related('changed_by').all())
    responses = list(complaint.responses.select_related('responder').all())

    timeline = []
    for sh in status_history:
        timeline.append({
            'type': 'status_change',
            'timestamp': sh.created_at,
            'actor': sh.changed_by,
            'old_status': sh.old_status,
            'new_status': sh.new_status,
            'comment': sh.comment,
            'title': f"Status changed to {dict(Complaint.STATUS_CHOICES).get(sh.new_status, sh.new_status)}" if sh.old_status != 'NONE' else "Complaint Submitted"
        })
    for resp in responses:
        timeline.append({
            'type': 'response',
            'timestamp': resp.created_at,
            'actor': resp.responder,
            'message': resp.message,
            'title': f"Response by {resp.responder.get_full_name() or resp.responder.username}"
        })
    timeline.sort(key=lambda x: x['timestamp'])

    # Determine escalation capability:
    # Mentor can escalate to HOD
    # HOD can escalate to Principal
    can_escalate_to_hod = False
    can_escalate_to_principal = False
    escalate_form = None
    next_escalation_target = None

    show_mentor_actions = False
    show_hod_actions = False
    show_principal_actions = False

    if can_manage and complaint.status not in ['RESOLVED', 'CLOSED', 'REJECTED']:
        user_role = request.user.profile.role if hasattr(request.user, 'profile') else 'STUDENT'
        # Strict admin check (superuser or explicitly ADMIN role) for override capabilities
        is_strict_admin = request.user.is_superuser or user_role == 'ADMIN'
        
        # New workflow flags
        if complaint.current_level == 'MENTOR' and (user_role in ['CLASS_MENTOR', 'MENTOR'] or is_strict_admin):
            show_mentor_actions = True
        elif complaint.current_level == 'HOD' and (user_role == 'HOD' or is_strict_admin):
            show_hod_actions = True
        elif complaint.current_level == 'PRINCIPAL' and (user_role == 'PRINCIPAL' or is_strict_admin):
            show_principal_actions = True

        if complaint.current_level == 'MENTOR' and (user_role in ['CLASS_MENTOR', 'MENTOR', 'HOD', 'PRINCIPAL', 'ADMIN'] or is_strict_admin):
            can_escalate_to_hod = True
            next_escalation_target = 'HOD'
            escalate_form = ComplaintEscalateForm(target_role='HOD')
        elif complaint.current_level == 'HOD' and (user_role in ['HOD', 'PRINCIPAL', 'ADMIN'] or is_strict_admin):
            can_escalate_to_principal = True
            next_escalation_target = 'PRINCIPAL'
            escalate_form = ComplaintEscalateForm(target_role='PRINCIPAL')

    status_form = ComplaintStatusUpdateForm(complaint=complaint) if can_manage else None
    assign_form = ComplaintAssignForm(instance=complaint) if can_manage else None
    response_form = ComplaintResponseForm()
    reopen_form = ComplaintReopenForm() if complaint.status in ['RESOLVED', 'CLOSED'] else None

    context = {
        'complaint': complaint,
        'is_admin': can_manage,
        'timeline': timeline,
        'status_form': status_form,
        'assign_form': assign_form,
        'response_form': response_form,
        'reopen_form': reopen_form,
        'can_escalate_to_hod': can_escalate_to_hod,
        'can_escalate_to_principal': can_escalate_to_principal,
        'show_mentor_actions': show_mentor_actions,
        'show_hod_actions': show_hod_actions,
        'show_principal_actions': show_principal_actions,
        'escalate_form': escalate_form,
        'next_escalation_target': next_escalation_target,
        'allowed_transitions': Complaint.ALLOWED_TRANSITIONS.get(complaint.status, []),
    }
    return render(request, 'complaints/complaint_detail.html', context)


@login_required
@staff_or_authority_required
def complaint_status_update_view(request, complaint_id):
    if request.method != 'POST':
        return redirect('complaint_detail', complaint_id=complaint_id)

    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)

    scoped_qs = get_user_scoped_complaints(request.user)
    if not scoped_qs.filter(id=complaint.id).exists():
        raise PermissionDenied("You do not have permission to update this complaint.")

    user_role = request.user.profile.role if hasattr(request.user, 'profile') else 'STUDENT'
    is_strict_admin = request.user.is_superuser or user_role == 'ADMIN'

    # Strict role check for action execution
    if not is_strict_admin:
        if complaint.current_level == 'MENTOR' and user_role not in ['CLASS_MENTOR', 'MENTOR']:
            raise PermissionDenied("Only Class Mentors can update mentor-level complaints.")
        elif complaint.current_level == 'HOD' and user_role != 'HOD':
            raise PermissionDenied("Only HODs can update HOD-level complaints.")
        elif complaint.current_level == 'PRINCIPAL' and user_role != 'PRINCIPAL':
            raise PermissionDenied("Only Principals can update Principal-level complaints.")

    form = ComplaintStatusUpdateForm(request.POST, complaint=complaint)

    if form.is_valid():
        new_status = form.cleaned_data['new_status']
        comment = form.cleaned_data.get('comment', '').strip()

        try:
            complaint.transition_status(new_status=new_status, changed_by=request.user, comment=comment)
            messages.success(request, f"Status updated to {complaint.get_status_display()} successfully.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        messages.error(request, "Invalid status transition selected.")

    return redirect('complaint_detail', complaint_id=complaint_id)


@login_required
@staff_or_authority_required
def complaint_escalate_view(request, complaint_id):
    if request.method != 'POST':
        return redirect('complaint_detail', complaint_id=complaint_id)

    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)

    scoped_qs = get_user_scoped_complaints(request.user)
    if not scoped_qs.filter(id=complaint.id).exists():
        raise PermissionDenied("You do not have permission to escalate this complaint.")

    user_role = request.user.profile.role if hasattr(request.user, 'profile') else 'STUDENT'
    is_strict_admin = request.user.is_superuser or user_role == 'ADMIN'

    if not is_strict_admin:
        if complaint.current_level == 'MENTOR' and user_role not in ['CLASS_MENTOR', 'MENTOR']:
            raise PermissionDenied("Only Class Mentors can escalate mentor-level complaints.")
        elif complaint.current_level == 'HOD' and user_role != 'HOD':
            raise PermissionDenied("Only HODs can escalate HOD-level complaints.")

    if complaint.status in ['RESOLVED', 'CLOSED', 'REJECTED']:
        messages.error(request, "Resolved, Closed, or Rejected complaints cannot be escalated.")
        return redirect('complaint_detail', complaint_id=complaint_id)

    target_role = 'HOD' if complaint.current_level == 'MENTOR' else 'PRINCIPAL'
    form = ComplaintEscalateForm(request.POST, target_role=target_role)
    if form.is_valid():
        reason = form.cleaned_data['escalation_reason']
        target_assignee = form.cleaned_data.get('assigned_to')

        if complaint.current_level == 'MENTOR':
            complaint.escalate_to_hod(escalated_by=request.user, reason=reason, assign_to=target_assignee)
            messages.success(request, f"Complaint {complaint.complaint_id} has been escalated to HOD level successfully.")
        elif complaint.current_level == 'HOD':
            complaint.escalate_to_principal(escalated_by=request.user, reason=reason, assign_to=target_assignee)
            messages.success(request, f"Complaint {complaint.complaint_id} has been escalated to Principal level successfully.")
        else:
            messages.info(request, "Complaint is already at the highest escalation level (Principal).")
    else:
        messages.error(request, "Escalation reason is required.")

    return redirect('complaint_detail', complaint_id=complaint_id)


@login_required
@staff_or_authority_required
def complaint_assign_view(request, complaint_id):
    if request.method != 'POST':
        return redirect('complaint_detail', complaint_id=complaint_id)

    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)

    scoped_qs = get_user_scoped_complaints(request.user)
    if not scoped_qs.filter(id=complaint.id).exists():
        raise PermissionDenied("You do not have permission to assign this complaint.")

    form = ComplaintAssignForm(request.POST, instance=complaint)

    if form.is_valid():
        old_assigned = complaint.assigned_to
        complaint = form.save()
        assigned_name = complaint.assigned_to.get_full_name() or complaint.assigned_to.username if complaint.assigned_to else "Unassigned"
        
        # Add history note
        ComplaintStatusHistory.objects.create(
            complaint=complaint,
            old_status=complaint.status,
            new_status=complaint.status,
            changed_by=request.user,
            comment=f"Assignment updated: {old_assigned.username if old_assigned else 'None'} → {assigned_name}"
        )
        messages.success(request, f"Complaint assigned to {assigned_name} successfully.")
    else:
        messages.error(request, "Failed to assign complaint.")

    return redirect('complaint_detail', complaint_id=complaint_id)


@login_required
@staff_or_authority_required
def complaint_priority_update_view(request, complaint_id):
    if request.method != 'POST':
        return redirect('complaint_detail', complaint_id=complaint_id)

    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)

    scoped_qs = get_user_scoped_complaints(request.user)
    if not scoped_qs.filter(id=complaint.id).exists():
        raise PermissionDenied("You do not have permission to update priority.")

    form = ComplaintPriorityUpdateForm(request.POST, instance=complaint)

    if form.is_valid():
        old_prio = complaint.get_priority_display()
        complaint = form.save()
        ComplaintStatusHistory.objects.create(
            complaint=complaint,
            old_status=complaint.status,
            new_status=complaint.status,
            changed_by=request.user,
            comment=f"Priority changed from {old_prio} to {complaint.get_priority_display()}."
        )
        messages.success(request, f"Priority updated to {complaint.get_priority_display()}.")
    else:
        messages.error(request, "Invalid priority.")

    return redirect('complaint_detail', complaint_id=complaint_id)


@login_required
@active_user_required
def complaint_response_view(request, complaint_id):
    if request.method != 'POST':
        return redirect('complaint_detail', complaint_id=complaint_id)

    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)

    scoped_qs = get_user_scoped_complaints(request.user)
    if not scoped_qs.filter(id=complaint.id).exists():
        raise PermissionDenied("You cannot respond to this complaint.")

    form = ComplaintResponseForm(request.POST)
    if form.is_valid():
        response = form.save(commit=False)
        response.complaint = complaint
        response.responder = request.user
        response.save()
        messages.success(request, "Response added successfully.")
    else:
        messages.error(request, "Response cannot be empty.")

    return redirect('complaint_detail', complaint_id=complaint_id)


@login_required
@active_user_required
def complaint_reopen_view(request, complaint_id):
    if request.method != 'POST':
        return redirect('complaint_detail', complaint_id=complaint_id)

    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)

    scoped_qs = get_user_scoped_complaints(request.user)
    if not scoped_qs.filter(id=complaint.id).exists():
        raise PermissionDenied("You cannot reopen this complaint.")

    if complaint.status not in ['RESOLVED', 'CLOSED']:
        messages.error(request, "Only resolved or closed complaints can be reopened.")
        return redirect('complaint_detail', complaint_id=complaint_id)

    form = ComplaintReopenForm(request.POST)
    if form.is_valid():
        comment = form.cleaned_data['comment']
        try:
            complaint.transition_status(
                new_status='REOPENED',
                changed_by=request.user,
                comment=f"Complaint reopened. Reason: {comment}"
            )
            messages.success(request, "Complaint has been reopened successfully.")
        except ValidationError as e:
            messages.error(request, str(e))
    else:
        messages.error(request, "Please provide a reason to reopen.")

    return redirect('complaint_detail', complaint_id=complaint_id)


@login_required
@active_user_required
def complaint_delete_view(request, complaint_id):
    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)

    is_owner = (complaint.user == request.user)
    is_admin = (
        request.user.is_superuser or 
        (hasattr(request.user, 'profile') and request.user.profile.is_admin())
    )

    if not (is_owner or is_admin):
        raise PermissionDenied("You do not have permission to delete this complaint.")

    if request.method == 'POST':
        c_id = complaint.complaint_id
        complaint.delete()
        messages.success(request, f"Complaint '{c_id}' has been deleted successfully.")
        return redirect('complaint_list')

    return redirect('complaint_detail', complaint_id=complaint_id)


# ==============================================================================
# CATEGORY MANAGEMENT (ADMIN ONLY)
# ==============================================================================

@login_required
@admin_required
def category_list_view(request):
    categories = ComplaintCategory.objects.annotate(complaint_count=Count('complaints')).order_by('name')
    return render(request, 'categories/category_list.html', {'categories': categories})


@login_required
@admin_required
def category_create_view(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' created successfully.")
            return redirect('category_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm()

    return render(request, 'categories/category_form.html', {'form': form, 'action': 'Create'})


@login_required
@admin_required
def category_edit_view(request, pk):
    category = get_object_or_404(ComplaintCategory, pk=pk)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' updated successfully.")
            return redirect('category_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm(instance=category)

    return render(request, 'categories/category_form.html', {'form': form, 'category': category, 'action': 'Edit'})


@login_required
@admin_required
def category_toggle_active_view(request, pk):
    if request.method != 'POST':
        return redirect('category_list')

    category = get_object_or_404(ComplaintCategory, pk=pk)
    category.is_active = not category.is_active
    category.save()
    status_str = "activated" if category.is_active else "deactivated"
    messages.success(request, f"Category '{category.name}' {status_str} successfully.")
    return redirect('category_list')


# ==============================================================================
# USER MANAGEMENT (ADMIN ONLY)
# ==============================================================================

@login_required
@admin_required
def user_create_view(request):
    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"User account '{user.username}' ({user.profile.get_role_display()}) created successfully.")
            return redirect('user_list')
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = AdminUserCreateForm()

    return render(request, 'users/user_form.html', {'form': form, 'action': 'Create'})


@login_required
@admin_required
def user_list_view(request):
    users = User.objects.select_related('profile', 'profile__academic_class').annotate(complaint_count=Count('complaints')).order_by('-date_joined')

    search_query = request.GET.get('q', '').strip()
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    role_filter = request.GET.get('role', '').strip()
    if role_filter:
        users = users.filter(profile__role=role_filter)

    status_filter = request.GET.get('status', '').strip()
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    paginator = Paginator(users, 15)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    return render(request, 'users/user_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'role_choices': UserProfile.ROLE_CHOICES,
    })


@login_required
@admin_required
def user_detail_view(request, user_id):
    target_user = get_object_or_404(User.objects.select_related('profile', 'profile__academic_class'), pk=user_id)
    user_complaints = Complaint.objects.filter(user=target_user).select_related('category', 'assigned_to').order_by('-created_at')

    return render(request, 'users/user_detail.html', {
        'target_user': target_user,
        'user_complaints': user_complaints,
    })


@login_required
@admin_required
def user_toggle_active_view(request, user_id):
    if request.method != 'POST':
        return redirect('user_list')

    target_user = get_object_or_404(User, pk=user_id)

    # Protect against admin self-deactivation
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own administrative account.")
        return redirect('user_list')

    target_user.is_active = not target_user.is_active
    target_user.save()
    status_str = "activated" if target_user.is_active else "deactivated"
    messages.success(request, f"User {target_user.username} has been {status_str} successfully.")
    return redirect('user_list')


@login_required
@admin_required
def user_delete_view(request, user_id):
    if request.method != 'POST':
        return redirect('user_list')

    target_user = get_object_or_404(User, pk=user_id)

    # Protect against admin self-deletion
    if target_user == request.user:
        messages.error(request, "You cannot delete your own administrative account.")
        return redirect('user_list')

    username = target_user.username
    target_user.delete()
    messages.success(request, f"User account '{username}' and associated records have been deleted successfully.")
    return redirect('user_list')


# ==============================================================================
# REPORTS & ANALYTICS (ADMIN ONLY)
# ==============================================================================

@login_required
@admin_required
def reports_view(request):
    complaints = Complaint.objects.select_related('category', 'user', 'assigned_to').all()

    # Date filtering
    date_preset = request.GET.get('preset', 'this_month')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    now = timezone.now()

    if date_preset == 'today':
        complaints = complaints.filter(created_at__date=now.date())
    elif date_preset == 'this_week':
        start_week = now.date() - timedelta(days=now.weekday())
        complaints = complaints.filter(created_at__date__gte=start_week)
    elif date_preset == 'this_month':
        complaints = complaints.filter(created_at__year=now.year, created_at__month=now.month)
    elif date_preset == 'custom':
        if date_from:
            complaints = complaints.filter(created_at__date__gte=date_from)
        if date_to:
            complaints = complaints.filter(created_at__date__lte=date_to)

    total_count = complaints.count()
    resolved_count = complaints.filter(status='RESOLVED').count()
    closed_count = complaints.filter(status='CLOSED').count()
    pending_count = complaints.filter(status__in=['SUBMITTED', 'UNDER_REVIEW', 'IN_PROGRESS', 'ESCALATED_HOD', 'ESCALATED_PRINCIPAL', 'REOPENED']).count()
    resolution_rate = round(((resolved_count + closed_count) / total_count * 100), 1) if total_count > 0 else 0

    # Breakdowns
    status_breakdown = complaints.values('status').annotate(total=Count('id')).order_by('-total')
    category_breakdown = complaints.values('category__name').annotate(total=Count('id')).order_by('-total')
    level_breakdown = complaints.values('current_level').annotate(total=Count('id')).order_by('-total')

    # Chart arrays
    status_labels = [dict(Complaint.STATUS_CHOICES).get(s['status'], s['status']) for s in status_breakdown]
    status_data = [s['total'] for s in status_breakdown]

    cat_labels = [c['category__name'] or 'Uncategorized' for c in category_breakdown]
    cat_data = [c['total'] for c in category_breakdown]

    level_labels = [dict(Complaint.LEVEL_CHOICES).get(l['current_level'], l['current_level']) for l in level_breakdown]
    level_data = [l['total'] for l in level_breakdown]

    context = {
        'total_count': total_count,
        'resolved_count': resolved_count,
        'closed_count': closed_count,
        'pending_count': pending_count,
        'resolution_rate': resolution_rate,
        'status_breakdown': status_breakdown,
        'category_breakdown': category_breakdown,
        'level_breakdown': level_breakdown,
        'status_labels': status_labels,
        'status_data': status_data,
        'cat_labels': cat_labels,
        'cat_data': cat_data,
        'level_labels': level_labels,
        'level_data': level_data,
        'date_preset': date_preset,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices_dict': dict(Complaint.STATUS_CHOICES),
        'level_choices_dict': dict(Complaint.LEVEL_CHOICES),
    }
    return render(request, 'reports/reports.html', context)


@login_required
@admin_required
def reports_export_csv_view(request):
    complaints = Complaint.objects.select_related('category', 'user', 'assigned_to').all()

    date_preset = request.GET.get('preset', 'all')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    now = timezone.now()

    if date_preset == 'today':
        complaints = complaints.filter(created_at__date=now.date())
    elif date_preset == 'this_week':
        start_week = now.date() - timedelta(days=now.weekday())
        complaints = complaints.filter(created_at__date__gte=start_week)
    elif date_preset == 'this_month':
        complaints = complaints.filter(created_at__year=now.year, created_at__month=now.month)
    elif date_preset == 'custom':
        if date_from:
            complaints = complaints.filter(created_at__date__gte=date_from)
        if date_to:
            complaints = complaints.filter(created_at__date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="complaints_report_{now.strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Complaint ID', 'Title', 'Category', 'Escalation Tier', 'Status',
        'Submitted By', 'Assigned To', 'Created Date', 'Resolved Date', 'Closed Date'
    ])

    for c in complaints:
        writer.writerow([
            c.complaint_id,
            c.title,
            c.category.name if c.category else 'N/A',
            c.get_current_level_display(),
            c.get_status_display(),
            c.user.get_full_name() or c.user.username,
            c.assigned_to.get_full_name() or c.assigned_to.username if c.assigned_to else 'Unassigned',
            c.created_at.strftime("%Y-%m-%d %H:%M"),
            c.resolved_at.strftime("%Y-%m-%d %H:%M") if c.resolved_at else '',
            c.closed_at.strftime("%Y-%m-%d %H:%M") if c.closed_at else ''
        ])

    return response


# ==============================================================================
# PROFILE VIEWS
# ==============================================================================

@login_required
@active_user_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=request.user, profile=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserProfileUpdateForm(instance=request.user, profile=profile)

    return render(request, 'profile/profile.html', {'form': form, 'profile': profile})


@login_required
@active_user_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was successfully updated!")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'profile/change_password.html', {'form': form})


# ==============================================================================
# ERROR HANDLERS
# ==============================================================================

def handler403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def handler404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def handler500(request):
    return render(request, 'errors/500.html', status=500)
