from accounts.models import GHLAuthCredentials
import requests
from decouple import config


def create_or_update_ghl_contact(submission, is_submit=False):
    try:
        print("🔹 Starting GHL contact sync...")
        credentials = GHLAuthCredentials.objects.first()
        if not credentials:
            print("❌ No GHLAuthCredentials found in DB.")
            return

        token = credentials.access_token
        location_id = credentials.location_id
        print(f"✅ Using token (truncated): {token[:10]}..., locationId: {location_id}")

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Version": "2021-07-28",
            "Content-Type": "application/json"
        }

        # Step 1: Determine search URL
        if submission.contact.contact_id:
            search_url = f"https://services.leadconnectorhq.com/contacts/{submission.contact.contact_id}"
            print(f"🔍 Searching by contact_id: {submission.contact.contact_id}")
        else:
            search_query = submission.contact.email or submission.contact.first_name
            if not search_query:
                print("❌ No identifier (email/first_name) to search GHL contact.")
                return
            search_url = f"https://services.leadconnectorhq.com/contacts/?locationId={location_id}&query={search_query}"
            print(f"🔍 Searching by query: {search_query}")

        # Step 2: Fetch existing contact
        print(f"➡️ Sending GET request to {search_url}")
        search_response = requests.get(search_url, headers=headers)
        print(f"⬅️ Response [{search_response.status_code}]: {search_response.text}")

        if search_response.status_code != 200:
            print("❌ Failed to search GHL contact.")
            return

        search_data = search_response.json()
        results = []

        # Handle both cases: list of contacts or single contact
        if "contacts" in search_data and isinstance(search_data["contacts"], list):
            results = search_data["contacts"]
            print(f"📋 Found {len(results)} contacts in search results.")
        elif "contact" in search_data and isinstance(search_data["contact"], dict):
            results = [search_data["contact"]]
            print("📋 Found 1 contact in search results.")
        else:
            print("ℹ️ No contacts found in GHL.")

        # Step 3: Build custom fields
        booking_url = f"{config('BASE_FRONTEND_URI')}/booking?submission_id={submission.id}"
        quote_url = f"{config('BASE_FRONTEND_URI')}/quote/details/{submission.id}"

        custom_fields = [{
            "id": "AfQbphMXdk6rk6vnWPPU",
            "field_value": quote_url if is_submit else booking_url
        }]
        print(f"🛠 Custom fields prepared: {custom_fields}")

        # Step 4: Update or create contact
        if results:
            ghl_contact_id = results[0]["id"]
            tags = results[0].get("tags", [])
            contact_payload = {"customFields": custom_fields}

            if is_submit:
                if "quote submitted" not in tags:
                    tags.append("quote submitted")
                contact_payload["tags"] = tags
            else:
                if "quoted" not in tags:
                    tags.append("quoted")
                contact_payload["tags"] = tags

            print(f"✏️ Updating contact {ghl_contact_id} with payload: {contact_payload}")
            contact_response = requests.put(
                f"https://services.leadconnectorhq.com/contacts/{ghl_contact_id}",
                json=contact_payload,
                headers=headers
            )
        else:
            contact_payload = {
                "firstName": submission.contact.first_name,
                "email": submission.contact.email,
                "phone": submission.contact.phone,
                "locationId": location_id,
                "customFields": custom_fields
            }
            print(f" Creating new contact with payload: {contact_payload}")
            contact_response = requests.post(
                "https://services.leadconnectorhq.com/contacts/",
                json=contact_payload,
                headers=headers
            )

        print(f"⬅️ Contact sync response [{contact_response.status_code}]: {contact_response.text}")

        if contact_response.status_code not in [200, 201]:
            print("❌ Failed to create/update contact in GHL.")
            return

        print("✅ Contact synced successfully.")

    except Exception as e:
        print(f"🔥 Error syncing contact: {e}")
