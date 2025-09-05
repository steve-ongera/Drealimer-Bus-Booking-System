from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import uuid

class Location(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class BusCompany(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='company_logos/', blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class SeatLayout(models.Model):
    SEAT_CLASS_CHOICES = [
        ('VIP', 'VIP'),
        ('BUSINESS', 'Business'),
        ('ECONOMY', 'Economy'),
    ]
    
    name = models.CharField(max_length=100)
    seat_class = models.CharField(max_length=20, choices=SEAT_CLASS_CHOICES)
    total_seats = models.PositiveIntegerField()
    rows = models.PositiveIntegerField()
    columns = models.PositiveIntegerField()
    layout_data = models.JSONField(default=dict)  # Stores the drag-drop layout
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.seat_class})"

class Bus(models.Model):
    BUS_TYPE_CHOICES = [
        ('VIP', 'VIP'),
        ('BUSINESS', 'Business'),
        ('ECONOMY', 'Economy'),
        ('MIXED', 'Mixed'),
    ]
    
    company = models.ForeignKey(BusCompany, on_delete=models.CASCADE)
    number_plate = models.CharField(max_length=20, unique=True)
    bus_type = models.CharField(max_length=20, choices=BUS_TYPE_CHOICES)
    seat_layout = models.ForeignKey(SeatLayout, on_delete=models.CASCADE)
    total_seats = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.company.name} - {self.number_plate}"

class Route(models.Model):
    origin = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='origin_routes')
    destination = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='destination_routes')
    distance = models.PositiveIntegerField(help_text="Distance in kilometers")
    estimated_duration = models.DurationField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('origin', 'destination')
    
    def __str__(self):
        return f"{self.origin} to {self.destination}"

class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    stop_order = models.PositiveIntegerField()
    distance_from_origin = models.PositiveIntegerField()
    
    class Meta:
        unique_together = ('route', 'stop_order')
        ordering = ['stop_order']
    
    def __str__(self):
        return f"{self.route} - {self.location} (Stop {self.stop_order})"

class Trip(models.Model):
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.route} - {self.departure_time.strftime('%Y-%m-%d %H:%M')}"

class Seat(models.Model):
    SEAT_TYPE_CHOICES = [
        ('WINDOW', 'Window'),
        ('AISLE', 'Aisle'),
        ('MIDDLE', 'Middle'),
    ]
    
    SEAT_CLASS_CHOICES = [
        ('VIP', 'VIP'),
        ('BUSINESS', 'Business'),
        ('ECONOMY', 'Economy'),
    ]
    
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='seats')
    seat_number = models.CharField(max_length=10)
    seat_type = models.CharField(max_length=20, choices=SEAT_TYPE_CHOICES)
    seat_class = models.CharField(max_length=20, choices=SEAT_CLASS_CHOICES)
    row_number = models.PositiveIntegerField()
    column_number = models.PositiveIntegerField()
    price_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('bus', 'seat_number')
    
    def __str__(self):
        return f"{self.bus} - Seat {self.seat_number}"

# In your models.py, replace the Booking model with this:

def generate_booking_id():
    """Generate a unique booking ID"""
    return str(uuid.uuid4())[:12].upper()

class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    ]
    
    booking_id = models.CharField(max_length=20, unique=True, default=generate_booking_id)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Guest booking details
    passenger_name = models.CharField(max_length=100)
    passenger_email = models.EmailField()
    passenger_phone = models.CharField(max_length=20)
    passenger_id_number = models.CharField(max_length=20)
    passenger_age = models.PositiveIntegerField()
    is_kenyan = models.BooleanField(default=True)
    
    # Booking details
    pickup_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='pickup_bookings')
    dropoff_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='dropoff_bookings')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Payment details
    mpesa_transaction_id = models.CharField(max_length=50, blank=True)
    payment_phone = models.CharField(max_length=20, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status == 'PENDING'
    
    def __str__(self):
        return f"Booking {self.booking_id} - {self.passenger_name}"
    
    
class BookingSeat(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booked_seats')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        unique_together = ('booking', 'seat')
    
    def __str__(self):
        return f"{self.booking.booking_id} - Seat {self.seat.seat_number}"

class TripSeatAvailability(models.Model):
    """Track seat availability for specific trips"""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=True)
    reserved_until = models.DateTimeField(null=True, blank=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ('trip', 'seat')
    
    def is_reservable(self):
        if not self.is_available:
            return False
        if self.reserved_until and timezone.now() < self.reserved_until:
            return False
        return True
    
    def __str__(self):
        return f"{self.trip} - Seat {self.seat.seat_number} ({'Available' if self.is_available else 'Booked'})"