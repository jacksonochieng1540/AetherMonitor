from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
import pandas as pd
import numpy as np

from metrics.models import Host, Metric, Alert
from ml_engine.detector import AnomalyDetector

# Mock Celery delay to run synchronously in tests or avoid execution
class MockTaskDelay:
    def __init__(self, *args, **kwargs):
        pass
    def delay(self, *args, **kwargs):
        return None

class MetricsModelTests(TestCase):
    def setUp(self):
        self.host = Host.objects.create(
            hostname="test-host-01",
            ip_address="192.168.1.10",
            os_info="Ubuntu 22.04",
            status="online"
        )

    def test_host_creation(self):
        self.assertEqual(self.host.hostname, "test-host-01")
        self.assertEqual(self.host.status, "online")
        self.assertEqual(str(self.host), "test-host-01")

    def test_metric_creation(self):
        metric = Metric.objects.create(
            host=self.host,
            cpu_percent=45.2,
            memory_percent=60.0,
            disk_percent=30.0,
            network_in=150.0,
            network_out=75.0,
            is_anomaly=False,
            anomaly_score=0.25
        )
        self.assertEqual(metric.host, self.host)
        self.assertFalse(metric.is_anomaly)
        self.assertIn("test-host-01", str(metric))

    def test_alert_creation(self):
        alert = Alert.objects.create(
            host=self.host,
            severity="warning",
            message="CPU spike detected"
        )
        self.assertEqual(alert.severity, "warning")
        self.assertFalse(alert.resolved)


class AnomalyDetectorTests(TestCase):
    def setUp(self):
        self.host_id = "test-ml-host"
        self.detector = AnomalyDetector(self.host_id)

    def test_rule_based_fallback_extreme_values(self):
        # Even without model training, extreme values > 95% should be flagged as anomalous
        metric = Metric(
            cpu_percent=98.0,
            memory_percent=50.0,
            disk_percent=20.0,
            network_in=10.0,
            network_out=10.0
        )
        is_anomaly, score = self.detector.predict(metric)
        self.assertTrue(is_anomaly)
        self.assertEqual(score, -1.0)

    def test_rule_based_fallback_normal_values(self):
        metric = Metric(
            cpu_percent=15.0,
            memory_percent=30.0,
            disk_percent=20.0,
            network_in=10.0,
            network_out=10.0
        )
        is_anomaly, score = self.detector.predict(metric)
        self.assertFalse(is_anomaly)
        self.assertGreater(score, 0)

    def test_insufficient_data_training_rejection(self):
        # IsolationForest needs at least 15 points
        df = pd.DataFrame({
            'cpu_percent': [10.0]*10,
            'memory_percent': [20.0]*10,
            'disk_percent': [30.0]*10,
            'network_in': [5.0]*10,
            'network_out': [5.0]*10
        })
        success = self.detector.train(df)
        self.assertFalse(success)


class MetricsAPITests(APITestCase):
    def setUp(self):
        self.host = Host.objects.create(
            hostname="agent-node-01",
            ip_address="10.0.0.5",
            os_info="Linux 6.2",
            status="online"
        )
        # Patch the Celery task delay method
        from metrics.views import process_incoming_metric
        self.original_delay = process_incoming_metric.delay
        process_incoming_metric.delay = lambda *args, **kwargs: None

    def tearDown(self):
        from metrics.views import process_incoming_metric
        process_incoming_metric.delay = self.original_delay

    def test_get_hosts_list(self):
        url = reverse('host-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['hostname'], "agent-node-01")

    def test_post_metric_creates_and_registers_host(self):
        url = reverse('metric-list')
        payload = {
            "hostname": "new-agent-node",
            "ip_address": "10.0.0.9",
            "os_info": "Linux Debian",
            "cpu_percent": 35.5,
            "memory_percent": 45.0,
            "disk_percent": 12.4,
            "network_in": 120.5,
            "network_out": 45.0
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Host.objects.filter(hostname="new-agent-node").exists())
        self.assertEqual(Metric.objects.filter(host__hostname="new-agent-node").count(), 1)

    def test_get_metric_history(self):
        # Create some historical metrics
        for i in range(5):
            Metric.objects.create(
                host=self.host,
                cpu_percent=10.0 + i,
                memory_percent=40.0,
                disk_percent=20.0,
                timestamp=timezone.now() - timezone.timedelta(seconds=i*10)
            )

        # GET history of agent-node-01
        url = reverse('metric-history', kwargs={'hostname': 'agent-node-01'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)
        # The history API returns oldest first (14.0 is oldest, 10.0 is newest)
        self.assertGreater(response.data[0]['cpu_percent'], response.data[4]['cpu_percent'])

    def test_resolve_alert(self):
        alert = Alert.objects.create(
            host=self.host,
            severity="critical",
            message="Host memory failure warning"
        )
        url = reverse('alert-resolve', kwargs={'pk': alert.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify db updated
        alert.refresh_from_db()
        self.assertTrue(alert.resolved)
        self.assertIsNotNone(alert.resolved_at)
