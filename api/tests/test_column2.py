from reference.column2 import column_for


def test_the_four_countries_general_note_3b_names_read_column_2():
    # 7208.51.00.30 is Free in Column 1 and 20% in Column 2. Defaulting a Russian shipment
    # to Column 1 is wrong by the whole duty.
    assert [column_for(c) for c in ("RU", "CU", "KP", "BY")] == ["2"] * 4


def test_every_other_origin_reads_column_1_general():
    assert column_for("CN") == "1-general"
    assert column_for("DE") == "1-general"


def test_no_country_named_falls_back_to_column_1_rather_than_guessing():
    assert column_for(None) == "1-general"
