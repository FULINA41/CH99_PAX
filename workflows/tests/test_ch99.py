from parsing.ch99 import (parse_ch99, _countries, _excluded_codes, _note_citations,
                          _scope, _subchapter)


def test_the_subchapter_is_the_headings_last_two_digits_in_roman():
    assert [_subchapter(h) for h in ("9902.04.06", "9903.88.01", "9915.62.01")] == [
        "II", "III", "XV"]


def test_only_chapter_99_codes_inside_an_except_clause_become_exclusions():
    text = ("Except for products described in headings 9903.01.02 and 9903.01.03, "
            "articles the product of Mexico, provided for in subheading 2922.49.30")

    assert _excluded_codes(text) == ["9903.01.02", "9903.01.03"]


def test_except_inside_a_product_description_carves_out_nothing():
    # "of bovine (except calfskin) leather" is a description, not an exclusion; 217 of
    # the 431 "except" clauses in the live data are this shape.
    assert _excluded_codes("Gloves of bovine (except calfskin) leather, provided for "
                           "in subheading 4203.29.15") == []


def test_a_country_list_is_split_and_the_article_dropped():
    named, generic = _countries("articles the product of the European Union or Jordan, "
                                "as provided for in U.S. note 5")

    assert named == ["European Union", "Jordan"]
    assert generic == []


def test_a_preposition_left_by_the_split_is_not_part_of_the_name():
    # "of Germany or of the United Kingdom" leaves 'of the United Kingdom' behind.
    named, _ = _countries("Articles the product of Germany or of the United Kingdom, "
                          "provided for in subheading 8703.23.01")

    assert named == ["Germany", "United Kingdom"]


def test_and_separates_two_countries():
    named, _ = _countries("articles the product of China and Hong Kong, entered under bond")

    assert named == ["China", "Hong Kong"]


def test_but_not_when_it_is_inside_one_countrys_name():
    named, _ = _countries("articles the product of Bosnia and Herzegovina, "
                          "provided for in subheading 7208.51.00")

    assert named == ["Bosnia and Herzegovina"]


def test_a_provision_keyed_on_origin_without_naming_a_country_is_not_invented():
    named, generic = _countries("articles the product of any country, entered under bond")

    assert named == []
    assert generic == ["any country"]


def test_scope_falls_back_to_country_only_when_no_code_is_named():
    assert _scope(["2922.49.30"], ["Mexico"]) == "by_code"
    assert _scope([], ["Mexico"]) == "by_country_all_goods"
    assert _scope([], []) == "unknown"


def test_a_provision_inherits_the_codes_its_ancestors_name(tmp_path):
    # 9903.17.01 says "first quota period" and nothing else; the sugar it applies to is
    # named two levels up.
    payload = tmp_path / "ch99.json"
    payload.write_text('''[
      {"indent":"0","htsno":"","superior":"true","description":"Sugars provided for in subheading 1701.12.10:"},
      {"indent":"1","htsno":"9903.17.01","description":"First quota period","general":"Free"}
    ]''')

    data = parse_ch99(str(payload), source_fetch_id=None)

    assert [e["target_hts"] for e in data.edges] == ["1701.12.10"]
    assert data.rules[0]["scope"] == "by_code"


def test_no_additional_duty_is_a_stated_zero_not_an_unreadable_rate(tmp_path):
    payload = tmp_path / "ch99.json"
    payload.write_text('''[
      {"indent":"0","htsno":"9903.01.01","description":"Articles",
       "general":"Free","additionalDuties":"No additional duty"}
    ]''')

    rule = parse_ch99(str(payload), source_fetch_id=None).rules[0]

    assert (rule["additional_duty_text"], rule["additional_duty_pct"]) == (
        "No additional duty", 0.0)


def test_a_subdivision_named_in_front_is_read_as_a_subdivision():
    # Reading only the inline 'U.S. note 31(g)' form linked 202 provisions to the parent
    # note, which holds the union of its subdivisions' lists.
    assert _note_citations("as provided for in subdivision (g) of U.S. note 31 to this "
                           "subchapter") == [
        ("subdivision (g) of U.S. note 31 to this subchapter", "(g)")]


def test_one_clause_naming_two_subdivisions_becomes_two_citations():
    cited = _note_citations("as provided for in subdivisions (d) and (f) of U.S. note 37 "
                            "to this subchapter")

    assert [path for _, path in cited] == ["(d)", "(f)"]


def test_a_nested_subdivision_path_is_kept_whole():
    assert _note_citations("in subdivision (j)(7)(iii) of U.S. note 52 to this subchapter") == [
        ("subdivision (j)(7)(iii) of U.S. note 52 to this subchapter", "(j)(7)(iii)")]


def test_the_inline_form_records_its_subdivision_the_same_way():
    assert _note_citations("the subheadings enumerated in U.S. note 20(b) to this "
                           "subchapter") == [("U.S. note 20(b) to this subchapter", "(b)")]


def test_a_country_named_after_a_subject_other_than_articles_is_still_found():
    # 'Potash that is a product of Canada' -- without this, 9903.01.15 has no country at
    # all and a China query cannot filter it out.
    named, _ = _countries("Potash that is a product of Canada, as provided for in U.S. note 2")

    assert named == ["Canada"]


def test_a_parenthesis_ends_a_country_name():
    named, _ = _countries("articles the product of Myanmar (Burma), as provided for in "
                          "subdivision (v) of U.S. note 2")

    assert named == ["Myanmar"]


def test_a_name_outside_ascii_survives_the_capture():
    named, _ = _countries("articles the product of C\u00f4te d\u2019Ivoire or Namibia, as provided for in")

    assert named == ["C\u00f4te d\u2019Ivoire", "Namibia"]


def test_an_area_is_not_taken_for_a_country():
    # "the product of any country or area including the United States" splits on 'or',
    # leaving 'area including the United States' looking like a name. It goes to the
    # generic pile, which is reported as an issue, rather than becoming a country link.
    named, generic = _countries("all the foregoing the product of any country or area "
                                "including the United States")

    assert named == []
