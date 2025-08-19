from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import CustomService

@receiver([post_save, post_delete], sender=CustomService)
def update_submission_total(sender, instance, **kwargs):
    """Update the parent submission total whenever custom services change"""
    submission = instance.purchase
    submission.calculate_final_total()
