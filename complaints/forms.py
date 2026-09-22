from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Complaint, ComplaintCategory, ComplaintResponse, UserProfile, AcademicClass


class UserRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    email = forms.EmailField(max_length=254, required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))
    academic_class = forms.ModelChoiceField(
        queryset=AcademicClass.objects.all(),
        required=False,
        empty_label="-- Select Your Academic Class (e.g. BCA S3) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}), required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}), required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match.")
            else:
                user = User(
                    username=self.cleaned_data.get('username', ''),
                    first_name=self.cleaned_data.get('first_name', ''),
                    last_name=self.cleaned_data.get('last_name', ''),
                    email=self.cleaned_data.get('email', '')
                )
                try:
                    validate_password(password, user=user)
                except ValidationError as e:
                    self.add_error('password', e)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
            if hasattr(user, 'profile'):
                user.profile.role = 'STUDENT'
                if self.cleaned_data.get('academic_class'):
                    user.profile.academic_class = self.cleaned_data['academic_class']
                    user.profile.department = self.cleaned_data['academic_class'].department
                user.profile.save()
        return user


class UserLoginForm(forms.Form):
    username = forms.CharField(label="Username or Email", max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username or Email', 'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))


class UserProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    academic_class = forms.ModelChoiceField(
        queryset=AcademicClass.objects.all(),
        required=False,
        empty_label="-- Select Academic Class --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional phone number'}))
    department = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional department/unit'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop('profile', None)
        super().__init__(*args, **kwargs)
        if self.profile:
            self.fields['phone'].initial = self.profile.phone
            self.fields['department'].initial = self.profile.department
            self.fields['academic_class'].initial = self.profile.academic_class

    def save(self, commit=True):
        user = super().save(commit=commit)
        if self.profile:
            self.profile.phone = self.cleaned_data.get('phone', '')
            self.profile.department = self.cleaned_data.get('department', '')
            selected_class = self.cleaned_data.get('academic_class')
            if selected_class:
                self.profile.academic_class = selected_class
                if not self.profile.department:
                    self.profile.department = selected_class.department
            else:
                self.profile.academic_class = None
            if commit:
                self.profile.save()
        return user


class ComplaintCreateForm(forms.ModelForm):
    confirm_duplicate = forms.BooleanField(required=False, widget=forms.HiddenInput())

    category = forms.ModelChoiceField(
        queryset=ComplaintCategory.objects.filter(is_active=True),
        empty_label="-- Select Category --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    title = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief summary of the issue'})
    )
    description = forms.CharField(
        min_length=10,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Detailed explanation of the complaint...'})
    )

    class Meta:
        model = Complaint
        fields = ['category', 'title', 'description']

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if len(title) < 5:
            raise ValidationError("Title must be at least 5 characters long.")
        return title


class ComplaintStatusUpdateForm(forms.Form):
    new_status = forms.ChoiceField(choices=Complaint.STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason or note for this status change (optional)'}))

    def __init__(self, *args, **kwargs):
        self.complaint = kwargs.pop('complaint', None)
        super().__init__(*args, **kwargs)
        if self.complaint:
            allowed = Complaint.ALLOWED_TRANSITIONS.get(self.complaint.status, [])
            choices = [(s, dict(Complaint.STATUS_CHOICES)[s]) for s in allowed]
            self.fields['new_status'].choices = choices


class ComplaintAssignForm(forms.ModelForm):
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="-- Unassigned --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Complaint
        fields = ['assigned_to']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(
            is_active=True
        ).filter(
            Q(is_staff=True) | Q(is_superuser=True) | Q(profile__role__in=['CLASS_MENTOR', 'MENTOR', 'HOD', 'ADMIN'])
        ).distinct().order_by('first_name', 'username')


class ComplaintPriorityUpdateForm(forms.ModelForm):
    priority = forms.ChoiceField(choices=Complaint.PRIORITY_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = Complaint
        fields = ['priority']


class ComplaintResponseForm(forms.ModelForm):
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Write your response or update here...'}),
        required=True
    )

    class Meta:
        model = ComplaintResponse
        fields = ['message']


class ComplaintReopenForm(forms.Form):
    comment = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Explain why this complaint should be reopened...'}),
        required=True
    )


class ComplaintEscalateForm(forms.Form):
    escalation_reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Explain why this issue cannot be resolved at this level and must be escalated...'}),
        required=True
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="-- Auto Assign / Keep Current --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        target_role = kwargs.pop('target_role', 'HOD')
        super().__init__(*args, **kwargs)
        if target_role == 'PRINCIPAL':
            self.fields['assigned_to'].empty_label = "-- Auto Assign to Principal / Keep Current --"
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True
            ).filter(
                Q(profile__role='PRINCIPAL') | Q(is_superuser=True)
            ).distinct().order_by('first_name', 'username')
        elif target_role == 'HOD':
            self.fields['assigned_to'].empty_label = "-- Auto Assign to Department HOD / Keep Current --"
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True
            ).filter(
                Q(profile__role='HOD') | Q(is_superuser=True)
            ).distinct().order_by('first_name', 'username')
        else:
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True
            ).filter(
                Q(profile__role__in=['HOD', 'PRINCIPAL', 'ADMIN']) | Q(is_superuser=True)
            ).distinct().order_by('first_name', 'username')


class CategoryForm(forms.ModelForm):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name'}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}))
    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = ComplaintCategory
        fields = ['name', 'description', 'is_active']


class AdminUserCreateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    email = forms.EmailField(max_length=254, required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, initial='STUDENT', widget=forms.Select(attrs={'class': 'form-select'}))
    academic_class = forms.ModelChoiceField(
        queryset=AcademicClass.objects.all(),
        required=False,
        empty_label="-- Select Class (e.g. BCA S3) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}), required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}), required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        role = self.cleaned_data.get('role', 'STUDENT')
        if role == 'ADMIN':
            user.is_staff = True
            user.is_superuser = True
        elif role in ['CLASS_MENTOR', 'HOD', 'PRINCIPAL']:
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_staff = False
            user.is_superuser = False

        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            ac = self.cleaned_data.get('academic_class')
            if ac:
                if role in ['CLASS_MENTOR', 'MENTOR']:
                    ac.mentor = user
                    ac.save()
                    profile.academic_class = ac
                    profile.department = ac.department
                elif role == 'STUDENT':
                    profile.academic_class = ac
                    profile.department = ac.department
                else:
                    profile.department = ac.department
            profile.save()
        return user
