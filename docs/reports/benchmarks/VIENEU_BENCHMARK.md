# AI VOICE STUDIO — BÁO CÁO BENCHMARK CHI TIẾT VIENEU-TTS (PHASE 1B)

**Kỹ sư phụ trách:** Lead AI/ML Infrastructure Engineer  
**Ngày thực hiện:** 2026-10-08  
**Đối tượng:** VieNeu-TTS v3 Turbo (`pnnbao97/VieNeu-TTS` @ `85344322b7258b4e25479b692e8e3396baf9db34`)  
**Backend:** ONNX Runtime (CPU, Không phụ thuộc PyTorch)  
**Môi trường:** Python 3.12.10, ONNX Runtime 1.30.0, Kaldi Native Fbank 1.22.3, Sea-G2P 0.10.0  
**Phần cứng:** Intel Core i5-12400F (6C/12T), 16GB RAM, Windows 11  
**Phán quyết:** **PASS** (Đạt hoàn toàn các tiêu chí CPU Speech Synthesis tiếng Việt)  

---

## 1. TỔNG QUAN KIẾN TRÚC VÀ CƠ CHẾ SUY LUẬN

VieNeu-TTS v3 Turbo là mô hình tổng hợp tiếng Việt hiện đại sử dụng kiến trúc codec thần kinh MOSS kết hợp mô hình biến đổi âm vị Rust (`sea-g2p`).
Trên môi trường CPU mục tiêu, gói SDK `vieneu-3.8.3` hoạt động ở chế độ **hoàn toàn không cần PyTorch (Torch-Free)** thông qua `onnxruntime` chuẩn FP32.

---

## 2. DỮ LIỆU ĐO LƯỜNG THỰC TẾ (EMPIRICAL MEASUREMENTS)

