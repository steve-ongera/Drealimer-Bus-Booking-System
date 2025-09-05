from django import forms
from django.core.exceptions import ValidationError
from .models import Location, Booking

class SearchForm(forms.Form):
    origin = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        empty_label="From",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'origin-select'
        })
    )
    destination = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        empty_label="To",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'destination-select'
        })
    )
    travel_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': '2025-01-01'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        origin = cleaned_data.get('origin')
        destination = cleaned_data.get('destination')
        
        if origin and destination and origin == destination:
            raise ValidationError("Origin and destination cannot be the same.")
        
        return cleaned_data

class GuestBookingForm(forms.Form):
    passenger_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full Name'
        })
    )
    passenger_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )
    passenger_phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone Number (e.g., 0712345678)'
        })
    )
    passenger_id_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ID Number'
        })
    )
    passenger_age = forms.IntegerField(
        min_value=1,
        max_value=120,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Age'
        })
    )
    is_kenyan = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean_passenger_phone(self):
        phone = self.cleaned_data['passenger_phone']
        # Basic Kenyan phone number validation
        if not phone.startswith('0') and not phone.startswith('+254'):
            raise ValidationError("Please enter a valid Kenyan phone number.")
        return phone

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            'passenger_name', 'passenger_email', 'passenger_phone',
            'passenger_id_number', 'passenger_age', 'is_kenyan'
        ]
        widgets = {
            'passenger_name': forms.TextInput(attrs={'class': 'form-control'}),
            'passenger_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'passenger_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'passenger_id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'passenger_age': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_kenyan': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }