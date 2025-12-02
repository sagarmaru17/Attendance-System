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
    path('student/dashboard/', views.student_dashboard_view, name='student_dashboard'),

]