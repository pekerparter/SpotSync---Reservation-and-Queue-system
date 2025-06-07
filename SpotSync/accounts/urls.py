from django.urls import path
from .views import *
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', register_view, name='register'),
    path('login/', custom_login_view, name='custom_login'),
    path('landing-page/', landing_page, name='landing_page'),
    path('logout/', custom_logout, name='custom_logout'),
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
    path('business-portal/', views.business_portal, name='business_portal'),
    path('accounts/business/<int:business_id>/edit-staff/', edit_staff, name='edit_staff'),
    path('business/<int:business_id>/add-staff/', add_staff_member, name='add_staff_member'),
    path('get-role-permissions/<int:business_id>/', views.get_role_permissions, name='get_role_permissions'),
    path('update-role-permissions/<int:business_id>/', views.update_role_permissions, name='update_role_permissions'),
    path('delete-staff-member/<int:business_id>/<int:staff_id>/', views.delete_staff_member, name='delete_staff_member'),
    path('business/<int:business_id>/edit-info/', views.edit_business_info, name='edit_business_info'),
    path('business/<int:business_id>/customers/', views.business_customer_list, name='business_customer_list'),
    path('update-booking-status/<str:booking_type>/<int:booking_id>/', views.update_booking_status, name='update_booking_status'),
    path('business/<int:business_id>/edit-service/', views.edit_service, name='edit_service'),
]



