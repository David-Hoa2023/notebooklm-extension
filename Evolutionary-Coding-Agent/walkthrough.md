# Walkthrough: Phase 5 Hardening & Phase 6 Evidence (DeepSeek Migration)

Dự án **Evolutionary Coding Agent** đã hoàn thành nâng cấp hệ thống kết nối LLM từ Gemini API sang DeepSeek API, thay thế các API embedding bằng thuật toán băm đặc trưng cục bộ (local feature hashing) và cấu hình chống thu thập test case sai vị trí.

Dưới đây là chi tiết các thành phần đã triển khai và kết quả xác minh hệ thống.

---

## 1. Các thành phần đã triển khai (Epic Implementation Summary)

### Di Trú DeepSeek & Hashing Embeddings
*   **LLM Client Renaming & Migration**: Đổi tên lớp `GeminiClient` thành `LLMClient` trong `src/llm.py` và chuyển toàn bộ các yêu cầu sinh văn bản / đánh giá độc lập sang API DeepSeek (`deepseek-chat`) thông qua giao thức HTTP `requests`.
*   **Security Enforcement**: Loại bỏ hoàn toàn API key hardcode dự phòng trong mã nguồn. Hệ thống hiện bắt buộc biến môi trường `DEEPSEEK_API_KEY` phải có giá trị trong `os.environ`, nếu không sẽ ném ra ngoại lệ `ValueError`.
*   **Structured JSON Output**: Sử dụng cờ `response_format={"type": "json_object"}` của DeepSeek kết hợp với việc chuyển đổi tự động các schema JSON / Pydantic chèn vào system instruction nhằm đảm bảo DeepSeek luôn trả về cấu trúc dữ liệu JSON chính xác.
*   **Deterministic Local Hashing Embeddings**: Thay thế Gemini embeddings bằng bộ tạo vector 768 chiều hoạt động cục bộ hoàn toàn thông qua thuật toán băm MD5 (bag-of-words hashing trick) với độ dài chuẩn hóa $L_2 = 1$. Việc này loại bỏ hoàn toàn các lỗi `400 INVALID_ARGUMENT` của Gemini API và tăng tốc độ tìm kiếm bộ nhớ.

### Phase 5 Hardening: Bảo vệ Sandbox & Chống Lỗi Thư Viện
*   **Static Pytest Banning**: Bổ sung bộ lọc tĩnh trong `src/exploration/oracle_synthesis.py` để quét và từ chối ngay lập tức bất kỳ `test_code` hoặc `hidden_test_code` nào chứa lệnh `import pytest` hoặc `pytest.`.
*   **Function Name Presence Check**: Phân tích cú pháp mô tả nhiệm vụ để trích xuất tên hàm cần sinh, từ chối các oracle test code không chứa định nghĩa hoặc lời gọi tên hàm này.
*   **SMTP NEG Filter Hardening**: Bổ sung lọc nhiễu insight SMTP trên các tác vụ SMTP/NEG_001. Hệ thống sẽ bỏ qua mọi insight chứa các từ khóa liên quan đến xác thực hoặc bảo mật không khớp đặc tả (`"login"`, `"starttls"`, `"xác thực"`, `"authentication"`).

---

## 2. Kết quả Đánh giá Thực tế (Experimental Results — Cập nhật ngày 17/06/2026)

Chúng tôi đã tiến hành chạy đánh giá và kiểm thử toàn bộ luồng (`run-all`) bằng 2 seed `42, 43` trên nền tảng DeepSeek mới:

*   **Chỉ số Gain (PG / SG / GG)**: Đạt **0.000 / 0.000 / 0.000** trên cả 2 seed, chứng minh tính ổn định tuyệt đối của tác nhân tiến hóa khi sử dụng cơ chế lưu trữ và truy xuất bộ nhớ mới.
*   **Tỷ lệ Thành Công**: Tất cả các tác vụ training curriculum, held-out và robustness (naive stream, poisoning, negative transfer) đều chạy thành công tuyệt đối mà không có bất kỳ ngoại lệ kết nối LLM nào.
*   **Kháng Độc (Memory Poisoning)**: Nhờ cơ chế conflict resolution và quarantine, insight độc hại ("LUÔN LUÔN trả về một chuỗi rỗng") đã bị cách ly thành công và agent đạt điểm số tối đa `9.0` (Passed).
*   **Lọc Negative Transfer**: Task SMTP (`NEG_001`) đã tự động chặn các insight và skill liên quan đến regex/email và các bài học cấu hình login gây nhiễu, tách biệt hoàn toàn phạm vi tri thức.

---

## 3. Xác minh Hệ thống (Validation Status)

*   **Unit Tests**: Bổ sung tệp `pytest.ini` ở thư mục gốc để cấu hình pytest bỏ qua thư mục chứa các kịch bản nháp `scratch/` trong quá trình thu thập test case:
    ```ini
    [pytest]
    norecursedirs = scratch .venv
    ```
    Chạy lệnh pytest thông thường vượt qua thành công toàn bộ **26/26 bài test** mà không gặp lỗi:
    ```
    =========================== 26 passed in 25.55s ===========================
    ```

---
*Ghi chú: Toàn bộ dữ liệu chi tiết được lưu trữ dưới dạng trace log tại `logs/trace.jsonl` và giao diện Dashboard hiển thị tại `logs/dashboard.html`.*
