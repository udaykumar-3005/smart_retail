"""Run from the project root: python -m streamlit run dashboard/app.py."""
from pathlib import Path
import sys
import textwrap
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retail import (DATA_PATH, load_clean, analysis_view, kpis, performance,
                        monthly_performance, basket_summary, customer_summary,
                        rfm_snapshot, filter_transactions)

st.set_page_config(page_title="Smart Retail | Business intelligence", page_icon="◈", layout="wide")
st.markdown("""<style>
.block-container {padding-top:2.2rem; padding-bottom:3rem; max-width:1600px}
h1 {font-size:2.3rem!important;letter-spacing:-1.2px;font-weight:750!important}
h2,h3 {letter-spacing:-.4px}
[data-testid="stMetric"] {background:white;border:1px solid #e3e9f1;border-radius:12px;padding:18px 16px;min-height:115px}
[data-testid="stMetricValue"] {font-size:1.65rem}
[data-testid="stSidebar"] {border-right:1px solid #e3e9f1}
.eyebrow {color:#087f8c;font-size:12px;letter-spacing:2.5px;font-weight:700}
.hero-note {color:#5f6e83;font-size:16px;margin-bottom:22px}
</style>""", unsafe_allow_html=True)
PALETTE = ["#087F8C", "#23395B", "#F2A65A", "#AF5674", "#74B3CE", "#87A878", "#8C80B6"]
px.defaults.color_discrete_sequence = PALETTE


@st.cache_data(show_spinner="Reading and validating retail transactions…")
def get_data(modified):
    return analysis_view(load_clean())


@st.cache_data(show_spinner=False, max_entries=12)
def get_rfm(modified, end):
    return rfm_snapshot(get_data(modified), end)


def chart(fig, key, height=370):
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font_color="#172B4D",
                      margin=dict(l=10, r=10, t=35, b=15), height=height,
                      legend_title_text="", hovermode="closest")
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})


def table(frame, name):
    export = frame.copy()
    if isinstance(export.index, pd.PeriodIndex):
        export.index = export.index.astype(str)
    numeric_columns = export.select_dtypes(include="number").columns
    export[numeric_columns] = export[numeric_columns].round(2)
    st.dataframe(export, width="stretch")
    st.download_button("Download this table · CSV", export.to_csv().encode("utf-8-sig"),
                       file_name=f"{name}.csv", mime="text/csv", key=f"download_{name}")


def bars(frame, value, label, key, count=10):
    top = frame.nlargest(count, value).sort_values(value).reset_index()
    if label == "StockCode":
        top["Product"] = top.StockCode.map(product_label)
        top["Product label"] = top.Product.map(lambda name: "<br>".join(textwrap.wrap(name, width=32)))
        fig = px.bar(top, x=value, y="Product label", orientation="h",
                     hover_name="Product", hover_data={"Product label": False, "StockCode": True},
                     labels={"Product label": "Product"}, color_discrete_sequence=[PALETTE[0]])
    else:
        fig = px.bar(top, x=value, y=label, orientation="h", color_discrete_sequence=[PALETTE[0]])
    fig.update_yaxes(type="category")
    chart(fig, key, height=520 if label == "StockCode" else 370)


def product_label(code):
    name = descriptions.get(code)
    name = str(name).strip() if pd.notna(name) else ""
    return f"{name or 'Unnamed product'} · {code}"


def money(value):
    return "—" if pd.isna(value) else f"£{value:,.0f}"


def reset_filters():
    for key in ["dates", "countries", "products", "customers", "segments", "product_scope"]:
        st.session_state.pop(key, None)


if not DATA_PATH.exists():
    st.error(f"Dataset missing. Place Online Retail.xlsx in {DATA_PATH.parent}.")
    st.stop()
modified = DATA_PATH.stat().st_mtime_ns
data = get_data(modified)
first, last = data.Date.min().date(), data.Date.max().date()

