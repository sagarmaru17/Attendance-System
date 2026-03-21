from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name="signup"),

    # NEW CUSTOM PASSWORD RESET FLOW
    path('forgot_password/', views.forgot_password_view, name='forgot_password'),
    path('reset_password_confirm/', views.reset_password_confirm_view, name='reset_password_confirm'),
   

    # We will build these next! (Placeholders for now)
    path('teacher/dashboard/', views.teacher_dashboard_view, name='teacher_dashboard'),
    path('start_class/', views.start_class_view, name='start_class'),
    path('end_class/', views.end_class_view, name='end_class'),
    path('teacher/generate_report/', views.generate_report_view, name='generate_report'),# URL for generating reports
    path('api/generate-dynamic-qr/', views.generate_dynamic_qr_view, name='generate_dynamic_qr'),  # Dynamic QR with 20-second rotation


    path('student/dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('student/history/', views.student_history_view, name='student_history'),
    path('student/profile/', views.student_profile_view, name='student_profile'),
    path('student/process_scan/', views.process_scan_view, name='process_scan'),# URL for processing the QR scan
    
    # API Endpoints
    path('api/session/<str:session_id>/', views.get_session_details, name='get_session_details'),
    path('api/update-attendance/', views.update_attendance_status_view, name='update_attendance'),
]