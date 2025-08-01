from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from .models import Reservation
from .models import UserProfile
from .models import FitnessClass
from django.core.validators import RegexValidator

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    username = forms.CharField(
        max_length=150,
        label='Username',
        validators=[RegexValidator(r'^[\w ]+$', 'Username may contain letters, digits, underscores, and spaces.')]
    )
    role = forms.ChoiceField(
        choices=[('user', 'User'), ('instructor', 'Instructor')],
        widget=forms.RadioSelect,
        label='Register as'
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'role']


class SetGoalForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['fitness_goal']
        labels = {
            'fitness_goal': 'Your Fitness Goal',
        }
        widgets = {
            'fitness_goal': forms.RadioSelect(choices=UserProfile.FITNESS_GOALS)
        }

class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Username', max_length=150)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)

class RatingForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['rating', 'feedback']
        labels = {
            'rating': 'Rate this class (1-5)',
            'feedback': 'Feedback (optional)',
        }
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'feedback': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Write your feedback...'}),
        }

class CourseFilterForm(forms.Form):
    keyword = forms.CharField(label="Keyword", required=False)
    class_type = forms.ChoiceField(label="Class Type", choices=[('', 'All')] + FitnessClass.CLASS_TYPES, required=False)
    start_date = forms.DateField(label="Start Date", widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    end_date = forms.DateField(label="End Date", widget=forms.DateInput(attrs={'type': 'date'}), required=False)

class IntroVideoUploadForm(forms.ModelForm):
    class Meta:
        model = FitnessClass
        fields = ['intro_video']
