from django.contrib import admin
from .models import FitnessClass, Reservation

@admin.register(FitnessClass)
class FitnessClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'time','duration' ,'instructor', 'max_capacity','class_type','location')
    fields = ('name', 'description', 'date', 'time','duration', 'instructor',  'max_capacity','image','class_type','location')

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('user', 'fitness_class', 'timestamp')
