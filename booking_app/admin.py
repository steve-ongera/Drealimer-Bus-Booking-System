from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from .models import (
    Location, BusCompany, SeatLayout, Bus, Route, RouteStop,
    Trip, Seat, Booking, BookingSeat, TripSeatAvailability
)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'total_routes', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'code')
    ordering = ('name',)
    readonly_fields = ('created_at',)
    
    def total_routes(self, obj):
        """Show total routes (origin + destination) for this location"""
        origin_count = obj.origin_routes.count()
        destination_count = obj.destination_routes.count()
        return f"{origin_count + destination_count} routes"
    total_routes.short_description = "Total Routes"


@admin.register(BusCompany)
class BusCompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'total_buses', 'logo_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone', 'email')
    readonly_fields = ('created_at', 'logo_preview')
    
    def total_buses(self, obj):
        return obj.bus_set.count()
    total_buses.short_description = "Total Buses"
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover;" />',
                obj.logo.url
            )
        return "No Logo"
    logo_preview.short_description = "Logo Preview"


@admin.register(SeatLayout)
class SeatLayoutAdmin(admin.ModelAdmin):
    list_display = ('name', 'seat_class', 'total_seats', 'dimensions', 'buses_using', 'created_at')
    list_filter = ('seat_class', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)
    
    def dimensions(self, obj):
        return f"{obj.rows} x {obj.columns}"
    dimensions.short_description = "Rows x Columns"
    
    def buses_using(self, obj):
        count = obj.bus_set.count()
        return f"{count} buses"
    buses_using.short_description = "Buses Using Layout"


class SeatInline(admin.TabularInline):
    model = Seat
    extra = 0
    readonly_fields = ('seat_number', 'seat_type', 'seat_class', 'row_number', 'column_number')
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ('number_plate', 'company', 'bus_type', 'seat_layout', 'total_seats', 'total_trips', 'created_at')
    list_filter = ('bus_type', 'company', 'seat_layout__seat_class', 'created_at')
    search_fields = ('number_plate', 'company__name')
    readonly_fields = ('created_at',)
    inlines = [SeatInline]
    
    def total_trips(self, obj):
        return obj.trip_set.count()
    total_trips.short_description = "Total Trips"


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1
    ordering = ('stop_order',)


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('route_name', 'origin', 'destination', 'distance', 'estimated_duration', 'total_stops', 'total_trips', 'created_at')
    list_filter = ('origin', 'destination', 'created_at')
    search_fields = ('origin__name', 'destination__name')
    readonly_fields = ('created_at',)
    inlines = [RouteStopInline]
    
    def route_name(self, obj):
        return f"{obj.origin} → {obj.destination}"
    route_name.short_description = "Route"
    
    def total_stops(self, obj):
        return obj.stops.count()
    total_stops.short_description = "Stops"
    
    def total_trips(self, obj):
        return obj.trip_set.count()
    total_trips.short_description = "Total Trips"


@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ('route', 'location', 'stop_order', 'distance_from_origin')
    list_filter = ('route__origin', 'route__destination', 'location')
    search_fields = ('route__origin__name', 'route__destination__name', 'location__name')
    ordering = ('route', 'stop_order')


