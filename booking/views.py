
from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import RegisterForm
from django.contrib.auth import authenticate, login
from .forms import LoginForm
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

from django.shortcuts import redirect, get_object_or_404
from .models import FitnessClass, Reservation
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from .forms import RatingForm
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from .models import FitnessClass, UserProfile
from .forms import SetGoalForm
from django.db.models import Count
from .forms import CourseFilterForm
from django.utils.timezone import make_aware
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
            fitness_goal = form.cleaned_data['fitness_goal']  # 获取健身目标
            UserProfile.objects.create(user=user, fitness_goal=fitness_goal)  # 创建用户资料
            login(request, user)  # 注册成功后自动登录
            return redirect('class_list')  # 注册后跳转到课程列表页（你后面要实现的）
    else:
        form = RegisterForm()
    return render(request, 'booking/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('class_list')  # 登录成功后跳转（class_list 是后面要做的页面）
    else:
        form = LoginForm()
    return render(request, 'booking/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')  # 退出后跳转到登录页


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

    return render(request, 'booking/class_list.html', {
        'classes': classes,
        'form': form,
        'user_booked': user_booked
    })


@login_required
def book_class(request, class_id):
    if request.user.is_authenticated:
        fitness_class = get_object_or_404(FitnessClass, pk=class_id)

        # 防止重复预约
        already_booked = Reservation.objects.filter(user=request.user, fitness_class=fitness_class).exists()
        if already_booked:
            messages.warning(request, 'You have already booked this class.')
            return redirect('class_list')  # 跳转页面

        # ✅ 检查是否已有在相同时间的预约
        overlapping = Reservation.objects.filter(
            user=request.user,
            fitness_class__date=fitness_class.date,
            fitness_class__time=fitness_class.time
        ).exists()

        if overlapping:
            messages.error(request, "You already have a class booked at this time.")
            return redirect('class_list')

        # 最大人数检查
        current_count = Reservation.objects.filter(fitness_class=fitness_class).count()
        if current_count >= fitness_class.max_capacity:
         messages.error(request, 'This class is fully booked.')
         return redirect('class_list')

        # 创建预约记录
        Reservation.objects.create(user=request.user, fitness_class=fitness_class)
        messages.success(request, 'Class booked successfully!')  # 提示成功
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

    upcoming = []
    ongoing = []
    past = []

    for r in reservations:
        class_datetime = datetime.combine(r.fitness_class.date, r.fitness_class.time)
        end_datetime = class_datetime + timedelta(minutes=r.fitness_class.duration)

        if class_datetime > now:
            upcoming.append(r)
        elif class_datetime <= now < end_datetime:
            ongoing.append(r)
        else:
            past.append(r)

    context = {
        'upcoming': upcoming,
        'ongoing': ongoing,
        'past': past
    }
    return render(request, 'booking/my_reservations.html', context)



def admin_reservations(request):
    reservations = Reservation.objects.select_related('user', 'fitness_class').order_by('-timestamp')
    return render(request, 'booking/admin_reservations.html', {'reservations': reservations})


@login_required
def rate_class(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    # 限制只能为已上课的课程评分（课程时间已过去）
    class_datetime = datetime.combine(reservation.fitness_class.date, reservation.fitness_class.time)
    end_datetime = class_datetime + timedelta(minutes=reservation.fitness_class.duration)
    if class_datetime > datetime.now():
        messages.error(request, "You can only rate a class after you attend it.")
        return redirect('my_reservations')

    # 实例化已有评分（允许编辑）
    if request.method == 'POST':
        form = RatingForm(request.POST, instance=reservation)
        if form.is_valid():
            form.save()
            messages.success(request, "You have successfully submitted your feedback.")
            return redirect('my_reservations')
    else:
        form = RatingForm(instance=reservation)

    return render(request, 'booking/rate_class.html', {'form': form, 'reservation': reservation})



@staff_member_required  # 仅管理员可以访问feedback
def view_all_feedback(request):
    feedbacks = Reservation.objects.filter(rating__isnull=False).order_by('-fitness_class__date', '-fitness_class__time')
    return render(request, 'booking/all_feedback.html', {'feedbacks': feedbacks})


# 显示确认页
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

# 处理确认或取消
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
    all_classes = FitnessClass.objects.all()
    class_list = [
        f"{c.name} ({c.class_type}, {c.duration}min, {c.description})"
        for c in all_classes
    ]
    prompt = f"""
You are a fitness class recommendation AI. 
User's fitness goal: {fitness_goal}
User's total exercise time: {total_exercise_time}min
Physical improvement training: {physical_improvement_time}min
Strength training: {strength_training_time}min
User's booking history: {booking_history}
Available classes: {class_list}
Please recommend 3-5 classes for the user, and give a short summary (in English) explaining why you recommend them based on the user's goal, data, and history. Output format:
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
            # 解析AI返回内容
            if "Summary:" in content and "Recommended Classes" in content:
                ai_summary = content.split("Summary:")[1].split("Recommended Classes")[0].strip()
                ai_course_names = [line.strip() for line in content.split("Recommended Classes")[-1].split("\n") if line.strip() and not line.strip().startswith("Summary")]
            else:
                ai_summary = content
        else:
            ai_summary = "The AI recommendation service is temporarily unavailable. Please try again later."
    except Exception as e:
        ai_summary = f"AI recommendation error: {e}"

    # 根据AI返回的课程名查找详细信息
    for cname in ai_course_names:
        # 支持AI返回带序号或点号的情况
        cname_clean = cname
        if ". " in cname:
            cname_clean = cname.split(". ", 1)[1]
        elif "." in cname and cname[1] == ".":
            cname_clean = cname[2:].strip()
        # 只取课程名部分（去掉括号等）
        cname_clean = cname_clean.split("(")[0].strip()
        course = FitnessClass.objects.filter(name__icontains=cname_clean).order_by('date').first()
        if course:
            ai_courses.append(course)

    return render(request, 'booking/profile.html', {
        'ai_summary': ai_summary,
        'ai_courses': ai_courses,
        'fitness_goal': fitness_goal,
        'sports_data': sports_data,
    })



@login_required
def set_goal(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = SetGoalForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your fitness goal has been updated.")
            return redirect('profile')
    else:
        form = SetGoalForm(instance=profile)

    return render(request, 'booking/set_goal.html', {'form': form})

