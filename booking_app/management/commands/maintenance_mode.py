# management/commands/maintenance_mode.py

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Enable or disable maintenance mode for the DreamLine Bus Service'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['on', 'off', 'status'],
            help='Action to perform: on/off/status'
        )
        
        parser.add_argument(
            '--duration',
            type=int,
            help='Maintenance duration in minutes (default: 30)',
            default=30
        )
        
        parser.add_argument(
            '--message',
            type=str,
            help='Custom maintenance message',
            default='We are performing scheduled maintenance to improve your experience.'
        )
        
        parser.add_argument(
            '--eta',
            type=str,
            help='Estimated time to completion (e.g., "30 minutes", "1 hour")',
            default=None
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'on':
            self.enable_maintenance(options)
        elif action == 'off':
            self.disable_maintenance()
        elif action == 'status':
            self.show_status()

    def enable_maintenance(self, options):
        """Enable maintenance mode"""
        duration = options['duration']
        message = options['message']
        eta = options['eta'] or f"{duration} minutes"
        
        # Set maintenance mode in cache
        cache.set('maintenance_mode', True, timeout=None)  # No timeout
        cache.set('maintenance_message', message, timeout=None)
        cache.set('maintenance_eta', eta, timeout=None)
        cache.set('maintenance_start_time', timezone.now().isoformat(), timeout=None)
        
        # Set automatic disable if duration is specified
        if duration > 0:
            end_time = timezone.now() + timedelta(minutes=duration)
            cache.set('maintenance_end_time', end_time.isoformat(), timeout=None)
        
        self.stdout.write(
            self.style.WARNING(
                f'✓ Maintenance mode ENABLED\n'
                f'  Duration: {eta}\n'
                f'  Message: {message}\n'
                f'  Started: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
            )
        )
        
        # Show instructions
        self.stdout.write(
            self.style.SUCCESS(
                '\nInstructions:\n'
                f'• To disable: python manage.py maintenance_mode off\n'
                f'• To check status: python manage.py maintenance_mode status\n'
                f'• Admin users can still access the site normally\n'
                f'• Health check endpoint remains available'
            )
        )

    def disable_maintenance(self):
        """Disable maintenance mode"""
        was_enabled = cache.get('maintenance_mode', False)
        
        if not was_enabled:
            self.stdout.write(
                self.style.WARNING('Maintenance mode is already disabled.')
            )
            return
        
        # Get maintenance info before clearing
        start_time_str = cache.get('maintenance_start_time')
        if start_time_str:
            start_time = timezone.datetime.fromisoformat(start_time_str)
            duration = timezone.now() - start_time
            duration_str = str(duration).split('.')[0]  # Remove microseconds
        else:
            duration_str = 'Unknown'
        
        # Clear maintenance mode from cache
        cache.delete('maintenance_mode')
        cache.delete('maintenance_message')
        cache.delete('maintenance_eta')
        cache.delete('maintenance_start_time')
        cache.delete('maintenance_end_time')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Maintenance mode DISABLED\n'
                f'  Total maintenance time: {duration_str}\n'
                f'  Site is now fully operational'
            )
        )

    def show_status(self):
        """Show current maintenance mode status"""
        is_enabled = cache.get('maintenance_mode', False)
        
        if not is_enabled:
            self.stdout.write(
                self.style.SUCCESS('✓ Maintenance mode is DISABLED - Site is operational')
            )
            return
        
        # Get maintenance details
        message = cache.get('maintenance_message', 'No message set')
        eta = cache.get('maintenance_eta', 'Unknown')
        start_time_str = cache.get('maintenance_start_time')
        end_time_str = cache.get('maintenance_end_time')
        
        self.stdout.write(
            self.style.WARNING('⚠ Maintenance mode is ENABLED')
        )
        
        self.stdout.write(f'Message: {message}')
        self.stdout.write(f'Estimated duration: {eta}')
        
        if start_time_str:
            start_time = timezone.datetime.fromisoformat(start_time_str)
            elapsed = timezone.now() - start_time
            elapsed_str = str(elapsed).split('.')[0]
            self.stdout.write(f'Started: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
            self.stdout.write(f'Elapsed time: {elapsed_str}')
        
        if end_time_str:
            end_time = timezone.datetime.fromisoformat(end_time_str)
            if timezone.now() > end_time:
                self.stdout.write(
                    self.style.ERROR('⚠ Scheduled end time has passed! Consider disabling maintenance mode.')
                )
            else:
                remaining = end_time - timezone.now()
                remaining_str = str(remaining).split('.')[0]
                self.stdout.write(f'Scheduled end: {end_time.strftime("%Y-%m-%d %H:%M:%S")}')
                self.stdout.write(f'Time remaining: {remaining_str}')


# Additional utility command for error monitoring
class ErrorMonitorCommand(BaseCommand):
    """Command to monitor and report error statistics"""
    
    help = 'Monitor error statistics and generate reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            choices=['hour', 'day', 'week'],
            default='day',
            help='Time period to analyze (default: day)'
        )
        
        parser.add_argument(
            '--top',
            type=int,
            default=10,
            help='Number of top errors to show (default: 10)'
        )

    def handle(self, *args, **options):
        period = options['period']
        top_n = options['top']
        
        self.stdout.write(
            self.style.SUCCESS(f'Error Report - Last {period}')
        )
        self.stdout.write('=' * 50)
        
        # This would typically read from log files or a monitoring system
        # For now, we'll show a sample report structure
        
        if period == 'hour':
            window = 'last hour'
        elif period == 'day':
            window = 'last 24 hours'
        else:
            window = 'last week'
        
        self.stdout.write(f'Time period: {window}')
        self.stdout.write(f'Top {top_n} errors:\n')
        
        # Sample error data (in real implementation, this would come from logs)
        sample_errors = [
            ('404 - Page Not Found', 45, '/search/trips/invalid'),
            ('500 - Server Error', 12, '/booking/process-payment'),
            ('403 - Forbidden', 8, '/admin/dashboard'),
            ('429 - Rate Limited', 5, '/api/search'),
        ]
        
        for i, (error, count, path) in enumerate(sample_errors[:top_n], 1):
            self.stdout.write(f'{i:2d}. {error:<25} {count:>3} occurrences - {path}')
        
        self.stdout.write(f'\n📊 Total errors: {sum(count for _, count, _ in sample_errors)}')
        self.stdout.write(f'🚨 Critical errors: {sum(count for error, count, _ in sample_errors if "500" in error)}')
        
        self.stdout.write(
            self.style.SUCCESS(
                '\nRecommendations:\n'
                '• Monitor 500 errors closely\n'
                '• Consider adding redirects for common 404s\n'
                '• Review rate limiting settings if 429s are high\n'
                '• Check logs for detailed error information'
            )
        )