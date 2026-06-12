from django.urls import re_path
from metrics import consumers

websocket_urlpatterns = [
    re_path(r'^ws/metrics/all/$', consumers.MetricConsumer.as_asgi()),
    re_path(r'^ws/metrics/(?P<host_id>[^/]+)/$', consumers.MetricConsumer.as_asgi()),
]
