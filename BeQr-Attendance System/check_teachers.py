#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beqr.settings')
django.setup()

from core.models import CustomUser, AttendanceSession

print("All teachers and their available subjects:")
for teacher in CustomUser.objects.filter(role='teacher').order_by('last_name'):
    subjects = AttendanceSession.objects.filter(teacher=teacher).values_list('subject', flat=True).distinct()
    print(f"\n👨‍🏫 {teacher.first_name} {teacher.last_name} ({teacher.username})")
    if subjects:
        print(f"  ✅ Available subjects: {', '.join(sorted(subjects))}")
        print(f"  ✅ Can generate reports!")
    else:
        print(f"  ⚠️ No sessions - Start a class first")
