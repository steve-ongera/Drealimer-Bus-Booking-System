from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import json
import uuid
from .models import *

from .forms import SearchForm, BookingForm, GuestBookingForm

def home(request):
    """Home page with search form"""
    search_form = SearchForm()
    return render(request, 'home.html', {
        'search_form': search_form
    })

def location_autocomplete(request):
    """AJAX endpoint for location autocomplete"""
    if request.is_ajax():
        q = request.GET.get('term', '')
        locations = Location.objects.filter(
            name__icontains=q
        )[:10]
        results = []
        for location in locations:
            location_json = {
                'id': location.id,
                'label': location.name,
                'value': location.name
            }
            results.append(location_json)
        return JsonResponse(results, safe=False)
    return JsonResponse([], safe=False)

def search_trips(request):
    """Search for available trips"""
    if request.method == 'POST':
        form = SearchForm(request.POST)
        if form.is_valid():
            origin = form.cleaned_data['origin']
            destination = form.cleaned_data['destination']
            travel_date = form.cleaned_data['travel_date']
            
            # Find trips for the specified route and date
            trips = Trip.objects.filter(
                route__origin=origin,
                route__destination=destination,
                departure_time__date=travel_date,
                status='SCHEDULED'
            ).select_related('bus', 'bus__company', 'route')
            
            # Also include trips with intermediate stops
            intermediate_trips = Trip.objects.filter(
                route__stops__location=origin,
                route__destination=destination,
                departure_time__date=travel_date,
                status='SCHEDULED'
            ).exclude(
                route__origin=origin
            ).select_related('bus', 'bus__company', 'route')
            
            all_trips = list(trips) + list(intermediate_trips)
            
            return render(request, 'search_results.html', {
                'trips': all_trips,
                'origin': origin,
                'destination': destination,
                'travel_date': travel_date
            })
    
    return redirect('home')

def trip_seats(request, trip_id):
    """Display seat layout for a specific trip"""
    trip = get_object_or_404(Trip, id=trip_id)
    bus = trip.bus
    
    # Get seat availability for this trip
    seat_availability = TripSeatAvailability.objects.filter(
        trip=trip
    ).select_related('seat')
    
    # Create availability dict
    availability_dict = {
        sa.seat.id: sa for sa in seat_availability
    }
    
    # Get all seats for the bus
    seats = Seat.objects.filter(bus=bus, is_active=True).order_by('row_number', 'column_number')
    
    # Add availability info to seats
    for seat in seats:
        seat.availability = availability_dict.get(seat.id)
        if seat.availability:
            seat.is_available = seat.availability.is_reservable()
        else:
            # Create availability record if not exists
            TripSeatAvailability.objects.create(
                trip=trip,
                seat=seat,
                is_available=True
            )
            seat.is_available = True
    
    return render(request, 'seat_selection.html', {
        'trip': trip,
        'seats': seats,
        'layout_data': bus.seat_layout.layout_data
    })

@csrf_exempt
def reserve_seats(request):
    """Reserve selected seats temporarily"""
    if request.method == 'POST':
        data = json.loads(request.body)
        trip_id = data.get('trip_id')
        seat_ids = data.get('seat_ids', [])
        
        trip = get_object_or_404(Trip, id=trip_id)
        
        # Check if seats are available
        unavailable_seats = []
        for seat_id in seat_ids:
            try:
                availability = TripSeatAvailability.objects.get(
                    trip=trip,
                    seat_id=seat_id
                )
                if not availability.is_reservable():
                    unavailable_seats.append(seat_id)
            except TripSeatAvailability.DoesNotExist:
                unavailable_seats.append(seat_id)
        
        if unavailable_seats:
            return JsonResponse({
                'success': False,
                'message': 'Some seats are no longer available',
                'unavailable_seats': unavailable_seats
            })
        
        # Reserve seats for 5 minutes
        reservation_time = timezone.now() + timedelta(minutes=5)
        for seat_id in seat_ids:
            TripSeatAvailability.objects.filter(
                trip=trip,
                seat_id=seat_id
            ).update(
                reserved_until=reservation_time
            )
        
        # Calculate total price
        seats = Seat.objects.filter(id__in=seat_ids)
        total_price = sum([
            trip.base_price * seat.price_multiplier for seat in seats
        ])
        
        return JsonResponse({
            'success': True,
            'total_price': float(total_price),
            'reservation_expires': reservation_time.isoformat()
        })
    
    return JsonResponse({'success': False})

