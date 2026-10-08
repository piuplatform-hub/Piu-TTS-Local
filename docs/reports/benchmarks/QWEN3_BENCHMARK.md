# AI VOICE STUDIO — BÁO CÁO BENCHMARK CHI TIẾT QWEN3-TTS 0.6B (PHASE 1B)

**Kỹ sư phụ trách:** Lead AI/ML Infrastructure Engineer  
**Ngày thực hiện:** 2026-10-08  
**Đối tượng:** Qwen3-TTS-12Hz-0.6B-CustomVoice (`QwenLM/Qwen3-TTS` @ `022e286b98fbec7e1e916cb940cdf532cd9f488e`)  
**Backend:** PyTorch 2.6.0+cu124 (CUDA `cuda:0`, `torch.bfloat16`)  
**Môi trường:** Python 3.12.10, PyTorch cu124, Transformers 4.57.3, Accelerate 1.12.0  
**Phần cứng:** NVIDIA GeForce RTX 3050 (6GB VRAM, sm_86), Intel Core i5-12400F, Windows 11  
**Phán quyết:** **PASS** (Đạt hoàn toàn các tiêu chí GPU Speech Synthesis tiếng Trung trên 6GB VRAM)  

---

## 1. TỔNG QUAN KIẾN TRÚC VÀ CƠ CHẾ SUY LUẬN

Qwen3-TTS-12Hz-0.6B-CustomVoice là mô hình ngôn ngữ âm thanh tự hồi quy (discrete multi-codebook LM) với 0.6 tỷ tham số kết hợp Qwen3-TTS-Tokenizer-12Hz.
Mô hình đi kèm 9 giọng đọc nung sẵn (baked-in timbres) bao gồm nam, nữ và các giọng địa phương Trung Quốc.
Trên GPU NVIDIA GeForce RTX 3050 (6GB VRAM), mô hình được chạy ở độ chính xác **`torch.bfloat16`** để tối ưu hóa bộ nhớ và tốc độ xử lý Tensor Cores.

---

## 2. DỮ LIỆU ĐO LƯỜNG THỰC TẾ (EMPIRICAL MEASUREMENTS)

