from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import CustomService,QuoteSchedule, CustomerServiceSelection, CustomerPackageQuote
import requests
import json
from service_app.models import GlobalBasePrice

@receiver([post_save, post_delete], sender=CustomService)
def update_submission_total(sender, instance, **kwargs):
    """Update the parent submission total whenever custom services change"""
    submission = instance.purchase
    submission.calculate_final_total()





@receiver(post_save, sender=QuoteSchedule)
def handle_quote_submission(sender, instance, created, **kwargs):
    """
    Constructs and sends a payload to a webhook after a quote is submitted.
    """
    # Only proceed if the object was just submitted (is_submitted is True)
    if not created and instance.is_submitted:
        try:
            # Fetch related data
            submission = instance.submission
            contact = submission.contact
            address = submission.address
            
            customer_name = contact.first_name
            customer_email = contact.email
            customer_phone = contact.phone
            customer_address = submission.address.get_full_address() if submission.address else "N/A"
            
            # Retrieve all selected packages for the submission
            selected_services = CustomerServiceSelection.objects.filter(
                submission=submission,
                selected_package__isnull=False
            )
            
            jobs_selected = []
            total_price = float(0)
            for service_selection in selected_services:
                selected_package_quote = CustomerPackageQuote.objects.filter(
                    service_selection=service_selection,
                    is_selected=True
                ).first()
                
                if selected_package_quote:
                    job = {
                        "title": service_selection.service.name,
                        "price": float(selected_package_quote.total_price),
                        "duration": 180
                    }
                    jobs_selected.append(job)
                    total_price+=float(selected_package_quote.total_price)



            # Retrieve and add custom services to the jobs_selected list
            custom_services = CustomService.objects.filter(purchase=submission)
            for custom_service in custom_services:
                custom_job = {
                    "title": custom_service.product_name,
                    "price": float(custom_service.price),
                    "duration": 180
                }
                jobs_selected.append(custom_job)
                total_price+=float(custom_service.price)


            global_price = GlobalBasePrice.objects.first()
            adjustment_price = float(global_price.base_price) - total_price
            if adjustment_price < 0:
                adjustment_price = 0.0

            adjustment = {
                "title": "Adjustments",
                "price": adjustment_price,
                "duration": 180
            }
            jobs_selected.append(adjustment)


            print("jobs selected: :", jobs_selected)
            # Construct the final payload
            payload = {
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_address": customer_address,
                "customer_phone": customer_phone,
                "quoted_by": instance.quoted_by,
                "scheduled_date": instance.scheduled_date.isoformat(),
                "jobs_selected": jobs_selected,
                "first_time": instance.first_time
            }
            
            # Send the payload to the webhook URL
            webhook_url = "https://spelxsmrpbswmmahwzyg.supabase.co/functions/v1/quote-webhook"
            headers = {"Content-Type": "application/json"}

            print("payload: ", payload)
            response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
            response.raise_for_status()
            
            print(f"Successfully sent payload to webhook. Status Code: {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to send webhook payload: {e}")
        except Exception as e:
            print(f"An error occurred in the signal handler: {e}")