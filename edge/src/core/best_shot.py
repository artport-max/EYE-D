"""
best_shot.py
------------
동일인(동일 Track ID)의 궤적 내에서 품질이 가장 우수한 대표 프레임(Best-shot)을 선별하고,
추적 유실(소멸) 시점 혹은 설정된 프레임 주기마다 데이터를 전송하도록 제어하는 모듈입니다.
"""

import time
import logging

logger = logging.getLogger(__name__)


class BestShotSelector:
    """Track ID 별로 프레임 품질을 비교하여 대표 프레임을 선별하고 전송 시점을 제어하는 클래스."""

    def __init__(self, max_missing_frames: int = 30, min_bbox_size: int = 40, send_interval_frames: int = 0):
        """
        Args:
            max_missing_frames: 트랙 소멸을 감지하기 위한 최대 미출현 프레임 수 (기본: 30)
            min_bbox_size: 베스트 샷 후보가 되기 위한 최소 바운딩 박스 크기 (기본: 40px)
            send_interval_frames: 중간 전송 주기 프레임 수. 0 이하일 경우 주기적 전송은 비활성화되고 최종 소멸 시에만 송출 (기본: 0)
        """
        self.max_missing_frames = max_missing_frames
        self.min_bbox_size = min_bbox_size
        self.send_interval_frames = send_interval_frames
        
        # 활성 트랙 캐시 구조: 
        # { track_id: { 'track_id': int, 'vector': list, 'bbox': list, 'confidence': float, 'score': float, 'last_seen_frame': int, 'last_sent_frame': int, 'timestamp': float } }
        self.active_tracks = {}

    def update(self, reid_vectors: list, current_frame_idx: int) -> list:
        """매 프레임의 Re-ID 추출 결과들을 받아 베스트 샷을 캐싱하고, 주기적 전송 대상 및 소멸된 트랙들을 반환합니다.

        Args:
            reid_vectors: PipelineRunner에서 추출한 Re-ID 특징 리스트.
                예: [ { 'track_id': int, 'vector': list, 'bbox': list, 'confidence': float }, ... ]
            current_frame_idx: 현재 파이프라인의 프레임 인덱스

        Returns:
            서버/DB 전송이 확정된 프레임 특징 정보들의 리스트 (각 아이템에 is_final: bool 포함).
        """
        # 1. 현재 프레임에서 발견된 트랙 정보들로 캐시 갱신
        for item in reid_vectors:
            track_id = item.get('track_id')
            bbox = item.get('bbox', [])
            confidence = item.get('confidence', 0.0)
            vector = item.get('vector', [])

            if track_id is None or not bbox or len(bbox) < 4:
                continue

            # BBox 면적 및 해상도 분석
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            area = w * h

            # 가로/세로 중 하나라도 최소 크기 미달 시 베스트 샷 후보에서 배제
            if w < self.min_bbox_size or h < self.min_bbox_size:
                # 단, 이미 캐싱된 트랙이 존재할 경우 활성 상태 유지를 위해 프레임 인덱스만 갱신
                if track_id in self.active_tracks:
                    self.active_tracks[track_id]['last_seen_frame'] = current_frame_idx
                continue

            # 품질 점수 계산: YOLO Confidence * BBox Area
            score = float(confidence * area)

            # 캐시에 없거나, 현재 프레임의 샷이 이전보다 더 고품질일 때 업데이트
            if track_id not in self.active_tracks or score > self.active_tracks[track_id]['score']:
                # 기존에 있던 트랙의 last_sent_frame 유지
                last_sent = current_frame_idx
                if track_id in self.active_tracks:
                    last_sent = self.active_tracks[track_id]['last_sent_frame']

                self.active_tracks[track_id] = {
                    'track_id': track_id,
                    'vector': vector,
                    'bbox': bbox,
                    'confidence': confidence,
                    'score': score,
                    'last_seen_frame': current_frame_idx,
                    'last_sent_frame': last_sent,
                    'timestamp': time.time()
                }
            else:
                # 점수 갱신은 안 되었더라도 트랙 활성 상태 유지를 위해 최종 노출 프레임 인덱스만 갱신
                self.active_tracks[track_id]['last_seen_frame'] = current_frame_idx

        # 2. 주기적 전송 대상(Interval Sent) 및 소멸 트랙(Expired Tracks) 검출
        output_vectors = []
        for track_id, info in list(self.active_tracks.items()):
            # A. 소멸 조건 검증
            missing_frames = current_frame_idx - info['last_seen_frame']
            if missing_frames > self.max_missing_frames:
                logger.info(
                    f"[BestShot] Track {track_id} expired. "
                    f"Selected best-shot with score {info['score']:.1f} (missing {missing_frames} frames)."
                )
                out_info = info.copy()
                out_info['is_final'] = True
                output_vectors.append(out_info)
                del self.active_tracks[track_id]
                continue

            # B. 주기적 중간 전송 조건 검증 (활성 상태이고 주기 간격 설정이 되어 있을 때)
            if self.send_interval_frames > 0:
                elapsed_frames = current_frame_idx - info['last_sent_frame']
                if elapsed_frames >= self.send_interval_frames:
                    logger.info(
                        f"[BestShot] Track {track_id} sending periodic interval update. "
                        f"Current score: {info['score']:.1f} (elapsed {elapsed_frames} frames)."
                    )
                    out_info = info.copy()
                    out_info['is_final'] = False
                    output_vectors.append(out_info)
                    # 마지막 전송 지점 갱신
                    info['last_sent_frame'] = current_frame_idx

        return output_vectors

    def get_remaining_and_flush(self) -> list:
        """분석 종료 시 캐시에 남아 있는 모든 트랙 정보를 내보내고 캐시를 비웁니다."""
        remaining = []
        for track_id, info in list(self.active_tracks.items()):
            logger.info(
                f"[BestShot] Flushing remaining track {track_id} on pipeline stop. "
                f"Score: {info['score']:.1f}"
            )
            out_info = info.copy()
            out_info['is_final'] = True
            remaining.append(out_info)
            del self.active_tracks[track_id]
        return remaining
