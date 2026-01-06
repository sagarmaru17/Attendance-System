import random
import string
import uuid
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    # This field acts as Enrollment No for Students AND Faculty ID for Teachers
    enrollment_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return self.username

    # --- NEW: Helper Function to Generate Random ID ---
    def generate_unique_id(self):
        length = 6
        # Define valid characters: Uppercase letters and Numbers (e.g., A-Z, 0-9)
        characters = string.ascii_uppercase + string.digits
        
        while True:
            # Generate a random 6-char string (e.g., "TR45X9")
            new_id = ''.join(random.choices(characters, k=length))
            
            # Check if this ID already exists in the database
            if not CustomUser.objects.filter(enrollment_number=new_id).exists():
                return new_id

    # --- NEW: Override the Save Method ---
    def save(self, *args, **kwargs):
        # Logic: If this is a Teacher AND they don't have an ID yet...
        if self.role == 'teacher' and not self.enrollment_number:
            self.enrollment_number = self.generate_unique_id()
        
        # Finally, save the user to the database
        super().save(*args, **kwargs)


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


class AttendanceSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    course_name = models.CharField(max_length=100) # e.g., "BCA Sem 6"
    subject = models.CharField(max_length=100)     # e.g., "Python"
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Latitude/Longitude for location validation (Optional for now)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.subject} - {self.start_time.strftime('%H:%M')}"