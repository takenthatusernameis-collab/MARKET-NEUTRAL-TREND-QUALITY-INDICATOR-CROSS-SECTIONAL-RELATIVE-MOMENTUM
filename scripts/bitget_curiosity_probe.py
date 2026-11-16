#!/usr/bin/env python3
"""Run the Bitget public-data screen independently, without changing provider priority."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "perp_priority_probe", ROOT / "scripts" / "probe_perp_priority.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load the existing read-only exchange probe")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

result: dict[str, Any] = module.probe_bitget()
checks = result.get("checks", {})
required = ("instruments", "cross_margin", "contract_precision", "sampled_market_data")
technical_pass = all(checks.get(name) is True for name in required)
report = {
    "report_utc": datetime.now(UTC).isoformat(),
    "purpose": "curiosity_only_not_provider_selection",
    "priority_order_unchanged": ["polymarket", "mexc", "bitget"],
    "exchange": "bitget",
    "technical_public_data_pass": technical_pass,
    "required_checks": {name: checks.get(name) for name in required},
    "result": result,
    "safety": {
        "credentials_used": False,
        "private_endpoints_used": False,
        "orders_submitted": 0,
        "wallet_used": False,
        "proxy_or_vpn_used": False,
    },
}
output = json.dumps(report, indent=2, default=str)
print(output)
Path("bitget-curiosity-report.json").write_text(output + "\n", encoding="utf-8")
