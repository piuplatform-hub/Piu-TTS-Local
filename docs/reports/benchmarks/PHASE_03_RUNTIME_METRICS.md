# AI Voice Studio — Báo Cáo Đo Đạc Hiệu Năng Thực Tế (Runtime Metrics & Hardware Telemetry)
**Giai đoạn:** Phase 3 — Neural Speech Inference  
**Ngày đo:** 08/10/2026  
**Môi trường phần cứng kiểm thử:**
- **Hệ điều hành:** Windows 11 Pro 64-bit
- **CPU:** Intel Core i5-12400F (6 nhân hiệu năng cao, 12 luồng, xung nhịp cơ bản 2.5GHz, Turbo 4.4GHz)
- **GPU:** NVIDIA GeForce RTX 3050, 6GB GDDR6 VRAM (Driver 572.70, CUDA 12.4)
- **RAM:** 16GB DDR4 3200MHz

---

## 1. Engine A: VieNeu-TTS v3 Turbo (ONNX Runtime FP32 CPU)
Mô hình xử lý trực tiếp trên CPU thông qua ONNX Runtime 1.30.0, xuất âm thanh 48.000 Hz WAV PCM 16-bit mono.

### Thời gian khởi tạo tiến trình (Process Spawning):
- **Thời gian khởi động worker:** `0.32s` (Cơ chế subprocess với ephemeral loopback HTTP server).
- **Trạng thái ban đầu (Cold State):** Worker nạp server trong 0.32s, mô hình ONNX trì hoãn nạp cho đến yêu cầu đầu tiên (Lazy Loading) nhằm tiết kiệm tài nguyên khi nhàn rỗi.

### Bảng kết quả đo đạc:

| Lần chạy | Loại văn bản | Độ dài (ký tự) | Thời lượng âm thanh (giây) | Thời gian suy luận (Wall Time) | Real-Time Factor (RTF) | Đỉnh RAM Worker (RSS) | VRAM GPU | Đánh giá tốc độ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Run 1 (Cold)** | Ngắn (Chào hỏi) | 33 | 1.76s | 8.33s | **4.73** | 1,184 MB | 0 MB | Chậm (do nạp ONNX weights lần đầu) |
| **Run 2 (Warm)** | Trung bình (Studio) | 144 | 6.80s | 4.51s | **0.66** | 1,541 MB | 0 MB | **Nhanh hơn thời gian thực (Faster-than-real-time)** |
| **Run 3 (Warm)** | Dài (Bản tin thời tiết) | 244 | 12.32s | 8.08s | **0.66** | 2,433 MB | 0 MB | **Nhanh hơn thời gian thực (Faster-than-real-time)** |

### Phân tích kỹ thuật:
1. **Đặc tính thời gian thực:** Sau khi hoàn thành Cold Start, VieNeu-TTS trên CPU Intel Core i5-12400F đạt hệ số RTF ổn định ấn tượng **0.66**. Điều này có nghĩa để sinh ra 1 giây âm thanh tiếng Việt 48kHz chất lượng phòng thu, hệ thống chỉ mất **0.66 giây tính toán CPU**.
2. **Bộ nhớ RAM:** Mức chiếm dụng bộ nhớ tăng từ 1.18GB lên 2.43GB đối với các câu đọc văn bản dài, hoàn toàn nằm trong biên an toàn cho phép của hệ thống máy trạm 16GB RAM.

---

## 2. Engine B: Qwen3-TTS 0.6B CustomVoice (PyTorch CUDA bfloat16)
Mô hình ngôn ngữ tự hồi quy (Autoregressive Transformer) kết hợp CosyVoice vocoder, thực thi trên NVIDIA GeForce RTX 3050 (6GB VRAM) ở định dạng dấu phẩy động `bfloat16`, xuất âm thanh 24.000 Hz WAV.

### Thời gian khởi tạo tiến trình:
- **Thời gian khởi động worker:** `1.44s`
- **Tải trọng số GPU:** Trì hoãn cho tới khi nhận job đầu tiên.

### Bảng kết quả đo đạc:

| Lần chạy | Loại văn bản | Độ dài (ký tự) | Thời lượng âm thanh (giây) | Thời gian suy luận (Wall Time) | Real-Time Factor (RTF) | PyTorch Allocated VRAM | Đỉnh RAM Host (RSS) | Đánh giá tốc độ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Run 1 (Cold)** | Ngắn (Test) | 10 | 2.80s | 15.57s | **5.56** | 2,065 MB (~2.06 GB) | 1,836 MB | Chậm (tải trọng số vào VRAM) |
| **Run 2 (Warm)** | Trung bình (Giới thiệu) | 36 | 5.92s | 9.65s | **1.63** | 2,065 MB (~2.06 GB) | 1,841 MB | **Chậm hơn thời gian thực (~1.6x)** |
| **Run 3 (Warm)** | Dài (Bình luận AI) | 62 | 16.72s | 27.19s | **1.63** | 2,065 MB (~2.06 GB) | 1,848 MB | **Chậm hơn thời gian thực (~1.6x)** |

### Phân tích kỹ thuật & Lưu ý Rủi ro:
1. **RTF > 1.0 (Slower-than-real-time):** Với mô hình transformer 0.6 tỷ tham số trên card đồ họa phổ thông RTX 3050 (2048 CUDA cores), hệ số RTF đo được là **1.63**. Để sinh ra 10 giây âm thanh tiếng Trung, GPU cần tính toán khoảng 16.3 giây. **Đây là hạn chế phần cứng khách quan và không thể coi là suy luận thời gian thực**.
2. **Độ an toàn VRAM & Ngăn ngừa OOM:**
   - Mức chiếm dụng bộ nhớ VRAM phân bổ tĩnh của PyTorch duy trì chính xác ở mức **2,065 MB** trên tổng số 6,144 MB VRAM có sẵn (~33.6% VRAM card).
   - Qua các lần chạy lặp lại, VRAM không bị rò rỉ (không tăng lên).
   - Tuy nhiên, vì VRAM tổng của RTX 3050 chỉ có 6GB và Windows DWM/Desktop ngốn khoảng 0.8 - 1.2GB VRAM nền, việc áp đặt **`max_gpu_slots = 1`** là bắt buộc để ngăn chặn hoàn toàn nguy cơ CUDA Out-of-Memory khi nhiều tác vụ đồng thời gửi đến.

---

## 3. Khả năng Chạy Đồng thời (Concurrent CPU + GPU Inference)
Khi cho chạy đồng thời 1 tác vụ VieNeu-TTS (CPU) và 1 tác vụ Qwen3-TTS (GPU):
- Cả hai tác vụ hoàn thành song song mà không xảy ra hiện tượng khóa tài nguyên (resource deadlocks).
- CPU Intel i5-12400F xử lý tác vụ ONNX song song với luồng CUDA stream của card đồ họa mà không làm tụt xung đột ngột.
- Tổng mức RAM máy chủ khi cả hai mô hình cùng hoạt động đạt đỉnh **~4.3 GB**, đảm bảo an toàn tuyệt đối cho hệ thống 16GB RAM.
