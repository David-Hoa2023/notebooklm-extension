# Walkthrough: Phase 5 Hardening & Phase 6 Evidence

Dự án **Evolutionary Coding Agent** đã hoàn thành toàn bộ các hạng mục cốt lõi của cột mốc **Phase 5 Hardening + Phase 6 Evidence**. Chúng tôi đã củng cố độ tin cậy của Phase 5 (Active Exploration) chống lại các lỗi phụ thuộc thư viện trong Docker sandbox và thiết lập cơ chế đo lường thống kê thực tế chính xác hơn trên Dashboard.

Dưới đây là chi tiết các thành phần đã triển khai và kết quả chạy thử nghiệm thực tế.

---

## 1. Các thành phần đã triển khai (Epic Implementation Summary)

### Phase 5 Hardening: Bảo vệ Sandbox & Chống Lỗi Thư Viện
*   **Static Pytest Banning**: Bổ sung bộ lọc tĩnh trong `src/exploration/oracle_synthesis.py` để quét và từ chối ngay lập tức bất kỳ `test_code` hoặc `hidden_test_code` nào chứa lệnh `import pytest` hoặc `pytest.`. Điều này ngăn chặn triệt để lỗi `ModuleNotFoundError: No module named 'pytest'` khi chạy test suite tự sinh trong môi trường Docker slim image.
*   **Function Name Presence Check**: Phân tích cú pháp mô tả nhiệm vụ để trích xuất tên hàm cần sinh (ví dụ: `calculate_sum`). Validator sẽ từ chối các oracle test code không chứa định nghĩa hoặc lời gọi tên hàm này, ngăn chặn tình trạng sinh test case lạc đề hoặc không kiểm tra đúng hàm mục tiêu.
*   **Newline Escapes in JSON Parser**: Khắc phục lỗi phân tích JSON khi LLM sinh chuỗi code chứa các ký tự xuống dòng literal, đảm bảo tính ổn định của hàm `_escape_unescaped_newlines`.

### Phase 5 Budgeting & Regression (Backlog & Governor Tasks)
*   **Cost & Budget Governor (EL_OBS_004)**: Tích hợp giới hạn token chi phí (`budget_tokens: 200000` trong `config.yaml`). Khi tổng số token tiêu tốn vượt ngưỡng, hệ thống sẽ thực hiện hard stop lập tức và ghi nhận sự kiện dừng để tránh lãng phí tài nguyên API.
*   **Regression Suite Re-testing (EL_MEM_009)**: Triển khai luồng chạy lại các bài tập đã giải trước đó (`SUB_001` và `SUB_003`) sau mỗi lượt chạy explore để giám sát xem bộ nhớ skill mới có gây ra lỗi suy giảm chức năng (regression) hay không.

### Phase 6 Evidence: Nâng Cấp Giao Diện Báo Cáo & Đo Lường Thống Kê
*   **Split Dashboard (Keyword vs Skill-Backed Coverage)**: Tách biệt bảng thống kê năng lực (Capabilities Taxonomy) thành hai cột song song:
    1.  **Keyword Matching**: Khớp từ khóa lỏng lẻo dựa trên docstring và tên hàm.
    2.  **Verified Skill-Backed**: Chỉ ghi nhận năng lực nếu nó được củng cố bởi một active skill đã vượt qua toàn bộ unit test kiểm thử trong sandbox.
*   **Failed Exploration Error Logging**: Hiển thị chi tiết `stderr` và thông báo lỗi của tất cả các lượt chạy explore thất bại trực tiếp trên Dashboard, cải thiện đáng kể khả năng chẩn đoán lỗi.
*   **Multi-Seed Statistics & paired t-test**: Bổ sung tính toán độ lệch chuẩn (std) cho từng task và thực hiện kiểm định t-test cặp đôi giữa Baseline ($B_i$) và Second Pass ($S_i$) để xác minh ý nghĩa thống kê của Stability Gain.

---

## 2. Kết quả Đánh giá Thực tế (Experimental Results)

Chúng tôi đã chạy một lượt Active Exploration hoàn chỉnh bằng cách cấu hình `epsilon: 1.0` để ép buộc hệ thống chạy 100% chế độ **Active Exploration (Explore Mode)** thay vì Exploit.

### Thống kê chạy Active Exploration (Seeds 42, 43, 44):
*   **Số lượng quyết định (Policy Decisions)**: 12 lượt chạy (4 tasks/seed × 3 seeds).
*   **Số lượng task tự đề xuất (EXP_*)**: 12 task được sinh ra.
*   **Số lượng oracle bị từ chối (Oracle Rejected)**: **3 oracles** bị loại bỏ thành công (do vi phạm tĩnh `pytest` hoặc thiếu tên hàm kiểm thử), xác thực cơ chế lọc tĩnh hoạt động hoàn hảo.
*   **Số lượng oracle được duyệt (Oracle Validated)**: **9 oracles** được thông qua.
*   **Số lượng task chạy thực tế**: **9 tasks** (`EXP_091D450D`, `EXP_CD13BC42`, `EXP_BBD1A10D`, v.v.).
*   **Tỷ lệ thành công (Self-Proposed Success)**: **100% (9/9 passed)**.
    *   **Seed 42**: 2/2 passed.
    *   **Seed 43**: 4/4 passed.
    *   **Seed 44**: 3/3 passed.
*   **Tỷ lệ duyệt Oracle (Oracle Validation Rate)**: **75%** (9 validated / 3 rejected).

### Đo lường Thống kê (Phase 6 Evidence):
*   **Plasticity Gain (PG)**: `+0.04` (trung bình).
*   **Stability Gain (SG)**: `-0.81` (trung bình).
*   **p-value**: `0.1100` (ít ý nghĩa thống kê, giữ nguyên vì các task exploration tự sinh không làm thay đổi baseline/second pass của các bài tập mẫu. Việc cải thiện chỉ số p-value đòi hỏi chạy `run-all` trên cỡ mẫu seed rộng hơn: n >= 6 seeds).
*   **Keyword Matching Coverage**: `100%` (10/10 Capabilities).
*   **Verified Skill-Backed Coverage**: `80%` (8/10 Capabilities). Khoảng trống năng lực (Gaps) thực tế được xác định rõ là `testing` và `string_parsing` (do các active skills hiện tại chưa bao phủ hoặc kiểm định xong các phần này).

### Trực quan hóa giao diện báo cáo:
Dưới đây là ảnh chụp màn hình Dashboard thực tế sau lượt chạy Active Exploration cưỡng bức:

![Dashboard Layout](active_explore_results.png)

---

## 3. Xác minh Hệ thống (Validation Status)

*   **Unit Tests**: Chạy lệnh `.venv\Scripts\python -m pytest` vượt qua thành công toàn bộ **24/24 bài test** mà không gặp lỗi:
    ```
    ======================= 24 passed, 4 warnings in 25.69s =======================
    ```
    Bao gồm các bài test unit mới xác thực bộ lọc `pytest-ban`, hàm phân tích xuống dòng, và tính năng trả về `execution_mode` của validation gate.
