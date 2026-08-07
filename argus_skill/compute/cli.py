"""JSON-only command line interface for the dry-run compute broker."""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from .broker import BrokerPlanError, ComputeBroker, _read_json_object
from .budget import BudgetError, BudgetLedger, BudgetPolicy
from .verification import verify_compute_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="argus-compute")
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init-budget")
    initialize.add_argument("--ledger", type=Path, required=True)

    plan = commands.add_parser("plan")
    plan.add_argument("--project-root", type=Path, required=True)
    plan.add_argument("--ledger", type=Path)
    plan.add_argument("--request", type=Path, required=True)
    plan.add_argument("--price-snapshot", type=Path)
    plan.add_argument("--capabilities", type=Path)

    status = commands.add_parser("status")
    status.add_argument("--project-root", type=Path, required=True)
    status.add_argument("--job-key", required=True)

    settle = commands.add_parser("settle")
    settle.add_argument("--ledger", type=Path, required=True)
    settle.add_argument("--reservation-id", required=True)
    settle.add_argument("--actual-usd", required=True)

    release = commands.add_parser("release")
    release.add_argument("--ledger", type=Path, required=True)
    release.add_argument("--reservation-id", required=True)
    release.add_argument("--reason", required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--project-root", type=Path, required=True)
    verify.add_argument("--plan", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    return parser


def _emit(payload: dict[str, object], *, stream=None) -> None:
    target = sys.stdout if stream is None else stream
    target.write(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "init-budget":
            ledger = BudgetLedger.initialize(args.ledger, BudgetPolicy())
            snapshot = ledger.snapshot()
            _emit(
                {
                    "status": "initialized",
                    "ledger": str(ledger.path),
                    "policy": snapshot.policy.to_dict(),
                }
            )
        elif args.command == "plan":
            raw = _read_json_object(args.request, label="ComputeRequest")
            ticket = ComputeBroker(
                project_root=args.project_root,
                ledger_path=args.ledger,
            ).plan(
                raw,
                price_snapshot_path=args.price_snapshot,
                capabilities_path=args.capabilities,
            )
            _emit(ticket.to_dict())
        elif args.command == "status":
            ticket = ComputeBroker(project_root=args.project_root).status(args.job_key)
            _emit(ticket.to_dict())
        elif args.command == "settle":
            settlement = BudgetLedger(args.ledger).settle(
                args.reservation_id,
                actual_cost_usd=Decimal(str(args.actual_usd)),
            )
            _emit(
                {
                    "status": "settled",
                    "reservation_id": settlement.reservation_id,
                    "job_key": settlement.job_key,
                    "actual_cost_usd": str(settlement.actual_cost_usd),
                }
            )
        elif args.command == "release":
            BudgetLedger(args.ledger).release(
                args.reservation_id, reason=args.reason
            )
            _emit(
                {
                    "status": "released",
                    "reservation_id": args.reservation_id,
                }
            )
        elif args.command == "verify":
            plan = _read_json_object(args.plan, label="compute plan")
            manifest = _read_json_object(args.manifest, label="run manifest")
            report = verify_compute_run(
                project_root=args.project_root,
                plan=plan,
                manifest=manifest,
            )
            _emit(report.to_dict())
            return 0 if report.accepted else 3
        else:  # pragma: no cover - argparse enforces the command set
            raise BrokerPlanError(f"unsupported command: {args.command}")
        return 0
    except (BudgetError, BrokerPlanError, ValueError) as exc:
        # Exception messages carry only validated field names and safe paths;
        # raw request values are never echoed here.
        _emit({"status": "error", "error": str(exc)}, stream=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
