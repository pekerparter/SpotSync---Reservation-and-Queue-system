"""Customer bookings, queues, and business staff views."""

import json
import logging
import uuid
from datetime import datetime
from itertools import chain

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.views import PasswordResetView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_GET, require_POST

from .bookings import available_slots, parse_date, validate_booking
from .forms import CustomPasswordResetForm, CustomUserCreationForm, UserProfileForm
from .models import (
    Appointment,
    Business,
    BusinessHours,
    BusinessRolePermission,
    Category,
    CustomUser,
    Queue,
    Reservation,
)
from .permissions import business_permission_required, can_assign_staff_role


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)  # Create a user instance without saving to the database
            user.username = str(uuid.uuid4())[:8]
            user.set_password(form.cleaned_data['password1'])  # Hash the password
            user.save()  # Save the user to the database
            messages.success(request, 'Registration successful! You can now log in.')
            return redirect('custom_login')  # Redirect to the login page
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def custom_logout(request):
    messages.get_messages(request).used = True
    storage = messages.get_messages(request)
    storage.used = True
    for _ in storage:
        pass  # Iterate through messages to mark them as used
    logout(request)
    return redirect('landing_page')

def custom_login_view(request):
    storage = messages.get_messages(request)
    storage.used = True
    for _ in storage:
        pass
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')  # The form still uses 'username' field
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)  # Authenticate using email
            if user is not None:
                login(request, user)
                return redirect('landing_page')  # Redirect on successful login
            else:
                messages.error(request, 'Invalid email or password.')
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def landing_page(request):
    categories = Category.objects.all()[:3]  # Limit to 3 categories for the landing page
    
    # Get the nearest upcoming reservation or appointment
    now = timezone.localtime()
    upcoming_booking = None
    
    # Check for the nearest reservation
    nearest_reservation = Reservation.objects.filter(
        user=request.user,
        date__gte=now.date(),
        status__in=['booked', 'in_queue']
    ).order_by('date', 'time').first()
    
    # Check for the nearest appointment
    nearest_appointment = Appointment.objects.filter(
        user=request.user,
        date__gte=now.date(),
        status__in=['booked', 'in_queue']
    ).order_by('date', 'time').first()
    
    # Determine which is sooner
    if nearest_reservation and nearest_appointment:
        if nearest_reservation.date < nearest_appointment.date or \
           (nearest_reservation.date == nearest_appointment.date and nearest_reservation.time < nearest_appointment.time.strftime('%H:%M')):
            upcoming_booking = nearest_reservation
        else:
            upcoming_booking = nearest_appointment
    elif nearest_reservation:
        upcoming_booking = nearest_reservation
    elif nearest_appointment:
        upcoming_booking = nearest_appointment
    
    return render(request, 'accounts/landing_page.html', {
        'user': request.user,
        'categories': categories,
        'upcoming_booking': upcoming_booking
    })

@login_required
def booking_details(request, booking_type, booking_id):
    if booking_type == 'reservation':
        booking = get_object_or_404(Reservation, id=booking_id, user=request.user)
    elif booking_type == 'appointment':
        booking = get_object_or_404(Appointment, id=booking_id, user=request.user)
    elif booking_type == 'queue':
        booking = get_object_or_404(Queue, id=booking_id, user=request.user)
    else:
        raise Http404("Invalid booking type")

    # Adjust the status for queue entries
    display_status = booking.status
    if booking_type == 'queue' and booking.status == 'booked':
        display_status = 'in_queue'

    context = {
        'booking': booking,
        'booking_type': booking_type,
        'display_status': display_status,
    }
    return render(request, 'accounts/booking_details.html', context)


class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')
    form_class = CustomPasswordResetForm

@method_decorator(login_required, name='dispatch')
class SetNewPasswordView(View):
    def get(self, request):
        form = SetPasswordForm(user=request.user)
        return render(request, 'accounts/set_new_password.html', {'form': form})

    def post(self, request):
        form = SetPasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your password has been set successfully.')
            return redirect('custom_login')
        return render(request, 'accounts/set_new_password.html', {'form': form})


@login_required
def categories(request):
    categories = Category.objects.all().prefetch_related('businesses')
    return render(request, 'accounts/categories.html', {'categories': categories})


def view_all(request, category):
    category_obj = get_object_or_404(Category, name__iexact=category)
    businesses = category_obj.businesses.all()
    return render(request, 'accounts/view_all.html', {'category': category_obj, 'businesses': businesses})


