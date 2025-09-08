from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('search/', views.search_trips, name='search_trips'),
    
    # Trip and booking flow
    path('trip/<int:trip_id>/seats/', views.trip_seats, name='trip_seats'),
    path('trip/<int:trip_id>/booking/', views.booking_details, name='booking_details'),
    path('payment/<str:booking_id>/', views.payment, name='payment'),
    path('confirmation/<str:booking_id>/', views.booking_confirmation, name='booking_confirmation'),
    path('booking/<str:booking_id>/expired/', views.booking_expired, name='booking_expired'),
    # PDF download URLs
    path('booking/<str:booking_id>/pdf/', views.download_booking_pdf, name='download_booking_pdf'),
    
    # AJAX endpoints
    path('api/location-autocomplete/', views.location_autocomplete, name='location_autocomplete'),
    path('api/reserve-seats/', views.reserve_seats, name='reserve_seats'),
    path('api/process-payment/', views.process_payment, name='process_payment'),
    
    # Admin seat layout management
    path('admin-seat-layouts/', views.admin_seat_layout, name='admin_seat_layout'),
    path('admin-seat-layouts/<int:layout_id>/', views.admin_seat_layout, name='admin_seat_layout_edit'),
    path('api/save-seat-layout/', views.save_seat_layout, name='save_seat_layout'),

    path('booking/<str:booking_id>/not-found/', views.booking_not_found, name='booking_not_found'),
    path('trip/not-available/',  views.trip_not_available, name='trip_not_available'),    
    path('payment/failed/',  views.payment_failed,  name='payment_failed'),
]