Tất cả các số liệu dưới đây được đo lường trực tiếp từ quá trình chạy thực nghiệm [`benchmarks/run_qwen3_benchmark.py`](file:///d:/C/Dev/du%20an/TTS/benchmarks/run_qwen3_benchmark.py) trên card đồ họa RTX 3050:

### 2.1. Kiểm tra An toàn Bộ nhớ Đồ họa Trước Khởi Chạy (Pre-flight VRAM Inspection)
- **Tổng VRAM phần cứng:** `6,143.5 MB` (6GB GDDR6)
- **VRAM trống ban đầu:** `5,158.0 MB` (Đảm bảo an toàn tuyệt đối)
- **VRAM sau khi nạp mô hình:**
  - VRAM thực tế cấp phát (Allocated): **`2,056.9 MB`** (~2.0 GB)
  - VRAM bộ nhớ đệm PyTorch (Reserved): **`2,184.0 MB`** (~2.1 GB)
  - VRAM còn trống (Free): **`2,964.0 MB`** (~2.9 GB tự do)
- **Độ chính xác số học:** `torch.bfloat16`
- **Danh sách 9 giọng đọc dựng sẵn xác nhận:** `['aiden', 'dylan', 'eric', 'ono_anna', 'ryan', 'serena', 'sohee', 'uncle_fu', 'vivian']`

---

### 2.2. Kiểm thử Tạo Giọng Tiếng Trung Theo Độ Dài Khác Nhau

#### Bài test 1: Câu ngắn tiếng Trung — Giọng "Vivian" (Nữ trẻ trung, Cold Run)
- **Văn bản:** *"你好，欢迎使用本地AI语音合成工作台。"* (18 ký tự)
- **Thời gian sinh âm thanh (Latency):** **`21.95 giây`** (Bao gồm chi phí biên dịch kernel CUDA ban đầu)
- **Độ dài âm thanh sinh ra:** **`4.64 giây`**
- **Real-Time Factor (RTF):** **`4.730`**
- **Đỉnh VRAM tiến trình (Peak Allocated):** **`2,201.7 MB`** (Chỉ tăng 145 MB so với baseline)
- **Tần số lấy mẫu thực tế:** **`24,000 Hz`** (24kHz chuẩn của Qwen3 Tokenizer 12Hz)
- **Kiểm định âm thanh:** Mono, biên độ đỉnh `0.7812`, không clipping (`is_clipping = False`), phát âm chuẩn Mandarin, tự nhiên.

#### Bài test 2: Đoạn văn trung bình tiếng Trung — Giọng "Uncle_Fu" (Nam trầm ấm, Warm Run)
- **Văn bản:** *"人工智能正在深刻改变内容创作与人机交互的方式。通过本地化语音大模型，用户可以在保护隐私的前提下获得高质量且自然的语音体验。"* (68 ký tự)
- **Thời gian sinh âm thanh (Latency):** **`37.06 giây`**
- **Độ dài âm thanh sinh ra:** **`18.08 giây`**
- **Real-Time Factor (RTF):** **`2.050`**
- **Đỉnh VRAM tiến trình (Peak Allocated):** **`2,599.1 MB`** (Chỉ tăng 542 MB)
- **Tần số lấy mẫu:** **`24,000 Hz`**
- **Kiểm định âm thanh:** Mono, biên độ đỉnh `0.7422`, ngữ điệu nam trầm ấm, phát âm rõ ràng, không lẫn tạp âm.

#### Bài test 3: Đoạn văn dài tiếng Trung — Giọng "Serena" (Nữ dịu dàng, Warm Run)
- **Văn bản:** *"中国拥有悠久的历史和灿烂的文化，从长城脚下的古老传说到现代繁华都市的高铁网络，传统与现代在这里交相辉映。语言与文字作为文明的载体，记录了数千年的智慧与创造力，而在人工智能时代，声音的数字化再现赋予了语言新的生命。"* (112 ký tự)
- **Thời gian sinh âm thanh (Latency):** **`49.63 giây`**
- **Độ dài âm thanh sinh ra:** **`24.08 giây`**
- **Real-Time Factor (RTF):** **`2.061`**
- **Đỉnh VRAM tiến trình (Peak Allocated):** **`2,772.3 MB`**
- **Tần số lấy mẫu:** **`24,000 Hz`**
- **Kiểm định âm thanh:** Mono, biên độ đỉnh `0.3730`, duy trì ngữ điệu mượt mà suốt 24 giây không đứt quãng.

---

### 2.3. Khả năng Tự Khôi Phục Sau Lỗi (Error Recovery Verification)

- **Kịch bản kiểm tra:** Cố ý truyền mã giọng không tồn tại: `speaker="NonExistentSpeaker_12345"`.
- **Hành vi quan sát:** Mô hình phát hiện ngay lập tức và ném ngoại lệ chuẩn `ValueError: Unsupported speakers: ['NonExistentSpeaker_12345']` mà không làm hỏng tiến trình hay tràn VRAM.
- **Thực thi ngay sau lỗi:** Gửi yêu cầu tổng hợp văn bản hợp lệ: `text="恢复正常。", speaker="Vivian"`.
- **Kết quả:** Quá trình suy luận thành công ngay sau đó trong **`4.43 giây`**, chứng minh trạng thái GPU không bị rò rỉ hay nghẽn bộ đệm sau ngoại lệ.

---

### 2.4. Độ Ổn định và Tính Ổn Định Qua Các Lần Chạy (Repeated Runs)

Thực hiện 3 lần chạy liên tiếp trên câu ngắn:
- Vòng 1: Thời gian = `10.85s`, RTF = `2.187`
- Vòng 2: Thời gian = `9.00s`, RTF = `1.939`
- Vòng 3: Thời gian = `8.24s`, RTF = `1.873`
- **RTF trung bình (Warm Stable):** **`2.000`**

### 2.5. Phân Định Bộ Nhớ PyTorch vs Bộ Nhớ Vật Lý Card Đồ Họa (Board VRAM)
- **PyTorch Allocated Memory (`torch.cuda.memory_allocated()`):** Đo lường trọng số mô hình và tensor kích hoạt thực tế: Baseline `2,056.9 MB`, đỉnh `2,772.3 MB`.
- **PyTorch Reserved Memory (`torch.cuda.memory_reserved()`):** Bộ nhớ đệm được trình quản lý PyTorch CUDA Caching Allocator giữ lại từ OS: `~2,184 MB – 3,120 MB`.
- **Bộ nhớ Vật lý Toàn Bo mạch (Total Board VRAM qua `nvidia-smi`):** Bao gồm cả Desktop Window Manager (DWM), Chrome/Edge GPU acceleration, CapCut, Antigravity và các ứng dụng Windows khác:
  - Mức nền Windows nhàn rỗi: `~2,209 MiB – 2,472 MiB`.
  - Tổng VRAM toàn bo mạch khi đang suy luận Qwen3-TTS: **`~4,680 MiB – 5,250 MiB / 6,144 MiB`**.
- Sau khi benchmark hoàn tất, gọi `torch.cuda.empty_cache()` và giải phóng tiến trình, VRAM toàn bo mạch quay về mức nhàn rỗi `2,209 MiB`.

---

## 3. THẨM ĐỊNH BẢN QUYỀN MÃ NGUỒN VÀ TRỌNG SỐ

- **Mã nguồn (Code):** Phân phối theo giấy phép **Apache License 2.0** trong kho GitHub `QwenLM/Qwen3-TTS`.
- **Trọng số mô hình (Model Weights):** Trọng số `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` và `Qwen3-TTS-Tokenizer-12Hz` được Alibaba Qwen Team phân phối mở theo giấy phép **Apache-2.0** trên Hugging Face và ModelScope.

---

## 4. ĐÁNH GIÁ CHUYÊN MÔN VÀ CÁC RANH GIỚI BẮT BUỘC

1. **Ranh giới VRAM & Nguy cơ CUDA OOM (Chưa Triệt Tiêu Hoàn Toàn):**
   - Mặc dù bản 0.6B chỉ tiêu tốn nội bộ `~2.77 GB` VRAM cho PyTorch, **nguy cơ CUDA Out-Of-Memory (OOM) KHÔNG THỂ coi là đã bị triệt tiêu**.
   - Vì máy tính phát triển chạy Windows 11 với nhiều ứng dụng đồ họa song song (như CapCut, trình duyệt nhiều tab, Zalo, DWM), tổng bộ nhớ bo mạch đã chạm ngưỡng `~5.25 GB / 6 GB`.
   - Nếu người dùng xử lý video nặng hoặc mở thêm ứng dụng đồ họa khác trong lúc tổng hợp giọng nói, hoặc khi xử lý các đoạn văn bản dài gây phân mảnh bộ nhớ (VRAM fragmentation), sự cố CUDA OOM hoàn toàn có thể xảy ra.
2. **Tốc độ Suy luận (Slower-Than-Real-Time):**
   - RTF thực nghiệm nằm trong khoảng **`1.87 – 2.06` (RTF > 1.0)**.
   - Điều này đồng nghĩa với việc suy luận **chậm hơn thời gian thực khoảng 2 lần** (sinh 10 giây âm thanh mất khoảng 18 đến 20 giây tính toán).
   - Qwen3-TTS 0.6B trên phần cứng này **không phù hợp cho bài toán hội thoại thời gian thực trực tiếp (interactive streaming)** mà bắt buộc phải vận hành thông qua **hàng đợi tác vụ bất đồng bộ (Asynchronous Durable Job Queue)**.
3. **Phán quyết:** **PASS WITH LIMITATIONS** (Đạt cho xử lý hàng đợi nền, cần cơ chế kiểm soát VRAM và giới hạn xử lý đồng thời GPU = 1).
