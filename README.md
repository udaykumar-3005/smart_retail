# Smart Retail Sales Analysis

An end-to-end retail analytics portfolio project: transaction investigation, context-aware cleaning, sales and customer analysis, descriptive RFM segmentation, and an interactive Streamlit dashboard. The project continues the original notebook rather than replacing its exploratory work.

## Business problem

Understand where recorded revenue comes from, how sales change over time, which products and customers contribute value, and how cancellations affect performance. Distinguish transaction lines from invoices and recorded sales from accounting activity before calculating business metrics.

## Run locally

Tested with Python 3.13 and the package versions in `requirements.txt`. From the project root on Windows:

```powershell
# The existing project already has .venv. Create one only on a fresh checkout:
# py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

Open the local URL printed by Streamlit (normally http://localhost:8501). The first load reads the workbook and may take around 30 seconds; subsequent interactions reuse Streamlit's cached data. No API keys, accounts or database are needed. The workbook is read locally and never overwritten.

For macOS/Linux, use `python3 -m venv .venv`, then `.venv/bin/python` in place of the Windows interpreter path. Open `notebook/smart_retail.ipynb` in VS Code/Jupyter and select this environment to run the analysis. The notebook works from either the project root or the notebook directory.

## Project layout

```text
data/Online Retail.xlsx       Original workbook, unchanged
notebook/smart_retail.ipynb   Original investigation + executed completion analysis
src/retail.py                Shared cleaning, features, metrics, RFM and filters
dashboard/app.py             Separate Streamlit application
.streamlit/config.toml       Dashboard theme and local server configuration
tests/                      Data integrity and dashboard interaction checks
readmd.txt/readmd.txt        Preserved original working notes
requirements.txt            Tested dependency versions
```

The cleaned dataset is reproducibly built in memory rather than saved as a second potentially stale file. `analysis_view` adds features to a copy. The notebook verifies that the shared cleaning function exactly matches its original `df_clean` using `assert_frame_equal`. CSV downloads are analysis exports, not changes to the source.

## Dataset and provenance

Source: Chen, D. (2015), [Online Retail, UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/352/online%2Bretail), [DOI: 10.24432/C5BW33](https://doi.org/10.24432/C5BW33), CC BY 4.0. UCI describes a UK-based non-store retailer and prices in sterling. Local workbook evidence takes precedence over catalog summaries; despite the catalog's missing-value metadata, this workbook contains missing customer IDs and descriptions.

- Original workbook: **541,909 product-line records × 8 columns**.
- Observed timestamps: **1 December 2010 08:26 through 9 December 2011 12:50**.
- Fields: InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country.
- One invoice may contain many product lines. Revenue is `Quantity × UnitPrice`, not profit.

## Cleaning decisions

| Decision | Evidence and rationale |
|---|---|
| Keep positive prices | Exclude 2,517 non-positive-price rows from revenue analysis; free goods and internal records are not universally “errors” |
| Normalize StockCode case | Preserve the earlier investigation of `15056BL` / `15056bl` |
| Remove exact duplicates | Remove 5,263 duplicate rows after normalization, following the original notebook; identical repeated lines could still have operational meaning unavailable here |
| Retain negative quantities | C-invoice credits are needed for net revenue; 9,251 negative lines remain after deduplication |
| Retain missing customer IDs | 132,565 cleaned lines lack CustomerID; remove them only from customer-specific computations |
| Retain extreme invoices | The +80,995/−80,995 and +74,215/−74,215 pairs offset; removing only one side would distort revenue |
| Retain special codes and adjustments | Fees, postage and the positive bad-debt record remain in overall revenue; use explicit analysis subsets |

Result: **534,129 retained rows**. Revenue and YearMonth produce the original 10-column `df_clean`. Year, Month, Monday-based Week, Date, DayOfWeek, Hour, transaction type and product scope are additional analysis-only features.

## Metric definitions and verified baseline

These values are from the full local workbook after the established cleaning, without dashboard filters. Displayed money is rounded; calculations retain source precision.

| Measure | Value | Definition |
|---|---:|---|
| Net revenue | £9,748,131.07 | Signed revenue of all retained records |
| Gross normal sales | £10,631,048.74 | Positive-quantity numeric-invoice revenue |
| Cancellation value | £893,979.73 | Magnitude of C-prefix signed revenue |
| Other adjustments | £11,062.06 | Retained `A563185` bad-debt adjustment |
| Sales invoices | 19,959 | Distinct numeric invoices with positive quantities |
| Identified purchasing customers | 4,338 | Valid IDs with at least one normal sale |
| Net recorded units | 5,296,860 | Signed quantity including special records |
| Net revenue per sales invoice | £488.41 | Period net revenue / sales invoices |
| Mean gross invoice value | £532.64 | Gross sales / sales invoices |
| Median gross invoice value | £303.30 | Median of invoice-level gross values |
| Cancellation invoice share | 16.12% | C invoices / (sales invoices + C invoices) |
| Credit-value ratio | 8.41% | Cancellation value / gross sales |

**Revenue bridge:** gross sales − cancellation value + other adjustments = net revenue. A non-C invoice is not automatically a sale: `A563185` is reported separately. Net revenue per sales invoice is not matched-order AOV. Cancellation share is not the fraction of original orders returned; no general return-to-order linkage exists in the dataset.

## Completed analysis

The same notebook now contains the original cleaning investigation, monthly revenue and invoice analysis, plus:

- Daily, weekly, weekday and hourly patterns; monthly growth restricted to adjacent complete months.
- Product revenue, units, contribution and credit activity; special-record review alongside catalog products.
- Customer spending, purchasing frequency, repeat purchasing and missing-ID coverage.
- RFM scores, segment summaries, business interpretations and explicit tie handling.
- Country revenue, contribution, units, sales invoices and identified customers.
- Cancellation trends, high-credit products/customers and reconciliation to sales.
- Invoice value, quantity and product-count distributions; means, medians, percentiles and known reversals.
- Six evidence-based business insights, each with interpretation and limitations.

The last month is partial. Its apparent −70.28% change is not a normal full-month business decline. Missing weekdays/hour combinations indicate no recorded activity, not necessarily closure or zero demand. One annual cycle is insufficient to establish repeating seasonality.

## Product scope

Five-digit StockCodes with optional letters form the **catalog-product proxy**. This keeps ordinary coded products and the investigated suffix variants. Everything else remains in “Special / review,” including postage, manual fees, donations and gift records. Code format is not a verified physical-product taxonomy; special/review records can include actual merchandise. Inspect that table before making inventory decisions. Product contribution uses the selected product scope as its denominator.

## RFM methodology

RFM uses all available history through a specified end date, with the next day as the reference date. Only identified customers with at least one normal sale qualify. Recency measures days since the last recorded purchase; frequency counts sales invoices; monetary sums sales and credits, excluding adjustments. Cancellation-only customers remain in customer activity but are not assigned an RFM segment.

R/F/M scores equal the ceiling of average percentile rank × 5, clipped to 1–5, with lower recency ranked better. Ties receive equal scores; quintile sizes are not forced to be equal. Segments are evaluated in the following order:

| Segment | Rule | Candidate action to test |
|---|---|---|
| Net non-positive | Monetary ≤ 0 | Review credits/reversals |
| Champions | R, F, M ≥ 4 | Retention and relevant cross-sell |
| At-risk loyal | R ≤ 2, F ≥ 4 | Reactivation investigation |
| Loyal | R ≥ 3, F ≥ 4 | Repeat-purchase experience |
| Recent occasional | R ≥ 4, F ≤ 2 | Second-purchase journey |
| Dormant | R ≤ 2 | Low-cost reactivation |
| Developing | All remaining eligible customers | Learn preferences |

These rules are descriptive, not a validated predictive model. A later-cancelled invoice still counts as a recorded purchase. History before the workbook begins is unavailable.

## Business findings

| Finding and evidence | Interpretation | Limitation |
|---|---|---|
| UK represents about 84.0% of net revenue | Prioritize reliability in the largest observed market | No market size or profit information |
| November net revenue reaches £1,456,145.80, up 36.17% from October | Investigate inventory and fulfillment capacity around this peak | One annual cycle; no causal attribution |
| StockCode 22423 leads catalog net revenue at £164,459.49 | Review availability and related-product opportunities | Product-code proxy; no stock-out or margin data |
| About 65.6% of 4,338 identified purchasers bought on at least two invoices | Design measurable retention experiments using RFM | About 24.8% of lines have missing IDs |
| Credits equal £893,979.73 / 8.41% of gross sales | Investigate concentrated credit exposure and special fees | Credits are not all physical returns or matched orders |
| Median gross invoice £303.30 is below mean £532.64 | Describe typical baskets using distribution and median | Large reversed sales remain in gross averages |

## Dashboard guide

Seven analysis areas: **Overview**, **Products**, **Customers & RFM**, **Countries**, **Cancellations**, **Baskets**, and **Methodology**. Plotly charts allow hover, zoom and image export; tables have CSV downloads. The layout uses a consistent teal/navy palette, KPI cards and a sidebar for filters.

Date, country, StockCode, customer and RFM segment filters apply to activity KPIs/charts. Empty selections mean all values; incompatible combinations produce a clear no-results state. Reset Filters restores the full dataset. Product filters turn basket metrics into selected-line invoice metrics, which is stated in the interface.

RFM uses full history through the selected end date, then shows customers active in the filtered view. Changing the start date/country/product does not redefine the customer's segment. Segment filters intentionally exclude unidentified and credit-only customers. The Products-page scope control affects its product analysis only; the headline KPIs continue to represent all selected transactions.

## Validation

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Checks cover cleaning counts, monthly revenue reconciliation, normal-sale invoice counts, known reversal pairs, missing-ID retention, partial-month growth, zero denominators, no-future-data RFM, tied scores, inclusive end-date filters and dashboard navigation/filter/reset behavior. The 124-cell notebook was executed end to end with saved outputs. Original working notes remain unchanged; the notebook's hard-coded data path and mixed-type invoice lookup were corrected for reproducibility.

Streamlit implementation/testing references: [official caching guide](https://docs.streamlit.io/develop/concepts/architecture/caching) and [AppTest implementation](https://github.com/streamlit/streamlit/blob/develop/lib/streamlit/testing/v1/app_test.py).

## Limitations and next opportunities

Revenue is not margin or cash collection. Special records affect headline units and value; returns lack a reliable universal original-order link. Exact-duplicate removal follows the project's established assumption. Customer coverage is incomplete, and the window truncates both past and future behavior. Month-end reporting must respect the partial December cutoff. RFM actions require controlled evaluation before use in production.

The requested descriptive analytics and local dashboard are complete. Production hosting, predictive forecasting, churn prediction and transaction-level return matching are potential extensions, not claimed results of this project.
