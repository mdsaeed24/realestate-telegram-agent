"""The video gate must reject what uploads fine but plays badly."""
from app.media.probe import evaluate

H264 = {"codec_type": "video", "codec_name": "h264"}
AAC = {"codec_type": "audio", "codec_name": "aac"}


def test_accepts_h264_aac_single_audio():
    assert evaluate([H264, AAC]).ok


def test_rejects_non_h264_video():
    r = evaluate([{"codec_type": "video", "codec_name": "hevc"}, AAC])
    assert not r.ok and "hevc" in r.problems[0]


def test_rejects_non_aac_audio():
    r = evaluate([H264, {"codec_type": "audio", "codec_name": "mp3"}])
    assert not r.ok and "mp3" in r.problems[0]


def test_rejects_multiple_audio_streams():
    """Two audio streams upload fine and then fail to play inline."""
    r = evaluate([H264, AAC, AAC])
    assert not r.ok
    assert any("2 audio streams" in p for p in r.problems)


def test_rejects_missing_audio():
    assert not evaluate([H264]).ok


def test_reports_every_problem_at_once():
    r = evaluate([{"codec_type": "video", "codec_name": "vp9"},
                  {"codec_type": "audio", "codec_name": "opus"},
                  {"codec_type": "audio", "codec_name": "opus"}])
    assert len(r.problems) == 3
