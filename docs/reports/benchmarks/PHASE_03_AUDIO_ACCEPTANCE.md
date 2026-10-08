# AI VOICE STUDIO — BÁO CÁO KIỂM ĐỊNH GÓI ÂM THANH NGHIỆM THU PHASE 3
## PHASE 3 AUDIO ACCEPTANCE PACKAGE & HARDWARE TELEMETRY AUDIT

- **Thời gian sinh dữ liệu**: 2026-10-08 18:36:09
- **Vị trí lưu trữ thực tế**: `D:\AIVoiceStudioData\acceptance_audio_phase3\`
- **Manifest tệp đính kèm**: `D:\AIVoiceStudioData\acceptance_audio_phase3\acceptance_manifest.json`
- **Tập tin tham chiếu gốc**: `acceptance_cloning_reference.wav` (3.5s, 48kHz, mono 16-bit PCM)
- **Môi trường đo lường**: Windows 11 Pro, Intel Core i5-12400F, 16GB RAM, NVIDIA GeForce RTX 3050 (6GB VRAM, Driver 591.86)

---

## 1. DANH MỤC CÁC TỆP ÂM THANH NGHIỆM THU THỰC TẾ

Gói âm thanh bao gồm 4 tệp WAV được tạo trực tiếp từ hai mô hình nơ-ron thực tế trên môi trường máy trạm Windows của dự án:

| STT | Tên tệp | Mô hình / Engine | Thiết bị | Ngôn ngữ | Chế độ / Giọng | Thời lượng âm thanh | Thời gian xử lý | RTF | Tần số lấy mẫu | Kích thước | SHA-256 Checksum |
| :---: | :--- | :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `vi_male_haidang.wav` | VieNeu-TTS v3.8.3 | CPU | Tiếng Việt (`vi`) | Preset: Hải Đăng | **9.36s** | 12.97s* | **1.39** | 48,000 Hz | 898,604 bytes | `b613c8f089dfbd0621f357c97e79da7afa280538fce3822c3cc1a8aeed0e3f9e` |
| 2 | `vi_female_maianh.wav` | VieNeu-TTS v3.8.3 | CPU | Tiếng Việt (`vi`) | Preset: Mai Anh | **10.16s** | 6.28s | **0.62** | 48,000 Hz | 975,404 bytes | `4856259e21e7633d2fa1f2d474518633684a0955a87be0a541740f7ed00ae493` |
| 3 | `vi_cloned_sample.wav` | VieNeu-TTS v3.8.3 | CPU | Tiếng Việt (`vi`) | Zero-Shot Clone | **9.20s** | 8.49s | **0.92** | 48,000 Hz | 883,244 bytes | `e76240d67c3e7845e180b967ac8fba8df85fc4102eb53873e6990d206fa3ea2c` |
| 4 | `zh_female_vivian.wav` | Qwen3-TTS v1.0.0 | GPU CUDA | Tiếng Trung (`zh`) | Preset: Vivian | **12.40s** | 30.78s | **2.48** | 24,000 Hz | 595,244 bytes | `bb55e28b67f71e690486053a77b833fc8f4e55e39c63a313103c8e3b90f4bdb5` |

*\* Ghi chú: Thời gian xử lý của tệp số 1 bao gồm cả thời gian nạp các module ONNX Runtime lần đầu (cold initialization ~6.5s). Lần tổng hợp thứ 2 (tệp số 2) đạt tốc độ ổn định với RTF = 0.62 (nhanh hơn thời gian thực).*

---

## 2. NỘI DUNG VĂN BẢN VÀ THÔNG SỐ ĐẦU VÀO TƯƠNG ỨNG

### Tệp 1: `vi_male_haidang.wav`
- **Nội dung văn bản**: *"Chào mừng quý thính giả đến với hệ thống AI Voice Studio. Đây là bản thu âm kiểm thử chất lượng giọng đọc nam Hải Đăng chuẩn bốn mươi tám kilohertz trên nền tảng trí tuệ nhân tạo cục bộ."*
- **Số ký tự**: 193 ký tự.
- **Định dạng âm thanh**: 16-bit PCM Linear, Mono (1 channel), 48,000 Hz.

### Tệp 2: `vi_female_maianh.wav`
- **Nội dung văn bản**: *"Bản tin công nghệ hôm nay: Nền tảng AI Voice Studio đã hoàn thành tích hợp các mô hình giọng nói nơ-ron thế hệ mới, vận hành độc lập, an toàn và bảo mật dữ liệu tuyệt đối."*
- **Số ký tự**: 180 ký tự.
- **Định dạng âm thanh**: 16-bit PCM Linear, Mono (1 channel), 48,000 Hz.

### Tệp 3: `vi_cloned_sample.wav`
- **Nội dung văn bản**: *"Đây là bản ghi âm kiểm định tính năng nhân bản giọng đọc tức thời từ tệp âm thanh tham chiếu hợp pháp trên công nghệ VieNeu-TTS."*
- **Số ký tự**: 142 ký tự.
- **Mẫu tham chiếu**: `acceptance_cloning_reference.wav` (SHA-256: `007efc27e64ef8672edefe611152a0ead06aaeee093cbc5be16ac6e549a67132`), có xác nhận bản quyền hợp pháp (`voice_use_consent: true`), khử nhiễu tự động (`denoise: true`).
- **Định dạng âm thanh**: 16-bit PCM Linear, Mono (1 channel), 48,000 Hz.

### Tệp 4: `zh_female_vivian.wav`
- **Nội dung văn bản**: *"你好，欢迎使用 AI Voice Studio 本地智能语音合成系统。当前正在使用 Qwen3 神经语音模型进行中文语音生成测试。"*
- **Số ký tự**: 58 ký tự tiếng Trung.
- **Định dạng âm thanh**: 16-bit PCM Linear, Mono (1 channel), 24,000 Hz.

---

## 3. ĐO ĐẠC TELEMETRY PHẦN CỨNG CHI TIẾT (HARDWARE AUDIT)

### 3.1. Phân biệt Bộ nhớ PyTorch CUDA vs Tổng VRAM Bo mạch (Board VRAM)
Hệ thống đo lường song song qua hai kênh:
1. `torch.cuda.memory_allocated()` trong tiến trình worker:
   - Bộ nhớ tensor thực tế được cấp phát bởi PyTorch: **2,065.0 MB** (~2.02 GB).
2. `nvidia-smi` (toàn bộ bo mạch đồ họa NVIDIA GeForce RTX 3050):
   - **Mức nền trước khi chạy Qwen3 (Idle/Baseline)**: **776.0 MB** used / 6,144.0 MB total (5,227.0 MB free).
   - **Mức đỉnh điểm trong quá trình suy luận (Inference Peak)**: **3,523.0 MB** used (chiếm 57.3% VRAM).
   - **Mức còn trống tối thiểu (Minimum Free VRAM)**: **2,621.0 MB** free.
   - **Mức sau khi tắt worker (Post-Shutdown)**: **776.0 MB** used.
   - **Lượng VRAM được thu hồi sạch (Reclaimed VRAM)**: **2,747.0 MB**.

### 3.2. Tiêu thụ Bộ nhớ RAM Máy chủ (Host Memory)
- **Tiến trình VieNeu-TTS CPU Worker**:
  - RSS đỉnh điểm: **2,444.0 MB** RAM.
  - Sử dụng toàn bộ các nhân hiệu năng của Intel Core i5-12400F thông qua ONNX Runtime threadpool.
  - Giải phóng 100% khi tiến trình con kết thúc.

---

## 4. XÁC NHẬN CÁC ĐIỀU KIỆN QUẢN TRỊ KIẾN TRÚC R1.1

1. **Về tốc độ xử lý của Qwen3-TTS (RTF = 2.48)**:
   - Ghi nhận chính thức: Qwen3-TTS 0.6B chạy trên RTX 3050 có hệ số thời gian thực **RTF = 2.48 > 1.0**, nghĩa là để sinh 12.4 giây âm thanh mất 30.78 giây. Do đó, đây là hình thức xử lý **chậm hơn thời gian thực (slower-than-real-time)**, hoàn toàn phù hợp để chạy theo mô hình hàng đợi bất đồng bộ (durable asynchronous queue), không phù hợp cho phản hồi tương tác tức thì (real-time stream).
2. **Về tính năng nhân bản giọng đọc (Voice Cloning)**:
   - Luồng nghiệp vụ kỹ thuật (Upload WAV -> Validation -> Consent Check -> Embedding Extraction -> Synthesize) đã hoạt động trơn tru và an toàn 100%.
   - Mức độ tương đồng giọng nói theo thính giác người nghe (**Human-Perceived Voice Similarity**) được phân loại chính thức là **UNVERIFIED** và cần tiến hành đánh giá MOS chuyên biệt khi người dùng thực tế trải nghiệm.
3. **Về giới hạn an toàn GPU**:
   - Mặc dù hệ thống khóa cứng 1 GPU slot nội bộ để không bao giờ chạy đồng thời hai tác vụ GPU, nguy cơ CUDA OOM do các tiến trình ngoại vi của hệ điều hành (như game, render 3D khác) không được coi là bị loại trừ tuyệt đối.
