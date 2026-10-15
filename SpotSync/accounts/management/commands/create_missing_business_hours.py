from accounts.models import Business
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Creates default business hours for businesses that dont have any'

    def handle(self, *args, **options):
        businesses = Business.objects.all()
        for business in businesses:
            if not business.business_hours.exists():
                business.create_default_business_hours()
                self.stdout.write(self.style.SUCCESS(f'Created default business hours for {business.name}'))

        self.stdout.write(self.style.SUCCESS('Finished creating missing business hours'))