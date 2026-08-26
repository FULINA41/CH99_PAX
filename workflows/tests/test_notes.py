from parsing.notes import (NOTE_START, SUBDIVISION_START, NotesData, _codes_named_in_prose,
                           _content_kind, _split_notes, _union_subdivisions, find_codes)


def lines(*text):
    return [(0, t) for t in text]


def test_a_decimal_in_running_text_does_not_open_a_note():
    # '44.5 percent' would otherwise start note 44 and swallow the rest of the subchapter.
    assert NOTE_START.match("44.5 percent ad valorem") is None
    assert NOTE_START.match("44. For the purposes of heading 9903.01.01") is not None


def test_a_note_number_that_goes_backwards_is_a_false_start():
    notes = _split_notes(lines("1. first", "3. third", "2. a stray number in prose",
                               "5. fifth"))

    assert [number for number, _ in notes] == ["1", "3", "5"]


def test_a_skipped_note_number_is_still_a_note():
    # The schedule repeals notes and leaves the gap; subchapter III jumps 3 -> 5.
    notes = _split_notes(lines("3. third", "5. fifth"))

    assert [number for number, _ in notes] == ["3", "5"]


def test_subdivisions_run_past_two_letters():
    # Note 20's exclusions reach (www); a two-letter cap silently loses them.
    assert SUBDIVISION_START.match("(www) Heading 9903.88.69") is not None


def test_concatenated_codes_are_all_read_not_just_the_first():
    # pypdf flattens the four-column list pages into runs with no separator.
    assert find_codes("0201.10.500201.10.100201.10.05") == [
        "0201.10.50", "0201.10.10", "0201.10.05"]


def test_a_digit_run_longer_than_a_code_is_not_mined_for_one():
    # '99 - III - 377' and the like must not yield a code out of their middle.
    assert find_codes("123456.78.90") == []


def test_a_page_of_bare_codes_is_classified_as_a_list():
    body = " ".join(["0201.10.50"] * 40)

    assert _content_kind(body, find_codes(body)) == "subheading_list"


def test_prose_that_happens_to_cite_a_code_is_not_a_list():
    body = ("For the purposes of heading 9903.88.01, products of China classified in "
            "subheading 8471.30.01 shall be subject to an additional 25 percent ad "
            "valorem rate of duty, as provided in this note.")

    assert _content_kind(body, find_codes(body)) == "prose"


def test_a_roman_sub_item_does_not_open_a_second_subdivision():
    # '(i)' is both the ninth letter and the first roman numeral. Inside subdivision (b)
    # it is the latter, and treating it as a subdivision collides with the real (i).
    from parsing.notes import _split_subdivisions

    _, subs = _split_subdivisions(lines("(a) first", "(b) second", "(i) a sub-item of b",
                                        "(c) third"))

    assert [letter for letter, _ in subs] == ["a", "b", "c"]


def test_a_label_quoted_in_prose_does_not_block_the_next_real_one():
    # Note 20's text mentions (vvv); accepting it after (a) hid the real (b) and the
    # 7,000 codes under it.
    from parsing.notes import _split_subdivisions

    _, subs = _split_subdivisions(lines("(a) first", "as provided in", "(vvv) a citation",
                                        "(b) second"))

    assert [letter for letter, _ in subs] == ["a", "b"]


def test_the_sequence_runs_past_z_into_doubled_letters():
    from parsing.notes import _letter_index

    assert _letter_index("z") < _letter_index("aa") < _letter_index("ww") < _letter_index("aaa")


def test_a_note_that_says_only_what_it_covers_gives_up_its_codes():
    # note 31(i). Without this the provision citing it keeps 'all goods of this country',
    # and a 100% duty on rubber gloves lands on every import from China.
    body = ("Heading 9903.91.08 applies to products of China classified in 8-digit "
            "subheading 4015.12.10, effective January 1, 2026.")

    assert _codes_named_in_prose(body) == ["4015.12.10"]


def test_a_note_that_also_says_what_it_excludes_gives_up_nothing():
    # 107 notes state both directions in one body. A code in running text does not carry
    # which sentence it belonged to, so reading it could invert the provision.
    body = ("Heading 9903.88.04 applies to products of China, but shall not apply to "
            "goods classified in subheading 8471.30.01.")

    assert _codes_named_in_prose(body) == []


def test_a_numbered_item_list_inside_a_paragraph_is_read():
    body = ("Heading 9903.91.06 applies to products of China that are classified in the "
            "following subheadings: (1) 2504.10.10 (2) 2504.10.50 (3) 2504.90.00")

    assert _codes_named_in_prose(body) == ["2504.10.10", "2504.10.50", "2504.90.00"]


def test_a_note_record_inherits_the_codes_of_its_subdivisions():
    # U.S. note 20's body runs to 912,964 characters, so its code density reads as prose
    # and it was stored with none -- leaving 38 provisions citing it with nothing to reach.
    data = NotesData(
        notes=[{"subchapter": "III", "note_number": "20", "subdivision": None,
                "content_kind": "prose"}],
        subheadings=[{"note_key": ("III", "20", "b"), "hts_prefix": "8471.30.01", "ordinal": 0},
                     {"note_key": ("III", "20", "c"), "hts_prefix": "7208.51.00", "ordinal": 0},
                     {"note_key": ("III", "20", "c"), "hts_prefix": "8471.30.01", "ordinal": 1}])

    _union_subdivisions(data, "III", "20")

    inherited = [r["hts_prefix"] for r in data.subheadings if r["note_key"] == ("III", "20", None)]
    assert inherited == ["8471.30.01", "7208.51.00"]


def test_a_note_record_that_already_has_codes_is_left_alone():
    data = NotesData(
        notes=[{"subchapter": "III", "note_number": "2", "subdivision": None,
                "content_kind": "subheading_list"}],
        subheadings=[{"note_key": ("III", "2", None), "hts_prefix": "0101.21.00", "ordinal": 0},
                     {"note_key": ("III", "2", "c"), "hts_prefix": "7208.51.00", "ordinal": 0}])

    _union_subdivisions(data, "III", "2")

    assert len(data.subheadings) == 2
