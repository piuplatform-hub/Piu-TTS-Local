# AI VOICE STUDIO — BÁO CÁO KHẢ THI TỔNG THỂ ENGINE THỰC TẾ (PHASE 1B FEASIBILITY REPORT)

**Tác giả:** Lead AI/ML Infrastructure Engineer  
**Ngày thực hiện:** 2026-10-08  
**Trạng thái phê duyệt:** Đã hoàn tất thực nghiệm kiểm chứng phần cứng  
**Mục tiêu:** Xác nhận tính khả thi kỹ thuật của VieNeu-TTS và Qwen3-TTS trên môi trường Windows 11 / RTX 3050 6GB / RAM 16GB  

---

## 1. KẾT LUẬN VÀ PHÁN QUYẾT TỪNG ENGINE (FEASIBILITY VERDICTS)

### 1.1. Engine A: VieNeu-TTS v3 Turbo
- **Phán quyết:** **`PASS`**
- **Căn cứ kỹ thuật:**
  - Hoạt động ổn định trên CPU qua ONNX Runtime chuẩn `FP32`, hoàn toàn không cần PyTorch.
  - Tốc độ vượt trội: RTF đạt `0.55 - 0.75` (nhanh hơn thời gian thực 1.3x - 1.8x).
  - Tần số lấy mẫu đạt chuẩn `48,000 Hz` (chất lượng cao nhất hiện nay).
  - Đỉnh RAM chỉ `2,440 MB`, không xuất hiện rò rỉ bộ nhớ qua 5 vòng chạy lặp lại liên tiếp.
  - Đường ống kỹ thuật nhân bản giọng nói Zero-shot hoạt động tốt trên audio tham chiếu chuẩn.
  - **Khuyến nghị:** Đủ điều kiện 100% để xây dựng Adapter sản xuất chính thức cho Tiếng Việt trong Phase 3.

### 1.2. Engine B: Qwen3-TTS-12Hz-0.6B-CustomVoice
- **Phán quyết:** **`PASS`**
- **Căn cứ kỹ thuật:**
  - Chạy mượt mà trên GPU NVIDIA GeForce RTX 3050 (6GB VRAM) ở định dạng `torch.bfloat16`.
  - Đỉnh VRAM tối đa chỉ đạt **`2,772 MB`** (< 2.8 GB, chỉ chiếm ~45% VRAM của card 6GB), loại bỏ hoàn toàn nguy cơ tràn bộ nhớ (Out-Of-Memory).
  - 9 giọng đọc nung sẵn tiếng Trung (`Vivian`, `Uncle_Fu`, `Serena`,...) hoạt động chính xác, âm thanh tự nhiên, tần số `24,000 Hz`.
  - Tự động khôi phục sau ngoại lệ tham số tức thì trong `4.4s`, giải phóng VRAM sạch sẽ sau khi tắt tiến trình.
  - Tốc độ sinh RTF `~2.0` đáp ứng hoàn hảo yêu cầu của hàng đợi tác vụ nền (Background Queue).
  - **Khuyến nghị:** Đủ điều kiện 100% để xây dựng Adapter sản xuất chính thức cho Tiếng Trung trong Phase 3.

---

## 2. MA TRẬN KHẢ THI KỸ THUẬT (ENGINE FEASIBILITY MATRIX)

| Tiêu chí thẩm định | VieNeu-TTS (Tiếng Việt) | Qwen3-TTS 0.6B (Tiếng Trung) |
|:---|:---:|:---:|
| **Khả năng cài đặt Windows** | ✅ PASSED (pip độc lập) | ✅ PASSED (pip + PyTorch cu124) |
| **Bản quyền thương mại** | ✅ Apache-2.0 | ✅ Apache-2.0 |
| **An toàn phần cứng (RAM/VRAM)** | ✅ PASSED (RAM 2.4GB, 0MB VRAM) | ✅ PASSED (VRAM đỉnh 2.77GB / 6GB) |
| **Tính toàn vẹn âm thanh** | ✅ PASSED (48kHz, không clipping) | ✅ PASSED (24kHz, không clipping) |
| **Tự khôi phục sau sự cố** | ✅ PASSED | ✅ PASSED |
| **Độ ổn định không rò rỉ** | ✅ PASSED | ✅ PASSED |
| **Phán quyết cuối cùng** | **PASS** | **PASS** |

---

## 3. SỔ ĐĂNG KÝ NỢ KỸ THUẬT VÀ LƯU Ý GIAI ĐOẠN TIẾP THEO (TECHNICAL DEBT REGISTER)

1. **TD-001 — Chuẩn hóa Tần số Lấy Mẫu (Sample Rate Normalization):**
   - VieNeu xuất audio `48,000 Hz`, trong khi Qwen3 xuất audio `24,000 Hz`.
   - *Kế hoạch giải quyết:* Tại Phase 3 (Adapter Implementation), bổ sung bước chuẩn hóa tự động qua `soxr` trong Artifact Service để đưa toàn bộ file xuất bản về tần số đồng nhất (hoặc lưu trữ nguyên bản kèm metadata chính xác).
2. **TD-002 — Nhân bản Giọng Đọc Riêng của Cá Nhân (Personal Voice Cloning):**
   - Đường ống kỹ thuật đã được kiểm chứng bằng audio mẫu của repo (`example.wav`).
   - Việc nhân bản giọng đọc cụ thể của người dùng cuối sẽ ở trạng thái **PENDING** cho tới khi người dùng tải lên file mẫu giọng của mình trong giao diện người dùng.
3. **TD-003 — Hàng đợi Bền vững & Worker Lease Daemon (Phase 2):**
   - Cả hai mô hình đều hoạt động tốt trong Worker độc lập. Cần triển khai hàng đợi bền vững SQLite (Phase 2) trước khi nạp hai engine này vào quy trình sản xuất nhằm xử lý việc ngắt điện hoặc sập server đột ngột.

---

## 4. CHIẾN LƯỢC TÍCH HỢP ĐỀ XUẤT (NEXT STEPS PROPOSAL)

Vì cả hai engine đều đạt trạng thái **PASS**, kiến trúc phân tách mà dự án đã định hình trong Phase 0 là hoàn toàn chính xác:
1. **Bước 1 (Phase 2):** Xây dựng hàng đợi bền vững Durable SQLite Lease Queue và Worker Lease Daemon để bảo đảm an toàn tác vụ khi chạy engine thật.
2. **Bước 2 (Phase 3):** Xây dựng `engines/vieneu-tts` adapter (CPU ONNX) và `engines/qwen3-tts` adapter (GPU bfloat16) dựa trên Engine SDK v1 đã hoàn thiện ở Phase 1.
3. **Bước 3:** Tích hợp giao diện chọn giọng và nạp preset trực quan trên Web UI.
