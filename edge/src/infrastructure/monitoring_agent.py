import psutil
import time
import json
import logging

logger = logging.getLogger(__name__)

try:
    from jtop import jtop
    HAS_JTOP = True
except ImportError:
    HAS_JTOP = False
    logger.info("jtop not installed. GPU monitoring disabled.")


class MonitoringAgent:
    """리소스 및 장치 상태 모니터링."""

    def __init__(self):
        self.data = []
        self.jetson = None
        if HAS_JTOP:
            try:
                self.jetson = jtop()
                self.jetson.start()
            except Exception as e:
                logger.warning(f"Failed to start jtop: {e}")
                self.jetson = None

    def __del__(self):
        if self.jetson is not None:
            self.jetson.close()

    def sample(self):
        sample = {
            'timestamp': time.time(),
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
        }
        
        if self.jetson is not None and self.jetson.ok():
            try:
                sample['gpu_percent'] = self.jetson.stats.get('GPU', 0)
                sample['temperature'] = self.jetson.temperature.get('GPU', {}).get('temp', 0)
                sample['power_mw'] = self.jetson.power.get('tot', {}).get('power', 0)
            except Exception:
                pass

        self.data.append(sample)
        return sample

    def export_json(self, file_path):
        import os
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    def summary(self):
        if not self.data:
            return {'samples': []}
        avg_cpu = sum(d['cpu_percent'] for d in self.data) / len(self.data)
        avg_mem = sum(d['memory_percent'] for d in self.data) / len(self.data)
        return {
            'avg_cpu_percent': avg_cpu,
            'avg_memory_percent': avg_mem,
            'samples': self.data
        }
