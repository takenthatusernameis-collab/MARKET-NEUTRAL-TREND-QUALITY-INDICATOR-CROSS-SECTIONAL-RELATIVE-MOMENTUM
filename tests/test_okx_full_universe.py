import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_okx_eea_universe.py"
)
_SPEC = importlib.util.spec_from_file_location("okx_eea_full_universe", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
assert isinstance(_MODULE, ModuleType)
metadata_check = _MODULE.metadata_check
positive_decimal = _MODULE.positive_decimal


def test_positive_decimal_rejects_zero_negative_and_invalid_values() -> None:
    assert positive_decimal("0.01")
    assert positive_decimal(1)
    assert not positive_decimal("0")
    assert not positive_decimal("-1")
    assert not positive_decimal("NaN")
    assert not positive_decimal("invalid")
    assert not positive_decimal(None)


def test_metadata_check_accepts_complete_linear_usdt_swap() -> None:
    row = {
        "instId": "BTC-USDT-SWAP",
        "instFamily": "BTC-USDT",
        "ctType": "linear",
        "ctVal": "0.01",
        "ctMult": "1",
        "ctValCcy": "BTC",
        "tickSz": "0.1",
        "lotSz": "0.01",
        "minSz": "0.01",
        "maxLmtSz": "1000",
        "maxMktSz": "500",
        "settleCcy": "USDT",
        "state": "live",
        "instType": "SWAP",
        "ruleType": "normal",
    }
    assert metadata_check(row) == []


def test_metadata_check_flags_missing_and_nonpositive_contract_rules() -> None:
    row = {
        "instId": "BTC-USDT-SWAP",
        "instFamily": "BTC-USDT",
        "ctType": "linear",
        "ctVal": "0",
        "ctMult": "1",
        "ctValCcy": "BTC",
        "tickSz": "0.1",
        "lotSz": "0.01",
        "minSz": "0.01",
        "maxLmtSz": "",
        "maxMktSz": "500",
        "settleCcy": "USDT",
        "state": "live",
        "instType": "SWAP",
        "ruleType": "normal",
    }
    assert "INVALID_ctVal" in metadata_check(row)
    assert "maxLmtSz" in metadata_check(row)
