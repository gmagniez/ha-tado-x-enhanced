"""Static regression checks for DEV-004 default selection; no HA runtime required."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tado_x"

def test_default_consistency():
    const = (ROOT / "const.py").read_text()
    assert 'DEFAULT_SUPPLEMENTARY_POLL_MULTIPLIER: Final = 5' in const
    for name in ("__init__.py", "config_flow.py", "coordinator.py"):
        source = (ROOT / name).read_text()
        ast.parse(source)
        assert "DEFAULT_SUPPLEMENTARY_POLL_MULTIPLIER" in source
    flow = (ROOT / "config_flow.py").read_text()
    assert "current_multiplier = DEFAULT_SUPPLEMENTARY_POLL_MULTIPLIER" in flow
    for name in ("strings.json", "translations/en.json"):
        value = json.loads((ROOT / name).read_text())
        description = value["options"]["step"]["init"]["sections"]["supplementary_polling"]["data_description"]["supplementary_poll_multiplier"]
        assert "Higher multipliers mean less frequent updates and fewer API requests" in description
        assert "Default: 5×" not in description and "Default 5×." not in description
