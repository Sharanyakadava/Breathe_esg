from django.urls import path
from .views import IngestView

urlpatterns = [
    path('upload/', IngestView.as_view(), name='ingest-upload'),
]