with st.sidebar:
    st.markdown('<p class="eyebrow">SMART RETAIL / ANALYTICS</p>', unsafe_allow_html=True)
    st.header("Explore the business")
    st.caption("Choose a period and narrow the transaction view.")
    st.button("Reset Filters", on_click=reset_filters, width="stretch")
    dates = st.date_input("Date range", (first, last), min_value=first, max_value=last, key="dates")
    if len(dates) != 2:
        st.info("Select an end date to complete the range.")
        st.stop()
    start, end = dates
    countries = st.multiselect("Country", sorted(data.Country.unique()), key="countries", placeholder="All countries")
    descriptions = data.drop_duplicates("StockCode").set_index("StockCode").Description.to_dict()
    products = st.multiselect("Product / StockCode", sorted(data.StockCode.unique()), key="products",
                              format_func=product_label, placeholder="All products and special records")
    customers = st.multiselect("Customer", sorted(data.CustomerID.dropna().unique()), key="customers", placeholder="All, including unidentified")
    rfm = get_rfm(modified, end)
    segments = st.multiselect("RFM Segment", sorted(rfm.Segment.unique()), key="segments", placeholder="All customers")
    st.caption(f"RFM uses all history through {end:%d %b %Y}. Segment filters exclude unidentified and cancellation-only customers.")
    st.divider()
    st.caption(f"SOURCE COVERAGE\n\n{first:%d %b %Y} – {last:%d %b %Y}\n\nCurrency: GBP · Rows are product lines.")

filtered = filter_transactions(data, start, end, countries, products, customers, segments, rfm)
st.markdown('<p class="eyebrow">RETAIL INTELLIGENCE / PORTFOLIO</p>', unsafe_allow_html=True)
st.title("Smart Retail Sales Analysis Dashboard")
st.markdown('<div class="hero-note">Interactive analysis of retail sales, customers, products, countries, and cancellations.</div>', unsafe_allow_html=True)
st.caption(f"{start:%d %b %Y} — {end:%d %b %Y}  ·  {len(filtered):,} transaction lines  ·  {filtered.Country.nunique()} countries")
if filtered.empty:
    st.info("No transactions match these filters. Broaden the selection or use Reset Filters.")
    st.stop()
if pd.Timestamp(start).day != 1 or pd.Timestamp(end).day != pd.Timestamp(end).days_in_month:
    st.info("The selection includes a partial month. Monthly growth is shown only when both adjacent calendar months are fully covered. December 2011 ends on 9 December.")
if products:
    st.caption("Product filter active: invoice metrics describe only the selected lines within each invoice, not complete baskets.")

metrics = kpis(filtered)
labels = ["Net revenue", "Sales invoices", "Purchasing customers", "Net units", "Net revenue / sales invoice", "Cancellation invoice share"]
helps = ["All retained signed revenue, including adjustments.", "Unique numeric invoices with positive quantities.",
         "Identified customers with at least one sale in this view.", "Signed quantity across all retained lines; includes special records.",
         "Period net revenue / sales invoices; not matched-order AOV.",
         "C invoices / (sales + C invoices). Not the percentage of original orders returned."]
for col, label, help_text in zip(st.columns(6), labels, helps):
    value = metrics[label]
    formatted = "—" if pd.isna(value) else (money(value) if "revenue" in label else (f"{value:.1f}%" if "share" in label else f"{value:,.0f}"))
    col.metric(label, formatted, help=help_text)

page = st.radio("Analysis area", ["Overview", "Products", "Customers & RFM", "Countries", "Cancellations", "Baskets", "Methodology"], horizontal=True, label_visibility="collapsed")
monthly = monthly_performance(filtered, start, end)

