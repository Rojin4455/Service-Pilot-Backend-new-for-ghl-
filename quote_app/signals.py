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

    print("🚀 Signal triggered for QuoteSchedule:", instance.id)

    # Only proceed if the object was just submitted (is_submitted is True)
    if not created:
        try:
            print("✅ QuoteSchedule is submitted. Proceeding...")

            # Fetch related data
            submission = instance.submission
            contact = submission.contact
            address = submission.address
            

            print(f"Submission ID: {submission.id}")
            print(f"Contact: {contact.first_name}, {contact.email}, {contact.phone}")
            print(f"Address: {address.get_full_address() if address else 'N/A'}")

            customer_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
            customer_email = contact.email
            customer_phone = contact.phone
            ghl_contact_id = contact.contact_id
            customer_address = submission.address.get_full_address() if submission.address else "N/A"

            # Retrieve all selected packages for the submission
            selected_services = CustomerServiceSelection.objects.filter(
                submission=submission,
                selected_package__isnull=False
            )
            print(f"Found {selected_services.count()} selected services")

            jobs_selected = []
            total_price = float(0)

            for service_selection in selected_services:
                print(f"Processing service: {service_selection.service.name}")

                selected_package_quote = CustomerPackageQuote.objects.filter(
                    service_selection=service_selection,
                    is_selected=True
                ).first()

                if selected_package_quote:
                    print(f" → Selected package price: {selected_package_quote.total_price}")
                    job = {
                        "title": service_selection.service.name,
                        "price": float(selected_package_quote.total_price),
                        "duration": 30
                    }
                    jobs_selected.append(job)
                    total_price += float(selected_package_quote.total_price)
                else:
                    print(" → No selected package quote found for this service.")

            # Retrieve and add custom services to the jobs_selected list
            custom_services = CustomService.objects.filter(purchase=submission,is_active=True)
            print(f"Found {custom_services.count()} custom services")

            for custom_service in custom_services:
                print(f"Processing custom service: {custom_service.product_name}, Price: {custom_service.price}")
                custom_job = {
                    "title": custom_service.product_name,
                    "price": float(custom_service.price),
                    "duration": 30
                }
                jobs_selected.append(custom_job)
                total_price += float(custom_service.price)

            # Add adjustment job
            global_price = GlobalBasePrice.objects.first()
            adjustment_price = float(global_price.base_price) - total_price
            if adjustment_price < 0:
                adjustment_price = 0.0

            if adjustment_price != 0.0:
                adjustment = {
                    "title": "Adjustments",
                    "price": adjustment_price,
                    "duration": 30
                }
                jobs_selected.append(adjustment)

            print("📝 Final jobs_selected:", jobs_selected)

            # Construct the final payload
            payload = {
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_address": customer_address,
                "customer_phone": customer_phone,
                "ghl_contact_id":ghl_contact_id,
                "quoted_by": instance.quoted_by,
                "scheduled_date": instance.scheduled_date.isoformat() if instance.scheduled_date else None,
                "jobs_selected": jobs_selected,
                "first_time": instance.first_time
            }

            print("📦 Final Payload to Webhook:", json.dumps(payload, indent=2))

            # Send the payload to the webhook URL
            webhook_url = "https://spelxsmrpbswmmahwzyg.supabase.co/functions/v1/quote-webhook"
            headers = {"Content-Type": "application/json"}

            response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
            response.raise_for_status()

            print(f"✅ Successfully sent payload to webhook. Status Code: {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send webhook payload: {e}")
        except Exception as e:
            print(f"⚠️ An error occurred in the signal handler: {e}")
    else:
        print("⚠️ Signal ignored: Either created=True or is_submitted=False")
    