class BookingSeatInline(admin.TabularInline):
    model = BookingSeat
    extra = 0
    readonly_fields = ('seat', 'price')
    can_delete = False


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('trip_info', 'bus', 'route', 'departure_time', 'arrival_time', 'base_price', 'status', 'bookings_count', 'occupancy_rate')
    list_filter = ('status', 'bus__company', 'route__origin', 'route__destination', 'departure_time')
    search_fields = ('bus__number_plate', 'route__origin__name', 'route__destination__name')
    readonly_fields = ('created_at', 'bookings_count', 'occupancy_rate')
    date_hierarchy = 'departure_time'
    
    def trip_info(self, obj):
        return f"{str(obj.route)} - {obj.departure_time.strftime('%Y-%m-%d %H:%M')}"
    trip_info.short_description = "Trip"
    
    def bookings_count(self, obj):
        return obj.booking_set.filter(status__in=['CONFIRMED', 'PENDING']).count()
    bookings_count.short_description = "Bookings"
    
    def occupancy_rate(self, obj):
        total_seats = obj.bus.total_seats
        booked_seats = TripSeatAvailability.objects.filter(
            trip=obj, is_available=False
        ).count()
        if total_seats > 0:
            rate = (booked_seats / total_seats) * 100
            color = 'green' if rate > 70 else 'orange' if rate > 40 else 'red'
            return format_html(
                '<span style="color: {};">{}% ({}/{})</span>',
                color, f"{rate:.1f}", booked_seats, total_seats
            )
        return "0%"

    occupancy_rate.short_description = "Occupancy Rate"

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('seat_number', 'bus', 'seat_type', 'seat_class', 'row_number', 'column_number', 'price_multiplier', 'is_active')
    list_filter = ('seat_type', 'seat_class', 'bus__company', 'is_active')
    search_fields = ('seat_number', 'bus__number_plate', 'bus__company__name')
    readonly_fields = ('bus',)
    
    def has_add_permission(self, request):
        return False  # Seats should be created automatically with buses


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'passenger_name', 'trip_info', 'total_amount', 'status', 'seats_count', 'payment_status', 'created_at')
    list_filter = ('status', 'is_kenyan', 'trip__route__origin', 'trip__route__destination', 'created_at')
    search_fields = ('booking_id', 'passenger_name', 'passenger_email', 'passenger_phone', 'mpesa_transaction_id')
    readonly_fields = ('booking_id', 'created_at', 'expires_at', 'is_expired_status')
    date_hierarchy = 'created_at'
    inlines = [BookingSeatInline]
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('booking_id', 'trip', 'status', 'total_amount', 'created_at', 'expires_at', 'is_expired_status')
        }),
        ('Passenger Details', {
            'fields': ('user', 'passenger_name', 'passenger_email', 'passenger_phone', 'passenger_id_number', 'passenger_age', 'is_kenyan')
        }),
        ('Trip Details', {
            'fields': ('pickup_location', 'dropoff_location')
        }),
        ('Payment Information', {
            'fields': ('mpesa_transaction_id', 'payment_phone', 'paid_at')
        }),
    )
    
    def trip_info(self, obj):
        return f"{obj.trip.route} - {obj.trip.departure_time.strftime('%Y-%m-%d %H:%M')}"
    trip_info.short_description = "Trip"
    
    def seats_count(self, obj):
        return obj.booked_seats.count()
    seats_count.short_description = "Seats"
    
    def payment_status(self, obj):
        if obj.status == 'CONFIRMED':
            return format_html('<span style="color: green;">✓ Paid</span>')
        elif obj.status == 'PENDING':
            if obj.is_expired():
                return format_html('<span style="color: red;">⏰ Expired</span>')
            return format_html('<span style="color: orange;">⏳ Pending</span>')
        elif obj.status == 'CANCELLED':
            return format_html('<span style="color: red;">✗ Cancelled</span>')
        return obj.status
    payment_status.short_description = "Payment"
    
    def is_expired_status(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Yes - Expired</span>')
        return format_html('<span style="color: green;">No - Valid</span>')
    is_expired_status.short_description = "Is Expired"
    
    actions = ['mark_as_confirmed', 'mark_as_cancelled', 'mark_as_expired']
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(
            status='CONFIRMED',
            paid_at=timezone.now()
        )
        self.message_user(request, f'{updated} bookings marked as confirmed.')
    mark_as_confirmed.short_description = "Mark selected bookings as confirmed"
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.exclude(status='CANCELLED').update(status='CANCELLED')
        self.message_user(request, f'{updated} bookings marked as cancelled.')
    mark_as_cancelled.short_description = "Mark selected bookings as cancelled"
    
    def mark_as_expired(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='EXPIRED')
        self.message_user(request, f'{updated} bookings marked as expired.')
    mark_as_expired.short_description = "Mark selected bookings as expired"


@admin.register(BookingSeat)
class BookingSeatAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'passenger_name', 'seat_number', 'bus', 'price', 'booking_status')
    list_filter = ('booking__status', 'seat__seat_class', 'seat__bus__company')
    search_fields = ('booking__booking_id', 'booking__passenger_name', 'seat__seat_number', 'seat__bus__number_plate')
    readonly_fields = ('booking', 'seat', 'price')
    
    def booking_id(self, obj):
        return obj.booking.booking_id
    booking_id.short_description = "Booking ID"
    
    def passenger_name(self, obj):
        return obj.booking.passenger_name
    passenger_name.short_description = "Passenger"
    
    def seat_number(self, obj):
        return obj.seat.seat_number
    seat_number.short_description = "Seat"
    
    def bus(self, obj):
        return obj.seat.bus
    bus.short_description = "Bus"
    
    def booking_status(self, obj):
        status = obj.booking.status
        colors = {
            'CONFIRMED': 'green',
            'PENDING': 'orange',
            'CANCELLED': 'red',
            'EXPIRED': 'gray'
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(status, 'black'), status
        )
    booking_status.short_description = "Status"
    
    def has_add_permission(self, request):
        return False  # BookingSeats should be created with bookings


@admin.register(TripSeatAvailability)
class TripSeatAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('trip_info', 'seat_info', 'is_available', 'reserved_until', 'booking_link', 'is_reservable_status')
    list_filter = ('is_available', 'trip__status', 'seat__seat_class', 'trip__bus__company')
    search_fields = ('trip__bus__number_plate', 'seat__seat_number', 'booking__booking_id')
    readonly_fields = ('trip', 'seat', 'is_reservable_status')
    
    def trip_info(self, obj):
        return f"{obj.trip.route} - {obj.trip.departure_time.strftime('%Y-%m-%d %H:%M')}"
    trip_info.short_description = "Trip"
    
    def seat_info(self, obj):
        return f"{obj.seat.seat_number} ({obj.seat.seat_class})"
    seat_info.short_description = "Seat"
    
    def booking_link(self, obj):
        if obj.booking:
            url = reverse('admin:booking_app_booking_change', args=[obj.booking.pk])
            return format_html('<a href="{}">{}</a>', url, obj.booking.booking_id)
        return "-"
    booking_link.short_description = "Booking"
    
    def is_reservable_status(self, obj):
        if obj.is_reservable():
            return format_html('<span style="color: green;">✓ Available</span>')
        return format_html('<span style="color: red;">✗ Not Available</span>')
    is_reservable_status.short_description = "Reservable"
    
    def has_add_permission(self, request):
        return False  # Should be created automatically with trips


# Customize admin site header and title
admin.site.site_header = "Bus Booking Administration"
admin.site.site_title = "Bus Booking Admin"
admin.site.index_title = "Welcome to Bus Booking Administration"