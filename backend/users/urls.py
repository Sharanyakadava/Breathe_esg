from django.urls import path
from .views import LoginView, MeView
from .views import LoginView, MeView, RegisterView
urlpatterns = [
    path('login/', LoginView.as_view()),
    path('register/', RegisterView.as_view()),
    path('me/', MeView.as_view()),
]