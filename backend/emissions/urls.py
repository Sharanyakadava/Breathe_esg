from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmissionRecordViewSet, IngestionBatchViewSet, FacilityViewSet

router = DefaultRouter()
router.register('records', EmissionRecordViewSet, basename='record')
router.register('batches', IngestionBatchViewSet, basename='batch')
router.register('facilities', FacilityViewSet, basename='facility')

urlpatterns = [path('', include(router.urls))]
