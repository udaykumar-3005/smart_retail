"""Shared, auditable definitions for the existing retail notebook and dashboard."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "Online Retail.xlsx"


def clean_transactions(raw):
    """Reproduce the notebook's order of operations without changing raw data."""
    clean = raw.loc[raw.UnitPrice.gt(0)].copy()
    clean["StockCode"] = clean.StockCode.astype(str).str.upper()
    clean = clean.drop_duplicates().copy()
    clean["Revenue"] = clean.Quantity * clean.UnitPrice
    clean["YearMonth"] = clean.InvoiceDate.dt.to_period("M")
    return clean


def load_clean(path=DATA_PATH):
    return clean_transactions(pd.read_excel(path))


def analysis_view(clean):
    """Derived analysis columns live on a copy, never on the cleaned source."""
    data = clean.copy()
    invoice = data.InvoiceNo.astype(str)
    data["InvoiceNo"] = invoice
    data["CustomerID"] = data.CustomerID.astype("Int64").astype("string")
    data["TransactionType"] = np.select(
        [invoice.str.startswith("C"), invoice.str.fullmatch(r"\d+") & data.Quantity.gt(0)],
        ["Cancellation", "Sale"], default="Adjustment")
    # A catalog-code proxy, not proof of a physical item. Exceptions remain visible.
    data["ProductScope"] = np.where(data.StockCode.str.fullmatch(r"\d{5}[A-Z]*"),
                                    "Catalog products", "Special / review")
    dates = data.InvoiceDate
    data["Date"] = dates.dt.normalize()
    data["Year"] = dates.dt.year
    data["Month"] = dates.dt.month
    data["Week"] = dates.dt.to_period("W-SUN").dt.start_time
    data["DayOfWeek"] = dates.dt.day_name()
    data["Hour"] = dates.dt.hour
    data["GrossRevenue"] = data.Revenue.where(data.TransactionType.eq("Sale"), 0)
    data["CancellationValue"] = -data.Revenue.where(data.TransactionType.eq("Cancellation"), 0)
    data["AdjustmentRevenue"] = data.Revenue.where(data.TransactionType.eq("Adjustment"), 0)
    data["SoldUnits"] = data.Quantity.where(data.TransactionType.eq("Sale"), 0)
    data["CancelledUnits"] = -data.Quantity.where(data.TransactionType.eq("Cancellation"), 0)
    return data


def divide(numerator, denominator):
    return numerator / denominator if denominator else float("nan")


def kpis(data):
    sales = data.loc[data.TransactionType.eq("Sale")]
    cancellations = data.loc[data.TransactionType.eq("Cancellation")]
    sale_count = sales.InvoiceNo.nunique()
    credit_count = cancellations.InvoiceNo.nunique()
    return {
        "Net revenue": data.Revenue.sum(),
        "Sales invoices": sale_count,
        "Purchasing customers": sales.CustomerID.nunique(),
        "Net units": data.Quantity.sum(),
        "Net revenue / sales invoice": divide(data.Revenue.sum(), sale_count),
        "Cancellation invoice share": divide(credit_count, sale_count + credit_count) * 100,
        "Gross sales": data.GrossRevenue.sum(),
        "Cancellation value": data.CancellationValue.sum(),
        "Gross revenue / sales invoice": divide(data.GrossRevenue.sum(), sale_count),
        "Cancellation value / gross sales": divide(data.CancellationValue.sum(), data.GrossRevenue.sum()) * 100,
    }


def performance(data, group):
    result = data.groupby(group, observed=True).agg(
        NetRevenue=("Revenue", "sum"), GrossRevenue=("GrossRevenue", "sum"),
        CancellationValue=("CancellationValue", "sum"), AdjustmentRevenue=("AdjustmentRevenue", "sum"),
        NetUnits=("Quantity", "sum"), SoldUnits=("SoldUnits", "sum"), CancelledUnits=("CancelledUnits", "sum"))
    sales = data[data.TransactionType.eq("Sale")].groupby(group, observed=True)
    credits = data[data.TransactionType.eq("Cancellation")].groupby(group, observed=True)
    result["SalesInvoices"] = sales.InvoiceNo.nunique().reindex(result.index, fill_value=0)
    result["Customers"] = sales.CustomerID.nunique().reindex(result.index, fill_value=0)
    result["CancellationInvoices"] = credits.InvoiceNo.nunique().reindex(result.index, fill_value=0)
    result["NetRevenuePerSalesInvoice"] = result.NetRevenue / result.SalesInvoices.replace(0, np.nan)
    result["CancellationValuePct"] = result.CancellationValue / result.GrossRevenue.replace(0, np.nan) * 100
    result["NetRevenueSharePct"] = result.NetRevenue / (data.Revenue.sum() or np.nan) * 100
    return result


