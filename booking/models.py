from django.db import models

from django.contrib.auth.models import User
from django.utils import timezone



class FitnessClass(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    date = models.DateTimeField()
    time = models.TimeField()
    duration = models.IntegerField(help_text="Duration in minutes")
    instructor = models.CharField(max_length=100)
    max_capacity = models.PositiveIntegerField()  # 不加 default，管理员必须设置
    image = models.ImageField(upload_to='class_images/', blank=True, null=True)
    CLASS_TYPES = [
        ('muscle_gain', 'Muscle Gain'),
        ('flexibility', 'Flexibility'),
        ('weight_loss', 'Weight Loss'),
        ('general_fitness', 'General Fitness'),
    ]
    class_type = models.CharField(max_length=20, choices=CLASS_TYPES, default='weight_loss')
    location = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.date} {self.time}"
    def remaining_slots(self):
        return self.max_capacity - self.reservation_set.count()
    #快速预约的查找相似课程
    def find_next_same_class(self):
        return FitnessClass.objects.filter(
            name=self.name,
            instructor=self.instructor,
            date__gt=timezone.now().date()
        ).order_by('date', 'time').first()

class Reservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fitness_class = models.ForeignKey('FitnessClass', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField(null=True, blank=True)
    feedback = models.TextField(null=True, blank=True)


    def __str__(self):
        return f"{self.user.username} - {self.fitness_class.name}"

class UserProfile(models.Model):
    FITNESS_GOALS = [
        ('weight_loss', 'Weight Loss'),
        ('muscle_gain', 'Muscle Gain'),
        ('flexibility', 'Flexibility'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    fitness_goal = models.CharField(max_length=20, choices=FITNESS_GOALS, default='weight_loss')

    def __str__(self):
        return f"{self.user.username}'s profile"


