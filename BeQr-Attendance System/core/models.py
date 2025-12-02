from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    enrollment_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return self.username


class AllowedStudent(models.Model):
    enrollment_number = models.CharField(max_length=50, unique=True)
    email = models.EmailField(blank=True, null=True)
    
    def __str__(self):
        return self.enrollment_number

class Lecture(models.Model):
    name = models.CharField(max_length=255)
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} by {self.teacher.username}"

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('incomplete', 'Incomplete'),
    )
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE)
    time_in = models.DateTimeField(null=True, blank=True)
    time_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.student.username} - {self.lecture.name} - {self.status}"