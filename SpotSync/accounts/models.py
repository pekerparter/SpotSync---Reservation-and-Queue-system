from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils import timezone

class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True)
    objects = UserManager()

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Business(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=30)
    opening_time = models.CharField(max_length=5, default="09:00")  # Store as "HH:MM"
    closing_time = models.CharField(max_length=5, default="21:00")  # Store as "HH:MM"
    categories = models.ManyToManyField(Category, related_name='businesses')
    image = models.ImageField(upload_to='business_images/', null=True, blank=True)
    people_in_queue = models.IntegerField(default=0)
    estimated_wait_time = models.IntegerField(default=0)  # in minutes

    def __str__(self):
        return self.name


class Queue(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    time = models.TimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['business', 'user']

    def __str__(self):
        return f"{self.user.username} - {self.business.name} - {self.date} {self.time}"

class Appointment(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.business.name} - {self.date} {self.time}"

class Reservation(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.CharField(max_length=10)  # Store as "HH:MM"
    option = models.CharField(max_length=50)  # For storing "Arena 1", "Arena 2", etc.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['business', 'date', 'time', 'option']  # Add 'option' to the unique constraint

    def __str__(self):
        return f"{self.business.name} - {self.date} {self.time} - {self.option}"