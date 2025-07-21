
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Business, CustomUser, BusinessRolePermission

class Command(BaseCommand):
    help = 'Make an existing user the owner of a business using IDs'

    def handle(self, *args, **options):
        User = get_user_model()

        # Get the user ID
        user_id = input("Enter the ID of the user you want to make a business owner: ")
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with ID "{user_id}" does not exist.'))
            return
        except ValueError:
            self.stdout.write(self.style.ERROR("Invalid user ID. Please enter a number."))
            return

        # Get the business ID
        business_id = input("Enter the ID of the business: ")
        
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Business with ID "{business_id}" does not exist.'))
            return
        except ValueError:
            self.stdout.write(self.style.ERROR("Invalid business ID. Please enter a number."))
            return

        # Update the user's role and associate with the business
        user.staff_role = 'OWNER'
        user.business = business
        user.save()

        # Create or update BusinessRolePermission for the owner
        BusinessRolePermission.objects.update_or_create(
            business=business,
            role='OWNER',
            defaults={
                'can_edit_info': True,
                'can_edit_staff': True,
                'can_display_customers': True,
                'can_edit_availability': True,
                'can_edit_service': True
            }
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully made user (ID: {user_id}) the owner of business (ID: {business_id})'))

        # Display user and business details for confirmation
        self.stdout.write(f"\nUser Details:")
        self.stdout.write(f"ID: {user.id}")
        self.stdout.write(f"Username: {user.username}")
        self.stdout.write(f"Email: {user.email}")
        self.stdout.write(f"Staff Role: {user.get_staff_role_display()}")

        self.stdout.write(f"\nBusiness Details:")
        self.stdout.write(f"ID: {business.id}")
        self.stdout.write(f"Name: {business.name}")