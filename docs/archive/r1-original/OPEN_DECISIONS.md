# OPEN DECISIONS, TECHNICAL UNKNOWNS & APPROVAL GATES (REVISION R1)
**Project:** AI Voice Studio — Professional Modular AI Platform  
**Document ID:** ARCH-DEC-001-R1  
**Status:** REVISED ARCHITECTURE (R1) — AWAITING PHASE 1 AUTHORIZATION  
**Date:** October 2026  

---

## 1. Phân loại Quyết định Kiến trúc (Categorized Decision Matrix)

### 1.1 Kiến trúc Đã Phê duyệt (Approved Architecture Baseline)
* **API-First & Headless Core:** Core không phụ thuộc framework UI hay HTTP context.
* **Web-First (React 19 + TypeScript + Vite):** Phục vụ đồng thời desktop và trình duyệt LAN.
* **FastAPI Backend (Python 3.12):** Sinh tài liệu OpenAPI tự động, chuẩn hóa lỗi RFC 9457.
* **SQLite WAL Database & Durable Queue:** Cơ sở dữ liệu và hàng đợi atomic leases tích hợp trong một file `studio.db`.
* **Isolated Subprocess Workers:** Mỗi engine chạy trong tiến trình con độc lập với `.venv` riêng, giao tiếp qua loopback HTTP có token xác thực.
* **Bảo mật theo thiết kế từ Phase 1:** Onboarding wizard tạo Admin đầu tiên; RBAC và kiểm tra quyền sở hữu đối với mọi project và voice.

---

### 1.2 Quyết định Có Điều kiện (Conditional on Feasibility Spike Phase 1B)
* **Tần suất dọn dẹp Model GPU:** Nếu VRAM khả dụng luôn dao động dưới 3GB, model Qwen3 sẽ tự động `POST /unload` ngay sau 2 phút nhàn rỗi. Nếu VRAM dư dả (>3.5GB), model được giữ trong VRAM để phục vụ tức thì.
* **Giới hạn số tác vụ CPU đồng thời:** Mặc định chạy 1 job VieNeu-TTS. Nếu Spike đo đạc thấy mức chiếm dụng RAM dưới 1.5GB và CPU i5-12400F không bị bão hòa nhiệt, sẽ cho phép nâng lên 2 job CPU đồng thời.
* **Phiên bản Python cho Worker Qwen3:** Mặc định sử dụng Python 3.12 của hệ thống. Nếu quá trình cài PyTorch CUDA gặp lỗi wheel trên Windows 11, worker này sẽ chuyển sang Python 3.11 trong thư mục `engines/qwen3/.venv`.

---

### 1.3 Giả định Cần Đo đạc Thực tế (Unverified Assumptions to be Measured in Spike)
1. **Mức đỉnh VRAM của Qwen3-TTS 0.6B:** Giả định tài liệu là ~2.5–3.0 GB VRAM. Cần đo đạc thực tế khi sinh văn bản liên tục 50, 100 và 250 chữ Hán.
2. **Tốc độ sinh âm thanh (RTF) của VieNeu-TTS trên CPU i5-12400F:** Cần đo lường thời gian sinh âm thanh cho 1 câu 30 từ xem mất bao nhiêu giây.
3. **Chất lượng âm thanh clone giọng tiếng Việt:** Cần nghiệm thu xem mẫu 3–5 giây âm thanh mẫu tiếng Việt có cho ra chất lượng âm thanh 48kHz trong trẻo, không bị méo tiếng hay không.

---

### 1.4 Tính năng Hoãn lại Cụ thể (Explicitly Deferred Features)
* **DEF-001 (Hoãn đến Phase 5):** **Đóng gói Trình cài đặt Windows (.exe qua Inno Setup / WiX):** Giai đoạn 1–4 chạy máy chủ trực tiếp qua script launcher; đóng gói installer hoàn thiện ở Phase 5.
* **DEF-002 (Hoãn đến Phase 6):** **Model Context Protocol (MCP) Adapter:** Toàn bộ service đã thiết kế chuẩn headless; chỉ hiện thực adapter MCP ở Phase 6 khi sản phẩm đã hoàn chỉnh.
* **DEF-003 (Hoãn vô thời hạn):** **Chuyển đổi sang PostgreSQL:** Chỉ xem xét khi quy mô vượt quá 50 người dùng đồng thời.

---

## 2. Câu hỏi Cần Chủ Dự án Xác nhận Trước khi Bắt đầu Phase 1

1. **Phê duyệt Bản sửa đổi R1:** Bạn có đồng ý với toàn bộ các điều chỉnh trong bản **Architecture Review Revision R1**, bao gồm việc đưa **Bảo mật Onboarding vào Phase 1** và đưa **Engine Feasibility Spike vào Phase 1B** không?
2. **Phê duyệt Cấu trúc Thư mục Dữ liệu:** Bạn có đồng ý đặt thư mục lưu trữ dữ liệu chính thức tại `D:\AIVoiceStudioData` (tách biệt hoàn toàn với mã nguồn dự án tại `D:\C\Dev\du an\TTS`) để đảm bảo không bao giờ bị mất dữ liệu khi cập nhật code không?
3. **Cấp phép Kích hoạt Phase 1:** Bạn có chính thức cấp quyền để bắt đầu khởi tạo cấu trúc Monorepo, Database SQLite và Mock Engine của **Phase 1** không?
