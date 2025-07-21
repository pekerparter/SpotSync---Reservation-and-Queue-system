
from django.core.management.base import BaseCommand
from accounts.models import Business, Category
from django.core.exceptions import ValidationError
from django.utils.timezone import make_aware
from datetime import datetime

class Command(BaseCommand):
    help = 'Creates a new business entry'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating a new business entry...'))

        # Required fields
        name = input("Enter business name: ")
        address = input("Enter business address: ")
        phone_number = input("Enter business phone number: ")

        # Optional fields with defaults
        opening_time = input("Enter opening time (HH:MM) [default: 09:00]: ") or "09:00"
        closing_time = input("Enter closing time (HH:MM) [default: 21:00]: ") or "21:00"

        # Optional boolean field
        enable_time_estimation = input("Enable time estimation? (y/n) [default: n]: ").lower() == 'y'

        # Optional integer fields
        time_per_customer = input("Enter time per customer in minutes (leave blank for null): ")
        time_per_customer = int(time_per_customer) if time_per_customer else None

        reservation_interval = input("Enter reservation interval in minutes [default: 60]: ")
        reservation_interval = int(reservation_interval) if reservation_interval else 60

        appointment_interval = input("Enter appointment interval in minutes [default: 30]: ")
        appointment_interval = int(appointment_interval) if appointment_interval else 30

        # Optional float fields
        latitude = input("Enter latitude (leave blank for null): ")
        latitude = float(latitude) if latitude else None

        longitude = input("Enter longitude (leave blank for null): ")
        longitude = float(longitude) if longitude else None

        # Create the business
        try:
            business = Business.objects.create(
                name=name,
                address=address,
                phone_number=phone_number,
                opening_time=opening_time,
                closing_time=closing_time,
                enable_time_estimation=enable_time_estimation,
                time_per_customer=time_per_customer,
                reservation_interval=reservation_interval,
                appointment_interval=appointment_interval,
                latitude=latitude,
                longitude=longitude
            )

            # Handle categories
            self.stdout.write("Select categories for the business:")
            categories = Category.objects.all()
            for category in categories:
                if input(f"Add category '{category.name}'? (y/n): ").lower() == 'y':
                    business.categories.add(category)

            # Handle reservation options
            reservation_options = []
            while True:
                option = input("Enter a reservation option (or press enter to finish): ")
                if not option:
                    break
                reservation_options.append(option)
            business.reservation_options = reservation_options

            # Handle appointment reasons
            appointment_reasons = []
            while True:
                reason = input("Enter an appointment reason (or press enter to finish): ")
                if not reason:
                    break
                appointment_reasons.append(reason)
            business.appointment_reasons = appointment_reasons

            business.save()

            self.stdout.write(self.style.SUCCESS(f'Successfully created business: {business.name}'))

        except ValidationError as e:
            self.stdout.write(self.style.ERROR(f'Error creating business: {e}'))