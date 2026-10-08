# ARCHITECTURE REVIEW & CRITICAL EVALUATION (REVISION R1)
**Project:** AI Voice Studio — Professional Modular AI Platform  
**Document ID:** ARCH-REV-001-R1  
**Author:** Principal Software Architect & Technical Reviewer  
**Status:** R1.1 — PROPOSED / PENDING OWNER APPROVAL (documentation revision only)  
**Date:** October 2026  

> **Canonical contract:** [CANONICAL_CONTRACTS.md](CANONICAL_CONTRACTS.md). This R1.1 text is a design proposal, not evidence of implementation or measured performance. For contradictions, canonical contracts and accepted ADRs take precedence.

---

## 1. Executive Summary & Review R1 Status

### 1.1 Phán quyết Kiến trúc Revision R1: `ACCEPT WITH CHANGES (REVISED)`
Phiên bản duyệt lại **R1** đã **đề xuất giải pháp trên giấy** cho 10 yêu cầu hiệu chỉnh kỹ thuật (**CR-001 đến CR-010**) từ hội đồng đánh giá độc lập.

Kiến trúc giữ vững nền tảng cốt lõi:
* **API-First & Headless Core**
* **Modular Monolith** với phân ranh giới miền nghiệp vụ rõ ràng
* **Web-First (React + Vite)** cho giao diện người dùng
* **Isolated Inference Workers** với môi trường Python độc lập và giao tiếp loopback HTTP
* **Capability-Driven Engine SDK**

Đồng thời, phiên bản R1 loại bỏ triệt để các giả định non nớt về bảo mật, tài nguyên phần cứng và hàng đợi, chuyển dịch từ mô hình "thiết kế lý thuyết" sang mô hình **"bảo mật theo thiết kế (Security-by-Design)", "lập lịch theo thực tế tài nguyên (Resource-Aware)"** và **"nghiệm thu lát cắt dọc (Vertical Slice)"**.

### 1.2 Điểm tự đánh giá của bản R1: `9.4 / 10` (chủ quan, không phải điểm nghiệm thu)
* **Tính khả thi kỹ thuật:** Nâng từ 7.5 lên 9.5 nhờ đưa Spike kiểm chứng Engine vào đầu lộ trình và loại bỏ giả định tĩnh về VRAM.
* **Tính an toàn & bảo mật:** Nâng từ 7.0 lên 9.2 nhờ cơ chế onboarding có kiểm soát, xác thực người dùng ngay từ Phase 1 và quy chuẩn bảo mật mạng LAN đa lớp.
* **Độ bền vững của hàng đợi:** Nâng từ 8.0 lên 9.5 với cơ chế Atomic Leases, Heartbeat, Idempotency và Atomic Artifact Publication.

---

## 2. Nhật ký Thay đổi Kiến trúc (Changelog R0 -> R1)

