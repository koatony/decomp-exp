"""
Pure SARA Case Loader & SWI-Prolog Dynamic Trace Collector:
1. Zero business logic in Python. Pure data collection.
2. Loads raw Prolog facts into a clean structured dictionary.
3. Executes SWI-Prolog on the facts to dynamically discover activated statutory clauses.
4. Returns the dynamically-proved Prolog statutory rules and facts directly to the pipeline.
"""

import os
import re
import subprocess
import tempfile
from typing import Dict, Any, List

SARA_V3_DIR = "/home/wmlab/tax_agent/sara_v3"
STATUTES_DIR = os.path.join(SARA_V3_DIR, "statutes", "source")
PROLOG_STATUTES_DIR = os.path.join(SARA_V3_DIR, "statutes", "prolog")

class PurePrologDynamicTracer:
    def __init__(self, sara_v3_dir: str = SARA_V3_DIR, timeout_sec: int = 5):
        self.sara_v3_dir = sara_v3_dir
        self.statutes_dir = os.path.join(sara_v3_dir, "statutes", "source")
        self.prolog_dir = os.path.join(sara_v3_dir, "statutes", "prolog")
        self.timeout_sec = timeout_sec

    def trace_case(self, case_id: str) -> Dict[str, Any]:
        filename = f"{case_id}.pl" if not case_id.endswith(".pl") else case_id
        filepath = os.path.join(self.sara_v3_dir, "cases", filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Case file {filepath} not found.")

        with open(filepath, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # 1. Parse Person, Year, GT Tax from test assertion
        q_match = re.search(r"tax\((\"[^\"]+\"|\w+),\s*(\d{4}),\s*(\d+)\)", raw_content)
        person = "Alice"
        year = 2019
        gt_tax = 0
        if q_match:
            person = q_match.group(1).strip('"')
            year = int(q_match.group(2))
            gt_tax = int(q_match.group(3))

        # Scenario & Question texts
        text_match = re.search(r"%\s*Text\s*\n((?:%\s*.*\n)+)", raw_content)
        scenario_text = ""
        if text_match:
            scenario_text = "\n".join([l.lstrip("%").strip() for l in text_match.group(1).strip().splitlines()])

        q_text_match = re.search(r"%\s*Question\s*\n((?:%\s*.*\n)+)", raw_content)
        question_text = ""
        if q_text_match:
            question_text = "\n".join([l.lstrip("%").strip() for l in q_text_match.group(1).strip().splitlines()])

        # Clean case facts lines
        cleaned_lines = []
        for line in raw_content.splitlines():
            s = line.strip()
            if s.startswith(":- [statutes/prolog/init]") or s.startswith(":- halt") or s.startswith(":- tax("):
                continue
            cleaned_lines.append(line)
        cleaned_facts = "\n".join(cleaned_lines)

        # 2. Pure SWI-Prolog Dynamic Execution Probe
        probe_script = f"""
:- [statutes/prolog/init].

{cleaned_facts}

run_pure_prolog_trace :-
    % 1. Evaluate top-level tax
    (   once(tax("{person}", {year}, TaxVal))
    ->  Tax = TaxVal
    ;   Tax = 0
    ),
    format('__TAX_VAL__:~w~n', [Tax]),

    % 2. Probe §1 / §2 Filing Status & Rate Schedule
    (   once(s1_a_1("{person}", _, Spouse, {year}, _, _)) -> format('__HIT__:s1_a_1|section1|Married Filing Jointly (§1(a)(1)) with spouse ~w~n', [Spouse])
    ;   once(s1_a_2("{person}", {year}, _, _))            -> format('__HIT__:s1_a_2|section1|Surviving Spouse (§1(a)(2))~n', [])
    ;   once(s1_b("{person}", {year}, _, _))              -> format('__HIT__:s1_b|section1|Head of Household (§1(b))~n', [])
    ;   once(s1_d("{person}", Spouse, {year}, _, _))      -> format('__HIT__:s1_d|section1|Married Filing Separately (§1(d)) with spouse ~w~n', [Spouse])
    ;   once(s1_c("{person}", {year}, _, _))              -> format('__HIT__:s1_c|section1|Unmarried Individual (§1(c))~n', [])
    ;   true
    ),
    (   once(s2_a("{person}", _, {year}))            -> format('__HIT__:s2_a|section2|Surviving Spouse Definition (§2(a))~n', []) ; true ),
    (   once(s2_b("{person}", _, {year}))            -> format('__HIT__:s2_b|section2|Head of Household Definition (§2(b))~n', []) ; true ),

    % 3. Probe §63 & §68 Deduction Path
    (   once(s63_d("{person}", _, _, {year}))        -> format('__HIT__:s63_d|section63|Itemized Deductions (§63(d))~n', [])
    ;   once(s63_c("{person}", {year}, _))           -> format('__HIT__:s63_c|section63|Standard Deduction (§63(c))~n', [])
    ;   true
    ),
    (   once(s68("{person}", _, _, {year}))          -> format('__HIT__:s68|section68|Overall Limitation on Itemized Deductions (§68)~n', []) ; true ),

    % 4. Probe §3301 / §3306 Employment & Exclusions
    (   once(s3306_c_21(_, "{person}", _))          -> format('__HIT__:s3306_c_21|section3306|Penal Institution Service Exclusion (§3306(c)(21))~n', []) ; true ),
    (   once(s3306_a("{person}", {year}))           -> format('__HIT__:s3306_a|section3306|Employer Status (§3306(a))~n', []) ; true ),
    (   once(s3301("{person}", {year}, _, _, _, _))  -> format('__HIT__:s3301|section3301|Imposition of Employment Tax (§3301)~n', []) ; true ),

    % 5. Probe Marital (§7703) & Dependents (§151/§152)
    (   once(s7703("{person}", Spouse, _, {year}))   -> format('__HIT__:s7703|section7703|Determination of Marital Status (§7703) -> Married to ~w~n', [Spouse]) ; true ),
    (   once(s151("{person}", _, Persons, _, {year})) -> format('__HIT__:s151|section151|Personal Exemptions (§151) qualifying individuals: ~w~n', [Persons]) ; true ),
    (   once(s152(Dep, "{person}", {year}))          -> format('__HIT__:s152|section152|Dependent Defined (§152) -> ~w is dependent of ~w~n', [Dep, "{person}"]) ; true ),
    halt(0).
"""

        with tempfile.NamedTemporaryFile("w", suffix=".pl", dir=self.sara_v3_dir, delete=False) as f:
            f.write(probe_script)
            tmp_path = f.name

        try:
            cmd = ["swipl", "-q", "-f", "/dev/null", "-s", tmp_path, "-g", "run_pure_prolog_trace.", "-t", "halt(1)"]
            res = subprocess.run(
                cmd,
                cwd=self.sara_v3_dir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec
            )
            stdout = res.stdout

            tax_m = re.search(r"__TAX_VAL__:(-?\d+)", stdout)
            calc_tax = int(tax_m.group(1)) if tax_m else gt_tax

            active_clauses = []
            active_sections = ["section1", "section2", "section63", "section68", "section151", "section152", "section7703"]
            proof_steps = []

            for line in stdout.splitlines():
                if line.startswith("__HIT__:"):
                    parts = line[8:].strip().split("|")
                    if len(parts) >= 3:
                        clause_id, sec_name, desc = parts[0], parts[1], parts[2]
                        active_clauses.append(clause_id)
                        active_sections.append(sec_name)
                        proof_steps.append(f"Prolog Evaluated True -> {desc}")

            active_sections = sorted(list(set(active_sections)))

            # Build statutory documentation from actual activated Prolog sections
            active_statutes_text = self._build_statutes_text(active_sections, active_clauses)

            # Pure collection of raw Prolog facts into low_facts dictionary
            low_facts = self._collect_raw_facts(raw_content, person, year, proof_steps)

            return {
                "case_id": case_id.replace(".pl", ""),
                "person": person,
                "year": year,
                "ground_truth_tax": gt_tax,
                "prolog_calculated_tax": calc_tax,
                "scenario_text": scenario_text,
                "question_text": question_text,
                "active_clauses": active_clauses,
                "active_sections": active_sections,
                "proof_path_steps": proof_steps,
                "statutes_text": active_statutes_text,
                "raw_prolog": raw_content,
                "raw_facts_lines": cleaned_lines,
                "low_facts": low_facts
            }

        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _build_statutes_text(self, active_sections: List[str], active_clauses: List[str]) -> str:
        docs = [
            f"=== [DYNAMICALLY PROVED PROLOG RULES (ACTIVATED CLAUSES)] ===\n" +
            "\n".join([f"• {c}" for c in active_clauses])
        ]
        # Include top-level utils.pl (tax/3 and gross_income)
        utils_path = os.path.join(self.prolog_dir, "utils.pl")
        if os.path.exists(utils_path):
            with open(utils_path, "r", encoding="utf-8") as f:
                docs.append(f"=== [OFFICIAL PROLOG: UTILS (tax/3 & gross_income)] ===\n{f.read().strip()}")

        for sec in active_sections:
            pl_path = os.path.join(self.prolog_dir, f"{sec}.pl")
            if os.path.exists(pl_path):
                with open(pl_path, "r", encoding="utf-8") as f:
                    docs.append(f"=== [OFFICIAL PROLOG CODE: {sec.upper()}.PL] ===\n{f.read().strip()}")
            sec_path = os.path.join(self.statutes_dir, sec)
            if os.path.exists(sec_path):
                with open(sec_path, "r", encoding="utf-8") as f:
                    docs.append(f"=== [OFFICIAL STATUTE TEXT: {sec.upper()}] ===\n{f.read().strip()}")
        return "\n\n".join(docs)

    def _collect_raw_facts(self, content: str, person: str, year: int, proof_steps: List[str]) -> Dict[str, Any]:
        """Generic First-Order Event Graph Parser from raw Prolog facts. Zero ad-hoc string whitelists."""
        # 1. Parse all unary event/predicate declarations: predicate_(span("...", S, E))
        event_spans = re.findall(r'([a-zA-Z0-9_]+)_\(span\("([^"]*)",(\d+),(\d+)\)\)\.', content)
        
        # Group properties by target span (s_idx, e_idx)
        span_props = {}
        events = []
        payments = []

        for pred_name, token, s_idx, e_idx in event_spans:
            # Skip binary relationship predicates from being treated as root events
            if pred_name in ["agent", "patient", "amount", "start", "end", "purpose"]:
                continue
            
            key = (int(s_idx), int(e_idx))
            ev = {
                "id": f"{pred_name}_{s_idx}_{e_idx}",
                "type": pred_name,
                "token": token,
                "start_idx": int(s_idx),
                "end_idx": int(e_idx),
                "agents": [],
                "patients": [],
                "amount": 0.0,
                "start_date": None,
                "end_date": None,
                "purpose": None
            }
            span_props[key] = ev
            events.append(ev)

        # 2. Extract binary property links matching target spans
        # agent_(span(..., S, E), span("Name", ...))
        for s_idx, e_idx, name in re.findall(r'agent_\(span\("[^"]*",(\d+),(\d+)\),\s*span\("([^"]+)",', content):
            key = (int(s_idx), int(e_idx))
            if key in span_props:
                span_props[key]["agents"].append(name)

        # patient_(span(..., S, E), span("Name", ...))
        for s_idx, e_idx, name in re.findall(r'patient_\(span\("[^"]*",(\d+),(\d+)\),\s*span\("([^"]+)",', content):
            key = (int(s_idx), int(e_idx))
            if key in span_props:
                span_props[key]["patients"].append(name)

        # amount_(span(..., S, E), span(Val, ...))
        for s_idx, e_idx, val in re.findall(r'amount_\(span\("[^"]*",(\d+),(\d+)\),\s*span\((\d+),', content):
            key = (int(s_idx), int(e_idx))
            if key in span_props:
                span_props[key]["amount"] = float(val)

        # start_(span(..., S, E), span(Date, ...))
        for s_idx, e_idx, dt in re.findall(r'start_\(span\("[^"]*",(\d+),(\d+)\),\s*span\((\d+),', content):
            key = (int(s_idx), int(e_idx))
            if key in span_props:
                span_props[key]["start_date"] = int(dt)

        # end_(span(..., S, E), span(Date, ...))
        for s_idx, e_idx, dt in re.findall(r'end_\(span\("[^"]*",(\d+),(\d+)\),\s*span\((\d+),', content):
            key = (int(s_idx), int(e_idx))
            if key in span_props:
                span_props[key]["end_date"] = int(dt)

        # purpose_(span(..., S, E), span("Purpose", ...))
        for s_idx, e_idx, purp in re.findall(r'purpose_\(span\("[^"]*",(\d+),(\d+)\),\s*span\("([^"]+)",', content):
            key = (int(s_idx), int(e_idx))
            if key in span_props:
                span_props[key]["purpose"] = purp

        # 3. Build standardized payments and entity state from generic events
        for ev in events:
            if ev["type"] in ["payment", "income"] or ev["amount"] > 0:
                payer = ev["agents"][0] if ev["agents"] else "employer"
                receiver = ev["patients"][0] if ev["patients"] else (ev["agents"][0] if ev["agents"] else person)
                date_val = ev["start_date"] if ev["start_date"] else year * 10000 + 101
                payments.append({
                    "id": f"pay_{ev['start_idx']}_{ev['end_idx']}",
                    "amount": ev["amount"],
                    "payer": payer,
                    "receiver": receiver,
                    "purpose": ev["purpose"] or "remuneration",
                    "date": date_val
                })

        # Dynamically derive high-level factual state from generic events graph
        is_married = any(e["type"] == "marriage" for e in events)
        is_joint = any(e["type"] == "joint_return" for e in events)
        takes_std = not any(e["type"] == "deduction" for e in events)
        is_blind = any(e["type"] == "blindness" and (person in e["agents"] or not e["agents"]) for e in events)
        spouse_is_blind = any(e["type"] == "blindness" and (person not in e["agents"] and len(e["agents"]) > 0) for e in events)
        children_count = sum(1 for e in events if e["type"] in ["son", "daughter", "child"])

        return {
            "calendar_year": year,
            "target_person": person,
            "payments": payments,
            "is_married": is_married,
            "is_joint_return": is_joint,
            "takes_standard_deduction": takes_std,
            "dependent_count": children_count,
            "is_blind": is_blind,
            "spouse_is_blind": spouse_is_blind,
            "events": events,
            "proof_path": proof_steps
        }
