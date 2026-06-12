import logging
import pandas as pd
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Host, Metric, Alert
from ml_engine.detector import AnomalyDetector

logger = logging.getLogger(__name__)

def broadcast_to_websockets(metric, alert=None):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    # Prepare data payload
    metric_data = {
        'id': metric.id,
        'hostname': metric.host.hostname,
        'timestamp': metric.timestamp.isoformat(),
        'cpu_percent': metric.cpu_percent,
        'memory_percent': metric.memory_percent,
        'disk_percent': metric.disk_percent,
        'network_in': metric.network_in,
        'network_out': metric.network_out,
        'is_anomaly': metric.is_anomaly,
        'anomaly_score': metric.anomaly_score,
        'host_status': metric.host.status,
    }

    # Broadcast to global channels group
    async_to_sync(channel_layer.group_send)(
        "metrics_all",
        {
            "type": "metric_update",
            "data": metric_data
        }
    )

    # Broadcast to host-specific channels group
    async_to_sync(channel_layer.group_send)(
        f"metrics_host_{metric.host.hostname}",
        {
            "type": "metric_update",
            "data": metric_data
        }
    )

    if alert:
        alert_data = {
            'id': alert.id,
            'hostname': alert.host.hostname,
            'severity': alert.severity,
            'message': alert.message,
            'timestamp': alert.timestamp.isoformat(),
            'resolved': alert.resolved
        }
        # Broadcast alert to global group
        async_to_sync(channel_layer.group_send)(
            "metrics_all",
            {
                "type": "alert_update",
                "data": alert_data
            }
        )
        async_to_sync(channel_layer.group_send)(
            f"metrics_host_{alert.host.hostname}",
            {
                "type": "alert_update",
                "data": alert_data
            }
        )

@shared_task
def process_incoming_metric(metric_id):
    try:
        metric = Metric.objects.get(id=metric_id)
    except Metric.DoesNotExist:
        logger.error(f"Metric with id {metric_id} not found.")
        return

    host = metric.host

    # Run ML Anomaly Detection
    detector = AnomalyDetector(host.hostname)
    is_anomaly, score = detector.predict(metric)

    # Update metric
    metric.is_anomaly = is_anomaly
    metric.anomaly_score = score
    metric.save()

    # Determine Host Status
    new_status = 'online'
    alert = None

    if is_anomaly:
        # Determine Severity based on threshold parameters or score
        severity = 'warning'
        if metric.cpu_percent > 95.0 or metric.memory_percent > 95.0:
            severity = 'critical'
            new_status = 'critical'
        else:
            new_status = 'warning'

        # Check for alert spam control: don't create similar alert if one was created in the last 1 minute
        one_minute_ago = timezone.now() - timezone.timedelta(minutes=1)
        recent_alert_exists = Alert.objects.filter(
            host=host,
            severity=severity,
            resolved=False,
            timestamp__gte=one_minute_ago
        ).exists()

        if not recent_alert_exists:
            message = (f"Anomaly detected! Score: {score:.4f}. "
                       f"CPU: {metric.cpu_percent}%, RAM: {metric.memory_percent}%, "
                       f"Net In: {metric.network_in:.1f}KB/s, Net Out: {metric.network_out:.1f}KB/s.")
            
            alert = Alert.objects.create(
                host=host,
                severity=severity,
                message=message
            )
            # Log simulated alert output (Slack, Email, Webhook would connect here)
            logger.warning(f"[ALERT TRIGGERED] Host {host.hostname} - {severity.upper()}: {message}")

    # Save host state changes
    host.status = new_status
    host.last_seen = timezone.now()
    host.save()

    # Send to WebSockets
    broadcast_to_websockets(metric, alert)

@shared_task
def retrain_anomaly_models():
    logger.info("Starting periodic retraining of anomaly detection models.")
    hosts = Host.objects.all()
    
    for host in hosts:
        # Get historical metrics (last 500 samples)
        history = Metric.objects.filter(host=host).order_by('-timestamp')[:500]
        if len(history) < 15:
            logger.info(f"Skipping host {host.hostname}: only {len(history)} metrics points available. (min 15 required)")
            continue
        
        # Prepare Pandas DataFrame
        data = [{
            'cpu_percent': m.cpu_percent,
            'memory_percent': m.memory_percent,
            'disk_percent': m.disk_percent,
            'network_in': m.network_in,
            'network_out': m.network_out
        } for m in reversed(list(history))]
        
        df = pd.DataFrame(data)
        
        detector = AnomalyDetector(host.hostname)
        success = detector.train(df)
        if success:
            logger.info(f"Successfully retrained anomaly model for host {host.hostname} with {len(df)} points.")
        else:
            logger.error(f"Failed to train model for host {host.hostname}.")
