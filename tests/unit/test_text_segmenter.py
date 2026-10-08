"""
Unit Tests for Intelligent Text Segmenter
Tests linguistic boundary preservation for Vietnamese and Mandarin.
"""

from apps.server.src.services.text_segmenter import TextSegmenter


def test_segmenter_vietnamese_sentence_boundaries():
    text = (
        "Chào mừng bạn đến với AI Voice Studio. "
        "Hôm nay tại TP.HCM thời tiết rất trong xanh và nắng ấm. "
        "Nhiệt độ đo được là 30.5 độ C! "
        "Bạn đã sẵn sàng sáng tạo nội dung chưa? "
        "Hãy bắt đầu ngay hôm nay nhé..."
    )
    segments = TextSegmenter.segment_vietnamese(text, max_chars=120)
    assert len(segments) >= 3
    # Check that TP.HCM was not incorrectly split
    assert any("TP.HCM" in s for s in segments)
    # Check that 30.5 was not split
    assert any("30.5 độ C" in s for s in segments)


def test_segmenter_vietnamese_multi_paragraph():
    text = (
        "Đoạn văn thứ nhất nói về công nghệ tổng hợp tiếng nói cục bộ.\n\n"
        "Đoạn văn thứ hai tập trung vào việc quản trị tài nguyên GPU và CPU an toàn.\n\n"
        "Đoạn văn cuối cùng kết luận toàn bộ quy trình sản xuất âm thanh chất lượng cao."
    )
    segments = TextSegmenter.segment_vietnamese(text, max_chars=200)
    assert len(segments) == 3
    assert "Đoạn văn thứ nhất" in segments[0]
    assert "Đoạn văn thứ hai" in segments[1]
    assert "Đoạn văn cuối cùng" in segments[2]


def test_segmenter_mandarin_sentence_boundaries():
    text = (
        "你好，欢迎使用 AI Voice Studio 本地语音合成系统！"
        "当前系统支持高保真中文语音生成。"
        "你今天感觉如何？"
        "让我们一起开始创作吧。"
    )
    segments = TextSegmenter.segment_mandarin(text, max_chars=60)
    assert len(segments) >= 3
    for s in segments:
        assert len(s) <= 60
