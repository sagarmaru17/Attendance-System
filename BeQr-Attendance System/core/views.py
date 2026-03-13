from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.decorators import login_required
from .forms import StudentRegistrationForm, PasswordResetVerificationForm
from .models import Lecture, Attendance, CustomUser, AllowedStudent, AttendanceSession
import uuid
import jwt
import qrcode, csv
from io import BytesIO
from datetime import timedelta
from django.core.files import File
from django.conf import settings
from django.db.models import Count, Q


# --- HELPER FUNCTION: Get Teacher's IP ---
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# --- AUTHENTICATION VIEWS ---

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
                        
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


# --- TEACHER VIEWS ---

# @login_required
# def teacher_dashboard_view(request):
#     if request.user.role != 'teacher':
#         messages.warning(request, "Access denied. Restricted to faculty.")
#         return redirect('student_dashboard')

#     # 1. Fetch Teacher's Lectures
#     my_lectures = Lecture.objects.filter(teacher=request.user).order_by('-created_at')
    
#     # 2. Fetch Student Stats
#     registered_count = CustomUser.objects.filter(role='student').count()
#     total_allowed = AllowedStudent.objects.count()
    
#     # 3. Fetch the actual list (for the popup)
#     allowed_students_list = AllowedStudent.objects.all().order_by('enrollment_number')

#     # 4. Check if there is already an ACTIVE session for this teacher
#     active_session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()

#     # 5. NEW: Fetch live checked-in students for the active session
#     live_students = []
#     if active_session:
#         live_students = Attendance.objects.filter(session=active_session).order_by('-time_in')

#     context = {
#         'teacher': request.user,
#         'lectures': my_lectures,
#         'registered_count': max(0, registered_count - 1),  # Exclude admin/test accounts if needed
#         'total_allowed': total_allowed,
#         'allowed_students': allowed_students_list, 
#         'active_session': active_session, 
#         'live_students': live_students, # Pass to the template telemetry table
#     }
    
#     return render(request, 'core/teacher/dashboard.html', context)


@login_required
def teacher_dashboard_view(request):
    if request.user.role != 'teacher':
        messages.warning(request, "Access denied. Restricted to faculty.")
        return redirect('student_dashboard')

    # Fetch Student Stats
    registered_count = CustomUser.objects.filter(role='student').count()
    total_allowed = AllowedStudent.objects.count()
    allowed_students_list = AllowedStudent.objects.all().order_by('enrollment_number')

    # Check for active session
    active_session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()
    live_students = []
    if active_session:
        live_students = Attendance.objects.filter(session=active_session).order_by('-time_in')

    # --- NEW: Fetch Past Sessions & Calculate Stats ---
    all_past_sessions = AttendanceSession.objects.filter(
        teacher=request.user, 
        is_active=False
    ).annotate(
        present_count=Count('attendance', filter=Q(attendance__status='present')),
        absent_count=Count('attendance', filter=Q(attendance__status='absent')),
        incomplete_count=Count('attendance', filter=Q(attendance__status='incomplete'))
    ).order_by('-start_time')
    
    # Show only last 10 by default, but pass all sessions to template
    past_sessions = list(all_past_sessions)
    has_more = len(past_sessions) > 10

    context = {
        'teacher': request.user,
        'past_sessions': past_sessions,
        'has_more_sessions': has_more,
        'total_sessions': len(past_sessions),
        'registered_count': max(0, registered_count - 1),
        'total_allowed': total_allowed,
        'allowed_students': allowed_students_list, 
        'active_session': active_session, 
        'live_students': live_students,
    }
    
    return render(request, 'core/teacher/dashboard.html', context)