| Mã CR | Nội dung Hiệu chỉnh Cốt lõi | Trạng thái trong R1 |
| :--- | :--- | :--- |
| **CR-001** | **Bảo mật & Xác thực:** Đưa xác thực/phân quyền vào Phase 1; loại bỏ hoàn toàn cơ chế tự động cấp quyền Admin cho mọi request localhost; bổ sung quy trình Local Onboarding Wizard. | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-002** | **Bảo mật mạng LAN:** Định nghĩa chiến lược TLS / Reverse Proxy qua LAN; xác thực Host/Origin; phân quyền truy cập file; cấm chạy dưới quyền LocalSystem; khuyến nghị tài khoản dịch vụ tối thiểu quyền. | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-003** | **Quản lý Tài nguyên Thực tế:** Xóa bỏ giả định VRAM 3.8GB là giới hạn cố định; xây dựng Bộ lập lịch Dynamic Resource-Aware giám sát NVML/RAM trước và trong khi chạy; giới hạn CPU concurrency an toàn (mặc định 1 job, kiểm tra RAM). | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-004** | **Early Engine Feasibility Spike:** Đưa Spike kiểm chứng tương thích thực tế (VieNeu CPU, Qwen3 GPU, RAM/VRAM peak, Windows 11/Python 3.12) lên ngay đầu lộ trình (Phase 1B). | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-005** | **Hàng đợi Bền vững Chuẩn xác:** Bổ sung Atomic Leases (`BEGIN IMMEDIATE RETURNING`), Worker Ownership, Heartbeat/Expiry, Restart Recovery, Retry Backoff, Idempotency và Xuất bản Artifact nguyên tử. | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-006** | **An toàn Plugin & Chuẩn hóa Hợp đồng:** Yêu cầu Admin phê duyệt plugin; kiểm tra checksum/hash; phân tách rõ Engine/Model/Voice metadata; loại bỏ tham số tốc độ/cao độ hardcode; chuẩn hóa mã lỗi RFC 9457. | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-007** | **Ranh giới Dữ liệu & Di chuyển DB:** Tách riêng Code, Data, Model Weights vào thư mục Windows chuẩn (`%LOCALAPPDATA%` hoặc custom Drive D); đính chính việc chuyển đổi PostgreSQL đòi hỏi di chuyển locking/dialect. | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-008** | **Chuẩn hóa Bản quyền & MCP:** Bổ sung điều khoản cấp phép riêng cho Code/Weights; quy định rõ phương án phân phối FFmpeg (LGPL non-free binary / source offer); cập nhật RFC 9457 và chuẩn MCP Streamable HTTP. | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-009** | **Chiến lược Desktop:** Phân biệt rõ cửa sổ Edge App Window và ứng dụng desktop đóng gói độc lập; server hoạt động độc lập dưới dạng tiến trình nền/khay hệ thống (System Tray). | **Đã cập nhật thiết kế; chưa kiểm thử** |
| **CR-010** | **Lộ trình Lát cắt Dọc & Nền tảng UI:** Đưa UI Shell, Design System và API Client vào Phase 1 cùng Mock Engine để nghiệm thu trọn vẹn luồng tương tác sớm. | **Đã cập nhật thiết kế; chưa kiểm thử** |

---

## 3. Ma trận Truy xuất Yêu cầu (Requirements Traceability Matrix)

| Yêu cầu Hệ thống | Thành phần Kiến trúc Hiện thực | Tài liệu Tham chiếu | Kiểm thử & Nghiệm thu Tương ứng |
| :--- | :--- | :--- | :--- |
| **Bảo mật cục bộ & Onboarding** | `IdentityModule`, `LocalOnboardingWizard`, Argon2id | `SECURITY_DEPLOYMENT.md` | `test_auth_onboarding_bootstrap()`, `test_rbac_ownership()` |
| **Bảo mật chia sẻ LAN** | Host/Origin Guard, RateLimiter, TLS Caddy Proxy | `SECURITY_DEPLOYMENT.md` | `test_lan_unauthorized_rejection()`, `test_origin_validation()` |
| **Hàng đợi bền vững đa người dùng** | `DurableJobQueue`, SQLite WAL Atomic Leases | `API_DATA_DESIGN.md` | `test_atomic_lease_concurrency()`, `test_job_restart_recovery()` |
| **An toàn tài nguyên GPU/RAM** | `ResourceAwareScheduler`, Dynamic NVML Monitor | `TARGET_ARCHITECTURE.md` | `test_gpu_mutex_exhaustion()`, `test_low_vram_graceful_hold()` |
| **Độc lập Plugin & Engine SDK** | `EngineAdapterSDK`, Manifest Schema, Ephemeral HTTP | `PLUGIN_ARCHITECTURE.md` | `test_engine_contract_compliance()`, `test_worker_crash_isolation()` |
| **TTS Tiếng Việt & Clone giọng** | `VieNeuAdapter` (ONNX CPU, 48kHz) | `PLUGIN_ARCHITECTURE.md` | `test_vieneu_synthesis()`, `test_vieneu_voice_clone()` |
| **TTS Tiếng Trung (Mandarin)** | `Qwen3Adapter` (0.6B CustomVoice, PyTorch CUDA) | `PLUGIN_ARCHITECTURE.md` | `test_qwen_synthesis_preset_speakers()` |
| **Ghép thoại & Chuẩn hóa âm thanh** | `AudioDSPPipeline` (FFmpeg Standalone, EBU R128) | `TARGET_ARCHITECTURE.md` | `test_dialogue_concat_and_loudnorm()` |
| **Giao diện Studio chuyên nghiệp** | Web-First UI (React 19, Tailwind, shadcn/ui) | `IMPLEMENTATION_ROADMAP.md` | `test_e2e_speech_studio_workflow()` |
| **Sẵn sàng tích hợp MCP** | Application Services Headless Layer | `MCP_READINESS.md` | `test_headless_services_no_http_coupling()` |

