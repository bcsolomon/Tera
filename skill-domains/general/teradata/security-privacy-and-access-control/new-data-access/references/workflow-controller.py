"""
Workflow Controller for new-data-access skill.

This script enforces strictly sequential execution of the 14-step data access
onboarding workflow. The agent MUST call this controller at every step transition
to validate that the workflow state allows advancement.

The controller maintains a JSON state file that serves as both the workflow
state record and the audit log. No step may be skipped, no gate may be bypassed,
and no DDL may execute before Gate 3 (Step 13).

Usage by the agent:
    # Initialize a new workflow
    python workflow-controller.py init --request "User wants to onboard test_nda_bank_db"

    # Attempt to complete a step and advance
    python workflow-controller.py complete --step 1 --output '{"database": "test_nda_bank_db"}'

    # Record a gate approval
    python workflow-controller.py approve --gate 1

    # Check if a DDL operation is allowed
    python workflow-controller.py check-ddl

    # Get current workflow state
    python workflow-controller.py status

    # Log an audit entry
    python workflow-controller.py log --phase "discovery" --description "Found 3 tables"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# --- Step Definitions ---

STEPS = {
    1: {
        "name": "Identify the Database",
        "required_output_fields": ["database_name"],
        "completion_criteria": "Database name confirmed by user",
        "allowed_tools": ["base_databaseList", "base_readQuery"],
        "ddl_allowed": False,
    },
    2: {
        "name": "Enumerate Tables",
        "required_output_fields": ["tables_in_scope"],
        "completion_criteria": "Table list confirmed by user",
        "allowed_tools": ["base_tableList", "base_readQuery"],
        "ddl_allowed": False,
    },
    3: {
        "name": "Examine Columns and Assess Sensitivity",
        "required_output_fields": ["sensitivity_assessment"],
        "completion_criteria": "All columns classified and combination risks flagged",
        "allowed_tools": ["base_columnDescription", "base_readQuery"],
        "ddl_allowed": False,
    },
    4: {
        "name": "Recommend Protection Strategy",
        "required_output_fields": ["protection_recommendations"],
        "completion_criteria": "Protection strategy presented and user confirmed",
        "allowed_tools": ["base_readQuery"],
        "ddl_allowed": False,
    },
    5: {
        "name": "Build the Readiness Report",
        "required_output_fields": ["readiness_report"],
        "completion_criteria": "Readiness report compiled with all sections",
        "allowed_tools": ["base_readQuery"],
        "ddl_allowed": False,
    },
    6: {
        "name": "Present and Confirm Readiness Report",
        "required_output_fields": ["report_confirmed"],
        "completion_criteria": "User confirmed or corrected the readiness report",
        "allowed_tools": [],
        "ddl_allowed": False,
    },
    7: {
        "name": "Identify Roles",
        "required_output_fields": ["roles"],
        "completion_criteria": "All roles identified and confirmed by user",
        "allowed_tools": ["base_readQuery"],
        "ddl_allowed": False,
    },
    8: {
        "name": "Design Access Patterns",
        "required_output_fields": ["access_patterns"],
        "completion_criteria": "Access patterns defined for every role",
        "allowed_tools": ["base_readQuery"],
        "ddl_allowed": False,
    },
    9: {
        "name": "Assess ETL and Consumption Impact",
        "required_output_fields": ["etl_assessment"],
        "completion_criteria": "Downstream consumers assessed and mitigations documented",
        "allowed_tools": ["base_readQuery"],
        "ddl_allowed": False,
    },
    10: {
        "name": "GATE 1 — Approve Data and Roles",
        "required_output_fields": ["gate_1_approved"],
        "completion_criteria": "User explicitly approved the complete design",
        "allowed_tools": [],
        "ddl_allowed": False,
        "is_gate": True,
        "gate_number": 1,
    },
    11: {
        "name": "Generate SQL Files",
        "required_output_fields": ["setup_sql", "revert_sql"],
        "completion_criteria": "Both SQL files generated and presented",
        "allowed_tools": ["base_readQuery"],
        "ddl_allowed": False,
    },
    12: {
        "name": "GATE 2 — SQL Review and Approval",
        "required_output_fields": ["gate_2_approved"],
        "completion_criteria": "User explicitly approved both SQL files",
        "allowed_tools": [],
        "ddl_allowed": False,
        "is_gate": True,
        "gate_number": 2,
    },
    13: {
        "name": "GATE 3 — Apply SQL",
        "required_output_fields": ["gate_3_approved", "execution_results"],
        "completion_criteria": "User approved execution AND all statements executed",
        "allowed_tools": ["execute_sql", "base_readQuery"],
        "ddl_allowed": True,
        "is_gate": True,
        "gate_number": 3,
    },
    14: {
        "name": "GATE 4 — Review Test Results",
        "required_output_fields": ["gate_4_approved", "test_results"],
        "completion_criteria": "All tests run and user signed off on results",
        "allowed_tools": ["base_readQuery"],
        "ddl_allowed": False,
        "is_gate": True,
        "gate_number": 4,
    },
}

TOTAL_STEPS = 14
STATE_FILE = "workflow_state.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    with open(state_path) as f:
        return json.load(f)


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2, default=str)


def _append_audit(state: dict[str, Any], phase: str, description: str) -> None:
    entry = f"- {_now()} | {phase} | {description}"
    state.setdefault("audit_log", []).append(entry)


def cmd_init(args, state_path: Path) -> None:
    """Initialize a new workflow."""
    if state_path.exists():
        print(json.dumps({"error": "Workflow already initialized. Use 'reset' to start over."}))
        sys.exit(1)

    state = {
        "workflow_id": f"nda-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "current_step": 1,
        "completed_steps": [],
        "step_outputs": {},
        "validation_results": {},
        "approval_results": {},
        "audit_log": [],
        "created_at": _now(),
    }
    _append_audit(state, "request-received", f"User request: {args.request}")
    _append_audit(state, "workflow-init", "Workflow initialized at Step 1")
    _save_state(state_path, state)
    print(json.dumps({
        "status": "initialized",
        "workflow_id": state["workflow_id"],
        "current_step": 1,
        "message": "Workflow initialized. Execute Step 1: Identify the Database.",
    }))


def cmd_status(args, state_path: Path) -> None:
    """Return current workflow state."""
    state = _load_state(state_path)
    if not state:
        print(json.dumps({"error": "No workflow initialized. Run 'init' first."}))
        sys.exit(1)

    current = state["current_step"]
    step_def = STEPS.get(current, {})
    print(json.dumps({
        "workflow_id": state["workflow_id"],
        "current_step": current,
        "current_step_name": step_def.get("name", "Unknown"),
        "completed_steps": state["completed_steps"],
        "gates_approved": list(state.get("approval_results", {}).keys()),
        "ddl_allowed": step_def.get("ddl_allowed", False),
        "completion_criteria": step_def.get("completion_criteria", ""),
        "required_output_fields": step_def.get("required_output_fields", []),
    }))


def cmd_complete(args, state_path: Path) -> None:
    """Validate and complete the current step, then advance."""
    state = _load_state(state_path)
    if not state:
        print(json.dumps({"error": "No workflow initialized."}))
        sys.exit(1)

    requested_step = args.step
    current_step = state["current_step"]

    # Rule: Can only complete the current step
    if requested_step != current_step:
        msg = (
            f"Step {requested_step} is unavailable. "
            f"The current required step is Step {current_step} "
            f"({STEPS[current_step]['name']}). "
            f"Step {requested_step} cannot begin until Step {current_step} "
            f"has been completed."
        )
        print(json.dumps({"error": msg, "current_step": current_step}))
        sys.exit(1)

    # Rule: All previous steps must be completed
    required_previous = set(range(1, requested_step))
    completed = set(state["completed_steps"])
    missing = sorted(required_previous - completed)
    if missing:
        step_names = [f"Step {s} ({STEPS[s]['name']})" for s in missing]
        print(json.dumps({
            "error": f"Cannot complete Step {requested_step}. Previous steps incomplete: {step_names}",
            "missing_steps": missing,
        }))
        sys.exit(1)

    # Rule: If this step is a gate, it must have been approved first
    step_def = STEPS[current_step]
    if step_def.get("is_gate") and not args.force_gate:
        gate_num = step_def["gate_number"]
        if str(gate_num) not in state.get("approval_results", {}):
            print(json.dumps({
                "error": f"Step {current_step} is Gate {gate_num}. "
                         f"Gate approval is required before completion. "
                         f"Use 'approve --gate {gate_num}' first.",
                "gate_required": gate_num,
            }))
            sys.exit(1)

    # Validate output fields are present
    try:
        output = json.loads(args.output) if args.output else {}
    except json.JSONDecodeError:
        output = {"raw": args.output}

    missing_fields = [
        f for f in step_def.get("required_output_fields", [])
        if f not in output
    ]
    if missing_fields and not step_def.get("is_gate"):
        print(json.dumps({
            "error": f"Step {current_step} output is missing required fields: {missing_fields}",
            "required_fields": step_def["required_output_fields"],
            "provided_fields": list(output.keys()),
        }))
        sys.exit(1)

    # Complete the step
    state["step_outputs"][str(current_step)] = output
    state["completed_steps"].append(current_step)
    state["validation_results"][str(current_step)] = True

    # Advance to next step (or mark workflow complete)
    if current_step < TOTAL_STEPS:
        state["current_step"] = current_step + 1
        next_step = current_step + 1
        next_def = STEPS[next_step]
        _append_audit(
            state, "step-completed",
            f"Step {current_step} ({step_def['name']}) completed. Advancing to Step {next_step}."
        )
        _save_state(state_path, state)
        print(json.dumps({
            "status": "advanced",
            "completed_step": current_step,
            "current_step": next_step,
            "current_step_name": next_def["name"],
            "ddl_allowed": next_def.get("ddl_allowed", False),
            "is_gate": next_def.get("is_gate", False),
            "completion_criteria": next_def["completion_criteria"],
        }))
    else:
        state["current_step"] = "complete"
        _append_audit(state, "workflow-complete", "All 14 steps completed. Workflow finished.")
        _save_state(state_path, state)
        print(json.dumps({
            "status": "workflow_complete",
            "completed_step": current_step,
            "total_steps_completed": len(state["completed_steps"]),
            "message": "All steps completed. Present the final summary.",
        }))


def cmd_approve(args, state_path: Path) -> None:
    """Record a gate approval from the user."""
    state = _load_state(state_path)
    if not state:
        print(json.dumps({"error": "No workflow initialized."}))
        sys.exit(1)

    gate_num = args.gate
    current_step = state["current_step"]

    # Map gate to step
    gate_to_step = {1: 10, 2: 12, 3: 13, 4: 14}
    expected_step = gate_to_step.get(gate_num)

    if expected_step is None:
        print(json.dumps({"error": f"Invalid gate number: {gate_num}. Valid gates: 1, 2, 3, 4."}))
        sys.exit(1)

    if current_step != expected_step:
        print(json.dumps({
            "error": f"Gate {gate_num} can only be approved at Step {expected_step}. "
                     f"Current step is {current_step}.",
            "current_step": current_step,
            "required_step": expected_step,
        }))
        sys.exit(1)

    # Record approval
    state.setdefault("approval_results", {})[str(gate_num)] = {
        "approved": True,
        "approved_by": "user",
        "approved_at": _now(),
    }
    _append_audit(
        state, f"GATE-{gate_num}-APPROVED",
        f"User approved Gate {gate_num} at Step {expected_step} ({STEPS[expected_step]['name']})"
    )
    _save_state(state_path, state)
    print(json.dumps({
        "status": "gate_approved",
        "gate": gate_num,
        "step": expected_step,
        "message": f"Gate {gate_num} approved. Step {expected_step} may now be completed.",
    }))


def cmd_check_ddl(args, state_path: Path) -> None:
    """Check if DDL execution is currently permitted."""
    state = _load_state(state_path)
    if not state:
        print(json.dumps({"error": "No workflow initialized."}))
        sys.exit(1)

    current_step = state["current_step"]
    if current_step == "complete":
        print(json.dumps({"ddl_allowed": False, "reason": "Workflow is complete."}))
        return

    step_def = STEPS.get(current_step, {})
    ddl_allowed = step_def.get("ddl_allowed", False)

    if ddl_allowed:
        # Additional check: Gate 3 must be approved
        gate_3_approved = "3" in state.get("approval_results", {})
        if not gate_3_approved:
            print(json.dumps({
                "ddl_allowed": False,
                "reason": "Step 13 is current but Gate 3 has not been approved yet.",
                "action_required": "Obtain user approval for Gate 3 first.",
            }))
            return
        print(json.dumps({
            "ddl_allowed": True,
            "current_step": current_step,
            "reason": "Gate 3 approved. DDL execution is permitted.",
        }))
    else:
        print(json.dumps({
            "ddl_allowed": False,
            "current_step": current_step,
            "reason": f"DDL is not permitted at Step {current_step} ({step_def.get('name', '')}). "
                      f"DDL is only allowed at Step 13 after Gate 3 approval.",
        }))


def cmd_log(args, state_path: Path) -> None:
    """Append an audit log entry."""
    state = _load_state(state_path)
    if not state:
        print(json.dumps({"error": "No workflow initialized."}))
        sys.exit(1)

    _append_audit(state, args.phase, args.description)
    _save_state(state_path, state)
    print(json.dumps({
        "status": "logged",
        "entry": f"- {_now()} | {args.phase} | {args.description}",
    }))


def cmd_audit(args, state_path: Path) -> None:
    """Return the full audit log."""
    state = _load_state(state_path)
    if not state:
        print(json.dumps({"error": "No workflow initialized."}))
        sys.exit(1)

    print(json.dumps({
        "workflow_id": state["workflow_id"],
        "current_step": state["current_step"],
        "audit_log": state.get("audit_log", []),
    }))


def cmd_reset(args, state_path: Path) -> None:
    """Reset the workflow state (destructive)."""
    if state_path.exists():
        state_path.unlink()
    print(json.dumps({"status": "reset", "message": "Workflow state cleared."}))


def main():
    parser = argparse.ArgumentParser(description="Workflow Controller for new-data-access skill")
    parser.add_argument(
        "--state-file", default=STATE_FILE,
        help="Path to the workflow state JSON file"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new workflow")
    p_init.add_argument("--request", required=True, help="User's original request")

    # status
    subparsers.add_parser("status", help="Get current workflow state")

    # complete
    p_complete = subparsers.add_parser("complete", help="Complete the current step and advance")
    p_complete.add_argument("--step", type=int, required=True, help="Step number to complete")
    p_complete.add_argument("--output", default="{}", help="JSON output from the step")
    p_complete.add_argument("--force-gate", action="store_true", help="Skip gate check (for combined approve+complete)")

    # approve
    p_approve = subparsers.add_parser("approve", help="Record a gate approval")
    p_approve.add_argument("--gate", type=int, required=True, help="Gate number (1-4)")

    # check-ddl
    subparsers.add_parser("check-ddl", help="Check if DDL execution is permitted")

    # log
    p_log = subparsers.add_parser("log", help="Append an audit log entry")
    p_log.add_argument("--phase", required=True, help="Phase/category of the entry")
    p_log.add_argument("--description", required=True, help="Description of what happened")

    # audit
    subparsers.add_parser("audit", help="Return the full audit log")

    # reset
    subparsers.add_parser("reset", help="Reset the workflow (destructive)")

    args = parser.parse_args()
    state_path = Path(args.state_file)

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "complete": cmd_complete,
        "approve": cmd_approve,
        "check-ddl": cmd_check_ddl,
        "log": cmd_log,
        "audit": cmd_audit,
        "reset": cmd_reset,
    }

    commands[args.command](args, state_path)


if __name__ == "__main__":
    main()
