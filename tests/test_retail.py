from datetime import date
import numpy as np
import pandas as pd
import pytest
from src.retail import (load_clean, analysis_view, kpis, performance, monthly_performance,
                        rfm_snapshot, filter_transactions, basket_summary)


@pytest.fixture(scope="module")
def data():
    clean = load_clean()
    assert clean.shape == (534129, 10)
    assert clean.CustomerID.isna().sum() == 132565
    assert clean.duplicated().sum() == 0
    return analysis_view(clean)


def test_revenue_and_known_reversals(data):
    totals = performance(data, "YearMonth")
    assert np.allclose(totals.NetRevenue, totals.GrossRevenue - totals.CancellationValue + totals.AdjustmentRevenue)
    assert totals.loc[pd.Period("2011-11"), "NetRevenue"] == pytest.approx(1456145.80)
    assert totals.loc[pd.Period("2011-08"), "SalesInvoices"] == 1360
    for pair in [["581483", "C581484"], ["541431", "C541433"]]:
        assert data.loc[data.InvoiceNo.isin(pair), "Revenue"].sum() == pytest.approx(0)
    assert data.AdjustmentRevenue.sum() == pytest.approx(11062.06)


def test_partial_month_and_zero_denominator(data):
    monthly = monthly_performance(data, date(2010, 12, 1), date(2011, 12, 9))
    assert pd.isna(monthly.iloc[-1].MoMPercent)
    assert monthly.loc[pd.Period("2011-11"), "MoMPercent"] == pytest.approx(36.168792, rel=1e-6)
    credits = data[data.TransactionType.eq("Cancellation")]
    assert np.isnan(kpis(credits)["Net revenue / sales invoice"])
    assert kpis(credits)["Cancellation invoice share"] == 100
    assert basket_summary(credits).empty


def test_rfm_uses_no_future_and_ties_are_equal(data):
    cutoff = date(2011, 3, 31)
    snapshot = rfm_snapshot(data, cutoff)
    past = data[data.InvoiceDate.lt("2011-04-01")]
    pd.testing.assert_frame_equal(snapshot, rfm_snapshot(past, cutoff))
    assert snapshot.LastPurchase.max() < pd.Timestamp("2011-04-01")
    assert snapshot.Recency.min() >= 1
    for field, score in [("Recency", "R"), ("Frequency", "F"), ("Monetary", "M")]:
        assert snapshot.groupby(field)[score].nunique().max() == 1
        assert snapshot[score].between(1, 5).all()
    full = rfm_snapshot(data, date(2011, 12, 9))
    assert full.loc["12346", "Monetary"] == pytest.approx(0)
    assert full.loc["12346", "Segment"] == "Net non-positive"


def test_filters_include_end_day_and_do_not_mutate(data):
    before = data.shape
    filtered = filter_transactions(data, date(2011, 12, 9), date(2011, 12, 9), countries=["United Kingdom"])
    assert filtered.InvoiceDate.max().hour == 12
    assert filtered.Country.eq("United Kingdom").all()
    assert filter_transactions(data, date(2011, 12, 9), date(2011, 12, 9), customers=["nonexistent"]).empty
    snapshot = rfm_snapshot(data, date(2011, 12, 9))
    champions = filter_transactions(data, date(2010, 12, 1), date(2011, 12, 9), segments=["Champions"], rfm=snapshot)
    assert champions.CustomerID.notna().all()
    assert set(champions.CustomerID) <= set(snapshot.index[snapshot.Segment.eq("Champions")])
    assert data.shape == before
