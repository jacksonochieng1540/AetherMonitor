import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from django.conf import settings

MODELS_DIR = os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models')
os.makedirs(MODELS_DIR, exist_ok=True)

class AnomalyDetector:
    def __init__(self, host_id):
        self.host_id = host_id
        self.model_path = os.path.join(MODELS_DIR, f"{host_id}_isolation_forest.joblib")
        self.model = self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                return joblib.load(self.model_path)
            except Exception:
                pass
        return None

    def _save_model(self):
        if self.model:
            joblib.dump(self.model, self.model_path)

    def train(self, df_metrics):
        """
        Train the isolation forest model with historical metrics.
        df_metrics is expected to be a pandas DataFrame with columns:
        ['cpu_percent', 'memory_percent', 'disk_percent', 'network_in', 'network_out']
        """
        if len(df_metrics) < 15:
            return False

        X = df_metrics[['cpu_percent', 'memory_percent', 'disk_percent', 'network_in', 'network_out']].values
        
        
        clf = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
        clf.fit(X)
        
        self.model = clf
        self._save_model()
        return True

    def predict(self, metric):
        """
        Predict if a single metric data point is anomalous.
        Returns: (is_anomaly: bool, anomaly_score: float)
        """
    
        features = np.array([[
            metric.cpu_percent,
            metric.memory_percent,
            metric.disk_percent,
            metric.network_in,
            metric.network_out
        ]])


        if metric.cpu_percent > 95.0 or metric.memory_percent > 95.0:
            return True, -1.0  

        if self.model is None:
            is_anomaly = metric.cpu_percent > 90.0 or metric.memory_percent > 90.0 or metric.disk_percent > 90.0
            score = -0.5 if is_anomaly else 0.5
            return is_anomaly, score

        try:
            score = float(self.model.decision_function(features)[0])
            prediction = self.model.predict(features)[0]
            is_anomaly = (prediction == -1)
            
            if metric.cpu_percent > 90.0 or metric.memory_percent > 90.0:
                is_anomaly = True
                score = min(score, -0.1)

            return is_anomaly, score
        except Exception:
            is_anomaly = metric.cpu_percent > 90.0 or metric.memory_percent > 90.0
            return is_anomaly, -0.5 if is_anomaly else 0.5
