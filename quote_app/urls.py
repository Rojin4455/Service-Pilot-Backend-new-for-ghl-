# user_urls.py - URL patterns for user-side functionality
from django.urls import path
from . import views
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomServiceViewSet

router = DefaultRouter()
router.register(r'custom-services', CustomServiceViewSet, basename='customservice')
urlpatterns = [

    path('', include(router.urls)),
    # ============================================================================
    # QUOTE GENERATOR FLOW
    # ============================================================================
    
    # Step 1: Get initial data (locations, services, size ranges)
    path('initial-data/', views.InitialDataView.as_view(), name='initial-data'),

    path('contacts/search/', views.ContactSearchView.as_view(), name='contact-search'),

    path('address/by-contact/<int:contact_id>/', views.AddressByContactView.as_view(), name='address-by-contact'),


    path('services/', views.ServiceAndCustomServiceListView.as_view(), name='service-list'),

    # Step 2: Create customer submission
    path('create-submission/', views.CustomerSubmissionCreateView.as_view(), name='create-submission'),
    
    # Step 3: Add services to submission
    path('<uuid:submission_id>/add-services/', views.AddServicesToSubmissionView.as_view(), name='add-services'),
    
    # Step 4: Get questions for a service
    path('services/<uuid:service_id>/questions/', views.ServiceQuestionsView.as_view(), name='service-questions'),
    
    # Step 5: Get conditional questions
    path('conditional-questions/', views.ConditionalQuestionsView.as_view(), name='conditional-questions'),
    
    # Step 6: Submit service responses
    path('<uuid:submission_id>/services/<uuid:service_id>/responses/', views.SubmitServiceResponsesView.as_view(), name='submit-responses'),
    
    # Step 7: Get submission details with quotes
    path('<uuid:id>/', views.SubmissionDetailView.as_view(), name='submission-detail'),
    
    # Step 8: Submit final quote
    path('<uuid:submission_id>/submit/', views.SubmitFinalQuoteView.as_view(), name='submit-quote'),
    
    # ============================================================================
    # UTILITY ENDPOINTS
    # ============================================================================
    
    # Check submission status
    path('<uuid:submission_id>/status/', views.SubmissionStatusView.as_view(), name='submission-status'),
    
    # Get service packages
    path('services/<uuid:service_id>/packages/', views.ServicePackagesView.as_view(), name='service-packages'),
    path('schedule/update/<uuid:submission_id>/', views.QuoteScheduleUpdateView.as_view(), name='quote-schedule-update'),

    path(
        'submissions/<uuid:submission_id>/remove-service/<uuid:service_id>/',
        views.RemoveServiceFromSubmissionView.as_view(),
        name='remove-service-from-submission'
    ),

    path("global-base-price/", views.GlobalSettingsView.as_view(), name="global-settings"),

    path("schedule-calendar-appointment/", views.ScheduleCalendarAppointmentView.as_view(), name="schedule-calendar-appointment"),
]
