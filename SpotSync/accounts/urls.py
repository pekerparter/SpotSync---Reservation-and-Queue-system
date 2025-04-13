from django.urls import path
from .views import *
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', register_view, name='register'),
    path('login/', custom_login_view, name='custom_login'),
    path('landing-page/', landing_page, name='landing_page'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
     path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('set_new_password/', SetNewPasswordView.as_view(), name='set_new_password'),
    path('categories/', views.categories, name='categories'),
    path('my-reservations/', views.my_reservations, name='my_reservations'),
    path('profile/', views.profile, name='profile'),
    path('categories/<str:category>/view-all/', views.view_all, name='view_all'),
    path('business/<int:business_id>/', views.business_detail, name='business_detail'),
    path('business/<int:business_id>/add-to-queue/', views.add_to_queue, name='add_to_queue'),
    path('business/<int:business_id>/remove-from-queue/', views.remove_from_queue, name='remove_from_queue'),
    path('business/<int:business_id>/waiting-list/', views.waiting_list, name='waiting_list'),
    path('business/<int:business_id>/reservation/', views.reservation, name='reservation'),
    path('appointment/<int:business_id>/', views.appointment, name='appointment'),
    path('book_appointment/<int:business_id>/', views.book_appointment, name='book_appointment'),
    path('reservation/<int:business_id>/', views.reservation, name='reservation'),
    path('make_reservation/<int:business_id>/', views.make_reservation, name='make_reservation'),
    path('get_available_appointment_slots/<int:business_id>/', views.get_available_appointment_slots, name='get_available_appointment_slots'),
    path('get_available_reservation_slots/<int:business_id>/', views.get_available_reservation_slots, name='get_available_reservation_slots'),
    path('cancel-booking/<str:booking_type>/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('booking/<str:booking_type>/<int:booking_id>/', views.booking_details, name='booking_details'),
]



