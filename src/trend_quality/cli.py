"""Command-line entry points for safe diagnostics."""
from __future__ import annotations

import argparse
import json
import sys

from .bybit_api import BybitAPIError, BybitPublicClient


def public_api_smoke() -> int:
    client = BybitPublicClient()
    try:
        server_time = client.server_time_ms()
        instruments = client.eligible_linear_usdt_perpetuals()
    except BybitAPIError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": "SUCCESS",
                "mode": "public_data_only",
                "server_time_ms": server_time,
                "eligible_linear_usdt_perpetual_count": len(instruments),
                "orders_submitted": 0,
                "credentials_used": False,
            },
            indent=2,
        )
    )
    return 0 if instruments else 2


def main() -> int:
    parser = argparse.ArgumentParser(prog="trend-quality")
    parser.add_argument("command", choices=["public-api-smoke"])
    args = parser.parse_args()
    if args.command == "public-api-smoke":
        return public_api_smoke()
    return 2


if __name__ == "__main__":
    sys.exit(main())