@login_required
def start_class_view(request):
    if request.user.role != 'teacher':
        return redirect('login')

    if request.method == 'POST':
        # Get data from the modal/inline form
        subject = request.POST.get('subject')
        course = request.POST.get('course')
        division = request.POST.get('division')
        topic = request.POST.get('topic')
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        
        # Capture Teacher's IP (The Subnet Anchor)
        teacher_ip = get_client_ip(request)

        # 1. Create the Active Session
        session = AttendanceSession.objects.create(
            teacher=request.user,
            subject=subject,
            course_name=course,
            division=division,
            topic=topic,
            latitude=lat if lat else None,
            longitude=lon if lon else None,
            anchor_ip=teacher_ip,
            session_id=str(uuid.uuid4())
        )

        # 2. Layer 1 Security: Create the 15-Minute Expiry JWT Payload
        payload = {
            'session_id': session.session_id,
            'type': 'check_in',
            'exp': timezone.now() + timedelta(minutes=15) 
        }
        
        # Encrypt token using your Django SECRET_KEY
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        # 3. Generate the visual QR Code from the Token
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(token)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')

        # Save the image file to the Session record
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        file_name = f'qr_{session.session_id}.png'
        session.qr_code.save(file_name, File(buffer), save=True)

        return redirect('teacher_dashboard')
    
    return redirect('teacher_dashboard')


