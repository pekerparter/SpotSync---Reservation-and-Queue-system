from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager

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
    address = models.CharField(max_length=200, default="No address specified")
    phone_number = models.CharField(max_length=30, default="No Phone Number Specified")
    categories = models.ManyToManyField(Category, related_name='businesses')
    image = models.ImageField(upload_to='business_images/', null=True, blank=True)
    people_in_queue = models.IntegerField(default=0)
    estimated_wait_time = models.IntegerField(default=0)  # in minutes

    def __str__(self):
        return self.name


class Queue(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'business')

