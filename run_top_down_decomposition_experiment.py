#!/usr/bin/env python3
"""
Top-Down Rule Decomposition Experiment:
Tests whether an LLM can reliably decompose a coarse-grained rule into a fine-grained,
executable rule module when given the coarse rule and the statutory text/constants pool.

Phase 1 (Decomposition - Blind):
  - Input: Current coarse rule (AggregatedTaxInputs, calculate_total_tax) + 2017 Statutory Pool.
  - NO SARA CASE 20 SCENARIO OR QUESTION SHOWN.
  - Output: LLM-generated Pydantic intermediate schema & deterministic Python tax functions.

Phase 2 (Evaluation on Case 20):
  - Input: SARA Case 20 raw scenario text + LLM-generated schema from Phase 1.
  - Action: LLM extracts facts matching its own schema -> Executes its own generated code.
  - Verification: Compared directly against SARA Prolog Ground Truth ($90,683.0).
"""

import os
import re
import sys
import json
import importlib.util
from typing import Dict, Any

PROJECT_ROOT = "/home/wmlab/tax_agent"
sys.path.insert(0, PROJECT_ROOT)

from src.llm_client import LLMEngine

SARA_CASE_20_PATH = os.path.join(PROJECT_ROOT, "sara_v3", "cases", "tax_case_20.pl")
DECOMPOSED_DIR = os.path.join(PROJECT_ROOT, "rule_abstraction", "results", "decomposed")
os.makedirs(DECOMPOSED_DIR, exist_ok=True)

GENERATED_RULE_FILE = os.path.join(DECOMPOSED_DIR, "decomposed_case_20_rules.py")
EXTRACTION_RESULT_FILE = os.path.join(DECOMPOSED_DIR, "case_20_extraction.json")
EXPERIMENT_SUMMARY_FILE = os.path.join(DECOMPOSED_DIR, "experiment_summary.json")


# ==============================================================================
# Phase 1: Rule Decomposition (Pure Rule Engineering without seeing Case 20)
# ==============================================================================

COARSE_RULE_CODE = '''from pydantic import BaseModel

class AggregatedTaxInputs(BaseModel):
    target_person: str
    tax_year: int
    income_tax: float       # Black-box sub-tax float
    employment_tax: float   # Black-box sub-tax float

def calculate_total_tax(inputs: AggregatedTaxInputs) -> float:
    """
    Coarse-grained top-level macro rule:
    Total tax is the sum of personal income tax and employer employment tax.
    """
    return inputs.income_tax + inputs.employment_tax
'''

STATUTORY_POOL_2017 = '''Applicable Statutory Provisions, Thresholds, and Tables for 2017:

1. Standard Deductions (IRC §63):
   - Married filing jointly / Surviving spouse: $6,000.
   - Head of household: $4,400.
   - Single: $3,000.
   - Married filing separately: $3,000.

2. Overall Limitation on Itemized Deductions (IRC §68 - Pease Limitation):
   - Applicable threshold amount (IRC §68(b)):
     * Married filing jointly / Surviving spouse: $300,000.
     * Head of household: $275,000.
     * Single: $250,000.
     * Married filing separately: $150,000.
   - Limitation (IRC §68(a)): If adjusted gross income exceeds the applicable threshold amount,
     the amount of allowable itemized deductions is reduced by the lesser of:
     * 3% of the excess of adjusted gross income over the applicable threshold amount, or
     * 80% of the itemized deductions otherwise allowable.

3. Personal Exemptions & Phaseout (IRC §151 - PEP):
   - Base exemption amount (IRC §151(d)(1)): $2,000 per eligible exemption.
   - Eligibility (IRC §151(b), §152): 1 exemption for the taxpayer, and 1 exemption for each qualifying dependent.
   - Phaseout (IRC §151(d)(3)): If adjusted gross income exceeds the applicable threshold under §68(b),
     the exemption amount is reduced by 2 percentage points for each $2,500 (or fraction thereof;
     $1,250 for married filing separately) of the excess, up to 100%.

4. Tax Schedules (IRC §1):
   - Married filing jointly / Surviving spouse schedule (IRC §1(a)):
     * Taxable Income <= $36,900: 15% of taxable income.
     * $36,900 < Taxable Income <= $89,150: $5,535 + 28% of the excess over $36,900.
     * $89,150 < Taxable Income <= $140,000: $20,165 + 31% of the excess over $89,150.
     * $140,000 < Taxable Income <= $250,000: $35,928.50 + 36% of the excess over $140,000.
     * Taxable Income > $250,000: $75,528.50 + 39.6% of the excess over $250,000.
   - Head of household schedule (IRC §1(b)):
     * Taxable Income <= $29,600: 15% of taxable income.
     * $29,600 < Taxable Income <= $76,400: $4,440 + 28% of the excess over $29,600.
     * $76,400 < Taxable Income <= $127,500: $17,544 + 31% of the excess over $76,400.
     * $127,500 < Taxable Income <= $250,000: $33,385 + 36% of the excess over $127,500.
     * Taxable Income > $250,000: $77,485 + 39.6% of the excess over $250,000.
   - Single schedule (IRC §1(c)):
     * Taxable Income <= $22,100: 15% of taxable income.
     * $22,100 < Taxable Income <= $53,500: $3,315 + 28% of the excess over $22,100.
     * $53,500 < Taxable Income <= $115,000: $12,107 + 31% of the excess over $53,500.
     * $115,000 < Taxable Income <= $250,000: $31,172 + 36% of the excess over $115,000.
     * Taxable Income > $250,000: $79,772 + 39.6% of the excess over $250,000.
   - Married filing separately schedule (IRC §1(d)):
     * Taxable Income <= $18,450: 15% of taxable income.
     * $18,450 < Taxable Income <= $44,575: $2,767.50 + 28% of the excess over $18,450.
     * $44,575 < Taxable Income <= $70,000: $10,082.50 + 31% of the excess over $44,575.
     * $70,000 < Taxable Income <= $125,000: $17,964.25 + 36% of the excess over $70,000.
     * Taxable Income > $125,000: $37,764.25 + 39.6% of the excess over $125,000.

5. Employment / FUTA Tax (IRC §3301, §3306):
   - FUTA annual taxable wage base limit per employee (IRC §3306(b)(1)): $7,000.
   - General commercial employment threshold (IRC §3306(a)(1)): $1,500 cash remuneration in any calendar quarter.
   - Domestic service employment threshold (IRC §3306(a)(3)): $1,000 cash remuneration in any calendar quarter.
   - Agricultural labor employment threshold (IRC §3306(a)(2)): $20,000 cash remuneration in any calendar quarter.
   - Benefit Plan Exclusions (IRC §3306(b)(2)): Payments made under employee benefit plans for retirement,
     health insurance, or sickness are excluded from taxable wages.
   - FUTA tax rate: 6% of taxable wages paid.

6. Rounding Rule:
   - Round final taxes half-up to nearest integer (0.5 rounds up).
'''


