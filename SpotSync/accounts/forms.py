from django import forms
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm

from .models import Business, CustomUser


class CustomUserCreationForm(UserCreationForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-md focus:outline-none',
            'placeholder': 'Password',
        })
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-md focus:outline-none',
            'placeholder': 'Confirm Password',
        })
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'password1', 'password2']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-md focus:outline-none',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-md focus:outline-none',
                'placeholder': 'Last Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-md focus:outline-none',
                'placeholder': 'Email'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-md focus:outline-none',
                'placeholder': 'Phone Number'
            }),
        }
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Email is already in use.")
        return email


class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'}),
        label='',
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

class EditServiceForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['opening_time', 'closing_time', 'categories', 'reservation_options', 'appointment_reasons']
        widgets = {
            'opening_time': forms.TimeInput(attrs={'type': 'time'}),
            'closing_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    reservation_options = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': 'Enter options, one per line'}))
    appointment_reasons = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': 'Enter reasons, one per line'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.reservation_options:
            self.fields['reservation_options'].initial = '\n'.join(self.instance.reservation_options)
        if self.instance.appointment_reasons:
            self.fields['appointment_reasons'].initial = '\n'.join(self.instance.appointment_reasons)

    def clean(self):
        cleaned_data = super().clean()
        reservation_options = cleaned_data.get('reservation_options')
        appointment_reasons = cleaned_data.get('appointment_reasons')

        if reservation_options:
            cleaned_data['reservation_options'] = [option.strip() for option in reservation_options.split('\n') if option.strip()]
        else:
            cleaned_data['reservation_options'] = None

        if appointment_reasons:
            cleaned_data['appointment_reasons'] = [reason.strip() for reason in appointment_reasons.split('\n') if reason.strip()]
        else:
            cleaned_data['appointment_reasons'] = None

        return cleaned_data
