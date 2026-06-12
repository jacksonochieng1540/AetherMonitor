from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HostViewSet, MetricViewSet, AlertViewSet

router = DefaultRouter()
router.register(r'hosts', HostViewSet, basename='host')
router.register(r'metrics', MetricViewSet, basename='metric')
router.register(r'alerts', AlertViewSet, basename='alert')

urlpatterns = [
    path('', include(router.urls)),
]
