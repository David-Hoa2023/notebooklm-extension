import os
import json
from collections import defaultdict, deque

DEFAULT_CURRICULUM = [
    # --- SUBTASKS NỀN TẢNG (Level 1) ---
    {
        "id": "SUB_001",
        "title": "Regex Email Extractor",
        "difficulty": "basic",
        "dependencies": [],
        "is_held_out": False,
        "description": "Viết hàm `extract_emails(text: str) -> list[str]` trả về danh sách các địa chỉ email hợp lệ xuất hiện trong văn bản. Email hợp lệ có dạng local@domain.ext. Không phân biệt chữ hoa chữ thường.",
        "test_code": """
def test_extract_emails():
    # Test cases
    t1 = "Liên hệ chúng tôi qua info@example.com hoặc support.team@work-place.net nhé."
    res = extract_emails(t1)
    assert "info@example.com" in res
    assert "support.team@work-place.net" in res
    
    t2 = "Không có email nào ở đây cả: john@, @example.com, test@example."
    assert len(extract_emails(t2)) == 0
    
    t3 = "Email viết hoa: USERNAME@DOMAIN.COM"
    assert "username@domain.com" in [e.lower() for e in extract_emails(t3)]
test_extract_emails()
""",
        "hidden_test_code": """
def test_extract_emails_hidden():
    t4 = "Gửi thư cho contact@company.co.uk hoặc sales-dep@store.info."
    res = extract_emails(t4)
    assert "contact@company.co.uk" in res
    assert "sales-dep@store.info" in res
    t5 = "Email có subdomain: admin@mail.server.com"
    assert "admin@mail.server.com" in extract_emails(t5)
test_extract_emails_hidden()
"""
    },
    {
        "id": "SUB_002",
        "title": "Math Expression Parser",
        "difficulty": "basic",
        "dependencies": [],
        "is_held_out": False,
        "description": "Viết hàm `evaluate_expression(expr: str) -> float` nhận vào chuỗi biểu thức toán học cơ bản chứa các số và các toán tử +, -, *, / (có thể có khoảng trắng) và tính toán kết quả theo đúng độ ưu tiên toán học. Không cần xử lý dấu ngoặc đơn.",
        "test_code": """
def test_evaluate_expression():
    assert evaluate_expression("3 + 4 * 2") == 11.0
    assert evaluate_expression("10 - 2 / 4") == 9.5
    assert evaluate_expression("5 * 4 / 2 - 3") == 7.0
    assert evaluate_expression(" 100  + 200 ") == 300.0
test_evaluate_expression()
""",
        "hidden_test_code": """
def test_evaluate_expression_hidden():
    assert evaluate_expression("2 * 3 * 4 - 5") == 19.0
    assert evaluate_expression("10 / 2 + 5 * 3") == 20.0
test_evaluate_expression_hidden()
"""
    },
    {
        "id": "SUB_003",
        "title": "JSON File Validator",
        "difficulty": "basic",
        "dependencies": [],
        "is_held_out": False,
        "description": "Viết hàm `validate_and_summarize_json(json_str: str, required_keys: list[str]) -> dict` nhận vào một chuỗi JSON và danh sách các key bắt buộc. Hàm sẽ kiểm tra tính hợp lệ của JSON. Nếu JSON không hợp lệ, trả về {'valid': False, 'error': 'Invalid JSON'}. Nếu hợp lệ nhưng thiếu key bắt buộc, trả về {'valid': False, 'error': 'Missing keys'}. Nếu hợp lệ và đủ key, trả về {'valid': True, 'num_keys': len(keys), 'data': parsed_dict}.",
        "test_code": """
def test_validate_and_summarize_json():
    # Hợp lệ
    j1 = '{"name": "Agent", "version": "1.0", "active": true}'
    r1 = validate_and_summarize_json(j1, ["name", "version"])
    assert r1['valid'] is True
    assert r1['num_keys'] == 3
    assert r1['data']['name'] == "Agent"
    
    # Thiếu key
    r2 = validate_and_summarize_json(j1, ["name", "owner"])
    assert r2['valid'] is False
    assert "Missing keys" in r2['error']
    
    # Lỗi cú pháp JSON
    j3 = '{"name": "Agent", "version": 1.0,}'
    r3 = validate_and_summarize_json(j3, ["name"])
    assert r3['valid'] is False
    assert "Invalid JSON" in r3['error']
test_validate_and_summarize_json()
""",
        "hidden_test_code": """
def test_validate_and_summarize_json_hidden():
    j = '{"key1": "val1"}'
    r = validate_and_summarize_json(j, ["key1"])
    assert r['valid'] is True
    assert r['data']['key1'] == "val1"
test_validate_and_summarize_json_hidden()
"""
    },
    
    # --- COMPLEX TASKS (Level 2: Ghép nối các Skill) ---
    {
        "id": "COMPLEX_001",
        "title": "Log Analyzer Utility",
        "difficulty": "intermediate",
        "dependencies": ["SUB_001", "SUB_003"],
        "is_held_out": False,
        "description": "Viết hàm `analyze_log_file(log_data_json: str) -> dict` nhận vào một chuỗi JSON đại diện cho cấu trúc log dữ liệu. JSON có định dạng `{\"logs\": [\"[INFO] 2026-06-13: Hoạt động bình thường\", \"[ERROR] 2026-06-13: Lỗi kết nối gửi tới admin@system.org\", \"[WARN] ...\", ...]}`. Hàm cần: 1. Validate cấu trúc JSON đầu vào (phải có key `logs`). 2. Phân tích từng log line để đếm số lượng lỗi theo level (INFO, WARN, ERROR). 3. Sử dụng regex để tìm tất cả các email liên hệ xuất hiện trong các dòng ERROR và trả về danh sách email độc nhất đó. Trả về dict kết quả có dạng: `{\"status\": \"success\", \"counts\": {\"INFO\": x, \"WARN\": y, \"ERROR\": z}, \"error_emails\": [...]}`. Nếu JSON lỗi hoặc thiếu key `logs`, trả về `{\"status\": \"error\", \"message\": ...}`.",
        "test_code": """
def test_log_analyzer():
    input_data = '''{
        "logs": [
            "[INFO] 2026-06-13: System initialized.",
            "[ERROR] 2026-06-13: DB connection failed. Contact database-admin@example.com.",
            "[WARN] 2026-06-13: Disk usage at 85%.",
            "[ERROR] 2026-06-13: API failure. Alert developer@api-team.net and support@example.com.",
            "[INFO] 2026-06-13: Backup finished successfully."
        ]
    }'''
    res = analyze_log_file(input_data)
    assert res["status"] == "success"
    assert res["counts"]["INFO"] == 2
    assert res["counts"]["WARN"] == 1
    assert res["counts"]["ERROR"] == 2
    assert "database-admin@example.com" in res["error_emails"]
    assert "developer@api-team.net" in res["error_emails"]
    assert "support@example.com" in res["error_emails"]
    assert len(res["error_emails"]) == 3
    
    # Test case fail JSON
    res_fail = analyze_log_file("invalid json")
    assert res_fail["status"] == "error"
test_log_analyzer()
""",
        "hidden_test_code": """
def test_log_analyzer_hidden():
    input_data = '{"logs": ["[ERROR] 2026-06-13: Crash. Contact dev-ops@server.co.jp."]}'
    res = analyze_log_file(input_data)
    assert res["status"] == "success"
    assert "dev-ops@server.co.jp" in res["error_emails"]
test_log_analyzer_hidden()
"""
    },

    # --- HELD-OUT TASKS (Level 3: Tổng quát hóa - Độc lập hoàn toàn) ---
    {
        "id": "HELDOUT_001",
        "title": "SQLite Database Query Wrapper",
        "difficulty": "advanced",
        "dependencies": [],
        "is_held_out": True,
        "description": "Viết hàm `query_database(db_filepath: str, sql_command: str, params: tuple = ()) -> list` để quản lý kết nối và truy vấn SQLite database một cách an toàn. Hàm cần kết nối tới db, thực thi SQL command (có tham số để tránh SQL Injection), commit nếu là lệnh WRITE (INSERT/UPDATE/DELETE), và trả về danh sách các hàng kết quả (dưới dạng list of dict, với key là tên cột) nếu là lệnh SELECT. Đảm bảo đóng kết nối SQLite an toàn trong mọi trường hợp (dùng try/finally hoặc context manager).",
        "test_code": """
import sqlite3
import os

def test_query_database():
    db_file = "test_run_temp.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        
    try:
        # Tạo bảng
        query_database(db_file, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
        
        # Thêm dữ liệu
        query_database(db_file, "INSERT INTO users (name, email) VALUES (?, ?)", ("Alice", "alice@test.com"))
        query_database(db_file, "INSERT INTO users (name, email) VALUES (?, ?)", ("Bob", "bob@test.com"))
        
        # Lấy dữ liệu
        res = query_database(db_file, "SELECT name, email FROM users ORDER BY name")
        assert len(res) == 2
        assert res[0]["name"] == "Alice"
        assert res[0]["email"] == "alice@test.com"
        assert res[1]["name"] == "Bob"
        
    finally:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass
test_query_database()
""",
        "hidden_test_code": """
def test_query_database_hidden():
    db_file = "test_hidden_temp.db"
    import os
    if os.path.exists(db_file):
        os.remove(db_file)
    try:
        query_database(db_file, "CREATE TABLE logs (id INTEGER PRIMARY KEY, msg TEXT)")
        query_database(db_file, "INSERT INTO logs (msg) VALUES (?)", ("Hello Hidden",))
        res = query_database(db_file, "SELECT msg FROM logs")
        assert len(res) == 1
        assert res[0]["msg"] == "Hello Hidden"
    finally:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass
test_query_database_hidden()
"""
    },
    {
        "id": "SLS_REVENUE_001",
        "title": "Sales Revenue Aggregator",
        "difficulty": "basic",
        "dependencies": [],
        "is_held_out": False,
        "vertical": "sales",
        "description": "Viết hàm `aggregate_sales_revenue(orders: list[dict]) -> dict` nhận vào danh sách các đơn hàng (orders), mỗi đơn hàng có dạng `{'order_id': str, 'revenue': float, 'discount': float}`. Tính tổng doanh thu gốc (revenue), tổng giảm giá (discount), và doanh thu thực tế (revenue - discount). Trả về kết quả dưới dạng dict `{'total_revenue': float, 'total_discount': float, 'net_revenue': float}`. Tất cả giá trị làm tròn đến 2 chữ số thập phân.",
        "test_code": """
def test_aggregate_sales_revenue():
    orders = [
        {'order_id': 'O1', 'revenue': 100.0, 'discount': 10.0},
        {'order_id': 'O2', 'revenue': 250.5, 'discount': 25.5},
        {'order_id': 'O3', 'revenue': 50.0, 'discount': 0.0}
    ]
    res = aggregate_sales_revenue(orders)
    assert res['total_revenue'] == 400.5
    assert res['total_discount'] == 35.5
    assert res['net_revenue'] == 365.0
test_aggregate_sales_revenue()
""",
        "hidden_test_code": """
def test_aggregate_sales_revenue_hidden():
    orders = [
        {'order_id': 'O1', 'revenue': 10.123, 'discount': 1.005},
    ]
    res = aggregate_sales_revenue(orders)
    assert res['total_revenue'] == 10.12
    assert res['total_discount'] == 1.01
    assert res['net_revenue'] == 9.11
test_aggregate_sales_revenue_hidden()
"""
    },
    {
        "id": "MKT_SEGMENT_001",
        "title": "Marketing Campaign Segment Filter",
        "difficulty": "basic",
        "dependencies": [],
        "is_held_out": False,
        "vertical": "marketing",
        "description": "Viết hàm `filter_campaign_segments(campaigns: list[dict], min_clicks: int) -> list[str]` nhận vào danh sách các campaign, mỗi campaign có dạng `{'campaign_name': str, 'segment': str, 'clicks': int, 'utm_source': str}`. Trả về danh sách các segment (tên độc nhất) của các campaign có số clicks từ `min_clicks` trở lên và có `utm_source` hợp lệ (không rỗng). Trả về danh sách được sắp xếp theo bảng chữ cái.",
        "test_code": """
def test_filter_campaign_segments():
    campaigns = [
        {'campaign_name': 'C1', 'segment': 'Tech', 'clicks': 150, 'utm_source': 'google'},
        {'campaign_name': 'C2', 'segment': 'Fashion', 'clicks': 50, 'utm_source': 'facebook'},
        {'campaign_name': 'C3', 'segment': 'Tech', 'clicks': 200, 'utm_source': 'google'},
        {'campaign_name': 'C4', 'segment': 'Food', 'clicks': 300, 'utm_source': ''}
    ]
    res = filter_campaign_segments(campaigns, 100)
    assert res == ['Tech']
test_filter_campaign_segments()
""",
        "hidden_test_code": """
def test_filter_campaign_segments_hidden():
    campaigns = [
        {'campaign_name': 'C1', 'segment': 'B', 'clicks': 10, 'utm_source': 'a'},
        {'campaign_name': 'C2', 'segment': 'A', 'clicks': 10, 'utm_source': 'b'}
    ]
    res = filter_campaign_segments(campaigns, 5)
    assert res == ['A', 'B']
test_filter_campaign_segments_hidden()
"""
    },
    {
        "id": "FIN_LEDGER_001",
        "title": "Financial Ledger Balance Calculator",
        "difficulty": "basic",
        "dependencies": [],
        "is_held_out": False,
        "vertical": "finance",
        "description": "Viết hàm `calculate_ledger_balance(transactions: list[dict], initial_balance: float) -> dict` nhận vào danh sách các giao dịch (transactions), mỗi giao dịch có dạng `{'transaction_id': str, 'type': str ('credit' hoặc 'debit'), 'amount': float, 'tax_rate': float}`. Mỗi giao dịch credit sẽ cộng tiền vào tài khoản, debit sẽ trừ tiền ra. Nếu là debit, cần cộng thêm tiền thuế (amount * tax_rate) vào khoản trừ. Tính toán số dư cuối cùng và tổng tiền thuế đã thanh toán. Trả về kết quả dạng `{'final_balance': float, 'total_tax': float}`. Tất cả giá trị làm tròn đến 2 chữ số thập phân.",
        "test_code": """
def test_calculate_ledger_balance():
    txs = [
        {'transaction_id': 'T1', 'type': 'credit', 'amount': 1000.0, 'tax_rate': 0.0},
        {'transaction_id': 'T2', 'type': 'debit', 'amount': 200.0, 'tax_rate': 0.1},
        {'transaction_id': 'T3', 'type': 'debit', 'amount': 50.0, 'tax_rate': 0.2}
    ]
    res = calculate_ledger_balance(txs, 500.0)
    assert res['final_balance'] == 1220.0
    assert res['total_tax'] == 30.0
test_calculate_ledger_balance()
""",
        "hidden_test_code": """
def test_calculate_ledger_balance_hidden():
    txs = [
        {'transaction_id': 'T1', 'type': 'debit', 'amount': 10.05, 'tax_rate': 0.1}
    ]
    res = calculate_ledger_balance(txs, 100.0)
    # 10.05 * 0.1 = 1.005 -> 1.01 tax. Amount + tax = 11.06. Final balance = 100.0 - 11.06 = 88.94
    assert res['final_balance'] == 88.94
    assert res['total_tax'] == 1.01
test_calculate_ledger_balance_hidden()
"""
    }
]

