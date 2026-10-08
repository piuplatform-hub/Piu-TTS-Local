# AI VOICE STUDIO — BÁO CÁO KHẢ THI TỔNG THỂ ENGINE THỰC TẾ (PHASE 1B FEASIBILITY REPORT)

**Tác giả:** Lead AI/ML Infrastructure Engineer  
**Ngày thực hiện:** 2026-10-08  
**Trạng thái phê duyệt:** Đã hoàn tất thực nghiệm kiểm chứng phần cứng  
**Mục tiêu:** Xác nhận tính khả thi kỹ thuật của VieNeu-TTS và Qwen3-TTS trên môi trường Windows 11 / RTX 3050 6GB / RAM 16GB  

---

## 1. KẾT LUẬN VÀ PHÁN QUYẾT TỪNG ENGINE (FEASIBILITY VERDICTS)

### 1.1. Engine A: VieNeu-TTS v3 Turbo
- **Phán quyết:** **`PASS (CÓ ĐIỀU KIỆN)`**
- **Căn cứ kỹ thuật:**
  - Hoạt động ổn định trên CPU qua ONNX Runtime chuẩn `FP32`, hoàn toàn không cần PyTorch.
  - Tốc độ vượt trội: RTF đạt `0.55 - 0.75` (nhanh hơn thời gian thực 1.3x - 1.8x).
  - Tần số lấy mẫu đạt chuẩn `48,000 Hz` (chất lượng cao nhất hiện nay).
  - Đỉnh RAM `2,440 MB`. 5 vòng chạy ngắn hạn liên tiếp ổn định, nhưng **chưa chứng minh sự vắng mặt của rò rỉ bộ nhớ dài hạn**.
  - Pipeline kỹ thuật nhân bản giọng tiếp nhận reference audio thành công; tuy nhiên **chất lượng âm học và độ tương đồng người nói (speaker similarity) với giọng cá nhân thực tế là UNVERIFIED / PENDING**.
  - Toàn bộ code và model weights tuân thủ giấy phép Apache-2.0.
  - **Khuyến nghị:** Đủ điều kiện để xây dựng Adapter sản xuất cho Tiếng Việt trong Phase 3, kèm điều kiện giám sát bộ nhớ dài hạn.

### 1.2. Engine B: Qwen3-TTS-12Hz-0.6B-CustomVoice
- **Phán quyết:** **`PASS WITH LIMITATIONS (ĐẠT VỚI HẠN CHẾ QUẢN LÝ TÀI NGUYÊN)`**
- **Căn cứ kỹ thuật:**
  - Chạy trên GPU NVIDIA GeForce RTX 3050 (6GB VRAM) ở định dạng `torch.bfloat16`.
  - PyTorch allocated peak đạt **`2,772 MB`** (reserved cache `3,120 MB`), nhưng **tổng lượng board VRAM thực tế bị chiếm dụng là `~4,680 - 5,250 MB`** trên tổng số 6,144 MB.
  - **Nguy cơ CUDA OOM CHƯA bị triệt tiêu:** Biên an toàn VRAM còn lại thực tế < 1 GB. Cần kiểm soát chặt chẽ độ dài text và nghiêm cấm chạy đồng thời tác vụ GPU khác.
  - 9 giọng đọc nung sẵn tiếng Trung (`Vivian`, `Uncle_Fu`, `Serena`,...) hoạt động chính xác, âm thanh tự nhiên, tần số `24,000 Hz`.
  - Tự động khôi phục sau ngoại lệ tham số tức thì trong `4.4s`, giải phóng VRAM sau khi tắt tiến trình.
  - Tốc độ sinh RTF `~2.0` là **slower-than-real-time** (chậm hơn thời gian thực 2 lần), hoàn toàn không phù hợp streaming trực tiếp, bắt buộc phải quản lý bằng Durable Background Queue.
  - **Khuyến nghị:** Đủ điều kiện để xây dựng Adapter sản xuất cho Tiếng Trung trong Phase 3, với điều kiện bắt buộc quản lý tài nguyên nghiêm ngặt (tối đa 1 job GPU đồng thời, không vượt ngưỡng VRAM).

---

## 2. MA TRẬN KHẢ THI KỸ THUẬT (ENGINE FEASIBILITY MATRIX)