@login_required
def end_class_view(request):
    session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()
    if not session:
        return redirect('teacher_dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'initiate_checkout':
            # Phase 2: Generate the Check-Out QR Code
            session.is_checkout = True
            session.save()
            
            payload = {
                'session_id': session.session_id,
                'type': 'check_out',
                'exp': timezone.now() + timedelta(minutes=10) # 10 minute check-out window
            }
            token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(token)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            file_name = f'checkout_qr_{session.session_id}.png'
            session.qr_code.save(file_name, File(buffer), save=True)

        # ...existing code...
        elif action == 'close_session':
            # Phase 3: Finalize everything
            session.is_active = False
            session.end_time = timezone.now()
            session.save()
            
            # Mark incomplete students as absent (Optional logic based on your requirements)
            Attendance.objects.filter(session=session, status='incomplete').update(status='absent')
            
            messages.success(request, "Class session ended successfully.")

    return redirect('teacher_dashboard')

@login_required
def generate_report_view(request):
    if request.user.role != 'teacher':
        messages.error(request, "Access denied.")
        return redirect('login')

    if request.method == 'POST':
        # 1. Get the data submitted from the Modal form
        subject = request.POST.get('subject')
        report_type = request.POST.get('report_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        # 2. Setup the HTTP Response to act as a downloadable CSV file
        response = HttpResponse(content_type='text/csv')
        filename = f"BeQr_{report_type}_{subject}_{start_date}_to_{end_date}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # 3. Fetch all COMPLETED sessions for this teacher, subject, and date range
        sessions = AttendanceSession.objects.filter(
            teacher=request.user,
            subject=subject,
            start_time__date__gte=start_date, # Greater than or equal to start_date
            start_time__date__lte=end_date,   # Less than or equal to end_date
            is_active=False  # Only include closed classes
        )

        # --- REPORT LOGIC A: Monthly Master List ---
        if report_type == 'master':
            writer.writerow(['Roll Number', 'Student Name', 'Date', 'Topic', 'Status'])
            attendances = Attendance.objects.filter(session__in=sessions).order_by('session__start_time', 'student__roll_number')
            
            for att in attendances:
                writer.writerow([
                    att.student.roll_number,
                    f"{att.student.first_name} {att.student.last_name}",
                    att.session.start_time.strftime('%d-%b-%Y'),
                    att.session.topic,
                    att.get_status_display()
                ])

        # --- REPORT LOGIC B: 75% Defaulter List ---
        elif report_type == 'defaulter':
            writer.writerow(['Roll Number', 'Student Name', 'Total Classes', 'Classes Attended', 'Attendance %', 'Action'])
            total_classes = sessions.count()
            
            if total_classes > 0:
                # Get all students
                students = CustomUser.objects.filter(role='student').order_by('roll_number')
                for student in students:
                    # Count how many times this student was 'present' in the filtered sessions
                    attended = Attendance.objects.filter(student=student, session__in=sessions, status='present').count()
                    percentage = (attended / total_classes) * 100
                    
                    # ONLY write them to the file if they are below 75%
                    if percentage < 75.0:
                        writer.writerow([
                            student.roll_number,
                            f"{student.first_name} {student.last_name}",
                            total_classes,
                            attended,
                            f"{percentage:.2f}%",
                            "Defaulter Alert"
                        ])
            else:
                writer.writerow(['No classes found in this date range.'])

        # --- REPORT LOGIC C: Security & Telemetry Audit ---
        elif report_type == 'audit':
            writer.writerow(['Roll Number', 'Student Name', 'Date', 'Time In', 'Time Out', 'Final Status', 'Scanned IP', 'GPS Latitude', 'GPS Longitude'])
            attendances = Attendance.objects.filter(session__in=sessions).order_by('session__start_time', 'student__roll_number')
            
            for att in attendances:
                writer.writerow([
                    att.student.roll_number,
                    f"{att.student.first_name} {att.student.last_name}",
                    att.session.start_time.strftime('%d-%b-%Y'),
                    att.time_in.strftime('%I:%M %p') if att.time_in else 'Missed',
                    att.time_out.strftime('%I:%M %p') if att.time_out else 'Missed',
                    att.get_status_display(),
                    att.scanned_ip or 'N/A',
                    att.scanned_latitude or 'N/A',
                    att.scanned_longitude or 'N/A'
                ])

        return response # This triggers the download in the browser!

    return redirect('teacher_dashboard')




# --- STUDENT VIEWS ---

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
        'live_lecture': None, 
    }
    
    return render(request, 'core/student/dashboard.html', context)




# from time import timezone
# from django.http import HttpResponse
# from django.shortcuts import render, redirect
# from django.contrib.auth import authenticate, login, logout # For auth functions
# from django.contrib import messages # For flash messages
# from django.contrib.auth.forms import SetPasswordForm # Built-in form for password setting
# from django.contrib.auth.decorators import login_required # For protecting views
# from .forms import StudentRegistrationForm, PasswordResetVerificationForm # Import the new form
# from .models import Lecture, Attendance, CustomUser, AllowedStudent, AttendanceSession # Import models
# import uuid
# # Create your views here.
# # core/views.py

# # ... imports ...

# # CHANGE THE NAME HERE 👇
# def login_view(request):
#     if request.method == 'POST':
#         username = request.POST.get('username')
#         password = request.POST.get('password')

#         user = authenticate(request, username=username, password=password)

#         if user is not None:
#             # Now 'login' refers to the IMPORTED Django function, which is correct!
#             login(request, user) # Log the user in using the request and user objects.
                        
#             if user.role == 'teacher':
#                 return redirect('teacher_dashboard')
#             else:
#                 return redirect('student_dashboard')
#         else:
#             messages.error(request, "Invalid username or password.")

#     return render(request, 'core/login.html')

# def logout_view(request):
#     logout(request)
#     messages.success(request, "You have been logged out.")
#     return redirect('login')

# def signup_view(request):
#     if request.method == 'POST':
#         form = StudentRegistrationForm(request.POST)
#         if form.is_valid():
#             user = form.save(commit=False)
#             user.role = 'student'  # Automatically set role to Student
#             user.save()
#             messages.success(request, "Account created successfully! Please login.")
#             return redirect('login')
#         else:
#             messages.error(request, "Registration failed. Please correct the errors below.")
#     else:
#         form = StudentRegistrationForm()

#     return render(request, 'core/signup.html', {'form': form})

# # 1. VERIFY USER DETAILS
# def forgot_password_view(request):
#     if request.method == 'POST':
#         form = PasswordResetVerificationForm(request.POST)
#         if form.is_valid():
#             # Get the user found by the form
#             user = form.user_cache
            
#             # Store the user's ID in the session securely
#             request.session['reset_user_id'] = user.id
            
#             return redirect('reset_password_confirm')
#     else:
#         form = PasswordResetVerificationForm()

#     return render(request, 'core/forgot_password.html', {'form': form})


# # 2. SET NEW PASSWORD
# def reset_password_confirm_view(request):
#     # Security Check: Do we have a verified user in the session?
#     user_id = request.session.get('reset_user_id')
    
#     if not user_id:
#         messages.error(request, "Session expired or invalid. Please verify your details again.")
#         return redirect('forgot_password')

#     try:
#         user = CustomUser.objects.get(id=user_id)
#     except CustomUser.DoesNotExist:
#         return redirect('forgot_password')

#     if request.method == 'POST':
#         # Use Django's built-in SetPasswordForm (handles encryption & validation)
#         form = SetPasswordForm(user, request.POST)
#         if form.is_valid():
#             form.save()
            
#             # Clear the session so they can't reset it again
#             del request.session['reset_user_id']
            
#             messages.success(request, "Password changed successfully! Please login.")
#             return redirect('login')
#     else:
#         form = SetPasswordForm(user)

#     return render(request, 'core/reset_password_form.html', {'form': form})


# @login_required
# def teacher_dashboard_view(request):
#     if request.user.role != 'teacher':
#         messages.warning(request, "Access denied. Restricted to faculty.")
#         return redirect('student_dashboard')

#     # 1. Fetch Teacher's Lectures
#     my_lectures = Lecture.objects.filter(teacher=request.user).order_by('-created_at')
    
#     # 2. Fetch Student Stats
#     # Count how many students have actually signed up
#     registered_count = CustomUser.objects.filter(role='student').count()
#     # Count how many are in the Master List
#     total_allowed = AllowedStudent.objects.count()
    
#     # 3. Fetch the actual list (for the popup)
#     allowed_students_list = AllowedStudent.objects.all().order_by('enrollment_number')

#     # 4. Check if there is already an ACTIVE session for this teacher
#     active_session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()

#     context = {
#         'teacher': request.user,
#         'lectures': my_lectures,
#         'registered_count': registered_count-1,  # Exclude admin/test accounts if needed
#         'total_allowed': total_allowed,
#         'allowed_students': allowed_students_list, # Passing the list to template
#         'active_session': active_session, # Pass the session if it exists
#     }
    
#     return render(request, 'core/teacher/dashboard.html', context)



# @login_required
# def start_class_view(request):
#     if request.method == 'POST':
#         # Get data from the form (we will add this form to HTML next)
#         subject = request.POST.get('subject')
#         course = request.POST.get('course')
        
#         # Create the session
#         session = AttendanceSession.objects.create(
#             teacher=request.user,
#             subject=subject,
#             course_name=course,
#             session_id=str(uuid.uuid4()) # Unique ID for the QR code
#         )
#         return redirect('teacher_dashboard')
    
#     return redirect('teacher_dashboard')

# @login_required
# def end_class_view(request):
#     # Find the active session and close it
#     session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()
#     if session:
#         session.is_active = False
#         session.end_time = timezone.now()
#         session.save()
#     return redirect('teacher_dashboard')



# @login_required
# def student_dashboard_view(request):
#     # 1. Security Check: Only Students allowed
#     if request.user.role != 'student':
#         messages.warning(request, "Access denied. You are not a student.")
#         return redirect('teacher_dashboard')

#     # 2. Fetch Real Data: Get the last 5 attendance records for this student
#     recent_activity = Attendance.objects.filter(student=request.user).order_by('-time_in')[:5]

#     context = {
#         'student': request.user,
#         'recent_attendance': recent_activity,
#         'live_lecture': None, # We will activate this later when building the 'Start Class' feature
#     }
    
#     return render(request, 'core/student/dashboard.html', context)