@login_required
def business_detail(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    categories = business.categories.all()

    # Calculate the number of people in queue
    people_in_queue = Queue.objects.filter(
        business=business,
        status='in_queue'
    ).count()

    relevant_categories = []
    if any(category.name.lower() == 'waiting list' for category in categories):
        relevant_categories.append(('waiting_list', 'Waiting List'))
    if any(category.name.lower() == 'reservations' for category in categories):
        relevant_categories.append(('reservation', 'Reservations'))
    if any(category.name.lower() == 'appointments' for category in categories):
        relevant_categories.append(('appointment', 'Appointments'))

    if len(relevant_categories) == 1:
        # If there's only one relevant category, redirect to that page
        return redirect(relevant_categories[0][0], business_id=business_id)
    elif len(relevant_categories) > 1:
        # If there are multiple relevant categories, show options to the user
        context = {
            'business': business,
            'categories': relevant_categories,
            'people_in_queue': people_in_queue,
        }
        return render(request, 'accounts/business_category_choice.html', context)
    else:
        # If no relevant categories, show a generic detail page
        user_in_queue = Queue.objects.filter(user=request.user, business=business).exists()
        context = {
            'business': business,
            'user_in_queue': user_in_queue,
            'people_in_queue': people_in_queue,
        }
        return render(request, 'accounts/business_detail.html', context)


@require_POST
@login_required
def add_to_queue(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    # Get current day and time
    now = timezone.localtime()
    current_day = now.weekday()
    current_time = now.time()

    # Get business hours for the current day
    business_hours = BusinessHours.objects.filter(business=business, day=current_day).first()

    if not business_hours or not business_hours.is_working_day:
        return JsonResponse({'status': 'error', 'message': 'The business is closed today.'})

    opening_time = business_hours.opening_time
    closing_time = business_hours.closing_time

    # Check if current time is within business hours
    if current_time < opening_time or current_time > closing_time:
        return JsonResponse({'status': 'error', 'message': 'The business is currently closed.'})

    # Proceed with adding to queue if within business hours
    try:
        with transaction.atomic():
            Business.objects.select_for_update().get(pk=business_id)
            # Check if user is already in queue
            existing_queue = Queue.objects.filter(user=request.user, business=business, status='in_queue').first()
            if existing_queue:
                return JsonResponse({'status': 'error', 'message': 'You are already in the queue.'})

            # Create new queue entry
            queue_entry = Queue.objects.create(
                user=request.user,
                business=business,
                status='in_queue'
            )

            return JsonResponse({
                'status': 'success',
                'message': 'You have been added to the queue.',
                'position': queue_entry.position,
                'estimated_wait_time': queue_entry.estimated_wait_time
            })
    except IntegrityError:
        return JsonResponse({'status': 'error', 'message': 'An error occurred. Please try again.'})
    
@require_POST
@login_required
def remove_from_queue(request, business_id):
    business = get_object_or_404(Business, id=business_id)

    with transaction.atomic():
        Business.objects.select_for_update().get(pk=business_id)
        queue_entry = Queue.objects.filter(user=request.user, business=business, status='in_queue').first()

        if queue_entry:
            queue_entry.status = 'cancelled'
            queue_entry.save()
            
            business.update_queue_positions()
            
            return JsonResponse({'status': 'success', 'message': 'Removed from queue'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Not in queue'})
        
            

@login_required
def my_reservations(request):
    reservations = Reservation.objects.filter(user=request.user)
    appointments = Appointment.objects.filter(user=request.user)
    queues = Queue.objects.filter(user=request.user)

    all_bookings = list(chain(reservations, appointments, queues))
    all_bookings.sort(key=lambda x: (x.date, x.time if isinstance(x.time, str) else x.time.strftime('%H:%M')), reverse=True)

    bookings = []
    for booking in all_bookings:
        booking_type = booking.__class__.__name__.lower()
        can_cancel = booking.status == 'booked' or (booking_type == 'queue' and booking.status == 'in_queue')

        # Adjust the status for queue entries
        display_status = booking.status
        if booking_type == 'queue' and booking.status == 'booked':
            display_status = 'in_queue'

        bookings.append({
            'id': booking.id,
            'date': booking.date,
            'time': booking.time if isinstance(booking.time, str) else booking.time.strftime('%H:%M'),
            'business': booking.business,
            'booking_type': booking_type,
            'status': display_status,
            'can_cancel': can_cancel,
            'reason': getattr(booking, 'reason', ''),
            'option': getattr(booking, 'option', ''),
            'created_at': booking.created_at,
        })

    return render(request, 'accounts/my_reservations.html', {'bookings': bookings})


@require_POST
@login_required
def cancel_booking(request, booking_type, booking_id):
    if booking_type == 'reservation':
        booking = get_object_or_404(Reservation, id=booking_id, user=request.user)
    elif booking_type == 'appointment':
        booking = get_object_or_404(Appointment, id=booking_id, user=request.user)
    elif booking_type == 'queue':
        booking = get_object_or_404(Queue, id=booking_id, user=request.user)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid booking type'})

    try:
        with transaction.atomic():
            Business.objects.select_for_update().get(pk=booking.business_id)
            business = booking.business

            if booking.status != 'cancelled':
                booking.status = 'cancelled'
                booking.save()

                if booking_type == 'queue':
                    business.update_queue_positions()

        return JsonResponse({'success': True, 'message': 'Booking cancelled successfully'})
    except Exception:
        return JsonResponse({'success': False, 'message': 'The operation could not be completed.'})
@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Your profile has been updated successfully.')
                return redirect('profile')
            except IntegrityError:
                messages.error(request, 'An error occurred. Please try again.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def waiting_list(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    queue_entry = Queue.objects.filter(user=request.user, business=business, status='in_queue').first()

    # Check if the business is open
    now = timezone.localtime()
    current_day = now.weekday()
    current_time = now.time()
    business_hours = BusinessHours.objects.filter(business=business, day=current_day).first()
    
    is_open = False
    if business_hours and business_hours.is_working_day:
        if business_hours.opening_time <= current_time <= business_hours.closing_time:
            is_open = True

    context = {
        'business': business,
        'user_in_queue': bool(queue_entry),
        'is_open': is_open,
    }

    if queue_entry:
        context.update({
            'position': queue_entry.position,
            'people_ahead': queue_entry.people_ahead,
        })

    return render(request, 'accounts/waiting_list.html', context)

def reservation(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    context = {
        'business': business,
        'reservation_options': business.reservation_options or [],
    }
    return render(request, 'accounts/reservation.html', context)


@login_required
@require_POST
def make_reservation(request, business_id):
    option = request.POST.get('option') or None
    try:
        with transaction.atomic():
            business = get_object_or_404(Business.objects.select_for_update(), pk=business_id)
            if (business.reservation_options and option not in business.reservation_options) or (not business.reservation_options and option):
                return JsonResponse({'success': False, 'message': 'Invalid reservation option.'}, status=400)
            day, available = validate_booking(business, request.POST.get('date'), request.POST.get('time'), 'reservation', option)
            if not available:
                return JsonResponse({'success': False, 'message': 'This slot is no longer available.'})
            Reservation.objects.create(business=business, user=request.user, date=day,
                                       time=request.POST['time'], option=option, status='booked')
    except ValueError as error:
        return JsonResponse({'success': False, 'message': str(error)}, status=400)
    except IntegrityError:
        return JsonResponse({'success': False, 'message': 'This slot is no longer available.'})
    return JsonResponse({'success': True, 'message': 'Reservation made successfully!'})
def appointment(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    context = {
        'business': business,
        'appointment_reasons': business.appointment_reasons or [],
    }
    return render(request, 'accounts/appointment.html', context)


logger = logging.getLogger(__name__)


@require_GET
def get_available_reservation_slots(request, business_id):
    business = get_object_or_404(Business, pk=business_id)
    try:
        day = parse_date(request.GET.get('date'))
        slots = available_slots(business, day, 'reservation', request.GET.get('option'))
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'slots': slots})

@require_GET
def get_available_appointment_slots(request, business_id):
    business = get_object_or_404(Business, pk=business_id)
    try:
        day = parse_date(request.GET.get('date'))
        slots = available_slots(business, day, 'appointment', request.GET.get('option'))
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'slots': slots})


@require_POST
@login_required
def book_appointment(request, business_id):
    reason = request.POST.get('reason') or None
    try:
        with transaction.atomic():
            business = get_object_or_404(Business.objects.select_for_update(), pk=business_id)
            if reason and reason not in business.appointment_reasons:
                return JsonResponse({'success': False, 'message': 'Invalid appointment reason.'}, status=400)
            day, available = validate_booking(business, request.POST.get('date'), request.POST.get('time'), 'appointment')
            if not available:
                return JsonResponse({'success': False, 'message': 'This slot is already booked or unavailable.'})
            Appointment.objects.create(business=business, user=request.user, date=day,
                                       time=request.POST['time'], reason=reason, status='booked')
    except ValueError as error:
        return JsonResponse({'success': False, 'message': str(error)}, status=400)
    return JsonResponse({'success': True, 'message': 'Appointment booked successfully!'})


def is_business_staff(user):
    return user.is_business_staff

@login_required
@user_passes_test(is_business_staff)
def business_portal(request):
    business = request.user.business
    context = {
        'business': business,
        'can_edit_info': business.user_has_permission(request.user, 'can_edit_info'),
        'can_edit_staff': business.user_has_permission(request.user, 'can_edit_staff'),
        'can_display_customers': business.user_has_permission(request.user, 'can_display_customers'),
        'can_edit_service': business.user_has_permission(request.user, 'can_edit_service'),
    }
    return render(request, 'accounts/business_portal.html', context)


@business_permission_required('can_edit_staff')
def edit_staff(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    # Ensure the user has permission to edit this business's staff
    if not business.user_has_permission(request.user, 'can_edit_staff'):
        return HttpResponseForbidden("You don't have permission to edit staff for this business.")

    # Get all staff members for this business
    CustomUser = get_user_model()
    staff_members = CustomUser.objects.filter(business=business).exclude(staff_role='CUSTOMER')

    context = {
        'business': business,
        'staff_members': staff_members,
    }
    return render(request, 'accounts/edit_staff.html', context)

@require_POST
@business_permission_required('can_edit_staff')
def add_staff_member(request, business_id):
    business = request.business
    email = request.POST.get('email', '')
    role = request.POST.get('role')
    try:
        with transaction.atomic():
            Business.objects.select_for_update().get(pk=business.pk)
            user = CustomUser.objects.select_for_update().get(email=email)
            if not can_assign_staff_role(request.user, user, role):
                return JsonResponse({'success': False, 'message': 'Invalid or forbidden staff role.'}, status=403)
            if user.business_id == business.pk and user.staff_role != 'CUSTOMER':
                return JsonResponse({'success': False, 'message': 'This user is already a staff member of this business.'})
            if user.business_id is not None and user.business_id != business.pk:
                return JsonResponse({'success': False, 'message': 'This user is already associated with another business.'})
            user.business = business
            user.staff_role = role
            user.save(update_fields=['business', 'staff_role'])
        return JsonResponse({
            'success': True, 'message': 'Staff member added successfully.',
            'staff_id': user.pk, 'full_name': user.get_full_name(),
            'email': user.email, 'role': user.get_staff_role_display(),
        })
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'No user found with this email address.'})
    except CustomUser.MultipleObjectsReturned:
        return JsonResponse({'success': False, 'message': 'Email identifies more than one account.'}, status=400)
    
@require_GET
@business_permission_required('can_edit_staff')
def get_role_permissions(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    permissions = {
        'owner': {},
        'manager': {},
        'worker': {}
    }
    
    for role in permissions.keys():
        role_perm = BusinessRolePermission.objects.filter(business=business, role=role.upper()).first()
        if role_perm:
            permissions[role] = {
                'edit_info': role_perm.can_edit_info,
                'edit_service': role_perm.can_edit_service,
                'edit_staff': role_perm.can_edit_staff,
                'availability': role_perm.can_edit_availability,
                'display': role_perm.can_display_customers
            }
        else:
            # Set default permissions if not found in the database
            permissions[role] = {
                'edit_info': role == 'owner',
                'edit_service': role == 'owner',
                'edit_staff': role == 'owner',
                'availability': True,
                'display': True
            }
    
    return JsonResponse(permissions)

@require_POST
@business_permission_required(owner_only=True)
def update_role_permissions(request, business_id):
    with transaction.atomic():
        Business.objects.select_for_update().get(pk=business_id)
        for role in ['owner', 'manager', 'worker']:
            role_perm, _ = BusinessRolePermission.objects.get_or_create(
                business=request.business, role=role.upper(),
            )
            for field, suffix in {
                'can_edit_info': 'edit-info', 'can_edit_service': 'edit-service',
                'can_edit_staff': 'edit-staff', 'can_edit_availability': 'availability',
                'can_display_customers': 'display',
            }.items():
                setattr(role_perm, field, request.POST.get(f'{role}-{suffix}') == 'on')
            role_perm.save()
    return JsonResponse({'success': True})

@require_POST
@business_permission_required('can_edit_staff')
def delete_staff_member(request, business_id, staff_id):
    with transaction.atomic():
        Business.objects.select_for_update().get(pk=business_id)
        staff = get_object_or_404(CustomUser.objects.select_for_update(), pk=staff_id, business_id=business_id)
        if staff.staff_role == 'OWNER':
            return JsonResponse({'success': False, 'message': 'The owner cannot be deleted.'})
        if not can_assign_staff_role(request.user, staff, 'WORKER'):
            return JsonResponse({'success': False, 'message': 'You do not have permission to remove this staff member.'}, status=403)
        staff.business = None
        staff.staff_role = 'CUSTOMER'
        staff.save(update_fields=['business', 'staff_role'])
    return JsonResponse({'success': True, 'message': 'Staff member removed successfully'})
    
@business_permission_required('can_edit_info')
def edit_business_info(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    if not business.user_has_permission(request.user, 'can_edit_info'):
        messages.error(request, "You don't have permission to edit this business's information.")
        return redirect('business_portal')

    if request.method == 'POST':
        business.name = request.POST.get('name')
        business.address = request.POST.get('address')
        business.phone_number = request.POST.get('phone_number')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        if latitude and longitude:
            business.latitude = float(latitude)
            business.longitude = float(longitude)

        if 'image' in request.FILES:
            business.image = request.FILES['image']

        # Geocode the address
        lat, lng = geocode_address(business.address)
        if lat is not None and lng is not None:
            business.latitude = lat
            business.longitude = lng

        business.save(update_fields=['name', 'address', 'phone_number', 'latitude', 'longitude', 'image'])
        messages.success(request, 'Business information updated successfully.')
        return redirect('business_portal')

    context = {
        'business': business,
    }
    return render(request, 'accounts/edit_business_info.html', context)

@business_permission_required('can_display_customers')
def business_customer_list(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    # Check if the user has permission to view this data
    if not business.user_has_permission(request.user, 'can_display_customers'):
        return redirect('landing_page')  # or wherever you want to redirect unauthorized users

    reservations = Reservation.objects.filter(business=business).order_by('date', 'time')
    appointments = Appointment.objects.filter(business=business).order_by('date', 'time')
    queues = Queue.objects.filter(business=business).order_by('date', 'time')

    context = {
        'business': business,
        'booking_data': {
            'reservations': reservations,
            'appointments': appointments,
            'queues': queues,
        },
    }

    return render(request, 'accounts/business_customer_list.html', context)

@require_POST
@login_required
@user_passes_test(is_business_staff)
def update_booking_status(request, booking_type, booking_id):
    if booking_type == 'reservation':
        booking = get_object_or_404(Reservation, id=booking_id, business__staff=request.user)
    elif booking_type == 'appointment':
        booking = get_object_or_404(Appointment, id=booking_id, business__staff=request.user)
    elif booking_type == 'queue':
        booking = get_object_or_404(Queue, id=booking_id, business__staff=request.user)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid booking type'})

    if not booking.business.user_has_permission(request.user, 'can_display_customers'):
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)

    new_status = request.POST.get('status')
    if new_status not in dict(booking._meta.get_field('status').choices):
        return JsonResponse({'success': False, 'message': 'Invalid status'})

    try:
        with transaction.atomic():
            Business.objects.select_for_update().get(pk=booking.business_id)
            if new_status == 'booked' and booking_type in {'reservation', 'appointment'}:
                others = type(booking).objects.filter(business=booking.business, date=booking.date, time=booking.time).exclude(pk=booking.pk).exclude(status='cancelled')
                if booking_type == 'reservation':
                    others = others.filter(option=booking.option)
                if others.exists():
                    return JsonResponse({'success': False, 'message': 'This slot is already booked.'})
            booking.status = new_status
            booking.save()

            if booking_type == 'queue':
                booking.business.update_queue_positions()

        return JsonResponse({'success': True, 'message': 'Booking status updated successfully'})
    except Exception:
        return JsonResponse({'success': False, 'message': 'The operation could not be completed.'})
    


@business_permission_required('can_edit_service')
def edit_service(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    if request.method == 'POST':
        try:
            for field, default in [('reservation_interval', 60), ('appointment_interval', 30)]:
                if int(request.POST.get(field, default)) <= 0:
                    raise ValueError
            if int(request.POST.get('time_per_customer', 0)) < 0:
                raise ValueError
            for field in ['reservation_options', 'appointment_reasons']:
                values = json.loads(request.POST.get(field, '[]'))
                if not isinstance(values, list) or any(not isinstance(value, str) or len(value) > 255 for value in values):
                    raise ValueError
            for day in range(7):
                for field in ['opening_time', 'closing_time']:
                    value = request.POST.get(f'{field}_{day}')
                    if value:
                        datetime.strptime(value, '%H:%M')
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Invalid service configuration.'}, status=400)
        
        with transaction.atomic():
            # Handle service types
            service_types = request.POST.getlist('service_types')
            business.categories.clear()
            for service_type in service_types:
                category_name = {
                    'reservations': 'Reservations',
                    'appointments': 'Appointments',
                    'Waiting list': 'Waiting list'
                }.get(service_type)
                if category_name:
                    category, _ = Category.objects.get_or_create(name=category_name)
                    business.categories.add(category)
                else:
                    print(f"Unexpected service type: {service_type}")

            # Handle business hours
            for day in range(7):
                is_working_day = request.POST.get(f'working_day_{day}') == 'on'
                opening_time = request.POST.get(f'opening_time_{day}')
                closing_time = request.POST.get(f'closing_time_{day}')

                business_hours, created = BusinessHours.objects.get_or_create(
                    business=business,
                    day=day,
                    defaults={
                        'is_working_day': is_working_day,
                        'opening_time': opening_time or '09:00',  # Default to 09:00 if not provided
                        'closing_time': closing_time or '17:00'   # Default to 17:00 if not provided
                    }
                )

                if not created:
                    business_hours.is_working_day = is_working_day
                    business_hours.opening_time = opening_time or business_hours.opening_time
                    business_hours.closing_time = closing_time or business_hours.closing_time
                    business_hours.save()

            # Handle other fields
            reservation_options = json.loads(request.POST.get('reservation_options', '[]'))
            appointment_reasons = json.loads(request.POST.get('appointment_reasons', '[]'))

            business.reservation_options = [option.strip() for option in reservation_options if option.strip()]
            business.appointment_reasons = [reason.strip() for reason in appointment_reasons if reason.strip()]
            business.reservation_interval = int(request.POST.get('reservation_interval', 60))
            business.appointment_interval = int(request.POST.get('appointment_interval', 30))
            business.enable_time_estimation = request.POST.get('enable_time_estimation') == 'on'
            business.time_per_customer = int(request.POST.get('time_per_customer', 0)) or None

            business.save()
            business.update_queue_positions()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('business_portal')
    
    current_categories = list(business.categories.values_list('name', flat=True))
    business_hours = business.get_business_hours()
    
    context = {
        'business': business,
        'current_categories': current_categories,
        'business_hours': business_hours,
        'reservation_options': json.dumps(business.reservation_options),
        'appointment_reasons': json.dumps(business.appointment_reasons),
    }
    return render(request, 'accounts/edit_service.html', context)

def geocode_address(address):
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        return None, None
    try:
        response = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'address': address, 'key': api_key}, timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'OK':
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        # Do not log exception URLs: transport errors may include the API key.
        logger.warning('Geocoding failed; preserving the existing coordinates.')
    return None, None


@require_POST
@business_permission_required('can_edit_staff')
def update_staff_member(request, business_id, staff_id):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'success': False, 'message': 'Invalid JSON.'}, status=400)
    if not isinstance(data, dict) or not isinstance(data.get('email'), str):
        return JsonResponse({'success': False, 'message': 'A valid email and staff role are required.'}, status=400)
    email, role = data['email'].strip(), data.get('role')
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'success': False, 'message': 'Invalid email address.'}, status=400)
    with transaction.atomic():
        Business.objects.select_for_update().get(pk=business_id)
        staff = get_object_or_404(CustomUser.objects.select_for_update(), pk=staff_id, business_id=business_id)
        if not can_assign_staff_role(request.user, staff, role):
            return JsonResponse({'success': False, 'message': 'Invalid or forbidden staff role.'}, status=403)
        if CustomUser.objects.filter(email=email).exclude(pk=staff.pk).exists():
            return JsonResponse({'success': False, 'message': 'Email is already in use.'}, status=400)
        staff.email, staff.staff_role = email, role
        staff.save(update_fields=['email', 'staff_role'])
    return JsonResponse({'success': True, 'full_name': staff.get_full_name(),
                         'email': staff.email, 'role': staff.get_staff_role_display()})
