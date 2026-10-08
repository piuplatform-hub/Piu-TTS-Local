# HƯỚNG DẪN PHÁT TRIỂN CỤC BỘ (LOCAL DEVELOPMENT GUIDE)
**Hệ điều hành áp dụng:** Windows 10/11  
**Kho mã nguồn:** AI Voice Studio  

---

## 1. YÊU CẦU MÔI TRƯỜNG

- **Python:** Phiên bản 3.10 đến 3.12 (Khuyến nghị 3.12.x 64-bit).
- **Node.js:** Phiên bản 20.x hoặc 24.x LTS (kèm theo `npm` 10+).
- **PowerShell:** Mặc định của Windows.

---

## 2. THIẾT LẬP LẦN ĐẦU (FIRST-TIME SETUP)

### 2.1. Thiết lập Môi trường Ảo Python (Backend & SDK)
Từ thư mục gốc dự án:
```powershell
# 1. Tạo môi trường ảo (nếu chưa có)
python -m venv .venv

# 2. Cài đặt các thư viện backend
.venv\Scripts\pip install -r apps/server/requirements.txt

# 3. Cài đặt Engine Adapter SDK ở chế độ phát triển (Editable Mode)
.venv\Scripts\pip install -e packages/engine_sdk
```

### 2.2. Thiết lập Giao diện Web (Frontend)
```powershell
# Chuyển vào thư mục web và cài đặt gói
cd apps/web
npm install
npm run build
cd ../..
```

---

## 3. KHỞI CHẠY ỨNG DỤNG

### Chế độ A: Trọn gói All-in-One (Khuyến nghị)
FastAPI sẽ tự động phát hiện bundle tại `apps/web/dist` và phục vụ toàn bộ ứng dụng web trên một cổng duy nhất:
```powershell
.venv\Scripts\python -m apps.server.src.main
```
- Khi chạy, màn hình console sẽ hiển thị mã **One-Time Local Bootstrap Token**.
- Mở trình duyệt tại: **http://127.0.0.1:8765**
- Nhập thông tin quản trị và dán mã token để hoàn tất khởi tạo.

### Chế độ B: Chế độ Phát triển với Vite Hot-Reload
Chạy 2 terminal riêng biệt:
- **Terminal 1 (Backend API):**
  ```powershell
  .venv\Scripts\python -m apps.server.src.main
  ```
- **Terminal 2 (Frontend HMR):**
  ```powershell
  cd apps/web
  npm run dev
  ```
  Truy cập: **http://localhost:5173** (Yêu cầu API sẽ tự động proxy sang cổng 8765).

---

## 4. CHẠY BỘ KIỂM THỬ TỰ ĐỘNG (TEST SUITE)

Để chạy kiểm thử toàn bộ hệ thống (Hợp đồng Engine, Xác thực Onboarding, Luồng Job, Chịu lỗi Supervisor, Phục vụ SPA):
```powershell
.venv\Scripts\pytest -v tests/
```

Chạy kiểm thử riêng từng module:
```powershell
# Chỉ kiểm thử hợp đồng Mock Engine
.venv\Scripts\pytest -v tests/contract/

# Chỉ kiểm thử tích hợp API và khả năng chịu lỗi
.venv\Scripts\pytest -v tests/integration/
```

---

## 5. CẤU TRÚC LƯU TRỮ DỮ LIỆU CỤC BỘ

Mặc định, hệ thống lưu trữ dữ liệu tại `D:\AIVoiceStudioData` (hoặc tự động chuyển về `./data` nếu ổ đĩa không ghi được):
```
D:\AIVoiceStudioData/
├── studio.db           # SQLite Database ở chế độ WAL Mode
├── studio.db-wal       # File ghi trước nhật ký WAL
├── studio.db-shm       # File bộ nhớ chia sẻ WAL
├── .bootstrap_token    # Token một lần (tự động xóa sau khi khởi tạo thành công)
├── artifacts/          # Thư mục lưu trữ các file âm thanh WAV đã sinh
│   └── <uuid>.wav
├── models/             # Thư mục dành cho trọng số AI trong tương lai
└── backups/            # Thư mục lưu trữ bản sao lưu cơ sở dữ liệu
```

Để thay đổi đường dẫn lưu trữ dữ liệu, sao chép `.env.example` thành `.env` và điều chỉnh biến:
```env
STUDIO_DATA_DIR="C:\\Path\\To\\Your\\Data"
```