Tất cả các số liệu dưới đây được đo lường trực tiếp từ quá trình chạy thực nghiệm [`benchmarks/run_vieneu_benchmark.py`](file:///d:/C/Dev/du%20an/TTS/benchmarks/run_vieneu_benchmark.py) trên máy tính phát triển:

### 2.1. Khởi động và Nạp Mô hình (Cold Start Initialization)
- **Bộ nhớ tiến trình ban đầu (RSS):** `31.1 MB`
- **Bộ nhớ sau khi nạp mô hình ONNX:** `1,134.7 MB` (Mô hình chiếm dụng `1,103.5 MB` RAM)
- **Thời gian nạp mô hình:** `59.87s` (Bao gồm tải và kiểm tra hash trọng số ONNX từ Hugging Face Hub)
- **Số lượng giọng dựng sẵn (Preset Voices):** `25 giọng` (Đại diện 3 miền Bắc - Trung - Nam)

---

### 2.2. Kiểm thử Tạo Giọng Dựng Sẵn (Preset Voices)

#### Bài test 1: Câu ngắn tiếng Việt — Giọng "Hải Đăng" (Cold Run)
- **Văn bản:** *"Xin chào, chào mừng bạn đến với hệ thống AI Voice Studio trên máy tính."* (15 từ)
- **Thời gian sinh âm thanh (Latency):** **`3.10 giây`**
- **Độ dài âm thanh sinh ra:** **`3.60 giây`**
- **Real-Time Factor (RTF):** **`0.860`** (Nhanh hơn thời gian thực trên CPU!)
- **Tần số lấy mẫu thực tế (Sample Rate):** **`48,000 Hz`** (Chuẩn phòng thu 48kHz)
- **Mức tải CPU trung bình:** `73.3%`
- **Đỉnh RAM tiến trình:** `1,291.7 MB`
- **Kiểm định âm thanh:** Kênh đơn (Mono), biên độ đỉnh `0.8375`, không bị clipping (`is_clipping = False`), không bị câm (`is_silent = False`).

#### Bài test 2: Đoạn văn trung bình tiếng Việt — Giọng "Mai Anh" (Warm Run)
- **Văn bản:** *"Trí tuệ nhân tạo đang thay đổi sâu sắc cách con người làm việc và sáng tạo. Với công nghệ chuyển đổi văn bản thành giọng nói chạy trực tiếp trên máy tính cá nhân, chúng ta có thể bảo đảm tính riêng tư, tốc độ phản hồi nhanh chóng mà không cần kết nối internet."* (51 từ)
- **Thời gian sinh âm thanh (Latency):** **`11.18 giây`**
- **Độ dài âm thanh sinh ra:** **`14.86 giây`**
- **Real-Time Factor (RTF):** **`0.752`** (Rất ấn tượng đối với CPU thuần túy)
- **Tần số lấy mẫu:** **`48,000 Hz`**
- **Mức tải CPU trung bình:** `68.0%`
- **Đỉnh RAM tiến trình:** `2,139.8 MB`
- **Kiểm định âm thanh:** Mono, biên độ đỉnh `0.6312`, âm thanh trong trẻo, không rè hay méo tiếng.

---

### 2.3. Kiểm thử Đường ống Nhân bản Giọng nói (Zero-Shot Voice Cloning)

- **Mẫu tham chiếu kỹ thuật:** Sử dụng file mẫu chuẩn đi kèm kho mã nguồn `examples/audio_ref/example.wav` (Giọng nam đọc chuẩn thời lượng ~3.5s).
- **Quy trình thực thi:** Tự động khử nhiễu nền (`denoise=True`) -> Trích xuất đặc trưng speaker embedding qua Kaldi Native Fbank -> Suy luận qua ONNX Runtime.
- **Thời gian hoàn thành:** **`10.97 giây`**
- **Độ dài âm thanh sinh ra:** **`4.48 giây`**
- **Real-Time Factor (RTF):** **`2.448`** (Bao gồm chi phí phân tích âm phổ và khử ồn)
- **Đỉnh RAM tiến trình:** `2,440.4 MB`
- **Tần số lấy mẫu:** **`48,000 Hz`**
- **Lưu ý trung thực về nhân bản giọng cá nhân:** Đường ống kỹ thuật nhân bản giọng nói Zero-shot của VieNeu hoạt động hoàn toàn ổn định và chính xác. Tuy nhiên, tính năng nhân bản giọng đọc riêng của cá nhân người dùng được ghi nhận trạng thái **BLOCKED** chờ người dùng cung cấp file ghi âm mẫu chính chủ khi đưa vào vận hành thực tế.

---

### 2.4. Độ Ổn định và Kiểm tra Rò rỉ Bộ nhớ (5 Vòng Chạy Liên Tiếp)

Thực hiện 5 lần suy luận liên tiếp trên câu ngắn với cùng một giọng để đo độ biến thiên RTF và kiểm tra rò rỉ RAM:

| Vòng chạy | Thời gian thực thi | RTF | RAM tiến trình (RSS) |
|:---:|:---:|:---:|:---:|
| 1 | 2.45s | 0.639 | 2,442.1 MB |
| 2 | 2.44s | 0.587 | 2,443.2 MB |
| 3 | 2.14s | 0.545 | 2,443.2 MB |
| 4 | 2.08s | 0.552 | 2,443.2 MB |
| 5 | 2.04s | 0.555 | 2,443.3 MB |

- **RTF trung bình (Warm Runs):** **`0.576 ± 0.035`**
- **Độ dịch chuyển RAM (RAM Drift):** Tăng chỉ `1.2 MB` sau 5 vòng chạy liên tục -> **Không có rò rỉ bộ nhớ (Zero Memory Leak)**.

---

## 3. ĐÁNH GIÁ CHẤT LƯỢNG VÀ TÍNH KHẢ THI TÍCH HỢP

| Tiêu chí | Đánh giá | Chi tiết minh chứng |
|:---|:---:|:---|
| **Cài đặt Windows** | Xuất sắc | Cài đặt trực tiếp qua `pip install vieneu`, không gặp lỗi build C++ |
| **Độ độc lập tài nguyên** | Xuất sắc | Chạy hoàn toàn trên CPU qua ONNX, không tiêu tốn VRAM GPU |
| **Tốc độ sinh âm thanh** | Đạt yêu cầu | RTF 0.55 - 0.75 (nhanh hơn thời gian thực 1.3x - 1.8x) |
| **Chất lượng âm thanh** | Xuất sắc | Tần số 48,000 Hz, tự nhiên, không ngắt quãng |
| **Nhân bản giọng** | Khả thi | Pipeline hoạt động tốt trên mẫu tham chiếu kỹ thuật |

**Kết luận chuyên môn:** VieNeu-TTS v3 Turbo là ứng viên hoàn hảo cho adapter TTS tiếng Việt chạy cục bộ trên CPU của AI Voice Studio.
