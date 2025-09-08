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

import json
import uuid
import tempfile
import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.conf import settings
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from .models import Booking, TripSeatAvailability

from .forms import SearchForm, BookingForm, GuestBookingForm

def home(request):
    """Home page with search form"""
    search_form = SearchForm()
    return render(request, 'home.html', {
        'search_form': search_form
    })

def location_autocomplete(request):
    """AJAX endpoint for location autocomplete"""
    # Replace request.is_ajax() with header check
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
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

def booking_expired(request, booking_id):
    """Show booking expired page"""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    # Update booking status to expired if it's still pending
    if booking.is_expired() and booking.status == 'PENDING':
        booking.status = 'EXPIRED'
        booking.save()
        
        # Release reserved seats
        TripSeatAvailability.objects.filter(
            booking=booking
        ).update(
            is_available=True,
            reserved_until=None,
            booking=None
        )
    
    return render(request, 'booking_expired.html', {'booking': booking})


@csrf_exempt
def process_payment(request):
    """Process M-Pesa payment with automatic PDF email confirmation"""
    if request.method == 'POST':
        data = json.loads(request.body)
        booking_id = data.get('booking_id')
        phone_number = data.get('phone_number')
        
        booking = get_object_or_404(Booking, booking_id=booking_id)
        
        # Check if booking is still valid
        if booking.is_expired():
            return JsonResponse({
                'success': False,
                'error': 'Booking has expired',
                'redirect_url': f'/booking/{booking_id}/expired/'
            })
        
        # Mock M-Pesa payment processing
        # In real implementation, integrate with Safaricom API
        
        try:
            # Simulate successful payment
            booking.status = 'CONFIRMED'
            booking.paid_at = timezone.now()
            booking.mpesa_transaction_id = f"MPesa{uuid.uuid4().hex[:10].upper()}"
            booking.payment_phone = phone_number
            booking.save()
            
            # Update seat availability
            TripSeatAvailability.objects.filter(
                booking=booking
            ).update(
                is_available=False,
                reserved_until=None
            )
            
            # Send confirmation email with PDF attachment
            email_sent = send_booking_confirmation_with_pdf(request, booking)
            
            return JsonResponse({
                'success': True,
                'transaction_id': booking.mpesa_transaction_id,
                'booking_id': booking.booking_id,
                'email_sent': email_sent,
                'redirect_url': f'/booking/{booking_id}/confirmation/'
            })
            
        except Exception as e:
            # Log the error in production
            print(f"Payment processing error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Payment processing failed. Please try again.'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def payment_failed(request):
    """
    Custom view for payment failures
    """
    context = {
        'error_type': 'payment_failed',
        'title': 'Payment Failed',
        'message': 'Your payment could not be processed. Please try again.',
    }
    
    response = render(request, '500.html', context)
    response.status_code = 500
    return response

def generate_booking_pdf(request, booking):
    """Generate PDF for booking"""
    try:
        # Load the template
        template = get_template('booking_pdf.html')
        
        # Context for the template
        context = {
            'booking': booking,
            'company_info': {
                'name': 'DreamLine Bus Service',
                'address': 'P.O. Box 12345, Nairobi, Kenya',
                'phone': '+254 700 123456',
                'email': 'info@dreamlinebus.com',
                'website': 'www.dreamlinebus.com'
            }
        }
        
        # Render HTML
        html_string = template.render(context)
        
        # Generate PDF
        font_config = FontConfiguration()
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        
        # CSS for small horizontal receipt styling
        css_string = """
            @page {
                size: 8.5in 4in;
                margin: 0.2in;
            }
            body {
                font-family: 'Courier New', monospace;
                font-size: 8px;
                line-height: 1.2;
                margin: 0;
                padding: 0;
            }
            .receipt-container {
                border: 2px dashed #333;
                padding: 8px;
                height: calc(4in - 0.4in - 16px);
                display: flex;
                flex-direction: column;
            }
            .receipt-header {
                text-align: center;
                margin-bottom: 8px;
                border-bottom: 1px solid #333;
                padding-bottom: 4px;
            }
            .company-name {
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 2px;
            }
            .receipt-title {
                font-size: 10px;
                font-weight: bold;
                margin-bottom: 2px;
            }
            .booking-id {
                font-size: 9px;
                font-weight: bold;
                background: #000;
                color: white;
                padding: 2px 4px;
                display: inline-block;
                margin: 2px 0;
            }
            .receipt-body {
                display: flex;
                gap: 8px;
                flex: 1;
                font-size: 7px;
            }
            .column {
                flex: 1;
            }
            .info-line {
                margin-bottom: 2px;
                display: flex;
                justify-content: space-between;
            }
            .label {
                font-weight: bold;
                width: 45%;
                text-transform: uppercase;
            }
            .value {
                width: 55%;
                text-align: right;
            }
            .section-divider {
                border-bottom: 1px dashed #999;
                margin: 4px 0;
            }
            .seats {
                text-align: center;
                font-weight: bold;
                background: #f0f0f0;
                padding: 2px;
                margin: 2px 0;
            }
            .total-line {
                font-size: 10px;
                font-weight: bold;
                text-align: center;
                background: #000;
                color: white;
                padding: 4px;
                margin: 4px 0;
            }
            .footer {
                text-align: center;
                font-size: 6px;
                margin-top: 4px;
                border-top: 1px solid #333;
                padding-top: 4px;
            }
            .status {
                display: inline-block;
                padding: 1px 4px;
                background: #28a745;
                color: white;
                font-size: 6px;
                border-radius: 2px;
            }
            .barcode {
                text-align: center;
                font-family: 'Courier New', monospace;
                font-size: 6px;
                letter-spacing: 2px;
                margin: 2px 0;
            }
        """
        
        main_css = CSS(string=css_string, font_config=font_config)
        
        # Generate PDF
        pdf = html.render(stylesheets=[main_css], font_config=font_config)
        
        return pdf.write_pdf()
        
    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        return None

def send_booking_confirmation_with_pdf(request, booking):
    """Send booking confirmation email with PDF attachment"""
    try:
        # Generate PDF
        pdf_content = generate_booking_pdf(request, booking)
        if not pdf_content:
            # Fallback to sending email without PDF
            return send_booking_confirmation_text_only(booking)
        
        # Email subject and content
        subject = f'Booking Confirmed - {booking.booking_id} | DreamLine Bus Service'
        
        # HTML email template
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: #28a745; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .booking-info {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .seats {{ background: #007bff; color: white; padding: 5px 10px; border-radius: 3px; margin: 2px; }}
                .total {{ font-size: 18px; font-weight: bold; color: #28a745; }}
                .footer {{ background: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
                .important {{ background: #fff3cd; padding: 10px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #ffc107; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Booking Confirmed!</h1>
                <p>Thank you for choosing DreamLine Bus Service</p>
            </div>
            
            <div class="content">
                <p>Dear {booking.passenger_name},</p>
                
                <p>Great news! Your booking has been successfully confirmed and payment processed.</p>
                
                <div class="booking-info">
                    <h3>📋 Booking Details</h3>
                    <p><strong>Booking ID:</strong> {booking.booking_id}</p>
                    <p><strong>Route:</strong> {booking.trip.route}</p>
                    <p><strong>Bus Company:</strong> {booking.trip.bus.company.name}</p>
                    <p><strong>Bus Number:</strong> {booking.trip.bus.number_plate}</p>
                    <p><strong>Departure:</strong> {booking.trip.departure_time.strftime('%B %d, %Y at %H:%M')}</p>
                    <p><strong>Arrival:</strong> {booking.trip.arrival_time.strftime('%B %d, %Y at %H:%M')}</p>
                    <p><strong>Pickup Location:</strong> {booking.pickup_location.name}</p>
                    <p><strong>Drop-off Location:</strong> {booking.dropoff_location.name}</p>
                    <p><strong>Seats:</strong> 
                        {' '.join([f'<span class="seats">{seat.seat.seat_number}</span>' for seat in booking.booked_seats.all()])}
                    </p>
                    <p class="total"><strong>Total Paid:</strong> KSh {booking.total_amount:,.0f}</p>
                    <p><strong>Transaction ID:</strong> {booking.mpesa_transaction_id}</p>
                </div>
                
                <div class="important">
                    <h4>🚨 Important Information:</h4>
                    <ul>
                        <li><strong>Arrive 30 minutes early</strong> at the pickup location</li>
                        <li>Bring a <strong>valid ID</strong> for verification</li>
                        <li>Keep this confirmation and the attached receipt for your records</li>
                        <li>Contact us immediately if you need to make changes</li>
                    </ul>
                </div>
                
                <h4>📞 Need Help?</h4>
                <p>Our customer support team is available 24/7:</p>
                <ul>
                    <li>📱 Phone: +254 700 123456</li>
                    <li>📧 Email: support@dreamlinebus.com</li>
                    <li>🌐 Website: www.dreamlinebus.com</li>
                </ul>
                
                <p>Have a safe and comfortable journey!</p>
                
                <p>Best regards,<br>
                <strong>DreamLine Bus Service Team</strong></p>
            </div>
            
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this message.</p>
                <p>© 2024 DreamLine Bus Service. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_message = f"""
        Booking Confirmed - {booking.booking_id}
        
        Dear {booking.passenger_name},
        
        Your booking has been successfully confirmed!
        
        BOOKING DETAILS:
        ================
        Booking ID: {booking.booking_id}
        Route: {booking.trip.route}
        Bus Company: {booking.trip.bus.company.name}
        Departure: {booking.trip.departure_time.strftime('%B %d, %Y at %H:%M')}
        Arrival: {booking.trip.arrival_time.strftime('%B %d, %Y at %H:%M')}
        Pickup: {booking.pickup_location.name}
        Drop-off: {booking.dropoff_location.name}
        Seats: {', '.join([seat.seat.seat_number for seat in booking.booked_seats.all()])}
        Total Paid: KSh {booking.total_amount:,.0f}
        Transaction ID: {booking.mpesa_transaction_id}
        
        IMPORTANT:
        - Arrive 30 minutes early at pickup location
        - Bring valid ID for verification
        - Keep this confirmation for your records
        
        Need help? Contact us at +254 700 123456 or support@dreamlinebus.com
        
        Thank you for choosing DreamLine Bus Service!
        """
        
        # Create email message
        email = EmailMessage(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[booking.passenger_email],
            reply_to=['support@dreamlinebus.com'],
        )
        
        # Add HTML version
        email.content_subtype = 'html'
        email.body = html_message
        
        # Attach PDF
        email.attach(
            f'booking_{booking.booking_id}.pdf',
            pdf_content,
            'application/pdf'
        )
        
        # Send email
        email.send(fail_silently=False)
        
        return True
        
    except Exception as e:
        print(f"Email sending error: {str(e)}")
        # Try to send text-only email as fallback
        return send_booking_confirmation_text_only(booking)

def send_booking_confirmation_text_only(booking):
    """Fallback method to send text-only confirmation email"""
    try:
        from django.core.mail import send_mail
        
        subject = f'Booking Confirmed - {booking.booking_id}'
        message = f"""
        Dear {booking.passenger_name},
        
        Your booking has been confirmed!
        
        Booking ID: {booking.booking_id}
        Route: {booking.trip.route}
        Departure: {booking.trip.departure_time.strftime('%Y-%m-%d %H:%M')}
        Seats: {', '.join([bs.seat.seat_number for bs in booking.booked_seats.all()])}
        Total Amount: KSh {booking.total_amount}
        Transaction ID: {booking.mpesa_transaction_id}
        
        Please arrive at the pickup location 30 minutes before departure.
        
        Thank you for choosing {booking.trip.bus.company.name}!
        
        For support: +254 700 123456
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [booking.passenger_email],
            fail_silently=True,
        )
        
        return True
        
    except Exception as e:
        print(f"Fallback email error: {str(e)}")
        return False

def booking_confirmation(request, booking_id):
    """Show booking confirmation"""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    return render(request, 'booking_confirmation.html', {'booking': booking})



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


# views.py
from django.http import HttpResponse
from django.template.loader import get_template
from django.shortcuts import get_object_or_404
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
import tempfile
import os
from .models import Booking

def download_booking_pdf(request, booking_id):
    """
    Generate and download PDF receipt for booking
    """
    # Get the booking object
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    # Load the template
    template = get_template('booking_pdf.html')
    
    # Context for the template
    context = {
        'booking': booking,
        'company_info': {
            'name': 'DreamLine Bus Service',
            'address': 'P.O. Box 12345, Nairobi, Kenya',
            'phone': '+254 700 123456',
            'email': 'info@dreamlinebus.com'
        }
    }
    
    # Render HTML
    html_string = template.render(context)
    
    # Generate PDF
    font_config = FontConfiguration()
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    
    # CSS for small horizontal receipt styling
    css_string = """
        @page {
            size: 8.5in 4in;
            margin: 0.2in;
        }
        body {
            font-family: 'Courier New', monospace;
            font-size: 8px;
            line-height: 1.2;
            margin: 0;
            padding: 0;
        }
        .receipt-container {
            border: 2px dashed #333;
            padding: 8px;
            height: calc(4in - 0.4in - 16px);
            display: flex;
            flex-direction: column;
        }
        .receipt-header {
            text-align: center;
            margin-bottom: 8px;
            border-bottom: 1px solid #333;
            padding-bottom: 4px;
        }
        .company-name {
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 2px;
        }
        .receipt-title {
            font-size: 10px;
            font-weight: bold;
            margin-bottom: 2px;
        }
        .booking-id {
            font-size: 9px;
            font-weight: bold;
            background: #000;
            color: white;
            padding: 2px 4px;
            display: inline-block;
            margin: 2px 0;
        }
        .receipt-body {
            display: flex;
            gap: 8px;
            flex: 1;
            font-size: 7px;
        }
        .column {
            flex: 1;
        }
        .info-line {
            margin-bottom: 2px;
            display: flex;
            justify-content: space-between;
        }
        .label {
            font-weight: bold;
            width: 45%;
            text-transform: uppercase;
        }
        .value {
            width: 55%;
            text-align: right;
        }
        .section-divider {
            border-bottom: 1px dashed #999;
            margin: 4px 0;
        }
        .seats {
            text-align: center;
            font-weight: bold;
            background: #f0f0f0;
            padding: 2px;
            margin: 2px 0;
        }
        .total-line {
            font-size: 10px;
            font-weight: bold;
            text-align: center;
            background: #000;
            color: white;
            padding: 4px;
            margin: 4px 0;
        }
        .footer {
            text-align: center;
            font-size: 6px;
            margin-top: 4px;
            border-top: 1px solid #333;
            padding-top: 4px;
        }
        .status {
            display: inline-block;
            padding: 1px 4px;
            background: #28a745;
            color: white;
            font-size: 6px;
            border-radius: 2px;
        }
        .barcode {
            text-align: center;
            font-family: 'Courier New', monospace;
            font-size: 6px;
            letter-spacing: 2px;
            margin: 2px 0;
        }
    """
    
    main_css = CSS(string=css_string, font_config=font_config)
    
    # Generate PDF
    pdf = html.render(stylesheets=[main_css], font_config=font_config)
    
    # Create HTTP response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="booking_{booking_id}.pdf"'
    response.write(pdf.write_pdf())
    
    return response


# Alternative view using reportlab (if you prefer reportlab over weasyprint)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from django.http import HttpResponse
import io

def download_booking_pdf_reportlab(request, booking_id):
    """
    Alternative PDF generation using ReportLab
    """
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    # Create a file-like buffer to receive PDF data
    buffer = io.BytesIO()
    
    # Create the PDF object, using the buffer as its "file"
    p = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#28a745'),
        alignment=1  # Center alignment
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#333333')
    )
    
    # Title
    elements.append(Paragraph("DreamLine Bus Service", title_style))
    elements.append(Paragraph("BOOKING CONFIRMATION", heading_style))
    elements.append(Spacer(1, 20))
    
    # Booking ID
    booking_id_style = ParagraphStyle(
        'BookingID',
        parent=styles['Normal'],
        fontSize=14,
        alignment=1,
        backColor=colors.HexColor('#f8f9fa'),
        borderPadding=10
    )
    elements.append(Paragraph(f"Booking ID: {booking.booking_id}", booking_id_style))
    elements.append(Spacer(1, 20))
    
    # Trip Information Table
    trip_data = [
        ['Trip Information', ''],
        ['Route', str(booking.trip.route)],
        ['Bus Company', booking.trip.bus.company.name],
        ['Bus Number', booking.trip.bus.number_plate],
        ['Departure', booking.trip.departure_time.strftime('%B %d, %Y at %H:%M')],
        ['Arrival', booking.trip.arrival_time.strftime('%B %d, %Y at %H:%M')],
        ['Pickup Location', booking.pickup_location.name],
        ['Drop-off Location', booking.dropoff_location.name],
    ]
    
    trip_table = Table(trip_data, colWidths=[2.5*inch, 3*inch])
    trip_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(trip_table)
    elements.append(Spacer(1, 20))
    
    # Passenger Information Table
    passenger_data = [
        ['Passenger Information', ''],
        ['Name', booking.passenger_name],
        ['Email', booking.passenger_email],
        ['Phone', booking.passenger_phone],
        ['ID Number', booking.passenger_id_number],
        ['Age', f"{booking.passenger_age} years"],
        ['Nationality', 'Kenyan' if booking.is_kenyan else 'International'],
    ]
    
    passenger_table = Table(passenger_data, colWidths=[2.5*inch, 3*inch])
    passenger_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(passenger_table)
    elements.append(Spacer(1, 20))
    
    # Seats
    seats_text = "Seats: " + ", ".join([seat.seat.seat_number for seat in booking.booked_seats.all()])
    elements.append(Paragraph(seats_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Total Amount
    total_style = ParagraphStyle(
        'Total',
        parent=styles['Normal'],
        fontSize=18,
        alignment=1,
        backColor=colors.HexColor('#ffc107'),
        borderPadding=15
    )
    elements.append(Paragraph(f"Total Amount: KSh {booking.total_amount:,.0f}", total_style))
    
    # Build PDF
    p.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="booking_{booking_id}.pdf"'
    response.write(pdf)
    
    return response



from django.shortcuts import render
from django.http import HttpResponseNotFound, HttpResponseServerError, HttpResponseForbidden
from django.template import RequestContext
from django.views.decorators.csrf import requires_csrf_token
import logging

logger = logging.getLogger(__name__)

@requires_csrf_token
def custom_404(request, exception=None):
    """
    Custom 404 error page
    """
    # Log the 404 error for monitoring
    logger.warning(f"404 Error: {request.path} - User: {request.user if request.user.is_authenticated else 'Anonymous'} - IP: {get_client_ip(request)}")
    
    context = {
        'request_path': request.path,
        'user': request.user,
    }
    
    response = render(request, '404.html', context)
    response.status_code = 404
    return response

@requires_csrf_token
def custom_500(request):
    """
    Custom 500 error page
    """
    # Log the 500 error for monitoring
    logger.error(f"500 Error: {request.path} - User: {request.user if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'} - IP: {get_client_ip(request) if hasattr(request, 'META') else 'Unknown'}")
    
    context = {
        'request_path': getattr(request, 'path', '/'),
        'user': getattr(request, 'user', None),
    }
    
    try:
        response = render(request, '500.html', context)
        response.status_code = 500
        return response
    except Exception as e:
        # Fallback if even the error template fails
        logger.critical(f"Error template failed to render: {str(e)}")
        return HttpResponseServerError(
            '<h1>Internal Server Error</h1>'
            '<p>The server encountered an internal error and was unable to complete your request.</p>'
            '<p>Please try again later or contact support at support@dreamlinebus.com</p>'
        )

@requires_csrf_token
def custom_403(request, exception=None):
    """
    Custom 403 error page
    """
    # Log the 403 error for monitoring
    logger.warning(f"403 Error: {request.path} - User: {request.user if request.user.is_authenticated else 'Anonymous'} - IP: {get_client_ip(request)}")
    
    context = {
        'request_path': request.path,
        'user': request.user,
        'exception': exception,
    }
    
    response = render(request, '403.html', context)
    response.status_code = 403
    return response

def get_client_ip(request):
    """
    Get the real IP address of the client
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip



def booking_not_found(request, booking_id):
    """
    Custom view for when a booking is not found
    """
    context = {
        'booking_id': booking_id,
        'error_type': 'booking_not_found',
        'title': 'Booking Not Found',
        'message': f'The booking with ID "{booking_id}" could not be found.',
    }
    
    response = render(request, '404.html', context)
    response.status_code = 404
    return response


def trip_not_available(request):
    """
    Custom view for when a trip is no longer available
    """
    context = {
        'error_type': 'trip_not_available',
        'title': 'Trip Not Available',
        'message': 'This trip is no longer available for booking.',
    }
    
    response = render(request, '404.html', context)
    response.status_code = 404
    return response



