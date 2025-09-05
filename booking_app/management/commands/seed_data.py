import random
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from booking_app.models import (
    Location, BusCompany, SeatLayout, Bus, Route, RouteStop, 
    Trip, Seat, Booking, BookingSeat, TripSeatAvailability
)


class Command(BaseCommand):
    help = 'Seed the database with Kenyan bus booking data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to seed data...'))
        
        # Clear existing data (optional)
        if input("Do you want to clear existing data? (yes/no): ").lower() == 'yes':
            self.clear_data()
        
        self.create_locations()
        self.create_bus_companies()
        self.create_seat_layouts()
        self.create_buses()
        self.create_routes()
        self.create_route_stops()
        self.create_seats()
        self.create_trips()
        self.create_trip_seat_availability()
        self.create_users()
        self.create_bookings()
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded all data!'))

    def clear_data(self):
        """Clear existing data"""
        self.stdout.write('Clearing existing data...')
        TripSeatAvailability.objects.all().delete()
        BookingSeat.objects.all().delete()
        Booking.objects.all().delete()
        Trip.objects.all().delete()
        Seat.objects.all().delete()
        RouteStop.objects.all().delete()
        Route.objects.all().delete()
        Bus.objects.all().delete()
        SeatLayout.objects.all().delete()
        BusCompany.objects.all().delete()
        Location.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def create_locations(self):
        """Create Kenyan cities and locations"""
        self.stdout.write('Creating locations...')
        
        kenyan_locations = [
            ('Nairobi', 'NBI'),
            ('Mombasa', 'MSA'),
            ('Kisumu', 'KSM'),
            ('Nakuru', 'NKR'),
            ('Eldoret', 'ELD'),
            ('Nyeri', 'NYR'),
            ('Machakos', 'MCH'),
            ('Meru', 'MRU'),
            ('Thika', 'THK'),
            ('Kitale', 'KTL'),
            ('Garissa', 'GRS'),
            ('Kakamega', 'KKG'),
            ('Kericho', 'KRC'),
            ('Embu', 'EMB'),
            ('Malindi', 'MLD'),
            ('Lamu', 'LAM'),
            ('Isiolo', 'ISL'),
            ('Nanyuki', 'NYK'),
            ('Naivasha', 'NVS'),
            ('Voi', 'VOI'),
        ]
        
        for name, code in kenyan_locations:
            Location.objects.create(name=name, code=code)
        
        self.stdout.write(f'Created {len(kenyan_locations)} locations')

    def create_bus_companies(self):
        """Create Kenyan bus companies"""
        self.stdout.write('Creating bus companies...')
        
        companies_data = [
            ('Easy Coach', '+254-700-123456', 'info@easycoach.co.ke'),
            ('Modern Coast Express', '+254-700-234567', 'bookings@moderncoast.co.ke'),
            ('Mash East Africa', '+254-700-345678', 'info@masheastafrica.com'),
            ('Guardian Angel', '+254-700-456789', 'contact@guardianangel.co.ke'),
            ('Climax Coach', '+254-700-567890', 'info@climaxcoach.co.ke'),
            ('Tahmeed Coach', '+254-700-678901', 'bookings@tahmeed.co.ke'),
            ('Buscar', '+254-700-789012', 'info@buscar.co.ke'),
            ('Crown Bus Service', '+254-700-890123', 'contact@crownbus.co.ke'),
            ('Simba Coach', '+254-700-901234', 'info@simbacoach.co.ke'),
            ('Nyamakima Sacco', '+254-700-012345', 'info@nyamakima.co.ke'),
        ]
        
        for name, phone, email in companies_data:
            BusCompany.objects.create(name=name, phone=phone, email=email)
        
        self.stdout.write(f'Created {len(companies_data)} bus companies')

    def create_seat_layouts(self):
        """Create different seat layouts"""
        self.stdout.write('Creating seat layouts...')
        
        layouts = [
            # VIP Layout (2x2 configuration, 28 seats)
            {
                'name': 'VIP 2x2 Layout',
                'seat_class': 'VIP',
                'total_seats': 28,
                'rows': 7,
                'columns': 4,
                'layout_data': {
                    'config': '2x2',
                    'aisle_position': 'center',
                    'description': 'Luxury VIP seating with extra legroom'
                }
            },
            # Business Layout (2x2 configuration, 36 seats)
            {
                'name': 'Business 2x2 Layout',
                'seat_class': 'BUSINESS',
                'total_seats': 36,
                'rows': 9,
                'columns': 4,
                'layout_data': {
                    'config': '2x2',
                    'aisle_position': 'center',
                    'description': 'Comfortable business class seating'
                }
            },
            # Economy Layout (2x3 configuration, 45 seats)
            {
                'name': 'Economy 2x3 Layout',
                'seat_class': 'ECONOMY',
                'total_seats': 45,
                'rows': 9,
                'columns': 5,
                'layout_data': {
                    'config': '2x3',
                    'aisle_position': 'center',
                    'description': 'Standard economy seating'
                }
            },
            # Economy Layout (2x2 configuration, 40 seats)
            {
                'name': 'Economy 2x2 Layout',
                'seat_class': 'ECONOMY',
                'total_seats': 40,
                'rows': 10,
                'columns': 4,
                'layout_data': {
                    'config': '2x2',
                    'aisle_position': 'center',
                    'description': 'Economy 2x2 configuration'
                }
            },
        ]
        
        for layout_data in layouts:
            SeatLayout.objects.create(**layout_data)
        
        self.stdout.write(f'Created {len(layouts)} seat layouts')

    def create_buses(self):
        """Create buses for each company"""
        self.stdout.write('Creating buses...')
        
        companies = BusCompany.objects.all()
        layouts = SeatLayout.objects.all()
        
        # Kenyan number plate prefixes for different regions
        plate_prefixes = ['KAA', 'KBL', 'KCA', 'KCB', 'KDA', 'KEB']
        bus_types = ['VIP', 'BUSINESS', 'ECONOMY', 'MIXED']
        
        buses_created = 0
        for company in companies:
            # Each company gets 3-5 buses
            num_buses = random.randint(3, 5)
            
            for i in range(num_buses):
                bus_type = random.choice(bus_types)
                layout = random.choice(layouts)
                
                # Generate unique number plate
                prefix = random.choice(plate_prefixes)
                number = random.randint(100, 999)
                letter = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                plate = f"{prefix} {number:03d}{letter}"
                
                # Ensure unique plate
                while Bus.objects.filter(number_plate=plate).exists():
                    number = random.randint(100, 999)
                    letter = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                    plate = f"{prefix} {number:03d}{letter}"
                
                Bus.objects.create(
                    company=company,
                    number_plate=plate,
                    bus_type=bus_type,
                    seat_layout=layout,
                    total_seats=layout.total_seats
                )
                buses_created += 1
        
        self.stdout.write(f'Created {buses_created} buses')

    def create_routes(self):
        """Create routes between Kenyan cities"""
        self.stdout.write('Creating routes...')
        
        locations = list(Location.objects.all())
        
        # Popular Kenyan routes with realistic distances and durations
        popular_routes = [
            ('Nairobi', 'Mombasa', 484, timedelta(hours=8, minutes=30)),
            ('Nairobi', 'Kisumu', 350, timedelta(hours=6, minutes=0)),
            ('Nairobi', 'Nakuru', 160, timedelta(hours=2, minutes=30)),
            ('Nairobi', 'Eldoret', 310, timedelta(hours=5, minutes=0)),
            ('Nairobi', 'Nyeri', 150, timedelta(hours=2, minutes=45)),
            ('Nairobi', 'Machakos', 64, timedelta(hours=1, minutes=30)),
            ('Nairobi', 'Meru', 230, timedelta(hours=4, minutes=0)),
            ('Nairobi', 'Thika', 45, timedelta(hours=1, minutes=0)),
            ('Mombasa', 'Malindi', 118, timedelta(hours=2, minutes=0)),
            ('Mombasa', 'Lamu', 340, timedelta(hours=6, minutes=0)),
            ('Kisumu', 'Kakamega', 52, timedelta(hours=1, minutes=15)),
            ('Nakuru', 'Eldoret', 150, timedelta(hours=2, minutes=30)),
            ('Eldoret', 'Kitale', 65, timedelta(hours=1, minutes=30)),
            ('Nyeri', 'Nanyuki', 36, timedelta(hours=1, minutes=0)),
            ('Nakuru', 'Naivasha', 64, timedelta(hours=1, minutes=15)),
        ]
        
        location_dict = {loc.name: loc for loc in locations}
        
        for origin_name, dest_name, distance, duration in popular_routes:
            if origin_name in location_dict and dest_name in location_dict:
                Route.objects.create(
                    origin=location_dict[origin_name],
                    destination=location_dict[dest_name],
                    distance=distance,
                    estimated_duration=duration
                )
        
        self.stdout.write(f'Created {len(popular_routes)} routes')

    def create_route_stops(self):
        """Create intermediate stops for routes"""
        self.stdout.write('Creating route stops...')
        
        routes = Route.objects.all()
        all_locations = list(Location.objects.all())
        
        stops_created = 0
        for route in routes:
            # Add 1-3 intermediate stops for longer routes
            if route.distance > 200:
                num_stops = random.randint(2, 4)
            elif route.distance > 100:
                num_stops = random.randint(1, 3)
            else:
                num_stops = random.randint(0, 2)
            
            # Select random intermediate locations
            available_stops = [loc for loc in all_locations 
                             if loc != route.origin and loc != route.destination]
            
            if num_stops > 0 and available_stops:
                selected_stops = random.sample(available_stops, 
                                             min(num_stops, len(available_stops)))
                
                for i, stop_location in enumerate(selected_stops, 1):
                    distance_from_origin = int(route.distance * (i / (num_stops + 1)))
                    
                    RouteStop.objects.create(
                        route=route,
                        location=stop_location,
                        stop_order=i,
                        distance_from_origin=distance_from_origin
                    )
                    stops_created += 1
        
        self.stdout.write(f'Created {stops_created} route stops')

    def create_seats(self):
        """Create seats for all buses"""
        self.stdout.write('Creating seats...')
        
        buses = Bus.objects.all()
        total_seats = 0
        
        for bus in buses:
            layout = bus.seat_layout
            seats_created = 0
            
            # Generate seats based on layout
            if layout.layout_data.get('config') == '2x2':
                # 2x2 configuration (A-B aisle C-D)
                for row in range(1, layout.rows + 1):
                    positions = ['A', 'B', 'C', 'D']
                    for col, pos in enumerate(positions, 1):
                        if seats_created >= layout.total_seats:
                            break
                        
                        seat_type = 'WINDOW' if pos in ['A', 'D'] else 'AISLE'
                        
                        # Price multiplier based on seat type and class
                        if seat_type == 'WINDOW':
                            multiplier = Decimal('1.1')  # 10% premium for window
                        else:
                            multiplier = Decimal('1.0')
                        
                        # VIP seats get higher multiplier
                        if layout.seat_class == 'VIP':
                            multiplier += Decimal('0.5')
                        elif layout.seat_class == 'BUSINESS':
                            multiplier += Decimal('0.2')
                        
                        Seat.objects.create(
                            bus=bus,
                            seat_number=f"{row:02d}{pos}",
                            seat_type=seat_type,
                            seat_class=layout.seat_class,
                            row_number=row,
                            column_number=col,
                            price_multiplier=multiplier
                        )
                        seats_created += 1
                
            elif layout.layout_data.get('config') == '2x3':
                # 2x3 configuration (A-B aisle C-D-E)
                for row in range(1, layout.rows + 1):
                    positions = ['A', 'B', 'C', 'D', 'E']
                    for col, pos in enumerate(positions, 1):
                        if seats_created >= layout.total_seats:
                            break
                        
                        if pos in ['A', 'E']:
                            seat_type = 'WINDOW'
                        elif pos in ['B', 'C']:
                            seat_type = 'AISLE'
                        else:
                            seat_type = 'MIDDLE'
                        
                        # Price multiplier
                        if seat_type == 'WINDOW':
                            multiplier = Decimal('1.1')
                        elif seat_type == 'MIDDLE':
                            multiplier = Decimal('0.95')  # 5% discount for middle
                        else:
                            multiplier = Decimal('1.0')
                        
                        Seat.objects.create(
                            bus=bus,
                            seat_number=f"{row:02d}{pos}",
                            seat_type=seat_type,
                            seat_class=layout.seat_class,
                            row_number=row,
                            column_number=col,
                            price_multiplier=multiplier
                        )
                        seats_created += 1
            
            total_seats += seats_created
        
        self.stdout.write(f'Created {total_seats} seats')

    def create_trips(self):
        """Create trips for the next 7 days"""
        self.stdout.write('Creating trips...')
        
        buses = Bus.objects.all()
        routes = Route.objects.all()
        
        trips_created = 0
        base_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Base prices for different route distances
        base_prices = {
            'VIP': 25.0,      # per km
            'BUSINESS': 18.0, # per km  
            'ECONOMY': 12.0,  # per km
            'MIXED': 15.0     # per km
        }
        
        # Create trips for next 7 days
        for day_offset in range(7):
            trip_date = base_date + timedelta(days=day_offset)
            
            # Multiple trips per day for popular routes
            for route in routes:
                # 2-4 trips per day per route
                num_trips = random.randint(2, 4)
                
                for trip_num in range(num_trips):
                    bus = random.choice(buses)
                    
                    # Departure times: 6AM, 9AM, 2PM, 6PM, 10PM
                    departure_hours = [6, 9, 14, 18, 22]
                    departure_hour = random.choice(departure_hours)
                    departure_minute = random.choice([0, 30])
                    
                    departure_time = trip_date.replace(
                        hour=departure_hour, 
                        minute=departure_minute
                    )
                    
                    arrival_time = departure_time + route.estimated_duration
                    
                    # Calculate base price
                    price_per_km = base_prices[bus.bus_type]
                    base_price = Decimal(str(route.distance * price_per_km))
                    
                    # Add some randomness to pricing (+/- 20%)
                    price_variation = random.uniform(0.8, 1.2)
                    base_price = base_price * Decimal(str(price_variation))
                    
                    Trip.objects.create(
                        bus=bus,
                        route=route,
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        base_price=base_price.quantize(Decimal('0.01')),
                        status='SCHEDULED'
                    )
                    trips_created += 1
        
        self.stdout.write(f'Created {trips_created} trips')

    def create_trip_seat_availability(self):
        """Create seat availability records for all trips"""
        self.stdout.write('Creating trip seat availability...')
        
        trips = Trip.objects.all()
        availability_created = 0
        
        for trip in trips:
            seats = trip.bus.seats.all()
            
            for seat in seats:
                # 85% of seats available initially (some may be blocked for maintenance)
                is_available = random.choice([True] * 85 + [False] * 15)
                
                TripSeatAvailability.objects.create(
                    trip=trip,
                    seat=seat,
                    is_available=is_available
                )
                availability_created += 1
        
        self.stdout.write(f'Created {availability_created} seat availability records')

    def create_users(self):
        """Create sample users"""
        self.stdout.write('Creating users...')
        
        users_data = [
            ('john.doe', 'john.doe@email.com', 'John', 'Doe'),
            ('jane.smith', 'jane.smith@email.com', 'Jane', 'Smith'),
            ('peter.mwangi', 'peter.mwangi@email.com', 'Peter', 'Mwangi'),
            ('mary.wanjiku', 'mary.wanjiku@email.com', 'Mary', 'Wanjiku'),
            ('david.kiprotich', 'david.kiprotich@email.com', 'David', 'Kiprotich'),
        ]
        
        for username, email, first_name, last_name in users_data:
            user, created = User.objects.get_or_create(
                username=username,
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': True
                }
            )
            if created:
                user.set_password('password123')
                user.save()
        
        self.stdout.write(f'Created/verified {len(users_data)} users')

    def create_bookings(self):
        """Create sample bookings"""
        self.stdout.write('Creating bookings...')
        
        trips = list(Trip.objects.all()[:20])  # Use first 20 trips
        users = list(User.objects.all())
        locations = list(Location.objects.all())
        
        # Kenyan names for guest bookings
        kenyan_names = [
            'James Kamau', 'Grace Wanjiku', 'Peter Otieno', 'Sarah Chebet',
            'Daniel Mwangi', 'Faith Akinyi', 'Joseph Kiprotich', 'Mercy Wairimu',
            'Samuel Ochieng', 'Esther Njeri', 'Michael Mutua', 'Rose Cheptoo'
        ]
        
        # Kenyan phone numbers and emails
        phone_numbers = ['+254701234567', '+254722345678', '+254733456789', 
                        '+254744567890', '+254755678901', '+254766789012']
        
        bookings_created = 0
        
        for trip in trips:
            # Create 1-3 bookings per trip
            num_bookings = random.randint(1, 3)
            available_seats = list(TripSeatAvailability.objects.filter(
                trip=trip, is_available=True
            ))
            
            if not available_seats:
                continue
            
            for _ in range(min(num_bookings, len(available_seats))):
                # 70% registered users, 30% guests
                user = random.choice(users) if random.random() < 0.7 else None
                
                if user:
                    passenger_name = f"{user.first_name} {user.last_name}"
                    passenger_email = user.email
                else:
                    passenger_name = random.choice(kenyan_names)
                    passenger_email = f"{passenger_name.lower().replace(' ', '.')}@email.com"
                
                # Random passenger details
                passenger_phone = random.choice(phone_numbers)
                passenger_age = random.randint(18, 65)
                is_kenyan = random.choice([True] * 90 + [False] * 10)  # 90% Kenyan
                
                # ID number (Kenyan format)
                id_number = f"{random.randint(10000000, 39999999)}"
                
                # Pickup and dropoff locations
                pickup_location = trip.route.origin
                dropoff_location = trip.route.destination
                
                # Select 1-2 seats
                num_seats = random.choice([1, 1, 1, 2])  # Most bookings are single seat
                selected_seats = random.sample(available_seats, min(num_seats, len(available_seats)))
                
                # Calculate total amount
                total_amount = Decimal('0')
                for seat_avail in selected_seats:
                    seat_price = trip.base_price * seat_avail.seat.price_multiplier
                    total_amount += seat_price
                
                # Random booking status
                status = random.choices(
                    ['CONFIRMED', 'PENDING', 'CANCELLED'],
                    weights=[70, 20, 10]  # 70% confirmed, 20% pending, 10% cancelled
                )[0]
                
                booking = Booking.objects.create(
                    trip=trip,
                    user=user,
                    passenger_name=passenger_name,
                    passenger_email=passenger_email,
                    passenger_phone=passenger_phone,
                    passenger_id_number=id_number,
                    passenger_age=passenger_age,
                    is_kenyan=is_kenyan,
                    pickup_location=pickup_location,
                    dropoff_location=dropoff_location,
                    total_amount=total_amount.quantize(Decimal('0.01')),
                    status=status,
                    payment_phone=passenger_phone if status == 'CONFIRMED' else '',
                    mpesa_transaction_id=f"MPS{random.randint(100000, 999999)}" if status == 'CONFIRMED' else '',
                    paid_at=timezone.now() if status == 'CONFIRMED' else None
                )
                
                # Create booking seats and update availability
                for seat_avail in selected_seats:
                    seat_price = trip.base_price * seat_avail.seat.price_multiplier
                    
                    BookingSeat.objects.create(
                        booking=booking,
                        seat=seat_avail.seat,
                        price=seat_price.quantize(Decimal('0.01'))
                    )
                    
                    # Update seat availability
                    if status in ['CONFIRMED', 'PENDING']:
                        seat_avail.is_available = False
                        seat_avail.booking = booking
                        if status == 'PENDING':
                            seat_avail.reserved_until = timezone.now() + timedelta(minutes=5)
                        seat_avail.save()
                        
                        # Remove from available seats
                        if seat_avail in available_seats:
                            available_seats.remove(seat_avail)
                
                bookings_created += 1
        
        self.stdout.write(f'Created {bookings_created} bookings')