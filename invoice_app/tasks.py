from celery import shared_task
from invoice_app.services import sync_invoices

@shared_task
def sync_invoices_daily():
    sync_invoices()