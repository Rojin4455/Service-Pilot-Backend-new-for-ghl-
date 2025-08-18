from django.urls import path
from accounts.views import auth_connect,tokens,callback,sync_all_contacts_and_address


urlpatterns = [
    path("auth/connect/", auth_connect, name="oauth_connect"),
    path("auth/tokens/", tokens, name="oauth_tokens"),
    path("auth/callback/", callback, name="oauth_callback"),
    path("sync_contacts/", sync_all_contacts_and_address, name="sync_contacts"),
]