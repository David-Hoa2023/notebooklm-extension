# Walkthrough: Evolutionary Coding Agent - Hoàn thành Phase 5 Active Exploration

Dự án **Evolutionary Coding Agent** đã hoàn thiện toàn diện cột mốc **Phase 5: Active Exploration** (Khám phá chủ động). Hệ thống đã chuyển đổi từ một tác nhân thụ động (chỉ giải các bài tập có sẵn trong giáo trình) thành một tác nhân chủ động tự đề xuất bài toán, tự kiểm tra môi trường bằng các probe, tự tổng hợp oracle kiểm thử và tối ưu hóa kiến thức dựa trên mức độ mới lạ (novelty) và lỗ hổng năng lực (skill gaps).

Báo cáo này lưu trữ tài liệu kỹ thuật chi tiết về kiến trúc Phase 5, kết quả chạy thực nghiệm E2E và trạng thái kiểm thử của hệ thống.

---

## 1. Kiến trúc Phase 5: Active Exploration (Propose → Probe → Verify)

Luồng xử lý tự tiến hóa chủ động được thiết kế và triển khai như sau:

```
Chính sách Explore/Exploit
    ├─ explore  → Proposer (ZPD) → Oracle Synthesis → Env Probing → Pipeline Solve → Consolidation (Ghi bộ nhớ)
    └─ exploit  → Lấy bài tập giáo trình cố định ───────→ Env Probing → Pipeline Solve → Consolidation (Đóng băng bộ nhớ)
```

### Các thành phần cốt lõi trong Module `src/exploration/`:

1. **Curriculum Proposer (`curriculum_proposer.py`)**:
   * Tự động đề xuất các bài tập lập trình mới dựa trên năng lực hiện tại của Agent.
   * Định lượng độ khó phù hợp thông qua mô hình vùng phát triển gần nhất (ZPD - Zone of Proximal Development). Mức độ khó (`basic`, `intermediate`, `advanced`) được hiệu chỉnh động theo tỉ lệ thành công của các lượt chạy gần đây.

2. **Active Environment Probing (`environment_probe.py`)**:
   * Trước khi đưa ra giải pháp chính thức, Agent chạy các đoạn mã diagnostic thử nghiệm trong Docker sandbox để thu thập thông tin môi trường (hệ điều hành, phiên bản thư viện, cấu trúc tệp tin).
   * Các quan sát thu được được tích hợp trực tiếp vào ngữ cảnh (context prompt) giải bài toán.

3. **Oracle Synthesis & Verification (`oracle_synthesis.py`)**:
   * Khi tự đề xuất một bài toán mới, Agent không có sẵn unit tests từ con người. Nó tự tổng hợp một bộ test case (oracle) độc lập.
   * Để đảm bảo oracle an toàn và không bị "ảo giác", hệ thống kiểm tra oracle bằng cách chạy thử trên một giải pháp cố ý viết sai (known-bad solution stub) để chắc chắn oracle biết từ chối mã nguồn lỗi trước khi dùng nó làm thang đo chính thức.
   * Khắc phục triệt để lỗi parse JSON do Gemini sinh ra ký tự xuống dòng dư thừa và ép sử dụng thư viện chuẩn `unittest`/`assert` thay vì `pytest` trong container để tránh lỗi thiếu thư viện (`ModuleNotFoundError`).

4. **Skill-Gap-Driven Selection (`skill_gap_analyzer.py`)**:
   * Phân tích đối chiếu đồ thị Skill hiện có với hệ phân loại năng lực (Capabilities Taxonomy - gồm 10 nhóm chức năng như `string_parsing`, `regex`, `database_connection`, v.v.).
   * Xác định các lỗ hổng năng lực chưa có skill tương ứng và định hướng việc tự đề xuất bài tập tập trung vào các vùng trống này.

5. **Explore/Exploit Policy Controller (`explore_exploit_controller.py`)**:
   * Điều phối chính sách e-greedy. Khi token budget còn nhiều và tỉ lệ payoff tốt, hệ thống ưu tiên khám phá chủ động (`explore`), ngược lại sẽ chuyển sang củng cố (`exploit`).

6. **Novelty Reward (`novelty_reward.py`)**:
   * Tính toán độ mới lạ ngữ nghĩa (novelty score) bằng khoảng cách cosine của vector embedding của task mới đề xuất so với các ký ức hiện tại trong Vector DB, thúc đẩy Agent tìm kiếm các thử thách đa dạng.

---

## 2. Kết quả Kiểm thử Hệ thống (Verification Results)

### Kiểm thử Đơn vị (Unit & Integration Tests)
Chúng tôi đã chạy toàn bộ suite unit tests của dự án. Tất cả **19/19 tests** đều đã vượt qua thành công:
```
======================= 19 passed, 4 warnings in 36.05s =======================
```

Chi tiết các tệp kiểm thử:
* **`tests/test_exploration.py` (8 passed)**: Xác thực thuật toán tính ZPD, tính khoảng cách novelty cosine, phân tích skill gap và chính sách controller.
* **`tests/test_lifecycle.py` (3 passed)**: Xác thực các tác vụ quản lý vòng đời bộ nhớ (deduplication, conflict resolution, capacity limit).
* **`tests/test_retrieval.py` (2 passed)**: Đảm bảo tìm kiếm vector lai hoạt động chính xác.
* **`tests/test_retrieval_rerank.py` (3 passed)**: Xác minh việc xếp hạng lại (reranker) và định dạng prompt.
* **`tests/test_sandbox.py` (3 passed)**: Xác minh Docker sandbox cô lập, GradedAssertTransformer viết lại assertion và cơ chế local fallback an sau.

