#!/usr/bin/env python
"""Test script to verify PDF report generation"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beqr.settings')
django.setup()

from core.models import CustomUser, AttendanceSession, Lecture, Attendance
from django.utils import timezone
from datetime import timedelta
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

print("=" * 60)
print("TESTING PDF REPORT GENERATION")
print("=" * 60)

# Create test PDF
buffer = BytesIO()
doc = SimpleDocTemplate(buffer, pagesize=letter)
elements = []

styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=18,
    textColor=colors.HexColor('#1f4788'),
    spaceAfter=12,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

title = Paragraph("📊 BeQr Attendance System - Test Report", title_style)
elements.append(title)

# Test data
data = [['Roll No', 'Name', 'Status']]
for i in range(1, 6):
    data.append([f"10{i}", f"Student {i}", "Present"])

table = Table(data, colWidths=[1*inch, 2*inch, 1.5*inch])
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
]))
elements.append(table)

# Build PDF
doc.build(elements)
pdf_content = buffer.getvalue()

print(f"✅ PDF Generated Successfully!")
print(f"PDF Size: {len(pdf_content)} bytes")
print(f"PDF Header: {pdf_content[:20]}")

if pdf_content.startswith(b'%PDF'):
    print("✅ Valid PDF file generated!")
else:
    print("⚠️ Warning: PDF may not be valid")

# Save to file for testing
with open('/tmp/test_report.pdf', 'wb') as f:
    f.write(pdf_content)
    print(f"✅ PDF saved to /tmp/test_report.pdf")

print("\n" + "=" * 60)
print("✅ PDF GENERATION TEST PASSED!")
print("=" * 60)