def monthly_performance(data, start, end):
    result = performance(data, "YearMonth").reindex(pd.period_range(start, end, freq="M"))
    sums = ["NetRevenue", "GrossRevenue", "CancellationValue", "AdjustmentRevenue", "NetUnits",
            "SoldUnits", "CancelledUnits", "SalesInvoices", "Customers", "CancellationInvoices"]
    result[sums] = result[sums].fillna(0)
    result["CompleteMonth"] = [(p.start_time.date() >= pd.Timestamp(start).date()
                                and p.end_time.date() <= pd.Timestamp(end).date()) for p in result.index]
    growth = result.NetRevenue.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan) * 100
    result["MoMPercent"] = growth.where(result.CompleteMonth & result.CompleteMonth.shift(1, fill_value=False))
    result.index.name = "YearMonth"
    return result


def basket_summary(data):
    return data.loc[data.TransactionType.eq("Sale")].groupby("InvoiceNo").agg(
        InvoiceDate=("InvoiceDate", "min"), CustomerID=("CustomerID", "first"),
        Revenue=("Revenue", "sum"), Units=("Quantity", "sum"),
        UniqueProducts=("StockCode", "nunique"), Lines=("StockCode", "size"))


def customer_summary(data):
    identified = data[data.CustomerID.notna()]
    summary = performance(identified, "CustomerID")
    summary["RepeatPurchaser"] = summary.SalesInvoices.ge(2)
    return summary


def rfm_snapshot(data, end):
    """As-of snapshot using all available history through end; no future rows."""
    cutoff = pd.Timestamp(end).normalize() + pd.Timedelta(days=1)
    history = data.loc[data.InvoiceDate.lt(cutoff) & data.CustomerID.notna()]
    sales = history.loc[history.TransactionType.eq("Sale")]
    rfm = sales.groupby("CustomerID").agg(LastPurchase=("InvoiceDate", "max"),
                                           Frequency=("InvoiceNo", "nunique"))
    rfm["Recency"] = (cutoff - rfm.LastPurchase.dt.normalize()).dt.days
    rfm["Monetary"] = history.loc[~history.TransactionType.eq("Adjustment")].groupby("CustomerID").Revenue.sum().reindex(rfm.index)
    for column, score, ascending in [("Recency", "R", False), ("Frequency", "F", True), ("Monetary", "M", True)]:
        rfm[score] = np.ceil(rfm[column].rank(pct=True, method="average", ascending=ascending) * 5).clip(1, 5).astype(int)
    rfm["RFMScore"] = rfm[["R", "F", "M"]].astype(str).agg("".join, axis=1)
    rfm["Segment"] = np.select([
        rfm.Monetary.le(0),
        rfm.R.ge(4) & rfm.F.ge(4) & rfm.M.ge(4),
        rfm.R.le(2) & rfm.F.ge(4),
        rfm.R.ge(3) & rfm.F.ge(4),
        rfm.R.ge(4) & rfm.F.le(2),
        rfm.R.le(2)],
        ["Net non-positive", "Champions", "At-risk loyal", "Loyal", "Recent occasional", "Dormant"],
        default="Developing")
    return rfm


def filter_transactions(data, start, end, countries=(), products=(), customers=(), segments=(), rfm=None):
    mask = data.InvoiceDate.ge(pd.Timestamp(start)) & data.InvoiceDate.lt(pd.Timestamp(end) + pd.Timedelta(days=1))
    for column, selected in [("Country", countries), ("StockCode", products), ("CustomerID", customers)]:
        if selected:
            mask &= data[column].isin(selected)
    if segments:
        ids = rfm.index[rfm.Segment.isin(segments)]
        mask &= data.CustomerID.isin(ids)
    return data.loc[mask].copy()
