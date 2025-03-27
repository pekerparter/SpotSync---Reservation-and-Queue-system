from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views import View
from django.urls import reverse_lazy
import uuid
from django.db import IntegrityError
from .models import CustomUser, Category
from .forms import CustomUserCreationForm, PasswordResetForm, UserProfileForm

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

@login_required
def landing_page(request):
    categories = Category.objects.all()[:3]  # Limit to 3 categories for the landing page
    return render(request, 'accounts/landing_page.html', {
        'user': request.user,
        'categories': categories
    })


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
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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

@login_required
def my_reservations(request):
    return render(request, 'accounts/my_reservations.html')


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
    return render(request, 'accounts/reservation.html', {'business': business})

def appointment(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    return render(request, 'accounts/appointment.html', {'business': business})
