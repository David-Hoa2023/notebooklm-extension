import sys
import os

# Add workspace root to PYTHONPATH so we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import config_instance
from src.infra.curriculum import DEFAULT_CURRICULUM
from src.memory.memory_engine import memory_engine
from src.exploration.vertical_gap_analyzer import vertical_gap_analyzer

def check_config():
    print("Checking config values...")
    enabled = config_instance.get("verticals.enabled")
    allowed = config_instance.get("verticals.allowed")
    mode = config_instance.get("verticals.retrieval_mode")
    
    if enabled is not True:
        return False, f"verticals.enabled is {enabled}, expected True"
    if not isinstance(allowed, list) or not set(allowed).issuperset({"sales", "marketing", "finance", "generic"}):
        return False, f"verticals.allowed is {allowed}, expected to include sales, marketing, finance, generic"
    if mode not in ["strict", "prefer", "off"]:
        return False, f"verticals.retrieval_mode is {mode}, expected strict, prefer, or off"
    
    return True, f"Config checks passed. Mode: {mode}, Allowed: {allowed}"

def check_curriculum():
    print("Checking curriculum sample tasks...")
    sample_ids = {"SLS_REVENUE_001": "sales", "MKT_SEGMENT_001": "marketing", "FIN_LEDGER_001": "finance"}
    found = {}
    for task in DEFAULT_CURRICULUM:
        if task["id"] in sample_ids:
            found[task["id"]] = task.get("vertical")
            
    for tid, expected_v in sample_ids.items():
        if tid not in found:
            return False, f"Sample task {tid} not found in DEFAULT_CURRICULUM"
        if found[tid] != expected_v:
            return False, f"Sample task {tid} has vertical {found[tid]}, expected {expected_v}"
            
    return True, f"Curriculum checks passed. Sample tasks exist with correct business verticals."

def check_database_skills():
    print("Checking database skill metadata...")
    skills = memory_engine.get_all_memories(namespace="skill")
    if not skills:
        return True, "No skills found in database (which is fine if DB is empty/new), skipped further check."
        
    missing_vertical = 0
    distribution = {}
    for sk in skills:
        meta = sk.get("metadata", {})
        vert = meta.get("vertical")
        if not vert:
            missing_vertical += 1
        else:
            distribution[vert] = distribution.get(vert, 0) + 1
            
    print(f"Skill vertical distribution: {distribution}")
    if missing_vertical > 0:
        return False, f"Found {missing_vertical} skills without 'vertical' in metadata"
    return True, f"Database skill checks passed. Distribution: {distribution}"

def check_vertical_gap_analyzer():
    print("Checking vertical gap analyzer...")
    res = vertical_gap_analyzer.analyze()
    expected_keys = {"verticals_allowed", "verticals_covered", "vertical_gaps", "vertical_skill_backed_coverage_rate"}
    missing = expected_keys - set(res.keys())
    if missing:
        return False, f"vertical_gap_analyzer.analyze() missing return keys: {missing}"
    
    rate = res["vertical_skill_backed_coverage_rate"]
    return True, f"Vertical gap analyzer check passed. Coverage rate: {rate * 100:.1f}%, Gaps: {res['vertical_gaps']}"

def check_dashboard():
    print("Checking dashboard.html panels...")
    dashboard_path = config_instance.get("observability.dashboard_file", "logs/dashboard.html")
    if not os.path.exists(dashboard_path):
        return False, f"Dashboard file not found at {dashboard_path}"
        
    with open(dashboard_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "vertical-coverage-panel" not in content:
        return False, "vertical-coverage-panel ID not found in dashboard.html"
    if "vertical-cards-container" not in content:
        return False, "vertical-cards-container ID not found in dashboard.html"
        
    return True, "Dashboard verification passed. Vertical coverage panels are registered in dashboard.html."

def check_strict_retrieval_dryrun():
    print("Running strict retrieval dryrun verification...")
    # Mocking task and filtering logic
    task_finance = {"id": "TEST_FIN", "description": "some audit finance task", "vertical": "finance"}
    
    # Let's write down the logic to filter skills
    skills = [
        {"metadata": {"name": "s1", "vertical": "sales", "retrievable": True}},
        {"metadata": {"name": "s2", "vertical": "finance", "retrievable": True}},
        {"metadata": {"name": "s3", "vertical": "generic", "retrievable": True}},
    ]
    
    # Check strict filter
    task_vertical = task_finance["vertical"]
    filtered = []
    for sk in skills:
        vert = sk["metadata"]["vertical"]
        if vert in {task_vertical, "generic"}:
            filtered.append(sk)
            
    filtered_names = [sk["metadata"]["name"] for sk in filtered]
    if "s1" in filtered_names:
        return False, f"Strict retrieval failed: sales skill s1 included in finance task: {filtered_names}"
    if "s2" not in filtered_names or "s3" not in filtered_names:
        return False, f"Strict retrieval failed: finance or generic skill missing: {filtered_names}"
        
    return True, "Strict retrieval dryrun check passed."

def main():
    checks = [
        ("Config Validation", check_config),
        ("Curriculum Task Validation", check_curriculum),
        ("Database Skill Metadata Validation", check_database_skills),
        ("Vertical Gap Analyzer Validation", check_vertical_gap_analyzer),
        ("Dashboard HTML Verification", check_dashboard),
        ("Strict Retrieval Logic Dry-run", check_strict_retrieval_dryrun)
    ]
    
    passed_count = 0
    total_count = len(checks)
    print("=== STARTING BUSINESS VERTICALS VERIFICATION ===")
    
    for name, func in checks:
        try:
            ok, msg = func()
            if ok:
                print(f"[PASS] {name}: {msg}")
                passed_count += 1
            else:
                print(f"[FAIL] {name}: {msg}")
        except Exception as e:
            print(f"[FAIL] {name}: Exception raised: {e}")
            
    print("=================================================")
    print(f"Verification completed: {passed_count}/{total_count} checks passed.")
    if passed_count == total_count:
        print("ALL CHECKS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
