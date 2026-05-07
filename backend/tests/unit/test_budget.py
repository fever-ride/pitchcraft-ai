"""Tests for RequestBudget enforcement."""
import time

import pytest

from backend.core.graph.state import BudgetExceeded, RequestBudget


def test_budget_initial_state():
    budget = RequestBudget()
    assert budget.current_llm_calls == 0
    assert budget.current_search_calls == 0


def test_budget_use_llm_call_increments():
    budget = RequestBudget()
    budget.use_llm_call()
    assert budget.current_llm_calls == 1


def test_budget_llm_limit_exceeded():
    budget = RequestBudget(max_llm_calls=2)
    budget.use_llm_call()  # current=1, check 1>=2 → ok
    with pytest.raises(BudgetExceeded, match="LLM call limit"):
        budget.use_llm_call()  # current=2, check 2>=2 → raises


def test_budget_search_limit_exceeded():
    budget = RequestBudget(max_search_calls=2)
    budget.use_search_call()  # current=1, check 1>=2 → ok
    with pytest.raises(BudgetExceeded, match="Search call limit"):
        budget.use_search_call()  # current=2, check 2>=2 → raises


def test_budget_timeout():
    budget = RequestBudget(max_total_seconds=0)
    budget.start_time = time.time() - 1
    with pytest.raises(BudgetExceeded, match="Pipeline timeout"):
        budget.check()


def test_budget_within_limits_no_raise():
    budget = RequestBudget(max_llm_calls=30, max_search_calls=10)
    for _ in range(10):
        budget.use_llm_call()
    for _ in range(5):
        budget.use_search_call()
    # Should not raise
    budget.check()
