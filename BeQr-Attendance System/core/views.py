from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout # For auth functions
from django.contrib import messages # For flash messages
from django.contrib.auth.forms import SetPasswordForm # Built-in form for password setting
from django.contrib.auth.decorators import login_required # For protecting views
from .forms import StudentRegistrationForm, PasswordResetVerificationForm # Import the new form
from .models import Lecture, Attendance, CustomUser # Import models
# Create your views here.
# core/views.py

# ... imports ...

# CHANGE THE NAME HERE 👇
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Now 'login' refers to the IMPORTED Django function, which is correct!
            login(request, user) # Log the user in using the request and user objects.
                        
            if user.role == 'teacher':
                return redirect('teacher_dashboard')
            else:
                return redirect('student_dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')

def signup_view(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'student'  # Automatically set role to Student
            user.save()
            messages.success(request, "Account created successfully! Please login.")
            return redirect('login')
        else:
            messages.error(request, "Registration failed. Please correct the errors below.")
    else:
        form = StudentRegistrationForm()

    return render(request, 'core/signup.html', {'form': form})

# 1. VERIFY USER DETAILS
def forgot_password_view(request):
    if request.method == 'POST':
        form = PasswordResetVerificationForm(request.POST)
        if form.is_valid():
            # Get the user found by the form
            user = form.user_cache
            
            # Store the user's ID in the session securely
            request.session['reset_user_id'] = user.id
            
            return redirect('reset_password_confirm')
    else:
        form = PasswordResetVerificationForm()

    return render(request, 'core/forgot_password.html', {'form': form})


# 2. SET NEW PASSWORD
def reset_password_confirm_view(request):
    # Security Check: Do we have a verified user in the session?
    user_id = request.session.get('reset_user_id')
    
    if not user_id:
        messages.error(request, "Session expired or invalid. Please verify your details again.")
        return redirect('forgot_password')

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return redirect('forgot_password')

    if request.method == 'POST':
        # Use Django's built-in SetPasswordForm (handles encryption & validation)
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            
            # Clear the session so they can't reset it again
            del request.session['reset_user_id']
            
            messages.success(request, "Password changed successfully! Please login.")
            return redirect('login')
    else:
        form = SetPasswordForm(user)

    return render(request, 'core/reset_password_form.html', {'form': form})


@login_required
def teacher_dashboard_view(request):
    # 1. Security Check: Only Teachers allowed
    if request.user.role != 'teacher':
        messages.warning(request, "Access denied. Restricted to faculty.")
        return redirect('student_dashboard')

    # 2. Fetch Data: Get lectures assigned to THIS teacher only
    my_lectures = Lecture.objects.filter(teacher=request.user).order_by('-created_at')

    context = {
        'teacher': request.user,
        'lectures': my_lectures,
    }
    
    return render(request, 'core/teacher/dashboard.html', context)



@login_required
def student_dashboard_view(request):
    # 1. Security Check: Only Students allowed
    if request.user.role != 'student':
        messages.warning(request, "Access denied. You are not a student.")
        return redirect('teacher_dashboard')

    # 2. Fetch Real Data: Get the last 5 attendance records for this student
    recent_activity = Attendance.objects.filter(student=request.user).order_by('-time_in')[:5]

    context = {
        'student': request.user,
        'recent_attendance': recent_activity,
        'live_lecture': None, # We will activate this later when building the 'Start Class' feature
    }
    
    return render(request, 'core/student/dashboard.html', context)