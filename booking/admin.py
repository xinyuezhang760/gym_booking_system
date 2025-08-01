from django.contrib import admin
from django.contrib.admin import AdminSite
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Avg
from django.contrib.auth import logout
from .models import FitnessClass, Reservation, User, UserProfile

class CustomAdminSite(AdminSite):
    site_header = "Gym Booking System Administration"
    site_title = "Gym Booking Admin"
    index_title = "Welcome to Gym Booking Administration"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.index), name='index'),
            path('logout/', self.admin_view(self.custom_logout), name='logout'),
        ]
        return custom_urls + urls

    def index(self, request, extra_context=None):
        # Get statistical data
        total_users = User.objects.count()
        total_classes = FitnessClass.objects.count()
        total_reservations = Reservation.objects.count()
        avg_rating = Reservation.objects.filter(rating__isnull=False).aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Calculate average rating
        avg_rating = round(avg_rating, 1)
        
        # Get all user feedbacks - don't slice here to avoid filter error
        all_feedbacks = Reservation.objects.filter(feedback__isnull=False).order_by('-timestamp')
        
        # Get recent actions - don't slice here to avoid filter error
        recent_actions = LogEntry.objects.select_related('content_type', 'user').order_by('-action_time')

        context = {
            'total_users': total_users,
            'total_classes': total_classes,
            'total_reservations': total_reservations,
            'avg_rating': avg_rating,
            'all_feedbacks': all_feedbacks,
            'recent_actions': recent_actions,
            'log_entries': recent_actions,  # Add missing log_entries variable
            'title': 'Gym Booking System Administration',
            'subtitle': None,
            'app_list': self.get_app_list(request),
            **(extra_context or {}),
        }
        # Use the correct template path - Django will find it in booking/templates/admin/index.html
        return render(request, 'admin/index.html', context)

    def custom_logout(self, request):
        logout(request)
        return redirect('/login/')

# Create custom admin site instance
admin_site = CustomAdminSite()

# Register models to custom admin site
admin_site.register(FitnessClass)
admin_site.register(Reservation)
admin_site.register(User)
