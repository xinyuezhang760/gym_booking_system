
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from .models import UserProfile, FitnessClass, Reservation
from .forms import RegisterForm, LoginForm, CourseFilterForm, SetGoalForm, IntroVideoUploadForm
import requests

MOONSHOT_API_KEY = "sk-MybQw7Kvh5yruZO6jJuReOhv8pi645W4WWffEpYxMsZUA85I"
MOONSHOT_API_URL = "https://api.moonshot.cn/v1/chat/completions"

def home(request):
    return render(request, 'booking/home.html')

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = form.cleaned_data['role']
            is_instructor = (role == 'instructor')
            UserProfile.objects.create(user=user, is_instructor=is_instructor)
            login(request, user)
            return redirect('class_list')
    else:
        form = RegisterForm()
    return render(request, 'booking/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None:  # Add null check
                login(request, user)
                # Role-based redirection
                if hasattr(user, 'userprofile') and user.userprofile.is_instructor:
                    return redirect('instructor_home')
                elif user.is_staff or user.is_superuser:
                    return redirect('/admin/')  # Redirect admin users to admin page
                else:
                    # Check if user has set fitness goal
                    if hasattr(user, 'userprofile') and not user.userprofile.fitness_goal:
                        return redirect('set_goal')
                    else:
                        return redirect('class_list')
    else:
        form = LoginForm()
    return render(request, 'booking/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')  # Redirect to login page after logout


def class_list(request):
    classes = FitnessClass.objects.all().order_by('date', 'time')
    form = CourseFilterForm(request.GET or None)

    if form.is_valid():
        keyword = form.cleaned_data.get('keyword')
        class_type = form.cleaned_data.get('class_type')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')

        if keyword:
            classes = classes.filter(
                Q(name__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(instructor__icontains=keyword)
            )
        if class_type:
            classes = classes.filter(class_type=class_type)
        if start_date:
            classes = classes.filter(date__gte=start_date)
        if end_date:
            classes = classes.filter(date__lte=end_date)

    user_booked = Reservation.objects.filter(user=request.user).values_list('fitness_class_id', flat=True) if request.user.is_authenticated else []

    # Add historical post-class summary and expired status for each class
    for class_obj in classes:
        # Check if class has expired
        class_datetime = datetime.combine(class_obj.date, class_obj.time)
        class_obj.is_expired = class_datetime < datetime.now()
        
        # Find historical classes with same instructor and name, ordered by date descending
        historical_classes = FitnessClass.objects.filter(
            instructor=class_obj.instructor,
            name=class_obj.name,
            date__lt=class_obj.date  # Only find classes before current class
        ).order_by('-date')
        
        # Get the first historical class with post_class_summary
        historical_summary = None
        for hist_class in historical_classes:
            if hist_class.post_class_summary:
                historical_summary = hist_class.post_class_summary
                break
        
        # Add historical summary to current class object
        class_obj.historical_summary = historical_summary

    return render(request, 'booking/class_list.html', {
        'classes': classes,
        'form': form,
        'user_booked': user_booked
    })


@login_required
def book_class(request, class_id):
    if request.user.is_authenticated:
        fitness_class = get_object_or_404(FitnessClass, pk=class_id)
        
        # Check if class has expired
        class_datetime = datetime.combine(fitness_class.date, fitness_class.time)
        if class_datetime < datetime.now():
            messages.error(request, 'This class has already expired and cannot be booked.')
            return redirect('class_list')

        # Prevent duplicate booking
        already_booked = Reservation.objects.filter(user=request.user, fitness_class=fitness_class).exists()
        if already_booked:
            messages.warning(request, 'You have already booked this class.')
            return redirect('class_list')  # Redirect to class list

        # ✅ Check if user already has a booking at the same time
        overlapping = Reservation.objects.filter(
            user=request.user,
            fitness_class__date=fitness_class.date,
            fitness_class__time=fitness_class.time
        ).exists()

        if overlapping:
            messages.error(request, "You already have a class booked at this time.")
            return redirect('class_list')

                # Check maximum capacity
        current_count = Reservation.objects.filter(fitness_class=fitness_class).count()
        if current_count >= fitness_class.max_capacity:
            messages.error(request, 'This class is fully booked.')
            return redirect('class_list')

        # Create reservation record
        Reservation.objects.create(user=request.user, fitness_class=fitness_class)
        messages.success(request, 'Class booked successfully!')  # Success message
        return redirect('my_reservations')
    else:
        return redirect('login')

@login_required
def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    reservation.delete()
    messages.success(request, "Your reservation has been cancelled.")
    return redirect('my_reservations')


@login_required
def my_reservations(request):
    now = datetime.now()
    reservations = Reservation.objects.filter(user=request.user).select_related('fitness_class')

    current_reservations = []
    past_reservations = []

    for r in reservations:
        class_datetime = datetime.combine(r.fitness_class.date, r.fitness_class.time)
        end_datetime = class_datetime + timedelta(minutes=r.fitness_class.duration)
        
        # Add is_expired property to fitness class
        r.fitness_class.is_expired = end_datetime < now

        if class_datetime > now:
            current_reservations.append(r)
        else:
            past_reservations.append(r)

    context = {
        'current_reservations': current_reservations,
        'past_reservations': past_reservations
    }
    return render(request, 'booking/my_reservations.html', context)



def admin_reservations(request):
    reservations = Reservation.objects.select_related('user', 'fitness_class').order_by('-timestamp')
    return render(request, 'booking/admin_reservations.html', {'reservations': reservations})


@login_required
def rate_class(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    # Only allow rating for classes that have already ended (class time has passed)
    class_datetime = datetime.combine(reservation.fitness_class.date, reservation.fitness_class.time)
    end_datetime = class_datetime + timedelta(minutes=reservation.fitness_class.duration)
    if class_datetime > datetime.now():
        messages.error(request, "You can only rate a class after you attend it.")
        return redirect('my_reservations')

    # Initialize form with existing rating (allow editing)
    if request.method == 'POST':
        form = RatingForm(request.POST, instance=reservation)
        if form.is_valid():
            form.save()
            messages.success(request, "You have successfully submitted your feedback.")
            return redirect('my_reservations')
    else:
        form = RatingForm(instance=reservation)

    return render(request, 'booking/rate_class.html', {'form': form, 'reservation': reservation})



@staff_member_required  # Only admin can access feedback
def view_all_feedback(request):
    feedbacks = Reservation.objects.filter(rating__isnull=False).order_by('-fitness_class__date', '-fitness_class__time')
    return render(request, 'booking/all_feedback.html', {'feedbacks': feedbacks})


# Show confirmation page
@login_required
def rebook_confirm(request, reservation_id):
    old_class = get_object_or_404(Reservation, id=reservation_id, user=request.user).fitness_class
    new_class = FitnessClass.objects.filter(
        name=old_class.name,
        date__gt=timezone.now().date()
    ).order_by('date').first()

    if not new_class:
        messages.error(request, "No upcoming class available to rebook.")
        return redirect('my_reservations')

    return render(request, 'booking/rebook_confirm.html', {
        'new_class': new_class,
        'reservation_id': reservation_id
    })

# Handle confirmation or cancellation
@login_required
def rebook_final(request, reservation_id):
    if request.method == 'POST':
        action = request.POST.get('action')
        old_class = get_object_or_404(Reservation, id=reservation_id, user=request.user)
        new_class = FitnessClass.objects.filter(
            name=old_class.fitness_class.name,
            date__gt=timezone.now().date()
        ).order_by('date').first()

        if action == 'yes':
            Reservation.objects.create(user=request.user, fitness_class=new_class)
            messages.success(request, "Successfully booked the next available class!")
        else:
            messages.info(request, "You chose not to rebook.")

    return redirect('my_reservations')

GOAL_KEYWORDS = {
    'muscle_gain': ['hiit', 'bootcamp', 'body', 'blast', 'pump', 'burn', 'combat', 'core'],
    'flexibility': ['yoga', 'stretch', 'pilates', 'flow', 'balance', 'mobility'],
    'weight_loss': ['zumba', 'cardio', 'dance', 'step', 'sweat', 'burn', 'fat'],
    'general_fitness': ['fitness', 'tone', 'energy', 'move', 'fun', 'active'],
}


@login_required
def profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if not profile.fitness_goal:
        return redirect('set_goal')

    user_reservations = Reservation.objects.filter(user=request.user).select_related('fitness_class')
    total_exercise_time = sum(reservation.fitness_class.duration for reservation in user_reservations)
    physical_improvement_time = 0
    strength_training_time = 0
    for reservation in user_reservations:
        duration = reservation.fitness_class.duration
        class_type = reservation.fitness_class.class_type
        if class_type in ['weight_loss', 'flexibility', 'general_fitness']:
            physical_improvement_time += duration
        elif class_type == 'muscle_gain':
            strength_training_time += duration
    sports_data = {
        'total_exercise_time': total_exercise_time,
        'physical_improvement_time': physical_improvement_time,
        'strength_training_time': strength_training_time,
    }

    fitness_goal = profile.get_fitness_goal_display()
    booking_history = [
        f"{r.fitness_class.name} ({r.fitness_class.class_type}, {r.fitness_class.duration}min)"
        for r in user_reservations
    ]
    
    # Filter out expired classes for AI recommendations
    now = datetime.now()
    available_classes = FitnessClass.objects.all()
    non_expired_classes = []
    
    for c in available_classes:
        class_datetime = datetime.combine(c.date, c.time)
        end_datetime = class_datetime + timedelta(minutes=c.duration)
        if end_datetime > now:
            non_expired_classes.append(c)
    
    class_list = [
        f"{c.name} ({c.class_type}, {c.duration}min, {c.description})"
        for c in non_expired_classes
    ]
    
    prompt = f"""
You are a fitness class recommendation AI. 
User's fitness goal: {fitness_goal}
User's total exercise time: {total_exercise_time}min
Physical improvement training: {physical_improvement_time}min
Strength training: {strength_training_time}min
User's booking history: {booking_history}
Available classes (only non-expired classes): {class_list}
Please recommend 3-5 classes for the user, and give a short summary (in English) explaining why you recommend them based on the user's goal, data, and history. Only recommend classes that are still available (not expired). Output format:
Summary: ...\nRecommended Classes (only class names, one per line):\nClassName1\nClassName2\nClassName3\n...\n"""
    ai_summary = ""
    ai_course_names = []
    ai_courses = []
    try:
        headers = {
            "Authorization": f"Bearer {MOONSHOT_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "moonshot-v1-8k",
            "messages": [
                {"role": "system", "content": "You are a helpful fitness class recommendation assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        response = requests.post(MOONSHOT_API_URL, headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            # Parse AI response content
            if "Summary:" in content and "Recommended Classes" in content:
                ai_summary = content.split("Summary:")[1].split("Recommended Classes")[0].strip()
                ai_course_names = [line.strip() for line in content.split("Recommended Classes")[-1].split("\n") if line.strip() and not line.strip().startswith("Summary")]
            else:
                ai_summary = content
        else:
            ai_summary = "The AI recommendation service is temporarily unavailable. Please try again later."
    except Exception as e:
        ai_summary = f"AI recommendation error: {e}"

    # Find detailed information based on AI returned course names (only non-expired classes)
    for cname in ai_course_names:
        # Support AI returning course names with numbers or dots
        cname_clean = cname
        if ". " in cname:
            cname_clean = cname.split(". ", 1)[1]
        elif "." in cname and cname[1] == ".":
            cname_clean = cname[2:].strip()
        # Only take the course name part (remove parentheses, etc.)
        cname_clean = cname_clean.split("(")[0].strip()
        
        # Find the course and check if it's not expired
        course = FitnessClass.objects.filter(name__icontains=cname_clean).order_by('date').first()
        if course:
            class_datetime = datetime.combine(course.date, course.time)
            end_datetime = class_datetime + timedelta(minutes=course.duration)
            if end_datetime > now:
                ai_courses.append(course)

    return render(request, 'booking/profile.html', {
        'ai_summary': ai_summary,
        'ai_courses': ai_courses,
        'fitness_goal': fitness_goal,
        'total_exercise_time': sports_data['total_exercise_time'],
        'physical_improvement_time': sports_data['physical_improvement_time'],
        'strength_training_time': sports_data['strength_training_time'],
        'total_bookings': len(user_reservations),
        'avg_rating': user_reservations.aggregate(avg_rating=Avg('rating'))['avg_rating'] if user_reservations.exists() else None,
    })



@login_required
def set_goal(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = SetGoalForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your fitness goal has been updated successfully!")
            return redirect('profile')
    else:
        form = SetGoalForm(instance=profile)

    return render(request, 'booking/set_goal.html', {'form': form})


@login_required
def instructor_dashboard(request):
    user = request.user
    # Only allow instructor access
    if not hasattr(user, 'userprofile') or not user.userprofile.is_instructor:
        return redirect('home')

    # All classes for this instructor
    classes = FitnessClass.objects.filter(instructor=user.username)
    total_hours = sum(c.duration for c in classes)
    total_slots = sum(c.max_capacity for c in classes)
    total_reservations = Reservation.objects.filter(fitness_class__in=classes).count()
    attendance_rate = (total_reservations / total_slots * 100) if total_slots else 0

    # Ratings
    ratings = Reservation.objects.filter(fitness_class__in=classes, rating__isnull=False).values_list('rating', flat=True)
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

    # Satisfaction trend (weekly example)
    from django.db.models.functions import TruncWeek
    from django.db.models import Avg
    trends = (
        Reservation.objects
        .filter(fitness_class__in=classes, rating__isnull=False)
        .annotate(week=TruncWeek('fitness_class__date'))
        .values('week')
        .annotate(avg_rating=Avg('rating'))
        .order_by('week')
    )
    trend_labels = [t['week'].strftime('%Y-%m-%d') for t in trends]
    trend_data = [round(t['avg_rating'], 2) for t in trends]

    context = {
        'total_hours': total_hours,
        'attendance_rate': round(attendance_rate, 1),
        'avg_rating': avg_rating,
        'trend_labels': trend_labels,
        'trend_data': trend_data,
    }
    return render(request, 'booking/instructor_dashboard.html', context)


@login_required
def instructor_post_class_summary(request):
    user = request.user
    if not hasattr(user, 'userprofile') or not user.userprofile.is_instructor:
        return redirect('home')
    now = timezone.now()
    # 只查找已结束课程
    classes = FitnessClass.objects.filter(instructor=user.username, date__lt=now).order_by('-date')
    class_data = []
    for c in classes:
        reservations = Reservation.objects.filter(fitness_class=c)
        attendance = reservations.count()
        feedbacks = [r.feedback for r in reservations if r.feedback]
        ratings = [r.rating for r in reservations if r.rating is not None]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
        class_data.append({
            'obj': c,
            'attendance': attendance,
            'feedbacks': feedbacks,
            'ratings': ratings,
            'avg_rating': avg_rating,
        })
    return render(request, 'booking/instructor_post_class_summary.html', {'class_data': class_data})

@require_POST
@login_required
def generate_post_class_summary(request):
    class_id = request.POST.get('class_id')
    c = get_object_or_404(FitnessClass, id=class_id)
    reservations = Reservation.objects.filter(fitness_class=c)
    attendance = reservations.count()
    feedbacks = [r.feedback for r in reservations if r.feedback]
    ratings = [r.rating for r in reservations if r.rating is not None]
    prompt = f"""
You are an AI assistant for fitness instructors. Please write a post-class summary for the following class:
Class: {c.name}
Date: {c.date}
Instructor: {c.instructor}
Attendance: {attendance}
Average rating: {sum(ratings)/len(ratings) if ratings else 'N/A'}
Student feedback: {feedbacks}
Please summarize the class, highlight strengths, and give suggestions for improvement. Write in English.
"""
    headers = {
        "Authorization": f"Bearer sk-MybQw7Kvh5yruZO6jJuReOhv8pi645W4WWffEpYxMsZUA85I",
        "Content-Type": "application/json"
    }
    data = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system", "content": "You are a helpful fitness class summary assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    try:
        response = requests.post("https://api.moonshot.cn/v1/chat/completions", headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            result = response.json()
            summary = result["choices"][0]["message"]["content"]
        else:
            summary = "AI summary service is temporarily unavailable."
    except Exception as e:
        summary = f"AI summary error: {e}"
    return JsonResponse({'summary': summary})


@require_POST
@login_required
def submit_post_class_summary(request):
    class_id = request.POST.get('class_id')
    summary = request.POST.get('summary')
    from .models import FitnessClass
    c = FitnessClass.objects.get(id=class_id)
    c.post_class_summary = summary
    c.save()
    return JsonResponse({'status': 'ok', 'summary': summary})


@login_required
def instructor_home(request):
    user = request.user
    if not hasattr(user, 'userprofile') or not user.userprofile.is_instructor:
        return redirect('home')
    def normalize(name):
        import re
        return re.sub(r'\s+', '', name).lower()
    instructor_name = normalize(user.username)
    classes = FitnessClass.objects.all()
    my_classes = [c for c in classes if normalize(c.instructor) == instructor_name]
    
    # If normal matching doesn't find courses, try fuzzy matching
    if not my_classes:
        my_classes = [c for c in classes if any(word in c.instructor for word in user.username.split())]
    total_hours = sum(c.duration for c in my_classes)
    total_slots = sum(c.max_capacity for c in my_classes)
    total_reservations = Reservation.objects.filter(fitness_class__in=[c.id for c in my_classes]).count()
    attendance_rate = (total_reservations / total_slots * 100) if total_slots else 0
    ratings = Reservation.objects.filter(fitness_class__in=[c.id for c in my_classes], rating__isnull=False).values_list('rating', flat=True)
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    from django.db.models.functions import TruncWeek
    from django.db.models import Avg
    trends = (
        Reservation.objects
        .filter(fitness_class__in=[c.id for c in my_classes], rating__isnull=False)
        .annotate(week=TruncWeek('fitness_class__date'))
        .values('week')
        .annotate(avg_rating=Avg('rating'))
        .order_by('week')
    )
    trend_labels = [t['week'].strftime('%Y-%m-%d') for t in trends]
    trend_data = [round(t['avg_rating'], 2) for t in trends]
    now = timezone.now()
    ended_classes = [c for c in my_classes if c.date < now]
    class_data = []
    for c in ended_classes:
        reservations = Reservation.objects.filter(fitness_class=c)
        attendance = reservations.count()
        feedbacks = [r.feedback for r in reservations if r.feedback]
        ratings = [r.rating for r in reservations if r.rating is not None]
        avg_rating_c = round(sum(ratings) / len(ratings), 1) if ratings else None
        class_data.append({
            'obj': c,
            'attendance': attendance,
            'feedbacks': feedbacks,
            'ratings': ratings,
            'avg_rating': avg_rating_c,
            'post_class_summary': c.post_class_summary,
        })
    # Get current instructor's future classes
    # Ensure type matching: convert c.date to date object for comparison
    current_classes = [c for c in my_classes if c.date.date() >= now.date()]
    
    context = {
        'total_hours_taught': total_hours,
        'avg_attendance_rate': round(attendance_rate, 1),
        'avg_rating': avg_rating,
        'total_classes': len(my_classes),
        'chart_labels': trend_labels,
        'chart_data': trend_data,
        'ended_classes': ended_classes,
        'current_classes': current_classes,
    }
    return render(request, 'booking/instructor_home.html', context)


@login_required
def instructor_video_upload(request, class_id):
    user = request.user
    from .models import FitnessClass
    c = FitnessClass.objects.get(id=class_id)
    # Permission check: only allow this instructor to upload
    def normalize(name):
        import re
        return re.sub(r'\s+', '', name).lower()
    if normalize(c.instructor) != normalize(user.username):
        return redirect('instructor_home')
    if request.method == 'POST':
        form = IntroVideoUploadForm(request.POST, request.FILES, instance=c)
        if form.is_valid():
            # Can add 30-second validation
            form.save()
    return redirect('instructor_home')