def booking_details(request, trip_id):
    """Collect booking details"""
    trip = get_object_or_404(Trip, id=trip_id)
    seat_ids = request.GET.get('seats', '').split(',')
    
    if not seat_ids or not seat_ids[0]:
        return redirect('trip_seats', trip_id=trip_id)
    
    seats = Seat.objects.filter(id__in=seat_ids)
    total_price = sum([
        trip.base_price * seat.price_multiplier for seat in seats
    ])
    
    if request.method == 'POST':
        form = GuestBookingForm(request.POST)
        if form.is_valid():
            # Create booking
            booking = Booking.objects.create(
                booking_id=str(uuid.uuid4())[:12].upper(),
                trip=trip,
                user=request.user if request.user.is_authenticated else None,
                passenger_name=form.cleaned_data['passenger_name'],
                passenger_email=form.cleaned_data['passenger_email'],
                passenger_phone=form.cleaned_data['passenger_phone'],
                passenger_id_number=form.cleaned_data['passenger_id_number'],
                passenger_age=form.cleaned_data['passenger_age'],
                is_kenyan=form.cleaned_data['is_kenyan'],
                pickup_location=trip.route.origin,
                dropoff_location=trip.route.destination,
                total_amount=total_price,
                payment_phone=form.cleaned_data['passenger_phone']
            )
            
            # Create booking seats
            for seat in seats:
                BookingSeat.objects.create(
                    booking=booking,
                    seat=seat,
                    price=trip.base_price * seat.price_multiplier
                )
                
                # Update seat availability
                TripSeatAvailability.objects.filter(
                    trip=trip,
                    seat=seat
                ).update(
                    booking=booking,
                    reserved_until=booking.expires_at
                )
            
            return redirect('payment', booking_id=booking.booking_id)
    else:
        form = GuestBookingForm()
    
    return render(request, 'booking_details.html', {
        'trip': trip,
        'seats': seats,
        'total_price': total_price,
        'form': form
    })

def payment(request, booking_id):
    """Payment page with M-Pesa integration"""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    if booking.status == 'CONFIRMED':
        return redirect('booking_confirmation', booking_id=booking_id)
    
    if booking.is_expired():
        booking.status = 'EXPIRED'
        booking.save()
        
        # Release seats
        TripSeatAvailability.objects.filter(
            booking=booking
        ).update(
            is_available=True,
            reserved_until=None,
            booking=None
        )
        
        return render(request, 'booking_expired.html', {'booking': booking})
    
    return render(request, 'payment.html', {
        'booking': booking,
        'time_remaining': (booking.expires_at - timezone.now()).total_seconds()
    })

@csrf_exempt
def process_payment(request):
    """Process M-Pesa payment (mock implementation)"""
    if request.method == 'POST':
        data = json.loads(request.body)
        booking_id = data.get('booking_id')
        phone_number = data.get('phone_number')
        
        booking = get_object_or_404(Booking, booking_id=booking_id)
        
        # Mock M-Pesa payment processing
        # In real implementation, integrate with Safaricom API
        
        # Simulate successful payment
        booking.status = 'CONFIRMED'
        booking.paid_at = timezone.now()
        booking.mpesa_transaction_id = f"MPesa{uuid.uuid4().hex[:10].upper()}"
        booking.save()
        
        # Update seat availability
        TripSeatAvailability.objects.filter(
            booking=booking
        ).update(
            is_available=False,
            reserved_until=None
        )
        
        # Send confirmation email and SMS
        send_booking_confirmation(booking)
        
        return JsonResponse({
            'success': True,
            'transaction_id': booking.mpesa_transaction_id
        })
    
    return JsonResponse({'success': False})

def booking_confirmation(request, booking_id):
    """Show booking confirmation"""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    return render(request, 'booking_confirmation.html', {'booking': booking})

def send_booking_confirmation(booking):
    """Send booking confirmation via email and SMS"""
    subject = f'Booking Confirmation - {booking.booking_id}'
    message = f"""
    Dear {booking.passenger_name},
    
    Your booking has been confirmed!
    
    Booking ID: {booking.booking_id}
    Trip: {booking.trip.route}
    Departure: {booking.trip.departure_time.strftime('%Y-%m-%d %H:%M')}
    Seats: {', '.join([bs.seat.seat_number for bs in booking.booked_seats.all()])}
    Total Amount: KSh {booking.total_amount}
    
    Please arrive at the pickup location 30 minutes before departure.
    
    Thank you for choosing {booking.trip.bus.company.name}!
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [booking.passenger_email],
        fail_silently=True,
    )
    
    # SMS sending would be implemented here with SMS provider API

# Admin views for seat layout design
def admin_seat_layout(request, layout_id=None):
    """Admin interface for designing seat layouts"""
    if layout_id:
        layout = get_object_or_404(SeatLayout, id=layout_id)
    else:
        layout = None
    
    layouts = SeatLayout.objects.all()
    
    return render(request, 'admin/seat_layout_designer.html', {
        'layout': layout,
        'layouts': layouts
    })

@csrf_exempt
def save_seat_layout(request):
    """Save seat layout design"""
    if request.method == 'POST':
        data = json.loads(request.body)
        layout_id = data.get('layout_id')
        
        if layout_id:
            layout = get_object_or_404(SeatLayout, id=layout_id)
        else:
            layout = SeatLayout.objects.create(
                name=data.get('name'),
                seat_class=data.get('seat_class'),
                total_seats=data.get('total_seats', 0),
                rows=data.get('rows', 0),
                columns=data.get('columns', 0)
            )
        
        layout.layout_data = data.get('layout_data', {})
        layout.save()
        
        return JsonResponse({'success': True, 'layout_id': layout.id})
    
    return JsonResponse({'success': False})