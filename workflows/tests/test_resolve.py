from parsing.resolve import base_matcher, parse_citation


def test_a_citation_reaches_every_base_row_beneath_it():
    reach = base_matcher(["7208.51.00.30", "7208.51.00.45", "7208.52.00.00", "7209.15.00"])

    assert reach("7208.51") == ["7208.51.00.30", "7208.51.00.45"]


def test_prefix_matching_stops_at_a_separator():
    # Without the anchor, 2922.49.3 would reach 2922.49.30 and everything under it.
    reach = base_matcher(["2922.49.30.00", "2922.49.49.10"])

    assert reach("2922.49.3") == []
    assert reach("2922.49.30") == ["2922.49.30.00"]


def test_a_code_that_is_itself_a_base_row_matches_exactly():
    reach = base_matcher(["2922.49.30", "2922.49.30.00"])

    assert reach("2922.49.30") == ["2922.49.30", "2922.49.30.00"]


def test_a_retired_code_reaches_nothing_rather_than_guessing():
    assert base_matcher(["2922.49.30.00"])("1901.10.60") == []


def test_a_subchapter_citation_is_read_against_the_citing_provision():
    assert parse_citation("U.S. note 20(b) to this subchapter", "III") == ("III", "20", "b")


def test_a_note_without_a_subdivision_resolves_to_the_note_itself():
    assert parse_citation("U.S. note 52 to this subchapter", "III") == ("III", "52", None)


def test_a_chapter_note_is_not_looked_for_in_this_document():
    # 'additional U.S. note 1 to chapter 4' belongs to chapter 4's own notes.
    assert parse_citation("additional U.S. note 1 to chapter 4", "IV") is None
