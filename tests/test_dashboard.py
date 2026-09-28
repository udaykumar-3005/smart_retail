from datetime import date
from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_dashboard_pages_filters_empty_and_reset():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "dashboard/app.py", default_timeout=120).run()
    assert not app.exception
    assert len(app.metric) == 6
    initial = app.metric[0].value
    for page in ["Products", "Customers & RFM", "Countries", "Cancellations", "Baskets", "Methodology"]:
        app.radio[0].set_value(page).run()
        assert not app.exception, page
    app.multiselect(key="countries").set_value(["France"]).run()
    assert not app.exception
    assert app.metric[0].value != initial
    app.multiselect(key="countries").set_value(["France"]).run()
    app.multiselect(key="customers").set_value(["12346"]).run()
    assert not app.exception
    assert any("No transactions" in item.value for item in app.info)
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == initial
    app.date_input(key="dates").set_value((date(2011, 1, 1), date(2011, 1, 31))).run()
    assert not app.exception
    app.radio[0].set_value("Customers & RFM").run()
    assert not app.exception
    app.button[0].click().run()
    app.multiselect(key="segments").set_value(["Champions"]).run()
    assert not app.exception
    assert app.metric[0].value != initial
    app.button[0].click().run()
    app.multiselect(key="products").set_value(["22423"]).run()
    assert not app.exception
    assert app.metric[0].value == "£164,459"
    # Accounting-only selection: zero sales and no identified customers.
    app.multiselect(key="products").set_value(["B"]).run()
    assert not app.exception
    assert app.metric[4].value == "—"
    for page in ["Countries", "Cancellations", "Baskets", "Customers & RFM", "Products"]:
        app.radio[0].set_value(page).run()
        assert not app.exception, page
