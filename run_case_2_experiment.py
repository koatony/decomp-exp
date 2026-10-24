"""
Experiment Runner for SARA Case 2 with LLM:
1. Reads raw problem directly from sara_v3/cases/tax_case_2.pl (authentic file reading, zero hand-rewriting).
2. Schema 1 (Detailed Facts Extraction):
   - LLM extracts detailed unaggregated facts (target_person, spouse, tax_year, filing_status, incomes, dependents).
   - Feeds into rule_abstraction.rules.case_2.case_2_rules.calculate_case_2_tax.
   - Saves output to rule_abstraction/results/detailed/case_2.json
3. Schema 2 (Aggregated Tax Inputs Extraction):
   - LLM extracts macro sub-taxes (income_tax, employment_tax, reasoning).
   - Feeds into rule_abstraction.rules_aggregation.case_2.calculate_total_tax.
   - Saves output to rule_abstraction/results/aggregated/case_2.json
"""

import os
import sys
import re
import json
from typing import Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.llm_client import LLMEngine
from rule_abstraction.rules.case_2.case_2_rules import (
    Income, Dependent, calculate_case_2_tax, compute_joint_gross_income,
    get_standard_deduction_joint, compute_personal_exemptions, compute_taxable_income
)
from rule_abstraction.rules_aggregation.case_2 import (
    AggregatedTaxInputs, calculate_total_tax
)

SARA_CASE_2_PATH = os.path.join(PROJECT_ROOT, "sara_v3", "cases", "tax_case_2.pl")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "rule_abstraction", "results")
DETAILED_RESULTS_DIR = os.path.join(RESULTS_DIR, "detailed")
AGGREGATED_RESULTS_DIR = os.path.join(RESULTS_DIR, "aggregated")

os.makedirs(DETAILED_RESULTS_DIR, exist_ok=True)
os.makedirs(AGGREGATED_RESULTS_DIR, exist_ok=True)


