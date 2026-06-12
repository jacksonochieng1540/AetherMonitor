from django.db import models
from django.utils import timezone

class Host(models.Model):
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('unknown', 'Unknown'),
    ]
    
    hostname = models.CharField(max_length=255, primary_key=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    os_info = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='unknown')
    last_seen = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.hostname

class Metric(models.Model):
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='metrics')
    timestamp = models.DateTimeField(default=timezone.now)
    cpu_percent = models.FloatField()
    memory_percent = models.FloatField()
    disk_percent = models.FloatField()
    network_in = models.FloatField(default=0.0)   # in KB/s
    network_out = models.FloatField(default=0.0)  # in KB/s
    
    # ML Outputs
    is_anomaly = models.BooleanField(default=False)
    anomaly_score = models.FloatField(default=0.0)  # Outlier score

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['host', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.host.hostname} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

class Alert(models.Model):
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='alerts')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info')
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.severity.upper()}: {self.host.hostname} - {self.message[:50]}"
