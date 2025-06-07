from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, get_user_model, logout
from django.contrib.messages import get_messages
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views import View
from django.urls import reverse_lazy
import uuid
from django.db import IntegrityError
from .models import *
from .forms import CustomUserCreationForm, PasswordResetForm, UserProfileForm
from django.utils import timezone
from django.http import Http404

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

from django.db.models import Q
from django.utils import timezone

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
           (nearest_reservation.date == nearest_appointment.date and nearest_reservation.time < nearest_appointment.time):
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

from django.contrib.auth.views import PasswordResetView
from .forms import CustomPasswordResetForm

class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')
    form_class = CustomPasswordResetForm

class SetNewPasswordView(View):
    def get(self, request):
        form = SetPasswordForm(user=request.user)
        return render(request, 'accounts/set_new_password.html', {'form': form})

    def post(self, request):
        form = SetPasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your password has been set successfully.')
            return redirect('login')
        return render(request, 'accounts/set_new_password.html', {'form': form})

from django.shortcuts import render, redirect
from .models import Category, Business

@login_required
def categories(request):
    categories = Category.objects.all().prefetch_related('businesses')
    return render(request, 'accounts/categories.html', {'categories': categories})


from django.shortcuts import render, redirect, get_object_or_404
from .models import Category, Business
def view_all(request, category):
    category_obj = get_object_or_404(Category, name__iexact=category)
    businesses = category_obj.businesses.all()
    return render(request, 'accounts/view_all.html', {'category': category_obj, 'businesses': businesses})


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Business, Queue, Category
from django.db import transaction
@login_required
def business_detail(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    categories = business.categories.all()

    # Calculate the number of people in queue
    people_in_queue = Queue.objects.filter(
        business=business,
        status__in=['in_queue', 'booked']
    ).count()

    # Update the business's people_in_queue field
    if business.people_in_queue != people_in_queue:
        business.people_in_queue = people_in_queue
        business.save()

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

from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Business, Queue
from django.utils import timezone
from datetime import time

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
            # Check if user is already in queue
            existing_queue = Queue.objects.filter(user=request.user, business=business, status='in_queue').first()
            if existing_queue:
                return JsonResponse({'status': 'error', 'message': 'You are already in the queue.'})

            # Get the last position in the queue
            last_queue = Queue.objects.filter(business=business, status='in_queue').order_by('-position').first()
            new_position = last_queue.position + 1 if last_queue else 1

            # Create new queue entry
            queue_entry = Queue.objects.create(
                user=request.user,
                business=business,
                position=new_position,
                status='in_queue'
            )

            return JsonResponse({
                'status': 'success',
                'message': 'You have been added to the queue.',
                'position': new_position,
                'estimated_wait_time': queue_entry.estimated_wait_time
            })
    except IntegrityError:
        return JsonResponse({'status': 'error', 'message': 'An error occurred. Please try again.'})
    
@login_required
def remove_from_queue(request, business_id):
    business = get_object_or_404(Business, id=business_id)

    with transaction.atomic():
        queue_entry = Queue.objects.filter(user=request.user, business=business, status='in_queue').first()

        if queue_entry:
            queue_entry.status = 'cancelled'
            queue_entry.save()
            
            business.update_queue_positions()
            
            return JsonResponse({'status': 'success', 'message': 'Removed from queue'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Not in queue'})
        
            
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Reservation, Appointment, Queue
from itertools import chain
import datetime

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

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Reservation, Appointment, Queue, Business

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
            business = booking.business

            if booking.status != 'cancelled':
                booking.status = 'cancelled'
                booking.save()

                if booking_type == 'queue':
                    business.update_queue_positions()

        return JsonResponse({'success': True, 'message': 'Booking cancelled successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
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

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from .models import Business

@login_required
def waiting_list(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    queue_entry = Queue.objects.filter(user=request.user, business=business, status='in_queue').first()

    context = {
        'business': business,
        'user_in_queue': bool(queue_entry),
    }

    if queue_entry:
        context.update({
            'position': queue_entry.position,
            'people_ahead': queue_entry.people_ahead
        })

    return render(request, 'accounts/waiting_list.html', context)

def reservation(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    today = timezone.localtime().date()
    context = {
        'business': business,
        'reservation_options': business.reservation_options or []
    }
    return render(request, 'accounts/reservation.html', context)

from django.views.decorators.http import require_GET, require_POST
from datetime import datetime, timedelta


@login_required
@require_POST
def make_reservation(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    date = request.POST.get('date')
    time = request.POST.get('time')
    option = request.POST.get('option')

    # Check if the slot is still available
    is_available = not Reservation.objects.filter(
        business=business,
        date=date,
        time=time,
        option=option if option != '' else None,
        status__in=['booked', 'in_queue']  # Only consider active reservations
    ).exists()

    if is_available:
        try:
            reservation = Reservation.objects.create(
                business=business,
                user=request.user,
                date=date,
                time=time,
                option=option if option != '' else None,
                status='booked'  # Explicitly set the status
            )
            return JsonResponse({'success': True, 'message': 'Reservation made successfully!'})
        except IntegrityError:
            return JsonResponse({'success': False, 'message': 'This slot is no longer available.'})
    else:
        return JsonResponse({'success': False, 'message': 'This slot is no longer available.'})
def appointment(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    context = {
        'business': business,
        'appointment_reasons': business.appointment_reasons or []
    }
    return render(request, 'accounts/appointment.html', context)


import logging
logger = logging.getLogger(__name__)


@require_GET
def get_available_reservation_slots(request, business_id):
    logger.info(f"Fetching slots for business_id: {business_id}")
    business = get_object_or_404(Business, id=business_id)
    date_str = request.GET.get('date')
    option = request.GET.get('option')
    logger.info(f"Date: {date_str}, Option: {option}")

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        logger.error(f"Invalid date format: {date_str}")
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    # Get business hours for the specific day
    day_of_week = date.weekday()
    business_hours = BusinessHours.objects.filter(business=business, day=day_of_week, is_working_day=True).first()

    if not business_hours:
        return JsonResponse({'slots': []})  # No slots available on this day

    # Generate time slots from opening time to closing time
    start_time = timezone.make_aware(datetime.combine(date, business_hours.opening_time))
    end_time = timezone.make_aware(datetime.combine(date, business_hours.closing_time))
    logger.info(f"Start time: {start_time}, End time: {end_time}")

    time_slots = []
    current_time = start_time
    now = timezone.localtime()
    
    while current_time < end_time:
        time_slot = current_time.strftime('%H:%M')
        is_available = True

        # Check if the slot is in the past
        if date == now.date() and current_time <= now:
            is_available = False
        else:
            # Check if the slot is already booked and not cancelled
            if option:
                active_reservations = Reservation.objects.filter(
                    business=business,
                    date=date,
                    time=time_slot,
                    option=option
                ).exclude(status='cancelled').exists()
            else:
                active_reservations = Reservation.objects.filter(
                    business=business,
                    date=date,
                    time=time_slot
                ).exclude(status='cancelled').exists()
            
            if active_reservations:
                is_available = False

        time_slots.append({
            'time': time_slot,
            'available': is_available
        })
        current_time += timedelta(minutes=business.reservation_interval)

    logger.info(f"Generated {len(time_slots)} time slots")
    return JsonResponse({'slots': time_slots})

@require_GET
def get_available_appointment_slots(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    date_str = request.GET.get('date')
    date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Get business hours for the specific day
    day_of_week = date.weekday()
    business_hours = BusinessHours.objects.filter(business=business, day=day_of_week, is_working_day=True).first()

    if not business_hours:
        return JsonResponse({'slots': []})  # No slots available on this day

    # Generate time slots for appointments
    start_time = timezone.make_aware(datetime.combine(date, business_hours.opening_time))
    end_time = timezone.make_aware(datetime.combine(date, business_hours.closing_time))
    time_slots = []

    current_time = start_time
    now = timezone.localtime()
    
    while current_time < end_time:
        time_slot = current_time.strftime('%H:%M')
        is_available = True

        # Check if the slot is in the past
        if date == now.date() and current_time <= now:
            is_available = False
        else:
            # Check if the slot is already booked and not cancelled
            active_appointments = Appointment.objects.filter(
                business=business,
                date=date,
                time=time_slot
            ).exclude(status='cancelled').exists()
            
            if active_appointments:
                is_available = False

        time_slots.append({
            'time': time_slot,
            'available': is_available
        })
        current_time += timedelta(minutes=business.appointment_interval)

    return JsonResponse({'slots': time_slots})


@require_POST
@login_required
def book_appointment(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    date = request.POST.get('date')
    time = request.POST.get('time')
    reason = request.POST.get('reason')

    # Check if the appointment slot is already booked and not cancelled
    existing_appointment = Appointment.objects.filter(
        business=business,
        date=date,
        time=time
    ).exclude(status='cancelled').exists()

    if existing_appointment:
        return JsonResponse({"success": False, "message": "This slot is already booked."})

    # Create the appointment
    appointment = Appointment.objects.create(
        business=business,
        user=request.user,
        date=date,
        time=time,
        reason=reason if reason != '' else None,
        status='booked'  # Explicitly set the status
    )

    return JsonResponse({"success": True, "message": "Appointment booked successfully!"})

from django.contrib.auth.decorators import login_required, user_passes_test

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

from django.http import HttpResponseForbidden

@login_required
@user_passes_test(is_business_staff)
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

@login_required
@user_passes_test(lambda u: u.is_business_staff)
@require_POST
def add_staff_member(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    # Ensure the user has permission to edit this business's staff
    if not business.user_has_permission(request.user, 'can_edit_staff'):
        return JsonResponse({"success": False, "message": "You don't have permission to add staff for this business."}, status=403)

    email = request.POST.get('email')
    role = request.POST.get('role')

    CustomUser = get_user_model()
    
    try:
        user = CustomUser.objects.get(email=email)
        
        # Check if the user is already a staff member of this business
        if user.business == business and user.staff_role != 'CUSTOMER':
            return JsonResponse({"success": False, "message": "This user is already a staff member of this business."})
        
        # Update the user's business and role
        user.business = business
        user.staff_role = role
        user.save()
        
        return JsonResponse({
            "success": True, 
            "message": "Staff member added successfully.",
            "staff_id": user.id,
            "full_name": user.get_full_name(),
            "email": user.email,
            "role": user.get_staff_role_display()
        })
    except CustomUser.DoesNotExist:
        return JsonResponse({"success": False, "message": "No user found with this email address."})
    
@require_GET
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
def update_role_permissions(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    for role in ['owner', 'manager', 'worker']:
        role_perm, created = BusinessRolePermission.objects.get_or_create(
            business=business,
            role=role.upper()
        )
        
        role_perm.can_edit_info = request.POST.get(f'{role}-edit-info') == 'on'
        role_perm.can_edit_service = request.POST.get(f'{role}-edit-service') == 'on'
        role_perm.can_edit_staff = request.POST.get(f'{role}-edit-staff') == 'on'
        role_perm.can_edit_availability = request.POST.get(f'{role}-availability') == 'on'
        role_perm.can_display_customers = request.POST.get(f'{role}-display') == 'on'
        
        role_perm.save()
    
    return JsonResponse({'success': True})

@require_POST
@login_required
def delete_staff_member(request, business_id, staff_id):
    business = get_object_or_404(Business, id=business_id)
    staff_member = get_object_or_404(CustomUser, id=staff_id, business=business)

    # Check if the user has permission to edit staff
    if not business.user_has_permission(request.user, 'can_edit_staff'):
        return JsonResponse({'success': False, 'message': 'You do not have permission to delete staff members.'})

    # Check role-based restrictions
    if staff_member.staff_role == 'OWNER':
        return JsonResponse({'success': False, 'message': 'The owner cannot be deleted.'})
    elif staff_member.staff_role == 'MANAGER' and request.user.staff_role != 'OWNER':
        return JsonResponse({'success': False, 'message': 'Only the owner can delete a manager.'})
    elif staff_member.staff_role == 'WORKER' and request.user.staff_role not in ['OWNER', 'MANAGER']:
        return JsonResponse({'success': False, 'message': 'Only the owner or a manager can delete a worker.'})

    # Proceed with staff deletion
    try:
        with transaction.atomic():
            staff_member.business = None
            staff_member.staff_role = 'CUSTOMER'
            staff_member.save()
        return JsonResponse({'success': True, 'message': 'Staff member removed successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    
@login_required
@user_passes_test(is_business_staff)
def edit_business_info(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    if not business.user_has_permission(request.user, 'can_edit_info'):
        messages.error(request, "You don't have permission to edit this business's information.")
        return redirect('business_portal')

    if request.method == 'POST':
        business.name = request.POST.get('name')
        business.address = request.POST.get('address')
        business.phone_number = request.POST.get('phone_number')

        if 'image' in request.FILES:
            business.image = request.FILES['image']

        business.save()
        messages.success(request, 'Business information updated successfully.')
        return redirect('business_portal')

    return render(request, 'accounts/edit_business_info.html', {'business': business})

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST

@login_required
@user_passes_test(is_business_staff)
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

    new_status = request.POST.get('status')
    if new_status not in ['booked', 'cancelled', 'done', 'in_queue']:
        return JsonResponse({'success': False, 'message': 'Invalid status'})

    try:
        with transaction.atomic():
            booking.status = new_status
            booking.save()

            if booking_type == 'queue':
                booking.business.update_queue_positions()

        return JsonResponse({'success': True, 'message': 'Booking status updated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import JsonResponse
from .models import Business, Category, BusinessHours
from datetime import datetime
import json

@login_required
@user_passes_test(lambda u: u.is_business_staff)
def edit_service(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    if request.method == 'POST':
        
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