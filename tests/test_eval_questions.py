"""
LLM evaluation tests — one key question per data-quality dimension.

These hit the real /chat endpoint (LLM + MCP + database) so they are
slow and non-deterministic.  They are gated behind a ``--run-eval`` flag
and should be run manually or in a CI evaluation job.

Run:
    uv run pytest tests/test_eval_questions.py --run-eval -v

Each test sends a natural-language question to /chat and asserts that
the response (a) used a tool call and (b) contains an expected keyword
or pattern that proves the agent actually queried the DB.
"""

import re

import pytest
import pytest_asyncio
import httpx

BASE_URL = "http://localhost:8000"


def pytest_addoption(parser):
    parser.addoption(
        "--run-eval",
        action="store_true",
        default=False,
        help="Run LLM evaluation tests (requires running server + DB)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "eval: LLM evaluation test (slow, needs server)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-eval"):
        return
    skip = pytest.mark.skip(reason="need --run-eval option to run")
    for item in items:
        if "eval" in item.keywords:
            item.add_marker(skip)


# ── helpers ─────────────────────────────────────────────────────────────────


async def ask(question: str) -> dict:
    """Send a question to /chat and return the JSON body."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        resp = await client.post("/chat", json={"message": question})
        resp.raise_for_status()
        return resp.json()


def reply_contains_any(body: dict, *keywords: str) -> bool:
    """Check if the reply text contains at least one keyword (case-insensitive)."""
    text = body["reply"].lower()
    return any(kw.lower() in text for kw in keywords)


def used_tool(body: dict, tool_name: str = "execute_sql") -> bool:
    return any(tc["tool"] == tool_name for tc in body["tool_calls"])


# ── 1. Completeness ─────────────────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_completeness_null_count():
    """Are there any NULL clearing_dates? (check for missing data)"""
    body = await ask(
        "How many rows in accrual_transactions have a NULL clearing_date?"
    )
    assert used_tool(body)
    # The reply should contain a number
    assert re.search(r"\d+", body["reply"])


# ── 2. Uniqueness ───────────────────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_uniqueness_duplicate_check():
    """Are there duplicate rows based on a meaningful key?"""
    body = await ask(
        "Are there any duplicate rows in accrual_transactions when grouped by "
        "fiscal_year, posting_period, ref_doc_line_item, and transaction_value? "
        "Show the count of duplicates if any."
    )
    assert used_tool(body)
    assert re.search(r"\d+", body["reply"])


# ── 3. Validity ─────────────────────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_validity_currency_values():
    """What distinct currencies exist? (should only be USD / CAD)"""
    body = await ask(
        "What are the distinct currency values in accrual_transactions?"
    )
    assert used_tool(body)
    assert reply_contains_any(body, "USD", "CAD")


# ── 4. Consistency ──────────────────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_consistency_debit_credit_vs_sign():
    """Do debit_credit_indicator values match the sign of transaction_value?"""
    body = await ask(
        "Are there any rows where debit_credit_indicator is 'S' (debit) "
        "but transaction_value is negative, or where indicator is 'H' (credit) "
        "but transaction_value is positive? Show the count."
    )
    assert used_tool(body)
    assert re.search(r"\d+", body["reply"])


# ── 5. Accuracy ─────────────────────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_accuracy_total_value():
    """What is the total transaction value? (basic aggregation sanity)"""
    body = await ask(
        "What is the sum of transaction_value in accrual_transactions?"
    )
    assert used_tool(body)
    # Should contain a numeric value (possibly negative, with commas/decimals)
    assert re.search(r"[\d,]+\.?\d*", body["reply"])


# ── 6. Timeliness ───────────────────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_timeliness_fiscal_year_range():
    """What fiscal years are present in the data?"""
    body = await ask(
        "What is the minimum and maximum fiscal_year in accrual_transactions?"
    )
    assert used_tool(body)
    assert re.search(r"\d{4}", body["reply"])


# ── 7. Distribution & Outliers ──────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_distribution_transaction_value_stats():
    """Get basic stats (min/max/avg) on transaction_value."""
    body = await ask(
        "What are the min, max, and average transaction_value in "
        "accrual_transactions?"
    )
    assert used_tool(body)
    assert reply_contains_any(body, "min", "max", "avg", "average", "mean")


# ── 8. Schema Understanding ────────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_schema_column_awareness():
    """Can the agent list columns it knows about?"""
    body = await ask(
        "What columns are in the accrual_transactions table?"
    )
    # It should mention at least a few real columns
    assert reply_contains_any(
        body, "currency", "transaction_value", "fiscal_year", "posting_period"
    )


# ── 9. Aggregation & Analytics ──────────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_aggregation_by_period():
    """Aggregate total value by posting period."""
    body = await ask(
        "Show the total transaction_value grouped by posting_period, "
        "ordered by period."
    )
    assert used_tool(body)
    # Should have numbers in the output
    assert re.search(r"\d+", body["reply"])


# ── 10. Handle Vague User Questions ─────────────────────────────────────────


@pytest.mark.eval
@pytest.mark.asyncio
async def test_vague_question():
    """A vague question should still produce a useful answer from the DB."""
    body = await ask("Tell me something interesting about the accrual data.")
    assert used_tool(body)
    # Should not be an empty or error reply
    assert len(body["reply"]) > 20
