# management/commands/cleanup_expired_bookings.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from booking_app.models import Booking, TripSeatAvailability

class Command(BaseCommand):
    help = 'Clean up expired bookings and release reserved seats'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find expired bookings
        expired_bookings = Booking.objects.filter(
            status='PENDING',
            expires_at__lt=timezone.now()
        )
        
        expired_count = expired_bookings.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would clean up {expired_count} expired bookings')
            )
            
            for booking in expired_bookings:
                self.stdout.write(f'  - {booking.booking_id} (expired {booking.expires_at})')
                
        else:
            if expired_count == 0:
                self.stdout.write(
                    self.style.SUCCESS('No expired bookings found.')
                )
                return
            
            # Update booking status
            updated = expired_bookings.update(status='EXPIRED')
            
            # Release reserved seats
            released_seats = 0
            for booking in expired_bookings:
                seat_count = TripSeatAvailability.objects.filter(
                    booking=booking
                ).update(
                    is_available=True,
                    reserved_until=None,
                    booking=None
                )
                released_seats += seat_count
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully cleaned up {updated} expired bookings and released {released_seats} seats.'
                )
            )