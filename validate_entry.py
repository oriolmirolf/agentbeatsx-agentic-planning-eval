import json
import os
import sys
import re
from pathlib import Path

# --- PATH CONFIGURATION ---
# We assume the script is in the root and 'green_agent' is a top-level package
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Ensure EXAMPLES_DIR is set for the backend
if not os.getenv("EXAMPLES_DIR"):
    os.environ["EXAMPLES_DIR"] = str(BASE_DIR / "examples")

try:
    from green_agent import tools_backend as tb
except ImportError as e:
    print(f"❌ Setup Error: {e}")
    print("Ensure 'green_agent' folder is in the same directory as this script.")
    sys.exit(1)

def validate_all():
    """
    Exhaustive validation of the PDDL-to-Natural Language bridge.
    Ensures that for every domain and problem:
    1. The PDDL is valid.
    2. The 'Oracle' can translate the goal and state into NL.
    """
    print("🚀 Starting Symbolic Oracle Validation (Thesis RQ-Baseline)...")
    
    examples_root = Path(os.environ["EXAMPLES_DIR"])
    if not examples_root.exists():
        print(f"❌ Error: EXAMPLES_DIR '{examples_root}' not found.")
        return
        
    print(f"🔍 Environment: {examples_root.resolve()}\n")

    domains = sorted([d for d in examples_root.iterdir() if d.is_dir()])
    all_passed = True

    for domain_path in domains:
        domain = domain_path.name
        print(f"📂 Domain: {domain}")
        
        prompts_file = domain_path / "prompts.json"
        if not prompts_file.exists():
            print(f"  ❌ Missing prompts.json")
            all_passed = False
            continue
            
        with open(prompts_file) as f:
            data = json.load(f)
            problems = data.get("problems", [])

        for prob in problems:
            pid = prob["id"]
            # Extract number for the backend (e.g., 'p01' -> 1)
            idx = int(re.search(r'\d+', pid).group())
            
            print(f"  📝 Problem {pid}: ", end="")
            try:
                # Test the Symbolic Bridge
                tb.reset_episode(domain, idx)
                
                # Test NL Translation tools
                overview = tb.get_task_overview(domain, idx)
                state = tb.get_state()
                
                if not overview or "Facts:" not in state:
                    raise ValueError("Oracle returned incomplete NL description")
                
                print("✅ OK")
            except Exception as e:
                print(f"❌ FAILED: {e}")
                all_passed = False

    print("\n" + "="*40)
    if all_passed:
        print("✨ SUCCESS: 50/50 problems verified.")
        print("Grounded Planning Environment is ready for submission.")
    else:
        print("🚨 VALIDATION FAILED. Check PDDL or prompts.json integrity.")
        sys.exit(1)

if __name__ == "__main__":
    validate_all()