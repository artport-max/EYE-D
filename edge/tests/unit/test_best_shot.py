import pytest
from src.core.best_shot import BestShotSelector


def test_best_shot_updates_on_higher_score():
    """더 높은 품질 점수를 가진 프레임으로 베스트 샷 캐시가 갱신되는지 테스트."""
    selector = BestShotSelector(max_missing_frames=5, min_bbox_size=10)

    # 1. 첫 번째 프레임: track_id=1 등록 (BBox 크기: 10x10, 신뢰도: 0.8 => 점수: 80.0)
    reid_vectors_1 = [
        {'track_id': 1, 'bbox': [0, 0, 10, 10], 'confidence': 0.8, 'vector': [0.1, 0.2]}
    ]
    expired_1 = selector.update(reid_vectors_1, current_frame_idx=1)
    assert len(expired_1) == 0
    assert 1 in selector.active_tracks
    assert selector.active_tracks[1]['score'] == pytest.approx(80.0)
    assert selector.active_tracks[1]['bbox'] == [0, 0, 10, 10]

    # 2. 두 번째 프레임: 동일 track_id=1에 대해 더 나은 프레임 입력 (BBox 크기: 20x20, 신뢰도: 0.9 => 점수: 360.0)
    reid_vectors_2 = [
        {'track_id': 1, 'bbox': [0, 0, 20, 20], 'confidence': 0.9, 'vector': [0.5, 0.6]}
    ]
    expired_2 = selector.update(reid_vectors_2, current_frame_idx=2)
    assert len(expired_2) == 0
    assert selector.active_tracks[1]['score'] == pytest.approx(360.0)
    assert selector.active_tracks[1]['bbox'] == [0, 0, 20, 20]
    assert selector.active_tracks[1]['vector'] == [0.5, 0.6]

    # 3. 세 번째 프레임: 동일 track_id=1에 대해 품질이 낮은 프레임 입력 (BBox 크기: 5x5, 신뢰도: 0.5 => 점수: 12.5)
    # (하지만 min_bbox_size=10이므로 BBox가 너무 작아 무시되거나, 무시되지 않더라도 점수가 낮음)
    reid_vectors_3 = [
        {'track_id': 1, 'bbox': [0, 0, 15, 15], 'confidence': 0.4, 'vector': [0.9, 0.9]}  # 15x15 * 0.4 = 90.0
    ]
    expired_3 = selector.update(reid_vectors_3, current_frame_idx=3)
    assert len(expired_3) == 0
    # 점수는 기존 360.0이 유지되어야 하지만, 트랙 활성 유지를 위해 last_seen_frame은 3으로 갱신되어야 함
    assert selector.active_tracks[1]['score'] == pytest.approx(360.0)
    assert selector.active_tracks[1]['last_seen_frame'] == 3
    assert selector.active_tracks[1]['bbox'] == [0, 0, 20, 20]


def test_best_shot_expires_after_max_missing_frames():
    """지정한 프레임 수 동안 탐지되지 않는 트랙이 정상적으로 만료(소멸) 처리되어 반환되는지 테스트."""
    # max_missing_frames = 3으로 설정
    selector = BestShotSelector(max_missing_frames=3, min_bbox_size=10)

    # frame_idx=1: track_id=1 감지
    selector.update([
        {'track_id': 1, 'bbox': [0, 0, 20, 20], 'confidence': 0.8, 'vector': [0.1]}
    ], current_frame_idx=1)

    # frame_idx=2: track_id=1 미감지 (빈 리스트 전달)
    expired = selector.update([], current_frame_idx=2)
    assert len(expired) == 0
    assert 1 in selector.active_tracks  # 2 - 1 = 1 <= 3 이므로 유지

    # frame_idx=3: track_id=1 미감지
    expired = selector.update([], current_frame_idx=3)
    assert len(expired) == 0
    assert 1 in selector.active_tracks  # 3 - 1 = 2 <= 3 이므로 유지

    # frame_idx=4: track_id=1 미감지
    expired = selector.update([], current_frame_idx=4)
    assert len(expired) == 0
    assert 1 in selector.active_tracks  # 4 - 1 = 3 <= 3 이므로 아직 유지

    # frame_idx=5: track_id=1 미감지 -> 만료 프레임 초과 (5 - 1 = 4 > 3)
    expired = selector.update([], current_frame_idx=5)
    assert len(expired) == 1
    assert expired[0]['track_id'] == 1
    assert expired[0]['bbox'] == [0, 0, 20, 20]
    assert 1 not in selector.active_tracks  # 캐시에서 정리 완료


def test_best_shot_flushes_remaining_tracks():
    """분석 정지 시 캐시에 잔류하고 있던 트랙들이 정상적으로 강제 방출(Flush)되는지 테스트."""
    selector = BestShotSelector(max_missing_frames=10, min_bbox_size=10)

    # track_id=1, 2 등록
    selector.update([
        {'track_id': 1, 'bbox': [0, 0, 15, 15], 'confidence': 0.8, 'vector': [0.1]},
        {'track_id': 2, 'bbox': [0, 0, 20, 20], 'confidence': 0.9, 'vector': [0.2]}
    ], current_frame_idx=1)

    assert len(selector.active_tracks) == 2

    # Flush 실행
    flushed = selector.get_remaining_and_flush()
    assert len(flushed) == 2
    assert len(selector.active_tracks) == 0  # 캐시는 완전히 비워짐

    flushed_ids = {item['track_id'] for item in flushed}
    assert flushed_ids == {1, 2}


