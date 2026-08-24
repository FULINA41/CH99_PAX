from parsing.ch99 import parse_ch99, _countries, _excluded_codes, _scope, _subchapter


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