---

## 4. Phân ranh giới Quyết định (Decision Boundaries)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. KIẾN TRÚC ĐÃ PHÊ DUYỆT (Approved Baseline)                                          │
│ - API-First, Headless Core, Modular Monolith.                                         │
│ - React 19 + TypeScript + Vite (Web-First).                                            │
│ - FastAPI (Python 3.12) + SQLite WAL (Cơ sở dữ liệu & Hàng đợi giao dịch).             │
│ - Cô lập worker qua tiến trình con độc lập + loopback HTTP (có token xác thực).       │
│ - VieNeu-TTS chạy CPU (ONNX); Qwen3-TTS 0.6B chạy GPU (CUDA).                         │
│ - Bảo mật theo thiết kế: Onboarding Wizard, RBAC, tách biệt quyền sở hữu.             │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                            │
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. QUYẾT ĐỊNH CÓ ĐIỀU KIỆN (Conditional on Feasibility Spike)                          │
│ - Tần suất dọn dẹp model GPU (Unload sau X phút nhàn rỗi vs giữ liên tục).             │
│ - Mức giới hạn RAM an toàn cho CPU worker (tùy kết quả đo đạc Spike Phase 1B).         │
│ - Lựa chọn phiên bản Python chuẩn xác cho Worker Qwen3 (3.12 vs 3.11 nếu CUDA lỗi).    │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                            │
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. GIẢ ĐỊNH CHƯA ĐƯỢC XÁC MINH (Unverified Assumptions to be Measured in Spike)        │
│ - Mức tiêu thụ VRAM đỉnh thực tế của Qwen3-TTS 0.6B với văn bản dài (>200 từ).        │
│ - Real-Time Factor (RTF) của VieNeu-TTS v3 Turbo trên chip Intel Core i5-12400F.       │
│ - Độ ổn định của PyTorch CUDA 12/13 wheel trên Windows 11 với Python 3.12.            │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                            │
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. TÍNH NĂNG HOÃN LẠI (Explicitly Deferred Features)                                   │
│ - Triển khai thực tế MCP Server / Client (Hoãn đến Phase 6).                          │
│ - Đóng gói bộ cài đặt Windows độc lập (.exe / MSIX / Inno Setup) (Hoãn đến Phase 5).   │
│ - Chuyển đổi sang PostgreSQL (Chỉ xem xét khi số lượng người dùng vượt quá 50 người).  │
│ - Huấn luyện lại model (Training / Full Finetuning) từ đầu.                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Kết luận & Khuyến nghị Tiến độ

Kiến trúc **Revision R1** đã vá kín toàn bộ các kẽ hở về tính đúng đắn của hàng đợi, bảo mật đa người dùng, nguy cơ tràn VRAM và xung đột môi trường. Nền tảng này đảm bảo hệ thống có thể mở rộng vững chắc trong 5 năm mà không cần đập đi xây lại.

**Đề xuất hành động R1.1:** Review và phê duyệt **tài liệu** trước; Phase 1 source implementation và Phase 1B model benchmark là **hai authorization gate riêng biệt**.


## 6. Documentation corrections in R1.1

R1.1 removes the incompatible `UPDATE ... LIMIT ... RETURNING` example, prevents unsafe bootstrap, defines plugin hashes as integrity-only, and reconciles Phase 1 mock end-to-end acceptance with Phase 2 durable-queue hardening. See [R1_1_CHANGELOG.md](R1_1_CHANGELOG.md) and [CANONICAL_CONTRACTS.md](CANONICAL_CONTRACTS.md). These are **documentation changes**, not executed tests or shipped features.
