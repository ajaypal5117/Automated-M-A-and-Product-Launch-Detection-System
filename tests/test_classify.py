from corpevents import classify, cleaning


def test_acquisition_from_a_real_filing(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    event, confidence, evidence = classify.classify(text)
    assert event in {"acquisition", "merger"}
    assert confidence > 0.5
    assert evidence


def test_plan_of_merger_language_reads_as_merger(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert classify.classify(text)[0] == "merger"


def test_product_launch(fixture):
    text, _ = cleaning.clean(fixture("8k_launch.txt"))
    assert classify.classify(text)[0] == "product_launch"


def test_divestiture(fixture):
    text, _ = cleaning.clean(fixture("8k_divestiture.txt"))
    assert classify.classify(text)[0] == "divestiture"


def test_earnings_release_is_not_an_event(fixture):
    text, _ = cleaning.clean(fixture("8k_earnings.txt"))
    assert classify.classify(text)[0] is None


def test_dividend_announcement_is_not_an_event(fixture):
    """Item 8.01 passes the item filter, so the cue stage has to reject this."""
    text, _ = cleaning.clean(fixture("8k_dividend.txt"))
    assert classify.classify(text)[0] is None


def test_passing_mention_of_a_past_acquisition_does_not_trigger(fixture):
    """The launch fixture mentions a 2019 acquisition - it must still be a launch."""
    text, _ = cleaning.clean(fixture("8k_launch.txt"))
    assert classify.classify(text)[0] == "product_launch"


def test_counterparty_extraction(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert "Calderon" in classify.counterparty(text)


def test_counterparty_rejects_sentence_fragments():
    assert classify.counterparty("the acquisition of the assets described above") is None


def test_evidence_records_which_cues_fired(fixture):
    text, _ = cleaning.clean(fixture("8k_divestiture.txt"))
    _, _, evidence = classify.classify(text)
    assert any("sell" in cue or "divest" in cue for cue in evidence)
