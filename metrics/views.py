from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from .models import Host, Metric, Alert
from .serializers import HostSerializer, MetricSerializer, AlertSerializer
from .tasks import process_incoming_metric

class HostViewSet(viewsets.ModelViewSet):
    queryset = Host.objects.all()
    serializer_class = HostSerializer

class MetricViewSet(viewsets.ViewSet):
    def create(self, request):
        hostname = request.data.get('hostname')
        if not hostname:
            return Response({"error": "hostname is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        ip_address = request.data.get('ip_address', request.META.get('REMOTE_ADDR'))
        os_info = request.data.get('os_info', 'Linux')
        
        # Get or create/update host details
        host, _ = Host.objects.update_or_create(
            hostname=hostname,
            defaults={
                'ip_address': ip_address,
                'os_info': os_info,
                'status': 'online',
                'last_seen': timezone.now()
            }
        )
        
        serializer = MetricSerializer(data=request.data)
        if serializer.is_valid():
            metric = serializer.save(host=host)
            # Trigger Celery task asynchronously for ML checking and UI broadcast
            process_incoming_metric.delay(metric.id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='history/(?P<hostname>[^/]+)')
    def history(self, request, hostname=None):
        metrics = Metric.objects.filter(host__hostname=hostname).order_by('-timestamp')[:50]
        # Return in oldest-first order for graphing
        serializer = MetricSerializer(reversed(list(metrics)), many=True)
        return Response(serializer.data)

class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all().order_by('-timestamp')
    serializer_class = AlertSerializer
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.resolved = True
        alert.resolved_at = timezone.now()
        alert.save()
        return Response({'status': 'alert marked as resolved'}, status=status.HTTP_200_OK)
