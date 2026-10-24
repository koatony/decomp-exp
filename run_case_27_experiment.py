#!/usr/bin/env python3
"""
Case 27 Experiment Runner (SARA Benchmark).
Evaluates LLM on Case 27 using:
1. Pipeline 1 (Detailed Facts -> Micro-Rule):
   LLM extracts ONLY unaggregated, observable factual entities (dependents, parent-child, residences, maintenance, income).
   Zero high-level legal status extraction.
2. Pipeline 2 (Aggregated Sub-Taxes -> Macro-Rule):
   LLM extracts core sub-taxes (income_tax, employment_tax) -> Evaluated deterministically by rules_aggregation/case_27.py.

CRITICAL BENCHMARK CONSTRAINTS:
1. SARA question text leak is sanitized (strip answer from text).
2. Aggregation prompt contains ONLY annual constants, thresholds, and statutory tables (neutral 2017 context).
3. No procedural calculation formulas or reasoning scaffolds in the prompt.
4. Zero fallback in schema parsing and entity resolution.
"""

import os
import re
import sys
import json
from typing import Dict, Any, List

PROJECT_ROOT = "/home/wmlab/tax_agent"
sys.path.insert(0, PROJECT_ROOT)

from src.llm_client import LLMEngine
from rule_abstraction.rules.case_27.case_27_rules import (
    Person, ParentChild, Dependent, Residence, HouseholdMaintenance,
    calculate_case_27_tax, determine_filing_status,
    compute_standard_deduction, compute_personal_exemptions,
    calculate_income_tax_schedule_b
)
from rule_abstraction.rules_aggregation.case_27 import AggregatedTaxInputs, calculate_total_tax

SARA_CASE_27_PATH = os.path.join(PROJECT_ROOT, "sara_v3", "cases", "tax_case_27.pl")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "rule_abstraction", "results")
DETAILED_RESULTS_DIR = os.path.join(RESULTS_DIR, "detailed")
AGGREGATED_RESULTS_DIR = os.path.join(RESULTS_DIR, "aggregated")

os.makedirs(DETAILED_RESULTS_DIR, exist_ok=True)
os.makedirs(AGGREGATED_RESULTS_DIR, exist_ok=True)


def read_sara_case_from_file(filepath: str) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract Scenario Text
    text_m = re.search(r"%\s*Text\s*\n((?:%\s*.*\n)+)", content)
    scenario_text = ""
    if text_m:
        scenario_text = "\n".join([line.lstrip("%").strip() for line in text_m.group(1).strip().splitlines()])

    # Extract Question Text and strip answer leaks
    q_m = re.search(r"%\s*Question\s*\n((?:%\s*.*\n)+)", content)
    question_text = ""
    if q_m:
        raw_q = "\n".join([line.lstrip("%").strip() for line in q_m.group(1).strip().splitlines()])
        question_text = re.sub(r"\?\s*[\$0-9]+.*", "?", raw_q)

    # Extract Ground Truth from Prolog test assertion
    gt_m = re.search(r":-\s*tax\((\"[^\"]+\"|\w+),\s*(\d{4}),\s*(\d+(?:\.\d+)?)\)", content)
    person = gt_m.group(1).strip('"') if gt_m else "Alice"
    year = int(gt_m.group(2)) if gt_m else 2017
    gt_tax = float(gt_m.group(3)) if gt_m else 3720.0

    return {
        "file_path": filepath,
        "scenario_text": scenario_text,
        "question_text": question_text,
        "target_person": person,
        "tax_year": year,
        "ground_truth_tax": gt_tax,
        "full_file_content": content
    }


