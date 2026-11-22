import csv
import sys

SLO_MS = 120

with open("tests/load/results_stats.csv", newline="") as file:
    rows = list(csv.DictReader(file))

total = next((r for r in rows if r["Name"] == "Aggregated"), None)

if total is None:
    print("ERROR: No load test results found.")
    sys.exit(1)

p95 = float(total["95%"])
failures = int(total["Failure Count"])

print(f"95th percentile response time: {p95} ms")
print(f"Failed requests: {failures}")

if p95 <= SLO_MS and failures == 0:
    print("PASS: 120 ms SLO met.")
else:
    print("FAIL: 120 ms SLO not met.")
    sys.exit(1)
