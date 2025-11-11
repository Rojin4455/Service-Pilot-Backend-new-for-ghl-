from celery import shared_task
from invoice_app.services import invoice_sync

@shared_task
def sync_invoices_daily():
    invoice_sync()