def test_min_bbox_size_filtering():
    """식별력이 떨어지는 너무 작은 크기의 바운딩 박스는 캐싱에서 배제되는지 테스트."""
    # 최소 크기 제한을 40px로 설정
    selector = BestShotSelector(max_missing_frames=5, min_bbox_size=40)

    # 1. 30x30 크기의 작은 BBox 입력 (최소 규격 미달)
    reid_vectors_small = [
        {'track_id': 1, 'bbox': [0, 0, 30, 30], 'confidence': 0.9, 'vector': [0.1]}
    ]
    selector.update(reid_vectors_small, current_frame_idx=1)
    # 캐시에 등록되지 않아야 함
    assert 1 not in selector.active_tracks

    # 2. 50x50 크기의 규격 적합 BBox 입력
    reid_vectors_large = [
        {'track_id': 1, 'bbox': [0, 0, 50, 50], 'confidence': 0.9, 'vector': [0.1]}
    ]
    selector.update(reid_vectors_large, current_frame_idx=2)
    # 정상 등록 확인
    assert 1 in selector.active_tracks
    assert selector.active_tracks[1]['bbox'] == [0, 0, 50, 50]


def test_best_shot_sends_periodic_updates():
    """설정된 프레임 주기(send_interval_frames)마다 중간 정보(is_final=False)가 송출되고 소멸 시 최종(is_final=True) 송출되는지 테스트."""
    # max_missing_frames=5, send_interval_frames=5로 설정
    selector = BestShotSelector(max_missing_frames=5, min_bbox_size=10, send_interval_frames=5)

    # 1. frame_idx=1: track_id=1 최초 감지 및 등록
    res = selector.update([
        {'track_id': 1, 'bbox': [0, 0, 20, 20], 'confidence': 0.8, 'vector': [0.1]}
    ], current_frame_idx=1)
    assert len(res) == 0
    assert selector.active_tracks[1]['last_sent_frame'] == 1

    # 2. frame_idx=2~5: 지속적으로 감지되나 아직 주기가 도래하지 않음
    for f in range(2, 6):
        res = selector.update([
            {'track_id': 1, 'bbox': [0, 0, 20, 20], 'confidence': 0.8, 'vector': [0.1]}
        ], current_frame_idx=f)
        assert len(res) == 0

    # 3. frame_idx=6: 주기 도래 (6 - 1 = 5 >= 5) -> 중간 전송 발생
    res = selector.update([
        {'track_id': 1, 'bbox': [0, 0, 20, 20], 'confidence': 0.8, 'vector': [0.1]}
    ], current_frame_idx=6)
    assert len(res) == 1
    assert res[0]['track_id'] == 1
    assert res[0]['is_final'] is False  # 중간 전송이므로 False
    assert 1 in selector.active_tracks  # 캐시에는 계속 잔존
    assert selector.active_tracks[1]['last_sent_frame'] == 6

    # 4. frame_idx=7: 더 품질이 좋은 프레임 발견 -> 점수 및 내용 업데이트
    res = selector.update([
        {'track_id': 1, 'bbox': [0, 0, 30, 30], 'confidence': 0.9, 'vector': [0.5]}
    ], current_frame_idx=7)
    assert len(res) == 0
    assert selector.active_tracks[1]['score'] == pytest.approx(810.0)

    # 5. frame_idx=11: 두 번째 주기 도래 (11 - 6 = 5 >= 5) -> 갱신된 베스트 샷으로 중간 전송 발생
    res = selector.update([
        {'track_id': 1, 'bbox': [0, 0, 30, 30], 'confidence': 0.9, 'vector': [0.5]}
    ], current_frame_idx=11)
    assert len(res) == 1
    assert res[0]['track_id'] == 1
    assert res[0]['bbox'] == [0, 0, 30, 30]
    assert res[0]['is_final'] is False
    assert selector.active_tracks[1]['last_sent_frame'] == 11

    # 6. frame_idx=12~16: 미감지 (5프레임 연속 미감지 => 아직 소멸은 안 됨)
    for f in range(12, 17):
        res = selector.update([], current_frame_idx=f)
        assert len(res) == 0

    # 7. frame_idx=17: 미감지 만료 한도 도래 (17 - 11 = 6 > max_missing_frames=5) -> 최종 소멸 전송 발생
    res = selector.update([], current_frame_idx=17)
    assert len(res) == 1
    assert res[0]['track_id'] == 1
    assert res[0]['is_final'] is True  # 최종 소멸이므로 True
    assert 1 not in selector.active_tracks  # 캐시에서 소멸 정리 완료

