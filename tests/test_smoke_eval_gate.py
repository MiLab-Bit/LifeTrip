"""Negative controls: a successful HTTP response must not hide failed eval cases."""
from __future__ import annotations

import pytest

from smoke import require_complete_eval


def test_eval_gate_accepts_complete_pass():
    assert require_complete_eval(
        {"total": 2, "passed": 2,
         "results": [{"id": "F01", "passed": True}, {"id": "E01", "passed": True}]}
    ) == "eval 2/2 通过，全绿"


@pytest.mark.parametrize("payload", [
    {"total": 2, "passed": 1, "results": [
        {"id": "F01", "passed": True}, {"id": "E01", "passed": False}]},
    {"total": 2, "passed": 2, "results": [{"id": "F01", "passed": True}]},
    {"total": 0, "passed": 0, "results": []},
    {"total": 1, "passed": 0, "results": [{"id": "E01", "passed": False}]},
])
def test_eval_gate_rejects_failing_or_incomplete_results(payload):
    with pytest.raises(AssertionError):
        require_complete_eval(payload)
