from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views import View
from django.urls import reverse_lazy
import uuid
from django.db import IntegrityError
from .models import CustomUser, Category, Business, Reservation, Queue, Appointment
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

def custom_login_view(request):
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
    now = timezone.now()
    upcoming_booking = None
    
    # Check for the nearest reservation
    nearest_reservation = Reservation.objects.filter(
        user=request.user,
        date__gte=now.date()
    ).order_by('date', 'time').first()
    
    # Check for the nearest appointment
    nearest_appointment = Appointment.objects.filter(
        user=request.user,
        date__gte=now.date()
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

def booking_details(request, booking_type, booking_id):
    if booking_type == 'reservation':
        booking = get_object_or_404(Reservation, id=booking_id)
    elif booking_type == 'appointment':
        booking = get_object_or_404(Appointment, id=booking_id)
    elif booking_type == 'queue':
        booking = get_object_or_404(Queue, id=booking_id)
        booking.status = 'in_queue'  # Add a status for Queue objects
    else:
        raise Http404("Invalid booking type")

    context = {
        'booking': booking,
        'booking_type': booking_type,
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
@login_required
def business_detail(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    categories = business.categories.all()

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
        }
        return render(request, 'accounts/business_category_choice.html', context)
    else:
        # If no relevant categories, show a generic detail page
        user_in_queue = Queue.objects.filter(user=request.user, business=business).exists()
        context = {
            'business': business,
            'user_in_queue': user_in_queue,
        }
        return render(request, 'accounts/business_detail.html', context)


@login_required
def add_to_queue(request, business_id):
    business = get_object_or_404(Business, id=business_id)

    if not Queue.objects.filter(user=request.user, business=business).exists():
        Queue.objects.create(user=request.user, business=business)
        business.people_in_queue += 1
        business.save()
        return JsonResponse({'status': 'success', 'message': 'Added to queue'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Already in queue'})

@login_required
def remove_from_queue(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    queue_entry = Queue.objects.filter(user=request.user, business=business).first()

    if queue_entry:
        queue_entry.delete()
        business.people_in_queue -= 1
        business.save()
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

    # Combine all bookings
    all_bookings = list(chain(reservations, appointments, queues))

    # Sort the bookings
    all_bookings.sort(key=lambda x: (x.date, x.time if isinstance(x.time, str) else x.time.strftime('%H:%M')), reverse=True)

    # Prepare bookings for template
    bookings = []
    for booking in all_bookings:
        booking_type = booking.__class__.__name__.lower()
        if booking_type == 'queue':
            status = 'in_queue'
            can_cancel = True
        elif booking_type in ['reservation', 'appointment']:
            status = booking.status if hasattr(booking, 'status') else 'booked'
            can_cancel = status == 'booked'
        else:
            continue

        bookings.append({
            'id': booking.id,
            'date': booking.date,
            'time': booking.time if isinstance(booking.time, str) else booking.time.strftime('%H:%M'),
            'business': booking.business,
            'booking_type': booking_type,
            'status': status,
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
            if booking_type == 'queue':
                business = booking.business
                business.people_in_queue = max(0, business.people_in_queue - 1)
                business.save()
                booking.delete()
            elif booking_type in ['reservation', 'appointment']:
                if hasattr(booking, 'status'):
                    booking.status = 'cancelled'
                    booking.save()
                else:
                    booking.delete()
            else:
                return JsonResponse({'success': False, 'message': 'Booking cannot be cancelled'})

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
    user_in_queue = Queue.objects.filter(user=request.user, business=business).exists()

    context = {
        'business': business,
        'user_in_queue': user_in_queue,
    }
    return render(request, 'accounts/waiting_list.html', context)

def reservation(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    today = timezone.localtime(timezone.now()).date()
    return render(request, 'accounts/reservation.html', {'business': business})

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
        option=option
    ).exists()

    if is_available:
        try:
            reservation = Reservation.objects.create(
                business=business,
                user=request.user,
                date=date,
                time=time,
                option=option
            )
            return JsonResponse({'success': True, 'message': 'Reservation made successfully!'})
        except IntegrityError:
            return JsonResponse({'success': False, 'message': 'This slot is no longer available.'})
    else:
        return JsonResponse({'success': False, 'message': 'This slot is no longer available.'})
def appointment(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    return render(request, 'accounts/appointment.html', {'business': business})


@require_GET
def get_available_reservation_slots(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    date_str = request.GET.get('date')
    option = request.GET.get('option')
    date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Generate time slots from opening time to closing time
    start_time = timezone.make_aware(datetime.combine(date, datetime.strptime(business.opening_time, '%H:%M').time()))
    end_time = timezone.make_aware(datetime.combine(date, datetime.strptime(business.closing_time, '%H:%M').time()))
    time_slots = []

    current_time = start_time
    now = timezone.localtime(timezone.now())
    
    while current_time < end_time:
        time_slot = current_time.strftime('%H:%M')
        is_available = True

        # Check if the slot is in the past
        if date == now.date() and current_time <= now:
            is_available = False
        else:
            # Check if the slot is already booked for this specific option
            is_booked = Reservation.objects.filter(
                business=business,
                date=date,
                time=time_slot,
                option=option
            ).exists()
            if is_booked:
                is_available = False

        time_slots.append({
            'time': time_slot,
            'available': is_available
        })
        current_time += timedelta(minutes=60)  # 1-hour slots

    return JsonResponse({'slots': time_slots})

@require_GET
def get_available_appointment_slots(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    date_str = request.GET.get('date')
    date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Generate time slots for appointments (example: 30-minute slots)
    start_time = datetime.combine(date, datetime.strptime(business.opening_time, '%H:%M').time())
    end_time = datetime.combine(date, datetime.strptime(business.closing_time, '%H:%M').time())
    time_slots = []

    current_time = start_time
    now = timezone.localtime(timezone.now())
    
    while current_time < end_time:
        time_slot = current_time.strftime('%H:%M')
        is_available = True

        # Check if the slot is in the past
        if date == now.date() and current_time <= now:
            is_available = False
        else:
            # Check if the slot is already booked
            is_available = not Appointment.objects.filter(
                business=business,
                date=date,
                time=time_slot
            ).exists()

        time_slots.append({
            'time': time_slot,
            'available': is_available
        })
        current_time += timedelta(minutes=30)

    return JsonResponse({'slots': time_slots})

@require_GET
def get_available_appointment_slots(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    date_str = request.GET.get('date')
    date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Generate time slots for appointments (example: 30-minute slots)
    start_time = timezone.make_aware(datetime.combine(date, datetime.strptime(business.opening_time, '%H:%M').time()))
    end_time = timezone.make_aware(datetime.combine(date, datetime.strptime(business.closing_time, '%H:%M').time()))
    time_slots = []

    current_time = start_time
    now = timezone.localtime(timezone.now())
    
    while current_time < end_time:
        time_slot = current_time.strftime('%H:%M')
        is_available = True

        # Check if the slot is in the past
        if date == now.date() and current_time <= now:
            is_available = False
        else:
            # Check if the slot is already booked
            is_available = not Appointment.objects.filter(
                business=business,
                date=date,
                time=time_slot
            ).exists()

        time_slots.append({
            'time': time_slot,
            'available': is_available
        })
        current_time += timedelta(minutes=30)

    return JsonResponse({'slots': time_slots})


@require_POST
@login_required
def book_appointment(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    date = request.POST.get('date')
    time = request.POST.get('time')
    reason = request.POST.get('reason')

    # Check if the appointment slot is already booked
    existing_appointment = Appointment.objects.filter(
        business=business,
        date=date,
        time=time
    ).exists()

    if existing_appointment:
        return JsonResponse({"success": False, "message": "This slot is already booked."})

    # Create the appointment
    appointment = Appointment.objects.create(
        business=business,
        user=request.user,
        date=date,
        time=time,
        reason=reason
    )

    return JsonResponse({"success": True, "message": "Appointment booked successfully!"})