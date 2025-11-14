from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q, Sum, Count
from django.utils.dateparse import parse_datetime
from django_filters import rest_framework as filters
from .models import Invoice, InvoiceItem
from .serializers import InvoiceSerializer, InvoiceDetailSerializer, InvoiceItemSerializer
from .services.invoice_sync import sync_invoices


from django.utils import timezone
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from datetime import timedelta


class InvoiceFilter(filters.FilterSet):
    """Filter class for Invoice model"""
    
    search = filters.CharFilter(method='filter_search')
    status = filters.MultipleChoiceFilter(field_name='status', choices=Invoice.STATUS_CHOICES)
    
    issue_date_from = filters.DateTimeFilter(field_name='issue_date', lookup_expr='gte')
    issue_date_to = filters.DateTimeFilter(field_name='issue_date', lookup_expr='lte')
    due_date_from = filters.DateTimeFilter(field_name='due_date', lookup_expr='gte')
    due_date_to = filters.DateTimeFilter(field_name='due_date', lookup_expr='lte')
    created_date_from = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_date_to = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    total_min = filters.NumberFilter(field_name='total', lookup_expr='gte')
    total_max = filters.NumberFilter(field_name='total', lookup_expr='lte')
    amount_due_min = filters.NumberFilter(field_name='amount_due', lookup_expr='gte')
    amount_due_max = filters.NumberFilter(field_name='amount_due', lookup_expr='lte')
    
    contact_id = filters.CharFilter(field_name='contact_id')
    contact_email = filters.CharFilter(field_name='contact_email', lookup_expr='icontains')
    contact_name = filters.CharFilter(field_name='contact_name', lookup_expr='icontains')
    
    location_id = filters.CharFilter(field_name='location_id')
    company_id = filters.CharFilter(field_name='company_id')
    
    is_overdue = filters.BooleanFilter(method='filter_overdue')
    is_paid = filters.BooleanFilter(method='filter_paid')
    has_balance = filters.BooleanFilter(method='filter_has_balance')
    
    class Meta:
        model = Invoice
        fields = ['status', 'location_id', 'company_id', 'contact_id', 'invoice_number', 'currency']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(invoice_number__icontains=value) |
            Q(name__icontains=value) |
            Q(contact_name__icontains=value) |
            Q(contact_email__icontains=value) |
            Q(contact_phone__icontains=value)
        )
    
    def filter_overdue(self, queryset, name, value):
        from django.utils import timezone
        if value:
            return queryset.filter(
                due_date__lt=timezone.now(),
                amount_due__gt=0
            ).exclude(status__in=['paid', 'void'])
        return queryset.exclude(due_date__lt=timezone.now(), amount_due__gt=0)
    
    def filter_paid(self, queryset, name, value):
        if value:
            return queryset.filter(status='paid', amount_due=0)
        return queryset.exclude(status='paid')
    
    def filter_has_balance(self, queryset, name, value):
        if value:
            return queryset.filter(amount_due__gt=0)
        return queryset.filter(amount_due=0)