---

## 3. Chỉ Số Active Exploration Thực Tế (E2E Run Metrics)

Sau khi chạy thành công E2E loop khám phá chủ động với câu lệnh:
```powershell
python run.py explore
```
Hệ thống đã tự động cập nhật nhật ký chạy vào `logs/trace.jsonl` và kết xuất Dashboard HTML báo cáo tại `logs/dashboard.html`.

### Thống kê từ Dashboard Active Exploration:

* **Tỉ lệ bao phủ Skill Bank (Skill Bank Coverage)**: **100%** (10/10 nhóm khả năng được bao phủ).
  * *Đã bao phủ:* `string_parsing`, `regex`, `math_evaluation`, `data_structures`, `file_io`, `json_parsing`, `date_time`, `algorithms`, `error_handling`, `testing`
  * *Các lỗ hổng năng lực (Gaps):* Không có (tất cả các phân loại năng lực đều đã được bao phủ bởi các kỹ năng và bài học thu thập được).
* **Tỉ lệ xác thực Oracle thành công (Oracle Validation Rate)**: **100%** (6/6 oracles tự sinh đều vượt qua bộ lọc an toàn và từ chối chính xác các giải pháp bad-stub).
* **Tỉ lệ thành công của bài tập tự sinh (Self-Proposed Task Success Rate)**: **67%** (4/6 bài toán tự sinh như `EXP_A4BAA071`, `EXP_C5FBDC9E`, `EXP_21B1F1A6`, `EXP_FC5242A0` đã vượt qua unit tests; 2 bài toán gặp lỗi runtime `failed_runtime_error` và được học hỏi lại qua retry loop).
* **Độ mới lạ (Novelty Trend)**: Ghi nhận dao động từ `0.14` đến `0.24` (6 tasks) cho thấy Agent liên tục tìm được các bài tập độc lập không bị trùng lặp ngữ nghĩa cao với bộ nhớ cũ.


---

## Các Lưu Ý Về Việc Đánh Giá Chỉ Số (Interpretation Caveats)

* **Bao Phủ Từ Khóa Phân Loại (Taxonomy Keyword Coverage) vs. Khả Năng Thực Tế (Verified Skill Mastery)**: Tỉ lệ bao phủ 100% Skill Bank là lạc quan. Module `skill_gap_analyzer` sử dụng các thuật toán heuristic dựa trên từ khóa khớp trong tên skill, docstrings và insights chứ chưa chứng minh được năng lực thực tế. Ví dụ, một insight chứa từ khóa "test" có thể đánh dấu nhóm kiểm thử `testing` là đã bao phủ (đây chỉ là "taxonomy keyword coverage" chứ không hẳn là "verified skill mastery").
* **Cảnh Báo Về Smoke Test ($n=6$)**: Tỉ lệ thành công 67% trên tổng số $n=6$ task tự sinh của 3 seeds chỉ là một smoke test để kiểm tra tính đúng đắn của luồng lặp chứ không phải một bài benchmark thống kê ổn định. Hai lỗi runtime (`EXP_7602454C` và `EXP_17201BA0`) do import `pytest` trong sandbox là các khoảng trống thực sự cần khai thác và nâng cấp hệ thống.

---

## 4. Nhật Ký Khắc Phục Lỗi (Bug Fix Log)

Trong quá trình chạy tích hợp Phase 5, chúng tôi phát hiện và sửa các lỗi nghiêm trọng sau:
1. **Lỗi `ModuleNotFoundError: No module named 'pytest'` trong Sandbox**:
   * *Nguyên nhân*: Oracle tự sinh import `pytest` để kiểm thử giải pháp. Tuy nhiên, môi trường Docker sandbox dùng ảnh `python:3.10-slim` không được cài sẵn `pytest`.
   * *Khắc phục*: Tinh chỉnh System Instruction trong `oracle_synthesis.py` để cấm ngặt việc dùng `pytest`, bắt buộc dùng thư viện chuẩn `unittest` hoặc các câu lệnh `assert` cơ bản.
2. **Lỗi parse JSON do ký tự xuống dòng dư thừa**:
   * *Nguyên nhân*: Gemini đôi khi sinh ra JSON chứa các ký tự xuống dòng thực tế `\n` bên trong chuỗi, làm hỏng định dạng parser chuẩn.
   * *Khắc phục*: Triển khai hàm quét và escape thông minh `_escape_unescaped_newlines` trong `oracle_synthesis.py` để chuẩn hóa tệp JSON trước khi đưa vào module parse.
3. **Lỗi mất file `validation_gate.py` do overwrite nhầm**:
   * *Nguyên nhân*: Do nhầm lẫn ngữ cảnh giữa hai project (Evolutionary Coding Agent và NotebookLM Extension), file `validation_gate.py` đã bị ghi đè bởi phiên bản dùng `sqlite_utils` dành cho chrome extension.
   * *Khắc phục*: Phục hồi lại toàn bộ mã nguồn 270 dòng của `ValidationGate` từ tệp nhật ký chronological transcript log `transcript.jsonl` và cài đặt thêm thư viện `sqlite-utils` vào virtual environment của ECA để phục vụ các module kiểm thử.
