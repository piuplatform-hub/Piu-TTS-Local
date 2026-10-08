# AI VOICE STUDIO — BÁO CÁO MÔI TRƯỜNG THỰC THI & PRE-FLIGHT VERIFICATION (PHASE 1B)

**Kỹ sư phụ trách:** Lead AI/ML Infrastructure Engineer  
**Ngày thực hiện:** 2026-10-08  
**Phạm vi:** Kiểm tra trước thực thi (Pre-flight Checks), phân tích phần cứng, khả năng tương thích CUDA, bản quyền mã nguồn/trọng số, và kế hoạch cô lập môi trường  
**Trạng thái thẩm định Pre-flight:** **PASSED (Đạt tiêu chuẩn an toàn phần cứng)**  

---

## 1. THÔNG SỐ PHẦN CỨNG & HỆ ĐIỀU HÀNH MỤC TIÊU

| Thành phần | Thông số phát hiện thực tế | Ghi chú đánh giá |
|:---|:---|:---|
| **Hệ điều hành** | Windows 11 Pro 64-bit (Build 26100) | Môi trường mục tiêu |
| **CPU** | Intel Core i5-12400F (6 Cores, 12 Threads @ 2.50GHz - 4.40GHz) | Kiến trúc Alder Lake, hỗ trợ AVX2, VNNI |
| **RAM vật lý** | 16.0 GB DDR4 | Đạt ngưỡng tối thiểu cho mô hình 0.6B/ONNX |
| **GPU rời** | NVIDIA GeForce RTX 3050 (GA106/GA107, Ampere sm_86) | 6,144 MiB (6GB) VRAM GDDR6 |
| **NVIDIA Driver** | 591.86 | Driver hiện đại, hỗ trợ CUDA runtime lên tới 13.1 |
| **VRAM khả dụng** | ~3,672 MiB khả dụng (Hiện tại ~2,472 MiB đang được dùng bởi Desktop/App) | **Lưu ý an toàn:** Cần giám sát chặt chẽ VRAM peak của Qwen3-TTS |
| **Dung lượng ổ đĩa D:** | Dung lượng trống: **431.81 GB** (Tổng: 878.53 GB) | Hoàn toàn thoải mái cho bộ nhớ đệm model |
| **Dung lượng ổ đĩa C:** | Dung lượng trống: **246.68 GB** (Tổng: 476.00 GB) | An toàn |
| **Python hệ thống** | Python 3.12.10 64-bit (`C:\Users\OS\AppData\Local\Programs\Python\Python312\python.exe`) | Tương thích hoàn hảo với cả VieNeu-TTS và Qwen-TTS |

---

## 2. THẨM ĐỊNH TÍNH TƯƠNG THÍCH CUDA & PYTORCH

- **Kiến trúc GPU:** NVIDIA GeForce RTX 3050 thuộc thế hệ Ampere, năng lực tính toán Compute Capability **`sm_86`**.
- **Hỗ trợ định dạng số:** Hỗ trợ tính toán phần cứng cho cả `FP32`, `FP16` và `BF16` (Bfloat16).
- **Driver / CUDA Runtime:** NVIDIA Driver 591.86 hỗ trợ CUDA 11.x, 12.x và 13.x.
- **Phiên bản PyTorch CUDA lựa chọn cho Qwen3-TTS:** PyTorch 2.6+ hoặc 2.8+ với CUDA 12.4 / 12.6 / 12.8 (`cu124` / `cu126` / `cu128`), hoàn toàn tương thích và khai thác tối đa Tensor Cores của RTX 3050.

---

## 3. THẨM ĐỊNH BẢN QUYỀN MÃ NGUỒN VÀ TRỌNG SỐ (LICENSING AUDIT)

### 3.1. Engine A: VieNeu-TTS
- **Repository:** `https://github.com/pnnbao97/VieNeu-TTS`
- **Commit Hash:** `85344322b7258b4e25479b692e8e3396baf9db34` (Release v3.8.3)
- **Tác giả:** Phạm Nguyễn Ngọc Bảo (`pnnbao97`)
- **Bản quyền mã nguồn:** **Apache License 2.0** (Tự do sử dụng thương mại, sửa đổi, phân phối, có bảo vệ sáng chế).
- **Bản quyền bộ giọng mẫu (Preset Voices):** Đi kèm theo giấy phép **Apache 2.0**.
- **Bản quyền trọng số ONNX v3 Turbo:** Được phân phối mở trên Hugging Face theo điều khoản Apache 2.0.
- **Rủi ro pháp lý:** Thấp. Lưu ý: Phiên bản tương lai v4 dự kiến là độc quyền (proprietary), nhưng v3 Turbo hiện tại hoàn toàn là mã nguồn mở Apache 2.0.

### 3.2. Engine B: Qwen3-TTS
- **Repository:** `https://github.com/QwenLM/Qwen3-TTS`
- **Commit Hash:** `022e286b98fbec7e1e916cb940cdf532cd9f488e`
- **Tác giả:** Alibaba Qwen Team
- **Bản quyền mã nguồn:** **Apache License 2.0**.
- **Trọng số mô hình mục tiêu:** `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` và `Qwen/Qwen3-TTS-Tokenizer-12Hz`.
- **Bản quyền trọng số:** **Apache License 2.0** trên Hugging Face / ModelScope.
- **Rủi ro pháp lý:** Thấp. Cho phép tích hợp thương mại và sử dụng offline.

---

## 4. CHIẾN LƯỢC CÔ LẬP MÔI TRƯỜNG & KHÔNG GIAN LƯU TRỮ

Để đảm bảo tuân thủ nghiêm ngặt nguyên tắc cách ly của ADR-0003 và ranh giới Phase 1B:
1. **Không đụng chạm môi trường gốc:** Môi trường ảo của ứng dụng chính (`d:\C\Dev\du an\TTS\.venv`) và cơ sở dữ liệu (`D:\AIVoiceStudioData\studio.db`) được giữ nguyên 100%.
2. **Thư mục làm việc cô lập:**
   - Mã nguồn upstream: `D:\AIVoiceStudioData\benchmarks\sources\`
   - Môi trường ảo Engine A: `D:\AIVoiceStudioData\benchmarks\envs\vieneu_env\`
   - Môi trường ảo Engine B: `D:\AIVoiceStudioData\benchmarks\envs\qwen3_env\`
   - Trọng số mô hình: `D:\AIVoiceStudioData\benchmarks\models\` (Đặt `HF_HOME` và `MODELSCOPE_CACHE` trỏ về đây).
   - File âm thanh benchmark: `D:\AIVoiceStudioData\benchmarks\audio\`
3. **Ước tính lưu lượng tải về và dung lượng ổ cứng:**
   - VieNeu-TTS: ~1.5 GB (Dependencies + ONNX weights + G2P dictionary)
   - Qwen3-TTS: ~5.5 GB (PyTorch CUDA wheels + 0.6B CustomVoice model weights + Tokenizer)
   - Tổng lưu lượng: ~7.0 GB (Chiếm ~1.6% dung lượng trống 431 GB của ổ D: -> Hoàn toàn an toàn).

---

## 5. KẾT LUẬN PRE-FLIGHT

Điều kiện phần cứng, dung lượng đĩa, bản quyền và tính tương thích của cả 2 Engine đều **ĐẠT TIÊU CHUẨN**. Tiến hành thiết lập môi trường và thực thi benchmark theo đúng kế hoạch.