class InvoiceViewSet(viewsets.ModelViewSet):
    """ViewSet for Invoice model"""
    queryset = Invoice.objects.all().prefetch_related('items')
    serializer_class = InvoiceSerializer
    permission_classes = [AllowAny]
    filterset_class = InvoiceFilter
    ordering_fields = ['created_at', 'updated_at', 'issue_date', 'due_date', 'total', 'amount_due', 'invoice_number', 'status']
    ordering = ['-created_at']
    search_fields = ['invoice_number', 'contact_name', 'contact_email']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InvoiceDetailSerializer
        return InvoiceSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if hasattr(user, 'location_id') and user.location_id:
            queryset = queryset.filter(location_id=user.location_id)
        return queryset
    
    @action(detail=False, methods=['post'])
    def sync(self, request):
        """Sync invoices from GHL API"""

        print("triggered here")
        location_id = request.data.get('location_id')
        invoice_id = request.data.get('invoice_id')
        
        if not location_id:
            return Response({'error': 'location_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = sync_invoices(location_id, invoice_id)
            
            if invoice_id:
                if result:
                    serializer = self.get_serializer(result)
                    return Response({'message': 'Invoice synced successfully', 'invoice': serializer.data})
                else:
                    return Response({'error': 'Failed to sync invoice'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'message': 'Invoices synced successfully', 'statistics': result})
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Sync failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get invoice statistics"""
        queryset = self.filter_queryset(self.get_queryset())
        
        location_id = request.query_params.get('location_id')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        
        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=parse_datetime(date_from))
        
        date_to = request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=parse_datetime(date_to))
        
        stats = queryset.aggregate(
            total_invoices=Count('id'),
            total_amount=Sum('total'),
            total_paid=Sum('amount_paid'),
            total_due=Sum('amount_due')
        )
        
        status_breakdown = {}
        for choice_value, choice_label in Invoice.STATUS_CHOICES:
            count = queryset.filter(status=choice_value).count()
            status_breakdown[choice_value] = {'count': count, 'label': choice_label}
        
        from django.utils import timezone
        overdue_count = queryset.filter(
            due_date__lt=timezone.now(),
            amount_due__gt=0
        ).exclude(status__in=['paid', 'void']).count()
        
        return Response({
            'statistics': stats,
            'status_breakdown': status_breakdown,
            'overdue_count': overdue_count
        })


    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """
        Comprehensive invoice analytics endpoint.
        Returns summarized and trend data (daily/weekly/monthly).
        """
        queryset = self.filter_queryset(self.get_queryset())

        # === Query Params ===
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        granularity = request.query_params.get("granularity", "daily")  # daily | weekly | monthly
        location_id = request.query_params.get("location_id")

        if location_id:
            queryset = queryset.filter(location_id=location_id)

        if start_date:
            start_date = parse_datetime(start_date)
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            end_date = parse_datetime(end_date)
            queryset = queryset.filter(created_at__lte=end_date)
        else:
            end_date = timezone.now()

        # === Base Stats ===
        total_invoices = queryset.count()
        total_amount = queryset.aggregate(Sum("total"))["total__sum"] or 0
        total_paid = queryset.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
        total_due = queryset.aggregate(Sum("amount_due"))["amount_due__sum"] or 0

        overdue_qs = queryset.filter(
            due_date__lt=timezone.now(),
            amount_due__gt=0
        ).exclude(status__in=["paid", "void"])
        overdue_count = overdue_qs.count()
        overdue_total = overdue_qs.aggregate(Sum("amount_due"))["amount_due__sum"] or 0

        # === Paid vs Unpaid ===
        paid_count = queryset.filter(status="paid").count()
        unpaid_count = queryset.exclude(status="paid").count()

        paid_total = queryset.filter(status="paid").aggregate(Sum("total"))["total__sum"] or 0
        unpaid_total = queryset.exclude(status="paid").aggregate(Sum("total"))["total__sum"] or 0

        # === Status Distribution ===
        status_distribution = {}
        now = timezone.now()
        
        # Calculate Due and Overdue dynamically based on due_date
        # Due: invoices with due_date >= today and amount_due > 0, status not paid/void
        due_queryset = queryset.filter(
            due_date__gte=now,
            amount_due__gt=0,
            status='sent',
        )
        due_count = due_queryset.count()
        due_total = due_queryset.aggregate(Sum("total"))["total__sum"] or 0
        status_distribution["due"] = {
            "label": "Due",
            "count": due_count,
            "total": due_total,
        }
        
        # Overdue: invoices with due_date < today and amount_due > 0, status not paid/void
        overdue_queryset = queryset.filter(
            due_date__lt=now,
            amount_due__gt=0,
            status='sent'
        )
        overdue_count = overdue_queryset.count()
        overdue_total = overdue_queryset.aggregate(Sum("total"))["total__sum"] or 0
        status_distribution["overdue"] = {
            "label": "Overdue",
            "count": overdue_count,
            "total": overdue_total,
        }
        
        # Keep other statuses from STATUS_CHOICES (excluding 'overdue' since we calculate it dynamically)
        for value, label in Invoice.STATUS_CHOICES:
            if value != 'overdue':  # Skip 'overdue' as we calculate it dynamically
                count = queryset.filter(status=value).count()
                amount = queryset.filter(status=value).aggregate(Sum("total"))["total__sum"] or 0
                status_distribution[value] = {
                    "label": label,
                    "count": count,
                    "total": amount,
                }

        # === Grouping by Time (Trends) ===
        if granularity == "weekly":
            date_trunc = TruncWeek("created_at")
        elif granularity == "monthly":
            date_trunc = TruncMonth("created_at")
        else:
            date_trunc = TruncDate("created_at")

        trends = (
            queryset.annotate(period=date_trunc)
            .values("period")
            .annotate(
                total_invoices=Count("id"),
                total_amount=Sum("total"),
                total_paid=Sum("amount_paid"),
                total_due=Sum("amount_due"),
                paid_count=Count("id", filter=Q(status="paid")),
                unpaid_count=Count("id", filter=~Q(status="paid")),
            )
            .order_by("period")
        )

        # === Top Customers (by total invoiced) ===
        top_customers = (
            queryset.values("contact_name", "contact_email")
            .annotate(
                total_invoiced=Sum("total"),
                invoices_count=Count("id"),
                total_paid=Sum("amount_paid"),
            )
            .order_by("-total_invoiced")[:5]
        )

        # === Response ===
        return Response({
            "summary": {
                "total_invoices": total_invoices,
                "total_amount": total_amount,
                "total_paid": total_paid,
                "total_due": total_due,
                "overdue_count": overdue_count,
                "overdue_total": overdue_total,
            },
            "paid_unpaid_overview": {
                "paid": {"count": paid_count, "total": paid_total},
                "unpaid": {"count": unpaid_count, "total": unpaid_total},
            },
            "status_distribution": status_distribution,
            "trends": list(trends),
            "top_customers": list(top_customers),
        })
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Get all items for a specific invoice"""
        invoice = self.get_object()
        items = invoice.items.all()
        serializer = InvoiceItemSerializer(items, many=True)
        return Response(serializer.data)
    






