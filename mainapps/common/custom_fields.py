from django.db import models
from django.core.validators import MinValueValidator

class MoneyField(models.DecimalField):
    def __init__(self, *args, **kwargs):
        kwargs['max_digits'] = 19
        kwargs['decimal_places'] = 2 
        kwargs['validators'] = [MinValueValidator(0)] 
        super().__init__(*args, **kwargs)