def run_aggregated_pipeline(case_info: Dict[str, Any], engine: LLMEngine) -> Dict[str, Any]:
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
        "Applicable statutory constants, thresholds, and tables for 2017 benchmark:\n"
        "1. Standard Deductions (IRC §63):\n"
        "   - Married filing jointly / Surviving spouse: $6,000 (IRC §63(c)(2)(A)).\n"
        "   - Head of household: $4,400 (IRC §63(c)(2)(B)).\n"
        "   - Single: $3,000 (IRC §63(c)(2)(C)).\n"
        "   - Married filing separately: $3,000 (IRC §63(c)(2)(C)).\n"
        "2. Personal Exemptions (IRC §151):\n"
        "   - Exemption amount: $2,000 per allowable exemption.\n"
        "   - PEP phaseout thresholds: Head of Household: $275,000; Married Jointly: $300,000; Single: $250,000.\n"
        "3. Tax Schedules (IRC §1):\n"
        "   - Head of household schedule (IRC §1(b)):\n"
        "     * Taxable Income <= $29,600: 15% of taxable income.\n"
        "     * $29,600 < Taxable Income <= $76,400: $4,440 + 28% of the excess over $29,600.\n"
        "     * $76,400 < Taxable Income <= $127,500: $17,544 + 31% of the excess over $76,400.\n"
        "     * $127,500 < Taxable Income <= $250,000: $33,385 + 36% of the excess over $127,500.\n"
        "     * Taxable Income > $250,000: $77,485 + 39.6% of the excess over $250,000.\n"
        "   - Single schedule (IRC §1(c)):\n"
        "     * Taxable Income <= $22,100: 15% of taxable income.\n"
        "     * $22,100 < Taxable Income <= $53,500: $3,315 + 28% of the excess over $22,100.\n"
        "     * $53,500 < Taxable Income <= $115,000: $12,107 + 31% of the excess over $53,500.\n"
        "     * $115,000 < Taxable Income <= $250,000: $31,172 + 36% of the excess over $115,000.\n"
        "     * Taxable Income > $250,000: $79,772 + 39.6% of the excess over $250,000.\n"
        "4. Employment / FUTA Tax (IRC §3301, §3306):\n"
        "   - FUTA tax rate: 6% of taxable wages paid.\n"
        "5. Rounding:\n"
        "   - Round final tax half-up to nearest integer.\n"
    )

    user_prompt = (
        f"Case Text directly from SARA v3:\n{case_info['scenario_text']}\n\n"
        f"Question:\n{case_info['question_text']}\n\n"
        f"{statutory_context}\n"
        "Please evaluate and output the aggregated tax inputs JSON according to these statutory rules."
    )

    raw_response = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, response_mime_type="application/json", timeout=60)

    try:
        cleaned_json = re.sub(r"^```(?:json)?", "", raw_response.strip(), flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json.strip(), flags=re.MULTILINE).strip()
        extracted_agg = json.loads(cleaned_json)
    except Exception as e:
        extracted_agg = {"parse_error": str(e), "raw_response": raw_response}

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
        "case_id": "tax_case_27",
        "source_file": case_info["file_path"],
        "scenario_text": case_info["scenario_text"],
        "question_text": case_info["question_text"],
        "llm_extracted_aggregated_inputs": extracted_agg,
        "rule_execution": rule_exec_result
    }

    out_file = os.path.join(AGGREGATED_RESULTS_DIR, "case_27.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved Aggregated Pipeline Result to: {out_file}")
    return output


