# ============================================================
# PROJECT URL CONFIGURATION - beqr/urls.py
# ============================================================
#
# Root URL router for the BeQr Attendance System.
# Maps URL patterns to application routes.
#
# Route Structure:
# - /admin/ → Django admin panel
# - / (empty) → All core app URLs (see core/urls.py)
# - /media/ → Uploaded files (QR code images, etc.)

"""
URL configuration for beqr project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings             
from django.conf.urls.static import static
# ... imports ...

urlpatterns = [
    # Django Admin Interface
    # Access at: http://localhost:8000/admin/
    # Login with superuser credentials
    path('admin/', admin.site.urls),
    
    # Include all core app URLs (authentication, dashboards, API)
    # All core URLs are at root: http://localhost:8000/
    # Examples: /login/, /logout/, /teacher/dashboard/, /student/dashboard/, etc.
    # See core/urls.py for complete URL list
    path('', include('core.urls')),  # CONNECT THE CORE APP
]
# ... media static ...

# Serve media files (uploaded QR code images, etc.) in development
# In production, use a proper file server (AWS S3, etc.)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # SERVE MEDIA FILES IN DEVELOPMENT