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
    template = get_template('booking_app/booking_pdf.html')
    
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
    
    # CSS for PDF styling
    css_string = """
        @page {
            size: A4;
            margin: 1cm;
        }
        body {
            font-family: Arial, sans-serif;
            font-size: 12px;
            line-height: 1.4;
        }
        .pdf-header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
        }
        .company-logo {
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }
        .booking-title {
            font-size: 20px;
            color: #28a745;
            margin: 20px 0;
        }
        .booking-id {
            font-size: 16px;
            font-weight: bold;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin: 15px 0;
            text-align: center;
        }
        .section {
            margin-bottom: 25px;
        }
        .section-title {
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }
        .info-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .info-table td {
            padding: 8px;
            border-bottom: 1px solid #eee;
        }
        .info-table .label {
            font-weight: bold;
            width: 40%;
            color: #666;
        }
        .info-table .value {
            color: #333;
        }
        .seats-section {
            text-align: center;
            margin: 20px 0;
        }
        .seat {
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 8px 12px;
            margin: 3px;
            border-radius: 5px;
            font-weight: bold;
        }
        .total-section {
            background: #fff3cd;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            margin: 20px 0;
            border: 1px solid #ffeaa7;
        }
        .total-amount {
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 10px;
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 20px;
        }
        .status-badge {
            padding: 5px 10px;
            border-radius: 15px;
            font-weight: bold;
            font-size: 11px;
        }
        .status-confirmed {
            background: #d4edda;
            color: #155724;
        }
        .status-pending {
            background: #fff3cd;
            color: #856404;
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