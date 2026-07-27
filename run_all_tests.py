"""Run all specified test files one by one and write full output to results file."""
import subprocess
import sys
import os

os.chdir(r"c:\Users\HP\Desktop\Kulima vc brain")

test_files = [
    "test_trust_graph_visualization.py",
    "test_export_integrity.py",
    "test_ask_ic_integrity.py",
    "test_orchestrator_integrity.py",
    "test_evidence_integrity.py",
    "test_db_trust_layer.py",
    "test_models_trust_layer.py",
    "test_pipeline.py",
    "test_comparison.py",
    "test_trust_layer_ui.py",
]

results = []

for tf in test_files:
    print(f"\n{'='*70}")
    print(f"RUNNING: {tf}")
    print('='*70)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", tf, "-v", "--tb=long"],
        capture_output=True,
        text=True,
        cwd=r"c:\Users\HP\Desktop\Kulima vc brain",
    )
    output = proc.stdout + proc.stderr
    print(output)
    results.append((tf, proc.returncode, output))
    if proc.returncode != 0:
        print(f"\n*** FAILURE in {tf} (exit code {proc.returncode}) — stopping. ***")
        break

# Write to file
with open("all_pytest_runs.txt", "w", encoding="utf-8") as f:
    for tf, rc, out in results:
        f.write(f"\n{'='*70}\n")
        f.write(f"FILE: {tf}  EXIT_CODE: {rc}\n")
        f.write('='*70 + "\n")
        f.write(out)
        f.write("\n")

print("\nAll results written to all_pytest_runs.txt")
