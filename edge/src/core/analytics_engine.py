import logging
import time

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    """Calculates Entrance/Exit, Dwell time, and cross-camera matching."""
    
    def __init__(self, db_client=None, collection_name='reid_collection'):
        self.db_client = db_client
        self.collection_name = collection_name
        self.track_history = {} # track_id -> {'first_seen': timestamp, 'last_seen': timestamp, 'camera': cam_id}
        self.entrance_count = 0
        self.exit_count = 0
        
        # Define a virtual line for counting (y-coordinate)
        self.counting_line_y = 500

    def update_tracks(self, tracks, camera_id="cam_0"):
        current_time = time.time()
        for track in tracks:
            track_id = track['track_id']
            global_id = f"{camera_id}_{track_id}"
            x1, y1, x2, y2 = track['bbox']
            cy = (y1 + y2) / 2
            
            if global_id not in self.track_history:
                self.track_history[global_id] = {
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'camera': camera_id,
                    'last_cy': cy
                }
            else:
                prev_cy = self.track_history[global_id]['last_cy']
                self.track_history[global_id]['last_seen'] = current_time
                self.track_history[global_id]['last_cy'] = cy
                
                # Check line crossing
                if prev_cy < self.counting_line_y and cy >= self.counting_line_y:
                    self.entrance_count += 1
                    logger.info(f"Entrance detected: {global_id}")
                elif prev_cy >= self.counting_line_y and cy < self.counting_line_y:
                    self.exit_count += 1
                    logger.info(f"Exit detected: {global_id}")

    def get_dwell_times(self):
        dwell_times = {}
        for global_id, data in self.track_history.items():
            dwell_times[global_id] = data['last_seen'] - data['first_seen']
        return dwell_times

    def cross_camera_match(self, query_vector, threshold=0.8):
        """Finds same person across cameras using Vector DB."""
        if not self.db_client:
            return None
        
        try:
            results = self.db_client.validate_search(self.collection_name, query_vector, top_k=3)
            valid_hits = [hit for hit in results['hits'] if hit['score'] is not None and hit['score'] > threshold]
            return valid_hits
        except Exception as e:
            logger.warning(f"Cross-camera match failed: {e}")
            return None

    def get_statistics(self):
        return {
            'entrance_count': self.entrance_count,
            'exit_count': self.exit_count,
            'total_tracked': len(self.track_history)
        }