if page == "Overview":
    st.subheader("Sales performance")
    grain = st.segmented_control("Trend frequency", ["Monthly", "Weekly", "Daily"], default="Monthly")
    if grain == "Monthly":
        trend = monthly.copy()
        trend["Period"] = trend.index.to_timestamp()
        trend["Coverage"] = np.where(trend.CompleteMonth, "Full month", "Partial month")
    else:
        field = "Week" if grain == "Weekly" else "Date"
        trend = performance(filtered, field).reset_index().rename(columns={field: "Period"})
    chart(px.line(trend, x="Period", y=["GrossRevenue", "NetRevenue", "CancellationValue"], markers=True,
                  labels={"value": "Revenue · GBP", "variable": "Measure"}), "sales_trend")
    if grain == "Weekly":
        st.caption("Weeks start Monday. Boundary weeks can be incomplete; absent periods mean no recorded activity, not proof of store closure.")
    if grain == "Monthly":
        st.caption("December 2011 and date-filter boundary months may be partial. No extrapolation is applied.")
    a, b = st.columns(2)
    with a:
        st.subheader("Comparable monthly growth")
        mom = monthly.reset_index()
        mom["YearMonth"] = mom.YearMonth.astype(str)
        chart(px.bar(mom, x="YearMonth", y="MoMPercent", labels={"MoMPercent": "Net revenue change · %"}), "mom")
    with b:
        st.subheader("Sales invoice activity")
        chart(px.bar(mom, x="YearMonth", y="SalesInvoices", labels={"SalesInvoices": "Sales invoices"}), "invoice_trend")
    st.subheader("Net revenue per sales invoice")
    chart(px.line(mom, x="YearMonth", y="NetRevenuePerSalesInvoice", markers=True,
                  labels={"NetRevenuePerSalesInvoice": "GBP / sales invoice"}), "invoice_value_trend")
    a, b = st.columns(2)
    with a:
        st.subheader("Day-of-week pattern")
        weekday = performance(filtered, "DayOfWeek").reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]).reset_index()
        chart(px.bar(weekday, x="DayOfWeek", y="NetRevenue"), "weekday")
    with b:
        st.subheader("Trading-hour pattern")
        hourly = performance(filtered, "Hour").reset_index()
        chart(px.bar(hourly, x="Hour", y="NetRevenue"), "hourly")
    st.caption("Weekday/hour bars are recorded totals, not exposure-adjusted demand estimates. About one year of data cannot establish recurring annual seasonality.")
    table(monthly, "monthly_performance")

elif page == "Products":
    st.subheader("What drives product performance?")
    scope = st.radio("Product analysis scope", ["Catalog products", "Special / review", "All records"], horizontal=True, key="product_scope")
    product_data = filtered if scope == "All records" else filtered[filtered.ProductScope.eq(scope)]
    st.caption("Catalog products use a five-digit StockCode with optional letters. This is a documented proxy, not a verified physical-product catalog. Special/review records remain in headline KPIs.")
    if product_data.empty:
        st.info("No product records in this scope.")
    else:
        products_table = performance(product_data, "StockCode")
        products_table.insert(0, "Product", products_table.index.map(product_label))
        a, b = st.columns(2)
        with a:
            st.markdown("**Top products · net revenue**")
            bars(products_table, "NetRevenue", "StockCode", "product_revenue")
        with b:
            st.markdown("**Top products · units sold before cancellations**")
            bars(products_table, "SoldUnits", "StockCode", "product_units")
        st.caption("Revenue share is relative to this product scope and active filters. Negative shares can occur for products with net credits.")
        table(products_table.sort_values("NetRevenue", ascending=False), "product_performance")

