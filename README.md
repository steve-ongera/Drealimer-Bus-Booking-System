# Drealimer - Bus Booking System

A comprehensive Django-based bus booking system designed for the Kenyan market, featuring seat selection, M-Pesa payment integration, and real-time availability management system.

## Features

### Core Functionality
- **Trip Search**: Search for available bus trips by origin, destination, and date
- **Interactive Seat Selection**: Visual seat map with real-time availability
- **Guest & User Bookings**: Support for both registered users and guest bookings
- **Payment Integration**: M-Pesa payment processing (ready for Safaricom API integration)
- **Booking Management**: Complete booking lifecycle from search to confirmation
- **Email & SMS Notifications**: Automated confirmation messages

### Advanced Features
- **Seat Layout Designer**: Admin interface for creating custom bus seat layouts
- **Temporary Seat Reservations**: 5-minute seat holds during booking process
- **Multi-stop Route Support**: Handle trips with intermediate stops
- **Responsive Design**: Mobile-friendly interface for on-the-go bookings
- **Location Autocomplete**: Smart location search with AJAX
- **Real-time Availability**: Live seat availability updates

## Technology Stack

- **Backend**: Django 4.x
- **Database**: PostgreSQL (recommended) / SQLite for development
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap
- **Payment**: M-Pesa STK Push API integration ready
- **Email**: Django Email Backend
- **SMS**: Integration ready for SMS providers

## Installation

### Prerequisites
- Python 3.8+
- pip
- virtualenv (recommended)
- PostgreSQL (for production)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/drealimer.git
   cd drealimer
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Database Setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Load Sample Data (Optional)**
   ```bash
   python manage.py loaddata fixtures/sample_data.json
   ```

7. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

Visit `http://127.0.0.1:8000` to access the application.

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/drealimer

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@drealimer.com

# M-Pesa Configuration (Production)
MPESA_CONSUMER_KEY=your-consumer-key
MPESA_CONSUMER_SECRET=your-consumer-secret
MPESA_SHORTCODE=your-shortcode
MPESA_PASSKEY=your-passkey
MPESA_ENVIRONMENT=sandbox  # or 'production'

# SMS Configuration
SMS_API_KEY=your-sms-api-key
SMS_SENDER_ID=DREALIMER
```

### Database Configuration

For PostgreSQL in production:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'drealimer',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Usage

### For Administrators

1. **Access Admin Panel**: `/admin/`
2. **Manage Bus Companies**: Add and configure transport companies
3. **Create Routes**: Set up origin-destination routes with stops
4. **Design Seat Layouts**: Use the visual seat layout designer
5. **Add Buses**: Configure buses with seat layouts and amenities
6. **Schedule Trips**: Create trip schedules with pricing

### For Customers

1. **Search Trips**: Enter origin, destination, and travel date
2. **Select Seats**: Choose preferred seats from interactive seat map
3. **Booking Details**: Provide passenger information
4. **Payment**: Complete payment via M-Pesa
5. **Confirmation**: Receive booking confirmation via email/SMS

## API Endpoints

### Public Endpoints
- `GET /api/location-autocomplete/` - Location search autocomplete
- `POST /api/reserve-seats/` - Temporarily reserve seats
- `POST /api/process-payment/` - Process M-Pesa payment

### Admin Endpoints
- `GET /admin/seat-layouts/` - Seat layout management
- `POST /api/save-seat-layout/` - Save seat layout design

## Models Overview

### Core Models
- **Company**: Bus transport companies
- **Location**: Cities and towns
- **Route**: Travel routes with stops
- **SeatLayout**: Configurable bus seat arrangements
- **Bus**: Individual buses with specifications
- **Trip**: Scheduled trips
- **Booking**: Customer bookings
- **Payment**: Payment transactions

### Relationship Structure
```
Company → Bus → Trip → Booking
Route → Trip
SeatLayout → Bus → Seat → BookingSeat
```

## Payment Integration

### M-Pesa STK Push Integration

The system is ready for M-Pesa integration. Update the `process_payment` view with actual Safaricom API calls:

```python
# In views.py - replace mock implementation
def process_mpesa_payment(booking, phone_number):
    # Implement actual M-Pesa STK Push
    # Return transaction status
    pass
```

## Deployment

### Production Checklist

1. **Security Settings**
   - Set `DEBUG = False`
   - Configure `ALLOWED_HOSTS`
   - Use strong `SECRET_KEY`
   - Enable HTTPS

2. **Database**
   - Use PostgreSQL
   - Set up regular backups
   - Configure connection pooling

3. **Static Files**
   ```bash
   python manage.py collectstatic
   ```

4. **Web Server**
   - Configure Nginx/Apache
   - Set up Gunicorn/uWSGI
   - Configure SSL certificates

5. **Monitoring**
   - Set up logging
   - Configure error tracking
   - Monitor performance

### Docker Deployment (Optional)

```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "drealimer.wsgi:application"]
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Testing

Run the test suite:
```bash
python manage.py test
```

For coverage reporting:
```bash
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

## Support

For support and questions:
- Email: support@drealimer.com
- Documentation: [Wiki](https://github.com/yourusername/drealimer/wiki)
- Issues: [GitHub Issues](https://github.com/yourusername/drealimer/issues)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built for the Kenyan transportation industry
- Inspired by modern booking platforms
- Designed with mobile-first approach
- Optimized for East African market needs

---

**Drealimer** - Simplifying bus travel across Kenya 🚌