from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('classes/', views.class_list, name='class_list'),
    path('book/<int:class_id>/', views.book_class, name='book_class'),
    path('cancel/<int:reservation_id>/', views.cancel_reservation, name='cancel_reservation'),
    path('my_reservations/', views.my_reservations, name='my_reservations'),
    path('admin_reservations/', views.admin_reservations, name='admin_reservations'),
    path('rate/<int:reservation_id>/', views.rate_class, name='rate_class'),
    path('all-feedback/', views.view_all_feedback, name='all_feedback'),
    path('rebook_confirm/<int:reservation_id>/', views.rebook_confirm, name='rebook_confirm'),
    path('rebook_final/<int:reservation_id>/', views.rebook_final, name='rebook_final'),
    path('profile/', views.profile, name='profile'),
    path('set_goal/', views.set_goal, name='set_goal'),






]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



