import os
import re
import sys
import json
import importlib.util
from typing import Dict, Any

sys.path.insert(0, "/home/wmlab/tax_agent")
from src.llm_client import LLMEngine

OUTPUT_DIR = "/home/wmlab/tax_agent/rule_abstraction/results/grounded_decomposed"
RULE_FILE = os.path.join(OUTPUT_DIR, "grounded_decomposed_case_20_rules.py")
EXTRACTION_FILE = os.path.join(OUTPUT_DIR, "grounded_case_20_extraction.json")
SUMMARY_FILE = os.path.join(OUTPUT_DIR, "grounded_experiment_summary.json")
SARA_CASE_20_PATH = "/home/wmlab/tax_agent/sara_v3/cases/tax_case_20.pl"

def load_generated_module(module_path: str):
    spec = importlib.util.spec_from_file_location("grounded_decomposed_rules", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["grounded_decomposed_rules"] = module
    spec.loader.exec_module(module)
    return module

def read_case_20() -> Dict[str, Any]:
    with open(SARA_CASE_20_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    text_m = re.search(r"%\s*Text\s*\n((?:%\s*.*\n)+)", content)
    scenario_text = "\n".join([line.lstrip("%").strip() for line in text_m.group(1).strip().splitlines()]) if text_m else ""

    q_m = re.search(r"%\s*Question\s*\n((?:%\s*.*\n)+)", content)
    raw_question = "\n".join([line.lstrip("%").strip() for line in q_m.group(1).strip().splitlines()]) if q_m else ""
    # Sanitize ground truth leak in question
    clean_question = re.sub(r"\?\s*[\$0-9]+.*", "?", raw_question).strip()

    gt_m = re.search(r"\$\s*([0-9]+)", raw_question)
    gt_tax = float(gt_m.group(1)) if gt_m else 90683.0

    return {
        "scenario_text": scenario_text,
        "question_text": clean_question,
        "ground_truth_tax": gt_tax
    }

def main():
    print("="*70)
    print("▶ Evaluating Grounded Decomposed Rules on Case 20")
    print("="*70)

    # 1. Load generated rules module
    rules_mod = load_generated_module(RULE_FILE)
    GroundedTaxInputs = getattr(rules_mod, "GroundedTaxInputs")
    calculate_total_tax = getattr(rules_mod, "calculate_total_tax")

    # Inspect schema
    schema_json = GroundedTaxInputs.schema_json(indent=2)
    print("📋 Target Grounded Schema:")
    print(schema_json)

    # 2. Extract facts from Case 20 using LLM
    case_info = read_case_20()
    engine = LLMEngine()

    system_prompt = (
        "You are a precise tax data extractor. Given a tax scenario, extract all factual events "
        "and details into the required JSON format matching the provided Pydantic schema.\n"
        "Do not invent facts. Dates must be formatted as YYYY-MM-DD strings."
    )

    user_prompt = (
        f"Target Pydantic Schema:\n{schema_json}\n\n"
        f"Scenario Text:\n{case_info['scenario_text']}\n\n"
        f"Question:\n{case_info['question_text']}\n\n"
        "Extract the facts into a valid JSON object matching the schema."
    )

    print("⏳ Calling LLM to extract facts from Case 20 into GroundedTaxInputs...")
    raw_resp = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, response_mime_type="application/json")

    cleaned_json = re.sub(r"^```(?:json)?", "", raw_resp.strip(), flags=re.MULTILINE)
    cleaned_json = re.sub(r"```$", "", cleaned_json.strip(), flags=re.MULTILINE).strip()

    extracted_dict = json.loads(cleaned_json)
    with open(EXTRACTION_FILE, "w", encoding="utf-8") as f:
        json.dump(extracted_dict, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved extraction to: {EXTRACTION_FILE}")
    print("📦 Extracted Facts JSON:\n", json.dumps(extracted_dict, indent=2))

    # 3. Instantiate GroundedTaxInputs and execute calculation
    print("\n⏳ Executing deterministic rules with extracted facts...")
    inputs_obj = GroundedTaxInputs(**extracted_dict)
    calc_res = calculate_total_tax(inputs_obj)

    print("\n" + "="*70)
    print("📊 Execution Result:")
    if hasattr(calc_res, "model_dump_json"):
        print(calc_res.model_dump_json(indent=2))
    elif hasattr(calc_res, "json"):
        print(calc_res.json())
    else:
        print(calc_res)
    
    total_tax = calc_res.total_tax_rounded if hasattr(calc_res, "total_tax_rounded") else getattr(calc_res, "total_tax", None)
    gt_tax = case_info["ground_truth_tax"]

    print("\n" + "="*70)
    print(f"Ground Truth Tax : ${gt_tax:,.2f}")
    print(f"Calculated Tax   : ${total_tax:,.2f}")
    diff = total_tax - gt_tax
    print(f"Discrepancy      : ${diff:+,.2f}")
    if abs(diff) < 1.0:
        print("🎉 [SUCCESS] Exact Match with Ground Truth!")
    else:
        print(f"❌ [MISMATCH] Difference: {diff}")
    print("="*70)

    summary = {
        "case_id": "tax_case_20",
        "ground_truth_tax": gt_tax,
        "calculated_tax": total_tax,
        "discrepancy": diff,
        "match": abs(diff) < 1.0,
        "extracted_facts": extracted_dict,
        "calculation_details": json.loads(calc_res.model_dump_json()) if hasattr(calc_res, "model_dump_json") else str(calc_res)
    }
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
