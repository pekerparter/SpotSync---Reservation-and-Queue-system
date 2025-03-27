from django.core.management.base import BaseCommand
from accounts.models import Category, Business
from django.core.files import File
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Populate the database with sample businesses'

    def handle(self, *args, **kwargs):
        Category.objects.all().delete()
        Business.objects.all().delete()

        categories = ['Waiting list', 'Appointments', 'Reservations']
        businesses = [
            ('Waiting list', ['Restaurant', 'Clinic', 'Bank', 'Restaurant2', 'TecSupCen']),
            ('Appointments', ['Barber', 'Office', 'Beauty saloon', 'Agency', 'Language school']),
            ('Reservations', ['Football field', 'Volleyball court', 'Basketball court', 'Events arena', 'Music studio']),
        ]

        for cat_name in categories:
            category = Category.objects.create(name=cat_name)
            self.stdout.write(self.style.SUCCESS(f'Created category: {cat_name}'))

            for business_name in next(b[1] for b in businesses if b[0] == cat_name):
                image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
                image_path = None
                image_name = None

                # Try with spaces and underscores
                for name_variant in [business_name, business_name.replace(' ', '_')]:
                    for ext in image_extensions:
                        temp_image_name = f"{name_variant}{ext}"
                        temp_image_path = os.path.join(settings.BASE_DIR, 'static', 'accounts', 'images', temp_image_name)
                        if os.path.exists(temp_image_path):
                            image_path = temp_image_path
                            image_name = temp_image_name
                            break
                    if image_path:
                        break

                try:
                    business = Business.objects.create(name=business_name)
                    business.categories.add(category)

                    if image_path:
                        with open(image_path, 'rb') as f:
                            business.image.save(image_name, File(f), save=True)
                        self.stdout.write(self.style.SUCCESS(f'Created business: {business_name} with image {image_name}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Image not found for: {business_name}'))
                        self.stdout.write(self.style.SUCCESS(f'Created business: {business_name} without image'))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error creating business: {business_name}. Error: {str(e)}'))
        self.stdout.write(self.style.SUCCESS('Database populated successfully'))