elif page == "Customers & RFM":
    st.subheader("Customer value and retention")
    summary = customer_summary(filtered)
    purchasers = summary[summary.SalesInvoices.gt(0)]
    a, b, c = st.columns(3)
    a.metric("Repeat purchaser share", f"{purchasers.RepeatPurchaser.mean() * 100:.1f}%" if len(purchasers) else "—")
    b.metric("Median purchase frequency", f"{purchasers.SalesInvoices.median():.0f}" if len(purchasers) else "—")
    c.metric("Unidentified transaction lines", f"{filtered.CustomerID.isna().mean() * 100:.1f}%")
    st.caption("Repeat = at least two sales invoices within the filtered view. Missing IDs remain in sales totals but cannot be assigned to customers.")
    visible_rfm = rfm.loc[rfm.index.isin(filtered.CustomerID.dropna().unique())]
    a, b = st.columns(2)
    with a:
        st.markdown("**Segment mix · customers active in this view**")
        counts = visible_rfm.groupby("Segment").size().rename("Customers").reset_index()
        chart(px.bar(counts, x="Customers", y="Segment", orientation="h"), "segment_chart")
    with b:
        st.markdown("**Recency and monetary value · as-of history**")
        chart(px.scatter(visible_rfm.reset_index(), x="Recency", y="Monetary", color="Segment",
                         hover_name="CustomerID", hover_data=["Frequency", "RFMScore"], opacity=.65), "rfm_scatter")
    st.caption(f"RFM reference day: {(pd.Timestamp(end) + pd.Timedelta(days=1)).date()}. Scores use all history through {end}, regardless of start date, country or product filters. Tables below distinguish filtered activity from as-of RFM history.")
    st.markdown("**Customer activity · selected transactions**")
    table(summary.sort_values("NetRevenue", ascending=False), "customer_activity")
    st.markdown("**RFM snapshot · active identified customers with purchase history**")
    table(visible_rfm.sort_values("Monetary", ascending=False), "rfm_snapshot")

elif page == "Countries":
    st.subheader("Geographic revenue concentration")
    country_table = performance(filtered, "Country").sort_values("NetRevenue", ascending=False)
    a, b = st.columns(2)
    with a:
        bars(country_table, "NetRevenue", "Country", "country_revenue", 15)
    with b:
        chart(px.scatter(country_table.reset_index(), x="SalesInvoices", y="NetRevenue", hover_name="Country",
                         size="Customers", size_max=55), "country_value")
    st.caption("Country is the transaction's recorded country. Customer counts are distinct within each country and need not add to the global count.")
    table(country_table, "country_performance")

elif page == "Cancellations":
    st.subheader("Cancellation and credit exposure")
    a, b, c = st.columns(3)
    a.metric("Cancellation value", money(metrics["Cancellation value"]))
    b.metric("Cancelled units", f"{filtered.CancelledUnits.sum():,.0f}")
    ratio = metrics["Cancellation value / gross sales"]
    c.metric("Credit value / gross sales", "—" if pd.isna(ratio) else f"{ratio:.1f}%")
    st.caption("C-prefix invoices include returns, cancellations and operational credits. These ratios compare recorded activity; original sales are not matched. Ratios can exceed 100% in small or credit-heavy selections.")
    cancellation_trend = monthly.reset_index()
    cancellation_trend["YearMonth"] = cancellation_trend.YearMonth.astype(str)
    chart(px.bar(cancellation_trend, x="YearMonth", y="CancellationValue"), "credit_trend")
    a, b = st.columns(2)
    with a:
        st.markdown("**Products with the highest credit value · includes special codes**")
        credits_product = performance(filtered, "StockCode")
        credits_product.insert(0, "Product", credits_product.index.map(product_label))
        bars(credits_product, "CancellationValue", "StockCode", "credit_products")
    with b:
        st.markdown("**Identified customers with the highest credit value**")
        credits_customer = customer_summary(filtered)
        bars(credits_customer, "CancellationValue", "CustomerID", "credit_customers")
    table(credits_product.sort_values("CancellationValue", ascending=False), "product_cancellations")
    table(credits_customer.sort_values("CancellationValue", ascending=False), "customer_cancellations")

