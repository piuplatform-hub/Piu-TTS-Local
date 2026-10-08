---
id: ADR-0010
title: Single-Host Local Reverse Proxy & Internal TLS for Studio LAN Access
status: proposed
decision_authority: Product Owner
owner: Principal Software Architect
created: 2026-10-09
updated: 2026-10-09
related: [ADR-0001, ADR-0002, ADR-0005, ADR-0006]
---

# Decision record: ADR-0010: Single-Host Local Reverse Proxy & Internal TLS for Studio LAN Access

## Background / problem
Trong các Phase 0–4, máy chủ FastAPI chỉ lắng nghe trên giao diện cục bộ `127.0.0.1:8765` để đảm bảo an toàn tuyệt đối. Khi mở rộng sang Phase 5 cho phép các máy tính của biên tập viên trong cùng mạng nội bộ (mạng LAN phòng thu) truy cập vào ứng dụng, việc phơi bày trực tiếp giao thức HTTP thuần qua mạng tiềm ẩn nguy cơ bảo mật nghiêm trọng:
1. Gói tin truyền trên mạng Wi-Fi/LAN không được mã hóa, kẻ tấn công cùng mạng có thể đánh cắp JWT Bearer token qua kỹ thuật bắt gói tin (packet sniffing).
2. FastAPI và Uvicorn phải gánh tải phục vụ tệp tĩnh giao diện web (SPA assets) và trực tiếp đối mặt với các rủi ro kết nối TCP chậm (Slowloris attacks).
3. Thiếu cơ chế nén HTTP/2, gzip/zstd và bảo vệ tiêu đề an ninh đầu biên (HSTS, CSP, X-Frame-Options).

## Scope and exclusions
- **Trong phạm vi:** Thiết lập tầng Reverse Proxy biên trên cùng máy trạm Windows 11 để lắng nghe trên IP mạng LAN với mã hóa bắt buộc HTTPS/TLS; chuyển tiếp an toàn về FastAPI tại `127.0.0.1:8765`.
- **Ngoại trừ:** Nghiêm cấm mở cổng ra Internet công cộng hoặc tự ý thay đổi cấu hình tường lửa Windows khi chưa có sự cho phép của Product Owner.

## Proposed approach / options

### Phương án A (Được đề xuất): Caddy Server làm Local Reverse Proxy
- **Đặc điểm:** Tệp thực thi đơn lẻ (single portable binary `caddy.exe`), hiệu năng rất cao, chiếm <30MB RAM.
- **Ưu điểm vượt trội:** Tích hợp sẵn bộ máy quản lý chứng chỉ số nội bộ (**Caddy Internal CA**), tự động sinh và gia hạn chứng chỉ TLS cho IP LAN hoặc hostname nội bộ (`studio.local`) mà không cần kết nối Internet hay dùng Let's Encrypt. Hỗ trợ chuẩn HTTP/2, HTTP/3, tự động chuyển hướng HTTP sang HTTPS, nén zstd/gzip cực nhanh và cấu hình Caddyfile vô cùng tinh gọn.
- **Nhược điểm:** Cần tải tệp nhị phân `caddy.exe` đặt vào thư mục công cụ của dự án.

### Phương án B: Nginx for Windows
- **Đặc điểm:** Phổ biến trong môi trường Linux, nhưng bản chạy trên Windows sử dụng kiến trúc mô phỏng `select()` cũ, quản lý tiến trình phức tạp hơn và không có tính năng tự động cấp chứng chỉ TLS nội bộ (phải tự dùng OpenSSL dòng lệnh phức tạp).

### Phương án C: Uvicorn Native SSL trên FastAPI
- **Đặc điểm:** Cấu hình `--ssl-keyfile` và `--ssl-certfile` trực tiếp vào lệnh khởi chạy Uvicorn và bind `0.0.0.0`.
- **Nhược điểm:** Phá vỡ nguyên tắc phân tầng an ninh; FastAPI phải tự mã hóa SSL, tiêu tốn CPU của tiến trình Python; không hỗ trợ HTTP/2; khó quản lý phân phối chứng chỉ tự ký; nếu Uvicorn gặp lỗi thì toàn bộ kết nối mạng bị gián đoạn.

## Risks / security / operations
- **Bảo mật:** Bắt buộc 100% kết nối qua mạng LAN phải sử dụng HTTPS. Không cho phép fallback HTTP không mã hóa.
- **Chứng chỉ tự ký trên máy khách:** Máy tính biên tập viên truy cập lần đầu sẽ thấy cảnh báo "Untrusted Certificate" nếu chưa cài đặt Root CA của Caddy. Cung cấp script PowerShell một chạm (`scripts/install_lan_cert.ps1`) để nhập chứng chỉ tin cậy vào Windows Certificate Store của máy khách.

## Acceptance & evidence
- [ ] Caddy lắng nghe cổng 443 trên IP LAN và chuyển tiếp chính xác về `127.0.0.1:8765`.
- [ ] Mọi truy cập cổng 80 (HTTP) tự động chuyển hướng 301 sang cổng 443 (HTTPS).
- [ ] FastAPI vẫn duy trì lắng nghe an toàn trên `127.0.0.1:8765`.
- [ ] Tải tệp tĩnh và API qua HTTPS đạt độ trễ < 50ms trên mạng LAN 1Gbps.

## Decision / outcome / follow-up
- **Trạng thái:** **Proposed (Chờ Product Owner phê duyệt)**.
- **Kế hoạch liên quan:** [PHASE_05_DEPLOYMENT_SECURITY.md](../../plans/PHASE_05_DEPLOYMENT_SECURITY.md).
