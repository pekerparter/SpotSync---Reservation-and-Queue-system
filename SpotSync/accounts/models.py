from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils import timezone


class CustomUser(AbstractUser):
    STAFF_ROLES = [
        ('OWNER', 'Owner'),
        ('MANAGER', 'Manager'),
        ('WORKER', 'Worker'),
        ('CUSTOMER', 'Customer'),
    ]
    phone_number = models.CharField(max_length=15, blank=True)
    staff_role = models.CharField(max_length=10, choices=STAFF_ROLES, default='CUSTOMER')
    business = models.ForeignKey('Business', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff')
    objects = UserManager()

    @property
    def is_business_staff(self):
        return self.staff_role != 'CUSTOMER' and self.business is not None
    
    def __str__(self):
        return f"{self.username} - {self.get_staff_role_display()}"


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
    
class BusinessHours(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='business_hours')
    day = models.IntegerField(choices=DAYS_OF_WEEK)
    is_working_day = models.BooleanField(default=True)
    opening_time = models.TimeField(max_length=5, default="09:00")  # Store as "HH:MM"
    closing_time = models.TimeField(max_length=5, default="21:00")  # Store as "HH:MM"

    class Meta:
        unique_together = ('business', 'day')


class Business(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=30)
    opening_time = models.CharField(max_length=5, default="09:00")  # Store as "HH:MM"
    closing_time = models.CharField(max_length=5, default="21:00")  # Store as "HH:MM"
    categories = models.ManyToManyField(Category, related_name='businesses')
    image = models.ImageField(upload_to='business_images/', null=True, blank=True)
    people_in_queue = models.IntegerField(default=0)
    enable_time_estimation = models.BooleanField(default=False)
    time_per_customer = models.PositiveIntegerField(null=True, blank=True)
    estimated_wait_time = models.IntegerField(default=0)  # in minutes
    reservation_options = models.JSONField(null=True, blank=True)
    appointment_reasons = models.JSONField(null=True, blank=True)
    reservation_interval = models.IntegerField(default=60, null=True)  # Default to 60 minutes
    appointment_interval = models.IntegerField(default=30, null=True)  # Default to 30 minutes

    def get_business_hours(self):
        hours = self.business_hours.all()
        if not hours:
            # Create default business hours if not exist
            for day in range(7):
                BusinessHours.objects.create(
                    business=self,
                    day=day,
                    is_working_day=True if day < 5 else False,  # Mon-Fri working, Sat-Sun off
                    opening_time='09:00',
                    closing_time='17:00'
                )
            hours = self.business_hours.all()
        return hours
    
    def update_people_in_queue(self):
        active_queue_count = self.queue_set.filter(status='in_queue').count()
        if self.people_in_queue != active_queue_count:
            self.people_in_queue = active_queue_count
            self.save(update_fields=['people_in_queue'])
        
        return self.people_in_queue
    def get_people_in_queue(self):
        return self.update_people_in_queue()
    
    def update_estimated_wait_time(self):
        if self.enable_time_estimation and self.time_per_customer:
            self.estimated_wait_time = self.people_in_queue * self.time_per_customer
        else:
            self.estimated_wait_time = 0
        self.save(update_fields=['estimated_wait_time'])

    def get_role_permissions(self, role):
        try:
            return self.role_permissions.get(role=role)
        except BusinessRolePermission.DoesNotExist:
            return None

    def user_has_permission(self, user, permission):
        if user.is_superuser:
            return True
        role_permissions = self.get_role_permissions(user.staff_role)
        return getattr(role_permissions, permission, False) if role_permissions else False

    def __str__(self):
        return self.name

    def get_next_queue_position(self):
        return self.queue_set.filter(status='in_queue').count() + 1

    
    def update_queue_positions(self):
        with transaction.atomic():
            queues = list(self.queue_set.filter(status='in_queue').order_by('created_at'))
            
            updated_queues = []
            for index, queue in enumerate(queues, start=1):
                if queue.position != index:
                    queue.position = index
                    updated_queues.append(queue)
            
            if updated_queues:
                Queue.objects.bulk_update(updated_queues, ['position'])
            
            active_queue_count = len(queues)
            if self.people_in_queue != active_queue_count:
                self.people_in_queue = active_queue_count
                self.save(update_fields=['people_in_queue'])

    def update_people_in_queue(self):
        active_queue_count = self.queue_set.filter(status='in_queue').count()
        if self.people_in_queue != active_queue_count:
            self.people_in_queue = active_queue_count
            self.save(update_fields=['people_in_queue'])

class Queue(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    time = models.TimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    position = models.PositiveIntegerField(null=True, blank=True)
    estimated_wait_time = models.IntegerField(default=0)  # in minutes
    status = models.CharField(max_length=20, default='in_queue', choices=[
        ('in_queue', 'In Queue'),
        ('cancelled', 'Cancelled'),
        ('done', 'Done')
    ])

    def save(self, *args, **kwargs):
        if not self.pk and self.status == 'in_queue':
            # Cancel any existing 'in_queue' entries for this user and business
            Queue.objects.filter(
                business=self.business,
                user=self.user,
                status='in_queue'
            ).update(status='cancelled')
    
            # Set the position for the new entry
            self.position = self.business.get_next_queue_position()
    
            # Calculate estimated wait time
            if self.business.enable_time_estimation and self.business.time_per_customer:
                self.estimated_wait_time = self.position * self.business.time_per_customer
    
        super().save(*args, **kwargs)
        self.business.update_people_in_queue()
        self.business.update_estimated_wait_time()

    def delete(self, *args, **kwargs):
        business = self.business
        super().delete(*args, **kwargs)
        business.update_queue_positions()

    class Meta:
        indexes = [
            models.Index(fields=['business', 'user', 'status', 'date', 'time']),
        ]
        ordering = ['position']

    def __str__(self):
        return f"{self.user.username} - {self.business.name} - Position: {self.position}"

    @property
    def people_ahead(self):
        return Queue.objects.filter(
            business=self.business,
            status='in_queue',
            position__lt=self.position
        ).count()

class Appointment(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='booked', choices=[
        ('booked', 'Booked'),
        ('cancelled', 'Cancelled'),
        ('done', 'Done')
    ])

    def __str__(self):
        return f"{self.user.username} - {self.business.name} - {self.date} {self.time}"

class Reservation(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.CharField(max_length=10)  # Store as "HH:MM"
    option = models.CharField(max_length=255, null=True, blank=True)  # For storing "Arena 1", "Arena 2", etc.
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='booked', choices=[
        ('booked', 'Booked'),
        ('cancelled', 'Cancelled'),
        ('done', 'Done')
    ])

    class Meta:
        unique_together = ['business', 'date', 'time', 'option']  # Add 'option' to the unique constraint to ensure different options can be booked at the same time

    def __str__(self):
        return f"{self.business.name} - {self.date} {self.time} - {self.option}"
    
class BusinessRolePermission(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='role_permissions')
    role = models.CharField(max_length=10, choices=CustomUser.STAFF_ROLES)
    can_edit_info = models.BooleanField(default=False)
    can_edit_staff = models.BooleanField(default=False)
    can_display_customers = models.BooleanField(default=False)
    can_edit_availability = models.BooleanField(default=False)
    can_edit_service = models.BooleanField(default=False)

    class Meta:
        unique_together = ('business', 'role')

    def __str__(self):
        return f"{self.business.name} - {self.get_role_display()} Permissions"