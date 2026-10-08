# AI Voice Studio — Báo Cáo Triển Khai Giai Đoạn 3 (Phase 3 Implementation Report)

**Vai trò:** Principal AI/ML Infrastructure Engineer, Senior Backend Engineer, Software Architect & QA Lead  
**Trạng thái phê duyệt:** HOÀN THÀNH TOÀN DIỆN (100% VERIFICATION PASSED)  
**Ngày hoàn thành:** 08/10/2026  
**Commit cơ sở:** `3fb3bc5`  

---

## 1. TỔNG QUAN KẾT QUẢ ĐẠT ĐƯỢC

Giai đoạn 3 (Phase 3) đã hoàn tất việc tích hợp hai mô hình suy luận giọng nói nhân tạo (Neural Speech Engines) đầu tiên vào nền tảng AI Voice Studio. Toàn bộ kiến trúc tuân thủ nghiêm ngặt chuẩn kiến trúc R1.1, nguyên tắc Modular Monolith, hàng đợi bền vững SQLite WAL, cơ chế Fencing Token và cô lập tiến trình an toàn trên Windows.

### Các thành quả trọng tâm:
1. **Engine A — VieNeu-TTS v3 Turbo (`vieneu-tts`)**:
   - Triển khai thành công Engine Adapter SDK v1.0 trong thư mục `engines/vieneu/`.
   - Chạy cô lập trong môi trường Python 3.12 (`vieneu_env`), suy luận trực tiếp trên CPU qua ONNX Runtime 1.30.0 FP32.
   - Hỗ trợ đầy đủ **22 giọng đọc preset tiếng Việt** (Hải Đăng, Mai Anh, Trúc Ly, Thiện Minh, Thùy Dung,...).
   - Hỗ trợ tính năng **Nhân bản giọng nói Zero-Shot (Zero-shot voice cloning)** thông qua trích xuất speaker embedding từ tệp âm thanh tham chiếu (WAV).
   - Xuất âm thanh phòng thu **48.000 Hz WAV PCM 16-bit**.
2. **Engine B — Qwen3-TTS 0.6B CustomVoice (`qwen3-tts`)**:
   - Triển khai thành công Engine Adapter SDK v1.0 trong thư mục `engines/qwen3/`.
   - Chạy cô lập trong môi trường Python 3.12 (`qwen3_env`), suy luận trên GPU **NVIDIA GeForce RTX 3050 (6GB VRAM)** sử dụng định dạng tính toán `bfloat16`.
   - Hỗ trợ **9 giọng đọc built-in tiếng Trung** (Vivian, Uncle_Fu, Serena, Aiden, Dylan, Eric, Ono_Anna, Ryan, Sohee).
   - **Tuyệt đối từ chối voice cloning** đúng theo đặc tả an toàn và khả năng của mô hình CustomVoice.
   - Tự động bắt lỗi CUDA Out-of-Memory, thu gom rác bộ nhớ (`torch.cuda.empty_cache()`, `gc.collect()`), phục hồi trạng thái sẵn sàng.
   - Xuất âm thanh **24.000 Hz WAV PCM 16-bit**.
3. **Core Pipeline & Scheduler Alignment**:
   - Mở rộng `TTSJobSubmitRequest` với trường `parameters: Dict[str, Any]` để truyền các tùy chọn nâng cao như `ref_audio`, `denoise`.
   - Nâng cấp `DurableJobScheduler` truyền tải nguyên vẹn `parameters` tới `SynthesisRequest` của Engine SDK.
   - Nâng cấp `ProcessSupervisor` hỗ trợ đường dẫn môi trường ảo tuyệt đối (`virtualenv_path`).
   - Tăng timeout của `EngineWorkerClient` lên 180s để đảm bảo không bị gián đoạn khi thực hiện suy luận mô hình ngôn ngữ lớn (LLM-based TTS).
4. **Nâng cấp Giao diện Web (Studio UI)**:
   - Thêm bộ chọn AI Engine với đầy đủ thông tin đích phần cứng (CPU / GPU CUDA).
   - Tự động đồng bộ và lọc danh sách giọng đọc theo ngôn ngữ được hỗ trợ.
   - Giao diện chuyển đổi giữa "Giọng mẫu có sẵn (Preset Voice)" và "Nhân bản giọng nói (Zero-Shot Cloning)" khi động cơ hỗ trợ.
   - Trình phát âm thanh `AudioPlayer` hỗ trợ phát mượt mà cả 24kHz và 48kHz WAV, kèm nhãn chất lượng và nút tải tệp.
