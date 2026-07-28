from django.db import models

class Passenger(models.Model):
    telegram_id = models.IntegerField(unique=True)
    full_name = models.TextField()
    phone = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'passengers'

class Driver(models.Model):
    telegram_id = models.IntegerField(unique=True)
    full_name = models.TextField()
    phone = models.TextField(blank=True, null=True)
    car_model = models.TextField(blank=True, null=True)
    car_number = models.TextField(blank=True, null=True)
    is_approved = models.IntegerField(default=0)
    is_online = models.IntegerField(default=0)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    rating = models.FloatField(default=5.0)
    total_rides = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'drivers'

class Order(models.Model):
    # Bu yerda ForeignKey to'g'ri bog'lanishi uchun to_field='telegram_id' berilishi kerak 
    # chunki bot telegram_id ni yozgan. Lekin Django primary key 'id' ni kutadi, shuning uchun 
    # eng to'g'risi integer sifatida olishdir.
    passenger_id = models.IntegerField()
    driver_id = models.IntegerField(blank=True, null=True)
    pickup_lat = models.FloatField()
    pickup_lng = models.FloatField()
    pickup_address = models.TextField(blank=True, null=True)
    dest_lat = models.FloatField(blank=True, null=True)
    dest_lng = models.FloatField(blank=True, null=True)
    dest_address = models.TextField(blank=True, null=True)
    distance_km = models.FloatField(blank=True, null=True)
    price = models.IntegerField(blank=True, null=True)
    status = models.TextField(default='searching')
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'orders'