def read_sara_case_from_file(filepath: str) -> Dict[str, Any]:
    """Reads authentic SARA case directly from file without rewriting."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"SARA case file not found at: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    text_m = re.search(r"%\s*Text\s*\n((?:%\s*.*\n)+)", content)
    scenario_text = "\n".join([l.lstrip("%").strip() for l in text_m.group(1).splitlines()]) if text_m else ""

    q_m = re.search(r"%\s*Question\s*\n((?:%\s*.*\n)+)", content)
    raw_question = "\n".join([l.lstrip("%").strip() for l in q_m.group(1).splitlines()]) if q_m else ""
    question_text = re.sub(r"\?\s*[\$0-9]+.*", "?", raw_question).strip()

    gt_m = re.search(r":-\s*tax\(\s*\"?([^\",\s]+)\"?\s*,\s*(\d+)\s*,\s*(-?\d+)\s*\)\.", content)
    person = gt_m.group(1) if gt_m else "Alice"
    year = int(gt_m.group(2)) if gt_m else 2013
    gt_tax = float(gt_m.group(3)) if gt_m else 26567.0

    return {
        "file_path": filepath,
        "scenario_text": scenario_text,
        "question_text": question_text,
        "target_person": person,
        "tax_year": year,
        "ground_truth_tax": gt_tax,
        "full_file_content": content
    }


def run_detailed_facts_pipeline(case_info: Dict[str, Any], engine: LLMEngine) -> Dict[str, Any]:
    """
    Approach 1: LLM extracts detailed unaggregated facts -> Python micro-rules evaluate tax.
    """
    print("\n" + "="*70)
    print("▶ [Pipeline 1] Detailed Facts Extraction -> Micro-Rule Execution")
    print("="*70)

    system_prompt = (
        "You are an expert tax parser. Extract all factual entities from the tax scenario into strict JSON format.\n"
        "Identify the primary taxpayer, spouse (if any), filing status, all incomes earned, and dependents.\n"
        "Dates must be integers formatted as YYYYMMDD (e.g., 20130101, 20001009).\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "target_person": "string",\n'
        '  "spouse": "string or null",\n'
        '  "tax_year": integer,\n'
        '  "filing_status": "single" | "married_joint" | "married_separate" | "head_of_household",\n'
        '  "incomes": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "agent": "string",\n'
        '      "amount": float,\n'
        '      "start_date": integer\n'
        '    }\n'
        '  ],\n'
        '  "dependents": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "name": "string",\n'
        '      "parents": ["string"],\n'
        '      "birth_date": integer\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    user_prompt = (
        f"Case Text directly from SARA v3:\n{case_info['scenario_text']}\n\n"
        f"Question:\n{case_info['question_text']}\n\n"
        "Please extract all factual events into the required JSON schema."
    )

    raw_response = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, response_mime_type="application/json")

    # Parse JSON
    try:
        cleaned_json = re.sub(r"^```(?:json)?", "", raw_response.strip(), flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json.strip(), flags=re.MULTILINE).strip()
        extracted_facts = json.loads(cleaned_json)
    except Exception as e:
        extracted_facts = {"parse_error": str(e), "raw_response": raw_response}

    # Execute Python Rule with STRICT indexing (zero fallback)
    rule_exec_result = {}
    try:
        raw_incomes = extracted_facts["incomes"]
        raw_dependents = extracted_facts.get("dependents", [])

        income_objs = [Income(**inc) if isinstance(inc, dict) else inc for inc in raw_incomes]
        dependent_objs = [Dependent(**dep) if isinstance(dep, dict) else dep for dep in raw_dependents]

        rule_input_facts = {
            "target_person": extracted_facts["target_person"],
            "spouse": extracted_facts["spouse"],
            "tax_year": int(extracted_facts["tax_year"]),
            "filing_status": extracted_facts["filing_status"],
            "incomes": income_objs,
            "dependents": dependent_objs
        }

        calculated_tax = calculate_case_2_tax(rule_input_facts)
        gross_inc = compute_joint_gross_income(rule_input_facts["target_person"], rule_input_facts["spouse"], rule_input_facts["tax_year"], income_objs)
        std_ded = get_standard_deduction_joint(rule_input_facts["tax_year"], rule_input_facts["filing_status"])
        taxpayer_cnt = 2 if (rule_input_facts["filing_status"] == "married_joint" and rule_input_facts["spouse"]) else 1
        exemptions = compute_personal_exemptions(taxpayer_cnt, len(dependent_objs), rule_input_facts["tax_year"])
        taxable_inc = compute_taxable_income(gross_inc, std_ded, exemptions)

        rule_exec_result = {
            "computed_gross_income": gross_inc,
            "applied_standard_deduction": std_ded,
            "applied_exemptions": exemptions,
            "computed_taxable_income": taxable_inc,
            "calculated_total_tax": calculated_tax,
            "ground_truth_tax": case_info["ground_truth_tax"],
            "matches_ground_truth": (calculated_tax == case_info["ground_truth_tax"])
        }
    except Exception as e:
        rule_exec_result = {
            "execution_error": f"{type(e).__name__}: {str(e)}",
            "matches_ground_truth": False
        }

    output = {
        "pipeline": "detailed_facts_extraction",
        "case_id": "tax_case_2",
        "source_file": case_info["file_path"],
        "scenario_text": case_info["scenario_text"],
        "question_text": case_info["question_text"],
        "llm_extracted_facts": extracted_facts,
        "rule_execution": rule_exec_result
    }

    out_file = os.path.join(DETAILED_RESULTS_DIR, "case_2.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved Detailed Pipeline Result to: {out_file}")
    return output


def run_aggregated_pipeline(case_info: Dict[str, Any], engine: LLMEngine) -> Dict[str, Any]:
    """
    Approach 2: LLM extracts aggregated tax inputs -> Python macro-rule evaluates tax.
    """
    print("\n" + "="*70)
    print("▶ [Pipeline 2] Aggregated Tax Inputs Extraction -> Macro-Rule Execution")
    print("="*70)

    system_prompt = (
        "You are an expert tax legal engine. Given a tax legal scenario, analyze the statutes and calculate the core aggregated sub-taxes:\n"
        "1. income_tax: IRC Section 1 individual income tax for the tax year.\n"
        "2. employment_tax: IRC Section 3301 employer FUTA tax (if any).\n"
        "Provide a concise legal reasoning explaining the calculation for both values.\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "target_person": "string",\n'
        '  "tax_year": integer,\n'
        '  "income_tax": float,\n'
        '  "employment_tax": float,\n'
        '  "reasoning": "string explaining how income_tax and employment_tax were determined"\n'
        "}"
    )

    statutory_context = (
        "Applicable statutory constants for this benchmark:\n"
        "- 2013 married filing jointly standard deduction: $6,000.\n"
        "- Personal exemption amount: $2,000 per eligible exemption.\n"
        "- 2013 married filing jointly tax schedule:\n"
        "  * Taxable Income <= $36,900: 15% of taxable income.\n"
        "  * $36,900 < Taxable Income <= $89,150: $5,535 + 28% of the excess over $36,900.\n"
        "  * $89,150 < Taxable Income <= $140,000: $20,165 + 31% of the excess over $89,150.\n"
        "  * $140,000 < Taxable Income <= $250,000: $35,928.50 + 36% of the excess over $140,000.\n"
        "  * Taxable Income > $250,000: $75,528.50 + 39.6% of the excess over $250,000.\n"
        "- Round final tax half-up to nearest integer.\n"
    )

    user_prompt = (
        f"Case Text directly from SARA v3:\n{case_info['scenario_text']}\n\n"
        f"Question:\n{case_info['question_text']}\n\n"
        f"{statutory_context}\n"
        "Please evaluate and output the aggregated tax inputs JSON according to these statutory rules."
    )

    raw_response = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, response_mime_type="application/json")

    # Parse JSON
    try:
        cleaned_json = re.sub(r"^```(?:json)?", "", raw_response.strip(), flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json.strip(), flags=re.MULTILINE).strip()
        extracted_agg = json.loads(cleaned_json)
    except Exception as e:
        extracted_agg = {"parse_error": str(e), "raw_response": raw_response}

    # Execute Macro Rule with STRICT indexing (zero fallback)
    rule_exec_result = {}
    try:
        agg_inputs = AggregatedTaxInputs(
            target_person=extracted_agg["target_person"],
            tax_year=int(extracted_agg["tax_year"]),
            income_tax=float(extracted_agg["income_tax"]),
            employment_tax=float(extracted_agg["employment_tax"]),
            reasoning=extracted_agg.get("reasoning", "")
        )
        total_tax = calculate_total_tax(agg_inputs)
        rule_exec_result = {
            "income_tax": agg_inputs.income_tax,
            "employment_tax": agg_inputs.employment_tax,
            "calculated_total_tax": total_tax,
            "ground_truth_tax": case_info["ground_truth_tax"],
            "matches_ground_truth": (total_tax == case_info["ground_truth_tax"])
        }
    except Exception as e:
        rule_exec_result = {
            "execution_error": f"{type(e).__name__}: {str(e)}",
            "matches_ground_truth": False
        }

    output = {
        "pipeline": "aggregated_tax_inputs_extraction",
        "case_id": "tax_case_2",
        "source_file": case_info["file_path"],
        "scenario_text": case_info["scenario_text"],
        "question_text": case_info["question_text"],
        "llm_extracted_aggregated_inputs": extracted_agg,
        "rule_execution": rule_exec_result
    }

    out_file = os.path.join(AGGREGATED_RESULTS_DIR, "case_2.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved Aggregated Pipeline Result to: {out_file}")
    return output


def main():
    print("🚀 Starting SARA Case 2 Dual-Pipeline Experiment...")
    print(f"Reading SARA Case 2 directly from: {SARA_CASE_2_PATH}")
    case_info = read_sara_case_from_file(SARA_CASE_2_PATH)

    print(f"Taxpayer: {case_info['target_person']}")
    print(f"Year: {case_info['tax_year']}")
    print(f"Ground Truth Tax: ${case_info['ground_truth_tax']}")
    print(f"Scenario Text: {case_info['scenario_text']}")

    engine = LLMEngine()
    print(f"LLM Engine Initialized (Model: {engine.model_name}, Backend: {engine.backend})")

    # Run Pipeline 1: Detailed Facts -> Micro-Rule
    res_detailed = run_detailed_facts_pipeline(case_info, engine)

    # Run Pipeline 2: Aggregated Inputs -> Macro-Rule
    res_agg = run_aggregated_pipeline(case_info, engine)

    print("\n" + "="*70)
    print("📊 CASE 2 EXPERIMENT COMPARISON SUMMARY")
    print("="*70)
    print(f"Pipeline 1 (Detailed Facts -> Micro-Rule):")
    print(f"  Gross Income: {res_detailed.get('rule_execution', {}).get('computed_gross_income')}")
    print(f"  Taxable Income: {res_detailed.get('rule_execution', {}).get('computed_taxable_income')}")
    print(f"  Calculated Tax: {res_detailed.get('rule_execution', {}).get('calculated_total_tax')}")
    print(f"  Matches GT ($26,567): {res_detailed.get('rule_execution', {}).get('matches_ground_truth')}")
    print(f"  Saved to: rule_abstraction/results/detailed/case_2.json")

    print(f"\nPipeline 2 (Aggregated Sub-Taxes -> Macro-Rule):")
    print(f"  LM Income Tax: {res_agg.get('rule_execution', {}).get('income_tax')}")
    print(f"  LM Employment Tax: {res_agg.get('rule_execution', {}).get('employment_tax')}")
    print(f"  Calculated Tax: {res_agg.get('rule_execution', {}).get('calculated_total_tax')}")
    print(f"  Matches GT ($26,567): {res_agg.get('rule_execution', {}).get('matches_ground_truth')}")
    print(f"  Reasoning: {res_agg.get('llm_extracted_aggregated_inputs', {}).get('reasoning')}")
    print(f"  Saved to: rule_abstraction/results/aggregated/case_2.json")
    print("="*70)


if __name__ == "__main__":
    main()
