# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for CreditSink running-minimum semantics.

Covers first-observation capture, minimum-value retention, negative
(overdrawn) balances, and rejection of non-finite values (nan / ±inf).
"""

import pytest

from blockscout_mcp_server.pro_api_key_context import CreditSink


def test_credit_sink_first_observation_sets_value():
    sink = CreditSink()
    assert sink.remaining is None
    sink.record(5000.0)
    assert sink.remaining == 5000.0


def test_credit_sink_minimum_semantics_lower_second():
    """6000 then 4000 → 4000 (lower second value wins)."""
    sink = CreditSink()
    sink.record(6000.0)
    sink.record(4000.0)
    assert sink.remaining == 4000.0


def test_credit_sink_minimum_semantics_higher_second():
    """4000 then 6000 → 4000 (minimum is retained)."""
    sink = CreditSink()
    sink.record(4000.0)
    sink.record(6000.0)
    assert sink.remaining == 4000.0


def test_credit_sink_negative_value_captured():
    """Negative values (overdrawn paid account) are stored as-is."""
    sink = CreditSink()
    sink.record(-12.5)
    assert sink.remaining == -12.5


def test_credit_sink_negative_beats_positive():
    """A later negative value lowers the stored minimum below zero."""
    sink = CreditSink()
    sink.record(100.0)
    sink.record(-5.0)
    assert sink.remaining == -5.0


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_credit_sink_ignores_non_finite_values(non_finite):
    """nan / ±inf are rejected at the door: the sink stays at its prior state.

    float("-Infinity") would otherwise crash a downstream int() display
    conversion, and a nan/-inf recorded first would poison the running minimum.
    """
    sink = CreditSink()
    sink.record(non_finite)
    assert sink.remaining is None


@pytest.mark.parametrize("non_finite", [float("nan"), float("-inf")])
def test_credit_sink_non_finite_does_not_poison_minimum(non_finite):
    """Regression: a non-finite observation first must not block a later real
    low value from being recorded.

    Without the finite guard, `value < self.remaining` is always False once
    `remaining` is nan/-inf, so the genuine 2000 would be dropped and the
    low-credits advisory silently suppressed for the whole invocation.
    """
    sink = CreditSink()
    sink.record(non_finite)
    sink.record(2000.0)
    assert sink.remaining == 2000.0
