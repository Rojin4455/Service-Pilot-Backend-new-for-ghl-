
import requests
from celery import shared_task
from accounts.models import GHLAuthCredentials
from decouple import config
from accounts.utils import fetch_all_contacts


@shared_task
def make_api_call():
    credentials = GHLAuthCredentials.objects.first()
    
    print("credentials tokenL", credentials)
    refresh_token = credentials.refresh_token

    
    response = requests.post('https://services.leadconnectorhq.com/oauth/token', data={
        'grant_type': 'refresh_token',
        'client_id': config("GHL_CLIENT_ID"),
        'client_secret': config("GHL_CLIENT_SECRET"),
        'refresh_token': refresh_token
    })
    
    new_tokens = response.json()

    print("new tokens: ", new_tokens)

    obj, created = GHLAuthCredentials.objects.update_or_create(
            location_id= new_tokens.get("locationId"),
            defaults={
                "access_token": new_tokens.get("access_token"),
                "refresh_token": new_tokens.get("refresh_token"),
                "expires_in": new_tokens.get("expires_in"),
                "scope": new_tokens.get("scope"),
                "user_type": new_tokens.get("userType"),
                "company_id": new_tokens.get("companyId"),
                "user_id":new_tokens.get("userId"),

            }
        )
    


@shared_task
def fetch_all_contacts_task(location_id, access_token):
    """
    Celery task to fetch all contacts for a given location using the provided access token.
    """
    fetch_all_contacts(location_id, access_token)


from celery import shared_task
from accounts.models import GHLAuthCredentials
from django.utils.dateparse import parse_datetime
from accounts.utils import create_or_update_contact, delete_contact


@shared_task
def handle_webhook_event(data, event_type):
    try:
        if event_type in ["ContactCreate", "ContactUpdate"]:
            create_or_update_contact(data)
        elif event_type == "ContactDelete":
            delete_contact(data)
    except Exception as e:
        print(f"Error handling webhook event: {str(e)}")