| Tiêu chí thẩm định | VieNeu-TTS (Tiếng Việt) | Qwen3-TTS 0.6B (Tiếng Trung) |
|:---|:---:|:---:|
| **Khả năng cài đặt Windows** | ✅ PASSED (pip độc lập) | ✅ PASSED (pip + PyTorch cu124) |
| **Bản quyền thương mại** | ✅ Apache-2.0 (Code & Weights) | ✅ Apache-2.0 (Code & Weights) |
| **An toàn phần cứng (RAM/VRAM)** | ✅ PASSED (RAM 2.4GB, 0MB VRAM) | ⚠️ PASSED CÓ HẠN CHẾ (Board VRAM ~5.2GB/6GB; Nguy cơ OOM chưa triệt tiêu) |
| **Tốc độ sinh (RTF)** | ✅ PASSED (RTF 0.57 - Nhanh hơn Real-time) | ⚠️ SLOWER-THAN-REAL-TIME (RTF ~2.0; Cần Job Queue) |
| **Tính toàn vẹn âm thanh** | ✅ PASSED (48kHz, không clipping) | ✅ PASSED (24kHz, không clipping) |
| **Tự khôi phục sau sự cố** | ✅ PASSED | ✅ PASSED |
| **Độ ổn định bộ nhớ** | ⚠️ PASSED (Ổn định 5 lượt ngắn hạn; Dài hạn UNVERIFIED) | ⚠️ PASSED (Ổn định 5 lượt ngắn hạn; Dài hạn UNVERIFIED) |
| **Chạy đồng thời CPU + GPU** | ⚠️ **UNVERIFIED** (Chưa đo lường đồng thời) | ⚠️ **UNVERIFIED** (Chưa đo lường đồng thời) |
| **Phán quyết cuối cùng** | **PASS (Có điều kiện)** | **PASS WITH LIMITATIONS** |

---

## 3. SỔ ĐĂNG KÝ NỢ KỸ THUẬT VÀ LƯU Ý GIAI ĐOẠN TIẾP THEO (TECHNICAL DEBT REGISTER)

1. **TD-001 — Chuẩn hóa Tần số Lấy Mẫu (Sample Rate Normalization):**
   - VieNeu xuất audio `48,000 Hz`, trong khi Qwen3 xuất audio `24,000 Hz`.
   - *Kế hoạch giải quyết:* Tại Phase 3 (Adapter Implementation), bổ sung bước chuẩn hóa tự động qua `soxr` trong Artifact Service để đưa toàn bộ file xuất bản về tần số đồng nhất (hoặc lưu trữ nguyên bản kèm metadata chính xác).
2. **TD-002 — Nhân bản Giọng Đọc Riêng của Cá Nhân (Personal Voice Cloning):**
   - Đường ống kỹ thuật đã được kiểm chứng bằng audio mẫu của repo (`example.wav`).
   - Việc nhân bản giọng đọc cụ thể của người dùng cuối và đánh giá độ tương đồng người nói (speaker similarity) ở trạng thái **UNVERIFIED / PENDING** cho tới khi người dùng tải lên file mẫu giọng của mình trong giao diện người dùng.
3. **TD-003 — Hàng đợi Bền vững & Worker Lease Daemon (Phase 2):**
   - Do Qwen3-TTS có RTF ~2.0 (slower-than-real-time) và biên VRAM nhạy cảm, việc triển khai hàng đợi bền vững SQLite (Phase 2) với cơ chế Slot Locking (tối đa 1 GPU job) và Lease Expiration Recovery là bắt buộc để bảo đảm an toàn hệ thống.
4. **TD-004 — Đo lường Tải Đồng Thời CPU + GPU (Phase 3 Prep):**
   - Trước khi kích hoạt song song 2 worker thực tế, cần thực hiện stress test đồng thời cả 2 engine để đo lường băng thông bus RAM và nhiệt độ phần cứng.

---

## 4. CHIẾN LƯỢC TÍCH HỢP ĐỀ XUẤT (NEXT STEPS PROPOSAL)

1. **Bước 1 (Phase 2 - Hiện tại):** Xây dựng hàng đợi bền vững Durable SQLite Lease Queue, ResourceManager và Worker Lease Daemon với mock engine để bảo đảm an toàn tác vụ, phục hồi sau sập nguồn, kiểm soát slot CPU/GPU.
2. **Bước 2 (Phase 3):** Xây dựng `engines/vieneu-tts` adapter (CPU ONNX) và `engines/qwen3-tts` adapter (GPU bfloat16) dựa trên Engine SDK v1 đã hoàn thiện ở Phase 1.
3. **Bước 3:** Tích hợp giao diện chọn giọng và nạp preset trực quan trên Web UI.
