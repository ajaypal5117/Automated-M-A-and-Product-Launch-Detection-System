from corpevents import money


def test_billions_and_millions():
    assert money.headline_amount("consideration of $2.4 billion") == 2.4e9
    assert money.headline_amount("about $450 million in cash") == 450e6


def test_bare_comma_separated_figure():
    assert money.headline_amount("will pay $1,850,000,000 in cash") == 1_850_000_000


def test_abbreviated_units():
    assert money.headline_amount("a $3.2bn deal") == 3.2e9
    assert money.headline_amount("roughly $75mm") == 75e6


def test_headline_picks_the_aggregate_not_a_component(fixture):
    from corpevents import cleaning
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert money.headline_amount(text) == 2.4e9


def test_per_share_price_is_excluded():
    assert money.headline_amount("closed at $84.20 per share") is None


def test_revenue_figures_are_excluded():
    text = "acquisition for $500 million; the target reported revenue of $900 million"
    assert money.headline_amount(text) == 500e6


def test_no_amount_returns_none():
    assert money.headline_amount("no financial terms were disclosed") is None


def test_all_amounts_keeps_everything_for_diagnostics():
    assert len(money.all_amounts("$1 million and $2 billion and $3")) == 3
