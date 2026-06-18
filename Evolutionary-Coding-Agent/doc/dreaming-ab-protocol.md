# Protocol A/B: Offline Dreaming vs Memoryless Baseline

Nghị định thư đánh giá ảnh hưởng của Offline Dreaming đối với chất lượng mô hình (Plasticity/Stability/Generalization Gain) và khả năng xử lý biên (NEG_001).

## 1. Mục tiêu & Giả thuyết
- **H1 (Plasticity & Stability)**: Bật dreaming (`dreaming.enabled: true`) giúp duy trì hoặc tăng điểm số của các bài tập huấn luyện (training tasks) và kiểm thử (held-out tasks) ở mức 9.0 mà không bị suy giảm (stability).
- **H2 (Negative Cases)**: Các bài học biên từ `NEG_001` (ví dụ như SMTP mock rules) được chắt lọc thành công và áp dụng đúng phạm vi (`scope: task` hoặc `domain: smtp`) mà không gây nhiễu chéo sang các bài tập SMTP/regex khác (robustness).

## 2. Kịch bản Đánh giá (A/B Test)

### Bước 1: Thiết lập Baseline (Dreaming Off)
Chạy 2-seed (`42`, `43`) toàn bộ các task huấn luyện và kiểm thử mà không bật Dreaming.

1. Đảm bảo cấu hình trong `config.yaml` tắt dreaming:
   ```yaml
   dreaming:
     enabled: false
   ```
2. Reset cơ sở dữ liệu bộ nhớ để chạy sạch:
   ```powershell
   Remove-Item data/memory/memory.db -ErrorAction SilentlyContinue
   ```
3. Thực thi `run-all` với seeds 42,43:
   ```powershell
   $env:DEEPSEEK_API_KEY="your-key-here"; $env:PYTHONPATH="."; .venv\Scripts\python run.py run-all --seeds 42,43
   ```
4. Lưu trữ kết quả:
   - File logs: `logs/trace.jsonl`
   - File dashboard: `logs/dashboard.html`

### Bước 2: Chắt lọc bài học Offline (Dreaming)
Tạo bài học tổng hợp (Dream) từ vết thực thi ở Bước 1.

1. Chạy lệnh chưng cất offline từ trace file:
   ```powershell
   $env:DEEPSEEK_API_KEY="your-key-here"; $env:PYTHONPATH="."; .venv\Scripts\python run.py dream --trace logs/trace.jsonl --session-id run_all_baseline_seeds42_43
   ```
2. Xác nhận file bài học được tạo trong `data/memory/dreams/` (file JSON và link `latest.json`).
3. Kiểm tra bài học được ghi nhận vào bảng SQLite `dream` qua script kiểm định:
   ```powershell
   $env:PYTHONPATH="."; .venv\Scripts\python scratch/verify_dream_session.py
   ```

### Bước 3: Đánh giá Dreaming On (Dreaming Active)
Đánh giá hiệu suất học của tác nhân khi nạp các bài học chắt lọc từ phiên trước vào pha `first_pass` và `explore`.

1. Cập nhật `config.yaml` bật dreaming:
   ```yaml
   dreaming:
     enabled: true
   ```
2. Thực thi lại `run-all` với seeds 42,43:
   ```powershell
   $env:DEEPSEEK_API_KEY="your-key-here"; $env:PYTHONPATH="."; .venv\Scripts\python run.py run-all --seeds 42,43
   ```
3. Phân tích kết quả:
   - Đối chiếu chỉ số PG / SG / GG trên Dashboard (`logs/dashboard.html`).
   - Đảm bảo `NEG_001` (nếu chạy) đạt điểm tối đa nhờ bài học biên được nạp chính xác.

## 3. Báo cáo & So sánh Chỉ số
Mẫu so sánh ghi chép vào `memory.md`:

| Metric | Baseline (Dreaming Off) | Dreaming On (A/B Test) | Nhận xét |
| :--- | :--- | :--- | :--- |
| **Training Task Score** | 9.0 | 9.0 | Ổn định tại trần điểm |
| **Held-out Task Score** | 9.0 | 9.0 | Generalization vững chãi |
| **NEG_001 Score** | N/A / Passed | Passed | Xử lý SMTP mock tốt |
| **Plasticity Gain (PG)** | 0.000 | 0.000 | Không bị thụt lùi điểm số |
| **Stability Gain (SG)** | 0.000 | 0.000 | Kháng nhiễu tốt |