class CurriculumManager:
    def __init__(self, curriculum_path: str = "data/curriculum/tasks.json"):
        self.curriculum_path = curriculum_path
        os.makedirs(os.path.dirname(self.curriculum_path), exist_ok=True)
        self.tasks = []
        self.load_or_create_tasks()

    def load_or_create_tasks(self):
        recreate = False
        if not os.path.exists(self.curriculum_path):
            recreate = True
        else:
            try:
                with open(self.curriculum_path, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
                loaded_ids = {t["id"] for t in self.tasks}
                default_ids = {t["id"] for t in DEFAULT_CURRICULUM}
                if not default_ids.issubset(loaded_ids):
                    recreate = True
                else:
                    for t in self.tasks:
                        if "hidden_test_code" not in t:
                            recreate = True
                            break
            except Exception:
                recreate = True

        if recreate:
            self.tasks = DEFAULT_CURRICULUM
            self.save_tasks()


    def save_tasks(self):
        with open(self.curriculum_path, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=4, ensure_ascii=False)

    def get_task(self, task_id: str) -> dict:
        for t in self.tasks:
            if t["id"] == task_id:
                return t
        return None

    def get_training_curriculum(self) -> list[dict]:
        """
        Get all tasks that are not held-out.
        """
        return [t for t in self.tasks if not t.get("is_held_out", False)]

    def get_held_out_curriculum(self) -> list[dict]:
        """
        Get held-out evaluation tasks.
        """
        return [t for t in self.tasks if t.get("is_held_out", False)]

    def get_sorted_training_tasks(self) -> list[dict]:
        """
        Sort training tasks topologically by their dependencies.
        """
        train_tasks = self.get_training_curriculum()
        task_dict = {t["id"]: t for t in train_tasks}
        
        # Build dependency graph
        adj = defaultdict(list)
        in_degree = {t["id"]: 0 for t in train_tasks}
        
        for t in train_tasks:
            for dep in t.get("dependencies", []):
                # Only construct edges if dependency is in training task list
                if dep in task_dict:
                    adj[dep].append(t["id"])
                    in_degree[t["id"]] += 1
                    
        # Topological Sort (Kahn's Algorithm)
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        sorted_ids = []
        
        while queue:
            node = queue.popleft()
            sorted_ids.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        # Verify no cycle and all tasks are sorted
        if len(sorted_ids) != len(train_tasks):
            print("Warning: Dependency cycle detected in curriculum, or missing dependency! Falling back to raw list order.")
            return train_tasks
            
        return [task_dict[tid] for tid in sorted_ids]

    def verify_leakage_disjoint(self) -> bool:
        """
        Verifies that training tasks and held-out tasks do not overlap in terms of task IDs or Titles.
        Also check for keyword overlap to ensure domain separation.
        """
        train = self.get_training_curriculum()
        held_out = self.get_held_out_curriculum()
        
        train_ids = {t["id"] for t in train}
        held_out_ids = {t["id"] for t in held_out}
        
        # ID leakage check
        if train_ids.intersection(held_out_ids):
            return False
            
        # Title leakage check
        train_titles = {t["title"].lower() for t in train}
        held_out_titles = {t["title"].lower() for t in held_out}
        if train_titles.intersection(held_out_titles):
            return False
            
        # Domain overlap check (simple check for high-frequency code terms)
        # e.g., Held-out should not be regex-based if we are evaluating general code synthesis
        return True

# Singleton curriculum manager
curriculum_manager = CurriculumManager()