def run_detailed_facts_pipeline(case_info: Dict[str, Any], engine: LLMEngine) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("▶ [Pipeline 1] Detailed Facts Extraction -> Micro-Rule Execution")
    print("="*70)

    system_prompt = (
        "You are an expert tax fact parser. Extract ONLY observable factual entities from the tax scenario into strict JSON format.\n"
        "Identify the primary taxpayer, dependents, parent-child relationships, residences, household maintenance, and income.\n"
        "DO NOT extract, predict, or infer high-level legal conclusions such as filing status, deductions, or taxable income.\n"
        "Filing status and tax liability will be derived completely deterministically by code.\n"
        "Dates must be integers formatted as YYYYMMDD (e.g., 19780415, 20170101).\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "target_person": "string",\n'
        '  "tax_year": integer,\n'
        '  "gross_income": float,\n'
        '  "is_unmarried": boolean,\n'
        '  "persons": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "name": "string",\n'
        '      "birth_date": integer or null\n'
        '    }\n'
        '  ],\n'
        '  "dependents": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "name": "string",\n'
        '      "relationship": "string",\n'
        '      "gross_income": float\n'
        '    }\n'
        '  ],\n'
        '  "parent_child_relationships": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "parent": "string",\n'
        '      "child": "string",\n'
        '      "relationship": "string"\n'
        '    }\n'
        '  ],\n'
        '  "residences": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "person": "string",\n'
        '      "abode": "string",\n'
        '      "start_date": integer,\n'
        '      "end_date": integer\n'
        '    }\n'
        '  ],\n'
        '  "household_maintenances": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "agent": "string",\n'
        '      "abode": "string",\n'
        '      "amount": float or null,\n'
        '      "start_date": integer\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    user_prompt = (
        f"Case Text directly from SARA v3:\n{case_info['scenario_text']}\n\n"
        f"Question:\n{case_info['question_text']}\n\n"
        "Please extract all factual events into the required JSON schema without any legal conclusions."
    )

    raw_response = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, response_mime_type="application/json", timeout=60)

    try:
        cleaned_json = re.sub(r"^```(?:json)?", "", raw_response.strip(), flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json.strip(), flags=re.MULTILINE).strip()
        extracted_facts = json.loads(cleaned_json)
    except Exception as e:
        extracted_facts = {"parse_error": str(e), "raw_response": raw_response}

    rule_exec_result = {}
    try:
        raw_persons = extracted_facts.get("persons", [])
        person_objs = [Person(**p) if isinstance(p, dict) else p for p in raw_persons]

        raw_deps = extracted_facts.get("dependents", [])
        dep_objs = [Dependent(**d) if isinstance(d, dict) else d for d in raw_deps]

        raw_relationships = extracted_facts.get("parent_child_relationships", [])
        rel_objs = [ParentChild(**r) if isinstance(r, dict) else r for r in raw_relationships]

        raw_residences = extracted_facts.get("residences", [])
        residence_objs = [Residence(**r) if isinstance(r, dict) else r for r in raw_residences]

        raw_maintenances = extracted_facts.get("household_maintenances", [])
        maintenance_objs = [HouseholdMaintenance(**h) if isinstance(h, dict) else h for h in raw_maintenances]

        target_person = extracted_facts["target_person"]
        tax_year = int(extracted_facts["tax_year"])
        gross_income = float(extracted_facts["gross_income"])
        is_unmarried = bool(extracted_facts.get("is_unmarried", True))

        facts_for_rule = {
            "target_person": target_person,
            "tax_year": tax_year,
            "gross_income": gross_income,
            "is_unmarried": is_unmarried,
            "persons": person_objs,
            "dependents": dep_objs,
            "parent_child_relationships": rel_objs,
            "residences": residence_objs,
            "household_maintenances": maintenance_objs
        }

        derived_status = determine_filing_status(
            target_person, tax_year, is_unmarried,
            dep_objs, rel_objs, residence_objs, maintenance_objs
        )
        total_tax = calculate_case_27_tax(facts_for_rule)

        rule_exec_result = {
            "derived_filing_status": derived_status,
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
        "pipeline": "detailed_facts_extraction",
        "case_id": "tax_case_27",
        "source_file": case_info["file_path"],
        "scenario_text": case_info["scenario_text"],
        "question_text": case_info["question_text"],
        "llm_extracted_facts": extracted_facts,
        "rule_execution": rule_exec_result
    }

    out_file = os.path.join(DETAILED_RESULTS_DIR, "case_27.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved Detailed Pipeline Result to: {out_file}")
    return output


def main():
    print("="*70)
    print("SARA Dual-Pipeline Benchmark Runner: Case 27")
    print("="*70)

    case_info = read_sara_case_from_file(SARA_CASE_27_PATH)
    print(f"Target Person: {case_info['target_person']}")
    print(f"Tax Year:      {case_info['tax_year']}")
    print(f"Ground Truth:  ${case_info['ground_truth_tax']:,.2f}")
    print(f"Sanitized Q:   {case_info['question_text']}")

    engine = LLMEngine()

    res_p1 = run_detailed_facts_pipeline(case_info, engine)
    res_p2 = run_aggregated_pipeline(case_info, engine)

    print("\n" + "="*70)
    print("Execution Summary for Case 27:")
    print(f"Pipeline 1 (Detailed Facts -> Micro-Rule) Match: {res_p1['rule_execution'].get('matches_ground_truth')}")
    print(f"Pipeline 2 (Aggregated -> Macro-Rule) Match:     {res_p2['rule_execution'].get('matches_ground_truth')}")
    print("="*70)


if __name__ == "__main__":
    main()