def run_phase_1_decomposition(engine: LLMEngine) -> str:
    print("\n" + "="*70)
    print("▶ [Phase 1] Prompting LLM for Top-Down Rule Decomposition (No Case 20 Text)")
    print("="*70)

    system_prompt = (
        "You are an expert tax domain modeler and Python software architect.\n"
        "Your task is to take an existing coarse-grained tax rule and decompose it into a refined, intermediate-level symbolic rule module."
    )

    user_prompt = (
        "### 1. Existing Coarse-Grained Rule\n"
        "We currently have the following coarse tax calculation rule:\n"
        f"```python\n{COARSE_RULE_CODE}\n```\n\n"
        "### 2. Reference Statutory Provisions & Constants Pool (2017)\n"
        f"{STATUTORY_POOL_2017}\n\n"
        "### 3. Your Decomposition Task\n"
        "Our current rule is overly coarse: `income_tax` and `employment_tax` are black-box floats, which forces the caller to calculate all tax numbers outside the rule engine.\n"
        "Please decompose and refine this coarse rule into a complete, self-contained Python module that meets these criteria:\n"
        "1. Define intermediate Pydantic models (using `from pydantic import BaseModel`) that replace the black-box floats with structured intermediate legal concepts and facts (e.g., filing status, gross income, claimed deductions, exemptions, employee wages, plan exclusions, etc.). Name the main input model `DecomposedTaxInputs`.\n"
        "2. Implement deterministic Python calculation functions to compute `income_tax`, `employment_tax`, and the final `total_tax` from `DecomposedTaxInputs` based on the statutory provisions.\n"
        "3. Provide a top-level function `calculate_total_tax(inputs: DecomposedTaxInputs) -> float` that returns the final total tax.\n"
        "IMPORTANT: Do not hardcode values for any specific scenario. Build a general decomposed rule module for the provided statutory provisions.\n"
        "Return ONLY the complete, executable Python code inside a single ```python ... ``` markdown code block."
    )

    print("⏳ Calling LLM to decompose coarse rule...")
    raw_response = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, temperature=0.0)

    # Extract Python code
    code_match = re.search(r"```python(.*?)```", raw_response, re.DOTALL)
    if code_match:
        extracted_code = code_match.group(1).strip()
    else:
        # Fallback if no code fence
        extracted_code = raw_response.strip()

    with open(GENERATED_RULE_FILE, "w", encoding="utf-8") as f:
        f.write(extracted_code)

    print(f"✅ Successfully saved LLM-decomposed rule module to: {GENERATED_RULE_FILE}")
    return extracted_code


# ==============================================================================
# Phase 2: Downstream Evaluation on Case 20 (The Test)
# ==============================================================================

