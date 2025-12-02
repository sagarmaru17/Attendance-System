from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Lecture, Attendance, AllowedStudent

# Register your models here.

# 1. Configure how Users look in the Admin

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    # 1. Add 'roll_number' to the list view
    list_display = ['username', 'email', 'role', 'enrollment_number', 'roll_number', 'is_staff']
    
    # 2. Add it to the "Edit User" page
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'enrollment_number', 'roll_number')}),
    )
    
    # 3. Add it to the "Add User" page
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('role', 'enrollment_number', 'roll_number', 'email')}),
    )

@admin.register(AllowedStudent)
class AllowedStudentAdmin(admin.ModelAdmin):
    list_display = ('enrollment_number', 'email')
    search_fields = ('enrollment_number',)

# 2. Configure how Attendance looks
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'lecture', 'status', 'time_in', 'time_out')
    list_filter = ('status', 'lecture') # Add sidebar filters

# 3. Configure how Lectures look
class LectureAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher', 'created_at')

# 4. REGISTER EVERYTHING
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Lecture, LectureAdmin)
admin.site.register(Attendance, AttendanceAdmin)