# AI Voice Studio — Danh Mục Giới Hạn & Rủi Ro Đã Biết (Phase 3 Known Limitations)

**Giai đoạn:** Phase 3 — Production Engine Adapters  
**Trạng thái ghi nhận:** CHÍNH THỨC (BINDING)  
**Tác giả:** Principal AI/ML Infrastructure Engineer & QA Lead  

Tài liệu này ghi nhận trung thực các hạn chế kỹ thuật, đặc tính phần cứng và rủi ro còn tồn tại của hệ thống sau khi hoàn thành Phase 3, nhằm định hướng chuẩn xác cho việc lập kế hoạch các giai đoạn tiếp theo (Phase 4).

---

## 1. HIỆU NĂNG SUY LUẬN & TỐC ĐỘ THỜI GIAN THỰC (RTF)

1. **Qwen3-TTS 0.6B trên RTX 3050 KHÔNG ĐẠT tốc độ thời gian thực (RTF = 1.63 > 1.0)**:
   - Các phép đo lường thực tế trên card đồ họa NVIDIA GeForce RTX 3050 (6GB VRAM, 2048 CUDA cores) ghi nhận hệ số Real-Time Factor (RTF) của Qwen3-TTS đạt trung bình **1.63**.
   - Cụ thể: Để tổng hợp một câu tiếng Trung có độ dài âm thanh 10 giây, GPU cần khoảng 16.3 giây tính toán liên tục.
   - **Kết luận:** Đây là đặc tính kiến trúc tự hồi quy (Autoregressive Transformer) kết hợp vocoder nén âm thanh. Trên phần cứng hiện tại, Qwen3-TTS chỉ phù hợp cho tác vụ tổng hợp bất đồng bộ (Offline/Asynchronous batch synthesis), **không thể sử dụng làm hệ thống đàm thoại thời gian thực (Real-time conversational streaming)**.
2. **Cold Start Latency**:
   - VieNeu-TTS mất ~8.3 giây ở lần gọi đầu tiên để nạp các tệp mô hình ONNX FP32 vào RAM máy tính.
   - Qwen3-TTS mất ~15.6 giây ở lần gọi đầu tiên để nạp trọng số mô hình PyTorch vào VRAM của GPU.
   - Sau lần nạp đầu tiên (Warm State), độ trễ phản hồi giảm mạnh và ổn định.

---

## 2. NHÂN BẢN GIỌNG NÓI (VOICE CLONING) — ĐỘ HOÀN THIỆN & ĐÁNH GIÁ CHẤT LƯỢNG

1. **Xác nhận đường ống kỹ thuật (Technical Pipeline Verified)**:
   - Đã kiểm chứng đường ống kỹ thuật hoạt động hoàn chỉnh: Hệ thống tiếp nhận tệp WAV tham chiếu, giải mã audio, trích xuất vector đặc trưng người nói (Speaker Embedding) và đưa vào bộ giải mã ONNX để tổng hợp câu văn mới.
2. **Chưa có đánh giá định lượng độ tương đồng giọng nói (Unverified Perceptual Similarity)**:
   - **CẢNH BÁO QUAN TRỌNG:** Việc hoàn thành kiểm thử kỹ thuật không đồng nghĩa với việc độ tương đồng giọng nói giữa giọng đích và giọng mẫu đã đạt chuẩn phòng thu.
   - Chất lượng nhân bản giọng phụ thuộc nặng nề vào: chất lượng micro thu âm của tệp mẫu, độ dài mẫu (khuyến nghị 3-10 giây), mức độ ồn nền và ngữ điệu người nói.
   - Dự án chưa thực hiện đánh giá định lượng MOS (Mean Opinion Score) hoặc SECS (Speaker Embedding Cosine Similarity) có sự tham gia của con người. Hạng mục này được giữ nguyên trạng thái **UNVERIFIED PERCEPTUAL QUALITY** cho đến khi có benchmark âm học độc lập.

---

## 3. GIỚI HẠN PHẦN CỨNG & QUẢN TRỊ BỘ NHỚ VRAM

1. **Nguy cơ CUDA Out-of-Memory trên GPU 6GB VRAM**:
   - Card đồ họa RTX 3050 chỉ có 6GB VRAM vật lý. PyTorch cấp phát tĩnh ~2.06GB cho mô hình Qwen3-TTS 0.6B. Hệ điều hành Windows DWM tiêu thụ nền ~0.8 - 1.2GB. Dung lượng VRAM còn trống chỉ khoảng 2.7GB.
   - Do đó, hệ thống bắt buộc phải áp đặt quy tắc **`max_gpu_slots = 1`**.
   - Tuyệt đối không được nâng cấp mô hình lên bản Qwen3 1.5B hoặc 7B trên cấu hình máy trạm này vì chắc chắn sẽ gây lỗi tràn bộ nhớ CUDA OOM sập tiến trình.
2. **Độ dài văn bản đơn lẻ (Sentence Length Limits)**:
   - VieNeu-TTS hoạt động tối ưu nhất với các câu văn có độ dài dưới 300 ký tự. Với các văn bản quá dài, chất lượng phát âm ở cuối câu có xu hướng giảm nhẹ hoặc tăng mức chiếm dụng RAM lên trên 2.5GB.
   - Tính năng tự động phân đoạn văn bản thông minh (Text Chunking / Sentence Boundary Detection) và ghép nối âm thanh không gian (Audio Stitching) sẽ được triển khai chính thức trong Phase 4 (Long-form Synthesis).
