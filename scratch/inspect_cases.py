import os
import re
import json

cases_meta = {}
for i in range(21, 41):
    path = f"/home/wmlab/tax_agent/sara_v3/cases/tax_case_{i}.pl"
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Text
    text_m = re.search(r"%\s*Text\s*\n((?:%\s*.*\n)+)", content)
    text = ""
    if text_m:
        text = " ".join([line.lstrip("%").strip() for line in text_m.group(1).strip().splitlines()])

    # Question
    q_m = re.search(r"%\s*Question\s*\n((?:%\s*.*\n)+)", content)
    q = ""
    if q_m:
        q = " ".join([line.lstrip("%").strip() for line in q_m.group(1).strip().splitlines()])

    # GT
    gt_m = re.search(r":-\s*tax\((\"[^\"]+\"|\w+),\s*(\d{4}),\s*(\d+(?:\.\d+)?)\)", content)
    person = gt_m.group(1).strip('"') if gt_m else "Unknown"
    year = int(gt_m.group(2)) if gt_m else 0
    gt_tax = float(gt_m.group(3)) if gt_m else 0.0

    cases_meta[f"case_{i}"] = {
        "case_num": i,
        "person": person,
        "year": year,
        "gt_tax": gt_tax,
        "text": text,
        "question": q
    }

with open("/home/wmlab/tax_agent/rule_abstraction/cases_21_40_meta.json", "w", encoding="utf-8") as f:
    json.dump(cases_meta, f, indent=2)

print("Saved cases_21_40_meta.json successfully!")
