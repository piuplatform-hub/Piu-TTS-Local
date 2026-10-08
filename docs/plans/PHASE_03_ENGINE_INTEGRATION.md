# AI Voice Studio — Phase 3 Plan: Production AI Engine Adapters & End-to-End Inference Integration

## 1. Mục tiêu và Phạm vi (Scope)
Phase 3 hiện thực hóa việc kết nối hai neural speech engine đầu tiên vào nền tảng AI Voice Studio:
- **Engine A: VieNeu-TTS (`vieneu-tts`)**: Tổng hợp tiếng Việt trên CPU (ONNX Runtime FP32), xuất âm thanh chất lượng cao 48kHz WAV PCM 16-bit, hỗ trợ 22 giọng đọc preset và tính năng nhân bản giọng nói zero-shot (zero-shot voice cloning) thông qua trích xuất embedding từ tệp âm thanh WAV mẫu.
- **Engine B: Qwen3-TTS (`qwen3-tts`)**: Tổng hợp tiếng Trung (Mandarin Chinese) sử dụng mô hình 0.6B CustomVoice trên GPU NVIDIA GeForce RTX 3050 (6GB VRAM, `bfloat16`), xuất âm thanh 24kHz WAV, hỗ trợ 9 giọng đọc built-in (Vivian, Uncle_Fu, Serena, Aiden, Dylan, Eric, Ono_Anna, Ryan, Sohee). **Tuyệt đối không hỗ trợ voice cloning**.

Phạm vi Phase 3 tuân thủ nghiêm ngặt:
- Kiến trúc Modular Monolith và Headless Application Core (ADR-001, ADR-002).
- Cô lập worker processes trong môi trường Python độc lập (`vieneu_env`, `qwen3_env`), giao tiếp qua loopback HTTP với Engine Adapter SDK v1.0 (ADR-004, ADR-005).
- Tái sử dụng trọng số mô hình đã tải tại `D:\AIVoiceStudioData\benchmarks\models\huggingface`.
- Hàng đợi bền vững SQLite WAL, cơ chế Fencing Token và bộ điều phối tài nguyên slot (`max_gpu_slots=1`, `max_cpu_slots=1`).
- Giữ vững biên an toàn loopback: `127.0.0.1`, không mở mạng LAN, không can thiệp Windows Firewall.

---

## 2. Thiết kế Kỹ thuật (Technical Design)

```mermaid
flowchart TD
    subgraph Client["Web Frontend / Client"]
        UI["React Studio UI (apps/web)"]
        Audio["AudioPlayer (24kHz / 48kHz WAV)"]
    end

    subgraph Core["Headless Core (FastAPI)"]
        API["Jobs & Engines API"]
        DQueue["DurableQueueService (SQLite WAL)"]
        Sched["DurableJobScheduler"]
        RM["ResourceManager (Slot Locks)"]
        Sup["ProcessSupervisor (Job Objects)"]
        Art["ArtifactService (Local Storage)"]
    end

    subgraph Workers["Isolated Worker Subprocesses"]
        subgraph WorkerA["VieNeu Worker (vieneu_env, CPU)"]
            V_HTTP["Loopback HTTP :port"]
            V_ONNX["ONNX Runtime FP32"]
            V_Model["VieNeu-TTS v3 Turbo (48kHz)"]
        end
        subgraph WorkerB["Qwen3 Worker (qwen3_env, GPU)"]
            Q_HTTP["Loopback HTTP :port"]
            Q_Torch["PyTorch 2.6 CUDA bfloat16"]
            Q_Model["Qwen3-TTS 0.6B (24kHz)"]
        end
    end

    UI -->|POST /api/v1/jobs/speech| API
    API -->|Enqueue & Lease| DQueue
    Sched -->|Claim Job| DQueue
    Sched -->|Request Slot| RM
    Sched -->|Loopback HTTP RPC| Sup
    Sup -->|Forward Request| V_HTTP
    Sup -->|Forward Request| Q_HTTP
    V_HTTP --> V_Model
    Q_HTTP --> Q_Model
    V_Model -->|48kHz WAV Bytes| Sched
    Q_Model -->|24kHz WAV Bytes| Sched
    Sched -->|Store WAV & Calculate Metadata| Art
    Sched -->|Fenced Complete| DQueue
    DQueue -->|SSE Stream Events| UI
    Audio -->|GET /api/v1/artifacts/{id}/file| Art
```

---

## 3. Quản lý Tài nguyên & Slot Isolation
1. **NVIDIA RTX 3050 (6GB VRAM)**:
   - Mô hình Qwen3-TTS 0.6B chiếm ~2.06 GB VRAM cấp phát tĩnh.
   - `ResourceManager` áp đặt giới hạn cứng: `max_gpu_slots = 1`.
   - Nếu có nhiều job GPU gửi đến, job thứ hai được xếp hàng đợi với cờ `waiting_reason = "Awaiting GPU slot"`.
2. **Intel Core i5-12400F CPU**:
   - `max_cpu_slots = 1`, cho phép 1 job CPU chạy độc lập song song với 1 job GPU (`max_global_slots = 2`).
   - Tổng mức tiêu thụ RAM của VieNeu-TTS tối đa ~2.4GB, đảm bảo an toàn tuyệt đối trên hệ thống 16GB RAM.

---

## 4. Kế hoạch Kiểm thử & Tiêu chí Nghiệm thu (Acceptance Criteria)
1. **Pre-flight Gate**: Vượt qua toàn bộ 6 bài kiểm tra độc lập về scheduler, crash recovery, slot locks và SSE event replay.
2. **Contract Testing**: Cả 2 engine adapter đáp ứng chuẩn RFC 9457 Problem Details, HTTP endpoints `/health`, `/info`, `/synthesize`, `/unload`.
3. **Integration Testing**: Thực hiện trọn vẹn chu trình tạo job, xử lý lease, nhận audio artifact, kiểm tra sample rate (48000 Hz và 24000 Hz), kiểm thử tương tranh song song CPU/GPU.
4. **Browser E2E Testing**: Tự động hóa trình duyệt Google Chrome thông qua Playwright, xác nhận UI studio, voice dropdown, audio playback, tải tệp và xem lịch sử.
5. **Runtime Telemetry**: Đo lường trung thực Cold Start, Warm Start, RSS, VRAM, RTF.