elif page == "Baskets":
    st.subheader("Invoice size and transaction context")
    baskets = basket_summary(filtered)
    if baskets.empty:
        st.info("No normal sales invoices in this selection.")
    else:
        a, b, c = st.columns(3)
        a.metric("Median invoice value", money(baskets.Revenue.median()))
        b.metric("Mean invoice value", money(baskets.Revenue.mean()))
        c.metric("Median unique StockCodes", f"{baskets.UniqueProducts.median():.0f}")
        st.caption("Sales invoices before cancellations. Units and unique StockCodes include special lines. With product filters, these are partial invoice baskets.")
        distribution = baskets.assign(Log10Revenue=np.log10(baskets.Revenue))
        chart(px.histogram(distribution, x="Log10Revenue", nbins=50,
                           labels={"Log10Revenue": "log10(invoice revenue in GBP)"}), "basket_distribution")
        st.caption("Log scale exposes the typical invoice distribution while retaining extreme values: 2 means £100; 3 means £1,000.")
        table(baskets.sort_values("Revenue", ascending=False), "sales_baskets")
        st.markdown("**Investigated reversals · selected transaction rows**")
        pairs = filtered[filtered.InvoiceNo.isin(["581483", "C581484", "541431", "C541433"])]
        st.dataframe(pairs[["InvoiceNo", "Description", "StockCode", "CustomerID", "Quantity", "Revenue"]], width="stretch")
        st.caption("The full dataset contains matching +80,995/−80,995 and +74,215/−74,215 quantities. A filter may show only one side. They are retained rather than deleted as statistical outliers.")

else:
    st.subheader("Definitions you can defend in an interview")
    st.markdown("""
**Source and cleaning.** The local workbook is the source of truth. Keep UnitPrice > 0,
uppercase StockCodes, remove exact duplicates, then compute Revenue and YearMonth in
the same order as the original notebook. No transactions are removed for missing CustomerID,
negative quantity or high value. Additional dashboard features live on a copy.

**Revenue bridge.** Net revenue = gross normal sales − C-invoice credit value + other adjustments.
The positive £11,062.06 bad-debt adjustment remains in net revenue but is not a sales invoice.
Net revenue per sales invoice is a period ratio, not matched-order average order value.

**RFM.** Eligible customers have a valid ID and at least one normal sales invoice in history
through the chosen end date. Recency is days since the last purchase, measured on the following
day. Frequency counts distinct normal sales invoices. Monetary sums sales and credits, excluding
accounting adjustments. Credit-only customers are shown in customer activity but not scored.
Each R/F/M score is the ceiling of average percentile rank × 5 (1–5); lower recency scores higher.
Ties receive identical scores, so score groups need not contain equal customer counts.

**Segment rules, evaluated in order.** Net non-positive: Monetary ≤ 0. Champions: R, F, M ≥ 4.
At-risk loyal: R ≤ 2 and F ≥ 4. Loyal: R ≥ 3 and F ≥ 4. Recent occasional: R ≥ 4 and F ≤ 2.
Dormant: R ≤ 2. Developing: all remaining eligible customers.
These descriptive business rules are not a predictive or validated churn model.

**Limitations.** No cost, margin, acquisition or promotion data are available. Revenue is not
profit. Returns are not matched to original orders, and missing IDs limit customer coverage.
StockCode format is a product-catalog proxy. Just over one year cannot prove recurring annual
seasonality. Boundary months are partial; absent trading days are not evidence of zero demand.

**Filter semantics.** Headline KPIs and activity charts use the selected transactions. RFM
uses all history through the end date, then displays customers active in the filtered view.
Segment filters intentionally exclude unidentified and credit-only customers. Product scope
on the Products page affects that page's product tables, not the overall KPI definition.
""")
    st.markdown("**Current view · revenue reconciliation**")
    bridge = pd.DataFrame({"GBP": [filtered.GrossRevenue.sum(), -filtered.CancellationValue.sum(),
                                    filtered.AdjustmentRevenue.sum(), filtered.Revenue.sum()]},
                         index=["Gross sales", "Signed cancellations", "Other adjustments", "Net revenue"])
    table(bridge, "revenue_bridge")

st.divider()
st.caption("SMART RETAIL · Evidence before assumptions · All values calculated from the local dataset")