def read_case_20_blind() -> Dict[str, Any]:
    with open(SARA_CASE_20_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    text_m = re.search(r"%\s*Text\s*\n((?:%\s*.*\n)+)", content)
    scenario_text = "\n".join([line.lstrip("%").strip() for line in text_m.group(1).strip().splitlines()]) if text_m else ""

    q_m = re.search(r"%\s*Question\s*\n((?:%\s*.*\n)+)", content)
    raw_q = "\n".join([line.lstrip("%").strip() for line in q_m.group(1).strip().splitlines()]) if q_m else ""
    sanitized_q = re.sub(r"\?\s*[\$0-9]+.*", "?", raw_q)

    gt_m = re.search(r":-\s*tax\((\"[^\"]+\"|\w+),\s*(\d{4}),\s*(\d+(?:\.\d+)?)\)", content)
    gt_tax = float(gt_m.group(3)) if gt_m else 90683.0

    return {
        "scenario_text": scenario_text,
        "question_text": sanitized_q,
        "ground_truth_tax": gt_tax
    }


def run_phase_2_evaluation(generated_code: str, case_20_info: Dict[str, Any], engine: LLMEngine) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("▶ [Phase 2] Evaluating LLM-Decomposed Rule on SARA Case 20")
    print("="*70)

    # 1. Ask LLM to extract facts matching its OWN generated schema
    system_prompt = (
        "You are an expert tax data extractor. Given a tax scenario, extract all factual information "
        "into strict JSON matching the provided Pydantic data schema."
    )

    user_prompt = (
        f"Tax Scenario:\n{case_20_info['scenario_text']}\n\n"
        f"Question:\n{case_20_info['question_text']}\n\n"
        "Target Pydantic Schema Definition:\n"
        f"```python\n{generated_code}\n```\n\n"
        "Please extract all factual entities from the scenario to populate the `DecomposedTaxInputs` model.\n"
        "Return ONLY a valid JSON object matching the `DecomposedTaxInputs` schema."
    )

    print("⏳ Calling LLM to extract facts according to its generated schema...")
    raw_extract = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, response_mime_type="application/json")

    try:
        cleaned_json = re.sub(r"^```(?:json)?", "", raw_extract.strip(), flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json.strip(), flags=re.MULTILINE).strip()
        extracted_facts = json.loads(cleaned_json)
    except Exception as e:
        extracted_facts = {"parse_error": str(e), "raw_response": raw_extract}

    with open(EXTRACTION_RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(extracted_facts, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved Extracted Facts to: {EXTRACTION_RESULT_FILE}")

    # 2. Dynamically import and execute the LLM-generated code
    execution_result = {}
    try:
        spec = importlib.util.spec_from_file_location("decomposed_case_20_rules", GENERATED_RULE_FILE)
        decomposed_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(decomposed_mod)

        # Instantiate DecomposedTaxInputs
        decomposed_input_cls = getattr(decomposed_mod, "DecomposedTaxInputs")
        calc_func = getattr(decomposed_mod, "calculate_total_tax")

        # Parse data into model
        if hasattr(decomposed_input_cls, "model_validate"):
            model_instance = decomposed_input_cls.model_validate(extracted_facts)
        else:
            model_instance = decomposed_input_cls(**extracted_facts)

        calculated_total = float(calc_func(model_instance))
        gt_tax = case_20_info["ground_truth_tax"]

        execution_result = {
            "execution_status": "SUCCESS",
            "calculated_total_tax": calculated_total,
            "ground_truth_tax": gt_tax,
            "matches_ground_truth": (calculated_total == gt_tax),
            "discrepancy": round(calculated_total - gt_tax, 2)
        }
    except Exception as e:
        execution_result = {
            "execution_status": "ERROR",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "matches_ground_truth": False
        }

    summary = {
        "experiment": "top_down_rule_decomposition",
        "case_id": "tax_case_20",
        "generated_rule_file": GENERATED_RULE_FILE,
        "case_info": case_20_info,
        "extracted_facts": extracted_facts,
        "execution_result": execution_result
    }

    with open(EXPERIMENT_SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary


def main():
    print("🚀 Running Top-Down Rule Decomposition Experiment...")
    engine = LLMEngine()
    print(f"LLM Engine Initialized (Model: {engine.model_name}, Backend: {engine.backend})")

    # Step 1: LLM decomposes coarse rule into fine-grained module (without seeing Case 20)
    generated_code = run_phase_1_decomposition(engine)

    # Step 2: Test the LLM-decomposed module on Case 20
    case_20_info = read_case_20_blind()
    summary = run_phase_2_evaluation(generated_code, case_20_info, engine)

    print("\n" + "="*70)
    print("📊 TOP-DOWN DECOMPOSITION EXPERIMENT SUMMARY")
    print("="*70)
    exec_res = summary["execution_result"]
    print(f"Execution Status: {exec_res.get('execution_status')}")
    if exec_res.get("execution_status") == "SUCCESS":
        print(f"Calculated Total Tax: ${exec_res.get('calculated_total_tax')}")
        print(f"Ground Truth Tax:     ${exec_res.get('ground_truth_tax')}")
        print(f"Matches Ground Truth: {exec_res.get('matches_ground_truth')}")
        print(f"Discrepancy:          ${exec_res.get('discrepancy')}")
    else:
        print(f"Error: {exec_res.get('error_type')}: {exec_res.get('error_message')}")
        print(f"Matches Ground Truth: False")
    print(f"\nSaved Full Results to: {EXPERIMENT_SUMMARY_FILE}")
    print("="*70)


if __name__ == "__main__":
    main()