5. **Kiểm thử Toàn diện & Minh chứng E2E**:
   - Pre-flight Gate: **6/6 bài kiểm thử bắt buộc PASSED 100%**.
   - Contract Testing: **3/3 bài kiểm thử hợp đồng PASSED 100%** (`mock-tts`, `vieneu-tts`, `qwen3-tts`).
   - Integration Testing: **4/4 bài kiểm thử tích hợp đầu cuối PASSED 100%**.
   - Chrome Playwright E2E: **1/1 bài kiểm thử tự động hóa trình duyệt Chrome thực tế PASSED 100%**, lưu 6 ảnh chụp màn hình minh chứng chất lượng cao.

---

## 2. DANH MỤC THAY ĐỔI MÃ NGUỒN VÀ CẤU TRÚC TỆP

```
TTS/
├── engines/
│   ├── vieneu/
│   │   ├── engine.manifest.json         (Manifest: CPU, 48kHz, voice_cloning)
│   │   └── worker.py                    (Worker tiến trình độc lập, ONNX Runtime, 22 voices)
│   └── qwen3/
│       ├── engine.manifest.json         (Manifest: GPU, 24kHz, 9 speakers, NO cloning)
│       └── worker.py                    (Worker tiến trình độc lập, CUDA bfloat16, RTX 3050)
├── apps/
│   ├── server/src/
│   │   ├── schemas/job.py               (Thêm parameters: Dict[str, Any])
│   │   ├── supervisor/
│   │   │   ├── supervisor.py            (Hỗ trợ absolute virtualenv_path, Job Objects)
│   │   │   └── scheduler.py             (Forward parameters vào SynthesisRequest)
│   ├── web/
│   │   ├── src/
│   │   │   ├── api/client.ts            (Thêm parameters vào submitTTSJob)
│   │   │   └── components/
│   │   │       └── StudioView.tsx       (Giao diện Phase 3: Engine select, Voice cloning UI)
│   │   └── dist/                        (Production bundle mới sau khi build)
├── packages/
│   └── engine_sdk/
│       └── engine_sdk/
│           ├── client.py                (Timeout 180s cho neural synthesis)
│           └── protocol.py              (Bổ sung vram_mb vào HealthResponse)
├── tests/
│   ├── contract/
│   │   ├── test_vieneu_engine.py        (Kiểm thử hợp đồng VieNeu synthesis & cloning)
│   │   └── test_qwen3_engine.py         (Kiểm thử hợp đồng Qwen3 synthesis & OOM recovery)
│   ├── integration/
│   │   ├── test_phase3_preflight.py     (6 bài kiểm tra pre-flight bắt buộc)
│   │   └── test_phase3_integration.py   (4 bài kiểm thử tích hợp đầu cuối Phase 3)
│   └── e2e/
│       └── test_phase3_browser_e2e.py   (Kiểm thử Playwright trên Google Chrome thật)
├── scripts/
│   └── benchmark_phase3_metrics.py      (Script đo đạc benchmark phần cứng thực tế)
└── docs/
    ├── plans/PHASE_03_ENGINE_INTEGRATION.md
    └── reports/
        ├── benchmarks/PHASE_03_RUNTIME_METRICS.md
        ├── phases/
        │   ├── PHASE_03_IMPLEMENTATION_REPORT.md
        │   └── PHASE_03_KNOWN_LIMITATIONS.md
        ├── tests/PHASE_03_TEST_EVIDENCE.md
        └── screenshots/ (12 ảnh chụp màn hình minh chứng)
```

---

## 3. BẢO MẬT VÀ QUY TẮC AN TOÀN

1. **Loopback Only (`127.0.0.1`):** Mọi cổng giao tiếp giữa Supervisor và Child Worker đều gán ngẫu nhiên trên giao diện loopback cục bộ, xác thực qua token ngẫu nhiên độ an toàn cao (`secrets.token_hex(24)`). Tuyệt đối không mở cổng mạng LAN hay chỉnh sửa Windows Firewall.
2. **Dọn dẹp tiến trình qua Windows Job Object:** Các tiến trình con được gán trực tiếp vào Windows Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`), bảo đảm khi tiến trình cha dừng đột ngột hoặc tắt máy, toàn bộ cây tiến trình Python worker con bị dọn dẹp sạch sẽ, không để lại zombie process.
3. **Giới hạn khe tài nguyên cứng:** Slot GPU được giới hạn tuyệt đối `max_gpu_slots = 1`, triệt tiêu khả năng hai tiến trình tranh chấp VRAM trên card RTX 3050 6GB.
