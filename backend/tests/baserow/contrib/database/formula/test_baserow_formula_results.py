import datetime
import sys
from datetime import timedelta
from decimal import Decimal
from typing import List, Any, Optional

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils.duration import duration_string
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import FormulaField, Field
from baserow.contrib.database.rows.handler import RowHandler

VALID_FORMULA_TESTS = [
    ("'test'", "test"),
    ("UPPER('test')", "TEST"),
    ("LOWER('TEST')", "test"),
    ("LOWER(UPPER('test'))", "test"),
    ("LOWER(UPPER('test'))", "test"),
    ("CONCAT('test', ' ', 'works')", "test works"),
    ("CONCAT('test', ' ', UPPER('works'))", "test WORKS"),
    (
        "UPPER(" * 100 + "'test'" + ")" * 100,
        "TEST",
    ),
    (
        "UPPER('" + "t" * settings.MAX_FORMULA_STRING_LENGTH + "')",
        "T" * settings.MAX_FORMULA_STRING_LENGTH,
    ),
    ("'https://उदाहरण.परीक्षा'", "https://उदाहरण.परीक्षा"),
    ("UPPER('https://उदाहरण.परीक्षा')", "HTTPS://उदाहरण.परीक्षा"),
    ("CONCAT('https://उदाहरण.परीक्षा', '/api')", "https://उदाहरण.परीक्षा/api"),
    ("LOWER('HTTPS://उदाहरण.परीक्षा')", "https://उदाहरण.परीक्षा"),
    ("CONCAT('\ntest', '\n')", "\ntest\n"),
    ("1+1", "2"),
    ("1/0", "NaN"),
    ("10/3", "3.3333333333"),
    ("10+10/2", "15.0000000000"),
    ("(10+2)/3", "4.0000000000"),
    ("CONCAT(1,2)", "12"),
    ("CONCAT('a',2)", "a2"),
    ("'a' = 'a'", True),
    ("1 = '1'", True),
    ("IF('a' = 'a', 'a', 'b')", "a"),
    ("IF('a' = 'b', 'a', 'b')", "b"),
    ("IF('a' = 'b', 1, 'b')", "b"),
    ("IF('a' = 'a', 1, 'b')", "1"),
    (
        "tonumber('" + "9" * 100 + "')+1",
        "NaN",
    ),
    (
        "9" * 100 + "+1",
        "NaN",
    ),
    ("tonumber('1')", "1.00000"),
    ("tonumber('a')", "NaN"),
    ("tonumber('-12.12345')", "-12.12345"),
    ("1.2 * 2", "2.4"),
    ("isblank(1)", False),
    ("isblank('')", True),
    ("isblank(' ')", False),
    ("t('aaaa')", "aaaa"),
    ("t(10)", ""),
    ("true", True),
    ("false", False),
    ("not(false)", True),
    ("not(true)", False),
    ("true != false", True),
    ("'a' != 'b'", True),
    ("'a' != 'a'", False),
    ("1 != '1'", False),
    ("1 > 1", False),
    ("1 >= 1", True),
    ("1 < 1", False),
    ("1 <= 1", True),
    ("todate('20170103','YYYYMMDD')", "2017-01-03"),
    ("todate('blah', 'YYYY')", None),
    ("day(todate('20170103','YYYYMMDD'))", "3"),
    (
        "date_diff("
        "'yy', "
        "todate('20200101', 'YYYYMMDD'), "
        "todate('20100101', 'YYYYMMDD')"
        ")",
        "-10",
    ),
    (
        "date_diff("
        "'incorrect thingy', "
        "todate('20200101', 'YYYYMMDD'), "
        "todate('20100101', 'YYYYMMDD')"
        ")",
        "NaN",
    ),
    ("and(true, false)", False),
    ("and(false, false)", False),
    ("and(false, true)", False),
    ("and(true, true)", True),
    ("or(true, false)", True),
    ("or(false, false)", False),
    ("or(false, true)", True),
    ("or(true, true)", True),
    ("'a' + 'b'", "ab"),
    ("date_interval('1 year')", duration_string(timedelta(days=365))),
    ("date_interval('1 year') > date_interval('1 day')", True),
    ("date_interval('1 invalid')", None),
    ("todate('20200101', 'YYYYMMDD') + date_interval('1 year')", "2021-01-01"),
    ("date_interval('1 year') + todate('20200101', 'YYYYMMDD')", "2021-01-01"),
    ("todate('20200101', 'YYYYMMDD') + date_interval('1 second')", "2020-01-01"),
    ("todate('20200101', 'YYYYMMDD') - date_interval('1 year')", "2019-01-01"),
    ("month(todate('20200601', 'YYYYMMDD') - date_interval('1 year'))", "6"),
    (
        "month(todate('20200601', 'YYYYMMDD') "
        "+ ("
        "   todate('20200601', 'YYYYMMDD') "
        "   - todate('20100601', 'YYYYMMDD'))"
        ")",
        "6",
    ),
    (
        "todate('20200101', 'YYYYMMDD') - todate('20210101', 'YYYYMMDD')",
        duration_string(-timedelta(days=366)),
    ),
    (
        "date_interval('1 year') - date_interval('1 day')",
        duration_string(timedelta(days=364)),
    ),
    ("replace('test test', 'test', 'a')", "a a"),
    ("search('test test', 'test')", "1"),
    ("search('a', 'test')", "0"),
    ("length('aaa')", "3"),
    ("length('')", "0"),
    ("reverse('abc')", "cba"),
    ("totext(1)", "1"),
    ("totext(true)", "true"),
    ("totext(date_interval('1 year'))", "1 year"),
    ("totext(todate('20200101', 'YYYYMMDD'))", "2020-01-01"),
    ("not(isblank(tonumber('x')))", True),
    ("if(1=1, todate('20200101', 'YYYYMMDD'), 'other')", "2020-01-01"),
    ("not(isblank('')) != false", False),
    ("contains('a', '')", True),
    ("contains('a', 'a')", True),
    ("contains('a', 'x')", False),
    ("left('a', 2)", "a"),
    ("left('abc', 2)", "ab"),
    ("when_empty(1, 2)", "1"),
    ("round(1.12345, 0)", "1"),
    ("round(1.12345, 4)", "1.1234"),
    ("round(1.12345, 100)", "1.12345"),
    ("int(1.1234)", "1"),
    ("int(1.56)", "1"),
    ("int(-1.56)", "-1"),
]


def a_test_case(name: str, starting_table_setup, formula_info, expectation):
    return name, starting_table_setup, formula_info, expectation


def given_a_table(columns, rows):
    return columns, rows


def when_a_formula_field_is_added(formula):
    return formula


def when_multiple_formula_fields_are_added(formulas):
    return formulas


def then_expect_the_rows_to_be(rows):
    return rows


def assert_formula_results_are_case(
    data_fixture,
    given_field_in_table: Field,
    given_field_has_rows: List[Any],
    when_created_formula_is: str,
    then_formula_values_are: List[Any],
):
    assert_formula_results_with_multiple_fields_case(
        data_fixture,
        given_fields_in_table=[given_field_in_table],
        given_fields_have_rows=[[v] for v in given_field_has_rows],
        when_created_formula_is=when_created_formula_is,
        then_formula_values_are=then_formula_values_are,
    )


def assert_formula_results_with_multiple_fields_case(
    data_fixture,
    when_created_formula_is: str,
    then_formula_values_are: List[Any],
    given_fields_in_table: Optional[List[Field]] = None,
    given_fields_have_rows: Optional[List[List[Any]]] = None,
):
    if given_fields_in_table is None:
        given_fields_in_table = []
    if given_fields_have_rows is None:
        given_fields_have_rows = []

    data_fixture.create_rows(given_fields_in_table, given_fields_have_rows)
    formula_field = data_fixture.create_formula_field(
        table=given_fields_in_table[0].table, formula=when_created_formula_is
    )
    assert formula_field.cached_formula_type.is_valid
    rows = data_fixture.get_rows(fields=[formula_field])
    assert [item for sublist in rows for item in sublist] == then_formula_values_are


@pytest.mark.django_db
def test_formula_can_reference_and_add_to_an_integer_column(data_fixture):
    assert_formula_results_are_case(
        data_fixture,
        given_field_in_table=data_fixture.create_number_field(name="number"),
        given_field_has_rows=[1, 2, None],
        when_created_formula_is="field('number') + 1",
        then_formula_values_are=[2, 3, 1],
    )


@pytest.mark.django_db
def test_can_reference_and_if_a_text_column(data_fixture):
    assert_formula_results_are_case(
        data_fixture,
        given_field_in_table=data_fixture.create_text_field(name="text"),
        given_field_has_rows=["a", "b", None],
        when_created_formula_is="if(field('text')='a', field('text'), 'no')",
        then_formula_values_are=["a", "no", "no"],
    )


@pytest.mark.django_db
def test_can_reference_and_if_a_phone_number_column(data_fixture):
    assert_formula_results_are_case(
        data_fixture,
        given_field_in_table=data_fixture.create_phone_number_field(name="pn"),
        given_field_has_rows=["01772", "+2002", None],
        when_created_formula_is="if(field('pn')='01772', field('pn'), 'no')",
        then_formula_values_are=["01772", "no", "no"],
    )


@pytest.mark.django_db
def test_can_compare_a_date_field_and_text_with_formatting(data_fixture):
    assert_formula_results_are_case(
        data_fixture,
        given_field_in_table=data_fixture.create_date_field(
            date_format="US", name="date"
        ),
        given_field_has_rows=["2020-02-01", "2020-03-01", None],
        when_created_formula_is="field('date')='02/01/2020'",
        then_formula_values_are=[True, False, False],
    )


@pytest.mark.django_db
def test_can_compare_a_datetime_field_and_text_with_eu_formatting(data_fixture):
    assert_formula_results_are_case(
        data_fixture,
        given_field_in_table=data_fixture.create_date_field(
            date_format="EU", date_include_time="True", name="date"
        ),
        given_field_has_rows=["2020-02-01T00:10:00Z", "2020-02-01T02:00:00Z", None],
        when_created_formula_is="field('date')='01/02/2020 00:10'",
        then_formula_values_are=[True, False, False],
    )


@pytest.mark.django_db
def test_todate_handles_empty_values(data_fixture):
    assert_formula_results_are_case(
        data_fixture,
        given_field_in_table=data_fixture.create_text_field(name="date_text"),
        given_field_has_rows=[
            "20200201T00:10:00Z",
            "2021-01-22 | Some stuff",
            "",
            "20200201T02:00:00Z",
            None,
        ],
        when_created_formula_is="todate(left(field('date_text'),11),'YYYY-MM-DD')",
        then_formula_values_are=[None, datetime.date(2021, 1, 22), None, None, None],
    )


@pytest.mark.django_db
def test_can_use_a_boolean_field_in_an_if(data_fixture):
    assert_formula_results_are_case(
        data_fixture,
        given_field_in_table=data_fixture.create_boolean_field(name="boolean"),
        given_field_has_rows=[True, False],
        when_created_formula_is="if(field('boolean'), 'true', 'false')",
        then_formula_values_are=["true", "false"],
    )


@pytest.mark.django_db
def test_can_lookup_date_intervals(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    data_fixture.create_formula_field(
        user, table=table_b, formula="date_interval('2 days')", name="date_interval"
    )

    table_b_rows = data_fixture.create_rows_in_table(table=table_b, rows=[[], []])
    row_1 = data_fixture.create_row_for_many_to_many_field(
        table=table_a, field=link_field, values=[table_b_rows[0].id], user=user
    )

    lookup_formula = data_fixture.create_formula_field(
        user=user,
        table=table_a,
        formula=f"lookup('{link_field.name}', 'date_interval')",
    )

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table_a.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert [o[lookup_formula.db_column] for o in response.json()["results"]] == [
        [{"id": row_1.id, "value": "2 days"}]
    ]


@pytest.mark.django_db
def test_can_use_datediff_on_fields(data_fixture):
    table = data_fixture.create_database_table()
    assert_formula_results_with_multiple_fields_case(
        data_fixture,
        given_fields_in_table=[
            data_fixture.create_date_field(
                table=table,
                name="date1",
                date_format="EU",
                date_include_time=True,
            ),
            data_fixture.create_date_field(
                table=table,
                name="date2",
                date_format="EU",
                date_include_time=True,
            ),
        ],
        given_fields_have_rows=[
            ["2020-02-01T00:10:00Z", "2020-03-02T00:10:00Z"],
            ["2020-02-01T02:00:00Z", "2020-10-01T04:00:00Z"],
            [None, None],
        ],
        when_created_formula_is="date_diff('dd', field('date1'), field('date2'))",
        then_formula_values_are=[
            Decimal(30),
            Decimal(243),
            None,
        ],
    )


INVALID_FORMULA_TESTS = [
    (
        "test",
        "ERROR_WITH_FORMULA",
        (
            "Error with formula: Invalid syntax at line 1, col 4: "
            "mismatched input 'the end of the formula' expecting '('."
        ),
    ),
    (
        "UPPER(" * (sys.getrecursionlimit())
        + "'test'"
        + ")" * (sys.getrecursionlimit()),
        "ERROR_WITH_FORMULA",
        "Error with formula: it exceeded the maximum formula size.",
    ),
    (
        "CONCAT(" + ",".join(["'test'"] * 5000) + ")",
        "ERROR_WITH_FORMULA",
        "Error with formula: it exceeded the maximum formula size.",
    ),
    (
        "UPPER('" + "t" * (settings.MAX_FORMULA_STRING_LENGTH + 1) + "')",
        "ERROR_WITH_FORMULA",
        "Error with formula: an embedded "
        f"string in the formula over the maximum length of "
        f"{settings.MAX_FORMULA_STRING_LENGTH} .",
    ),
    (
        "CONCAT()",
        "ERROR_WITH_FORMULA",
        "Error with formula: 0 arguments were given to the function concat, it must "
        "instead be given more than 1 arguments.",
    ),
    (
        "CONCAT('a')",
        "ERROR_WITH_FORMULA",
        "Error with formula: 1 argument was given to the function concat, it must "
        "instead be given more than 1 arguments.",
    ),
    ("UPPER()", "ERROR_WITH_FORMULA", None),
    ("LOWER()", "ERROR_WITH_FORMULA", None),
    (
        "UPPER('a','a')",
        "ERROR_WITH_FORMULA",
        "Error with formula: 2 arguments were given to the function upper, it must "
        "instead be given exactly 1 argument.",
    ),
    ("LOWER('a','a')", "ERROR_WITH_FORMULA", None),
    ("LOWER('a', CONCAT())", "ERROR_WITH_FORMULA", None),
    (
        "'a' + 2",
        "ERROR_WITH_FORMULA",
        "Error with formula: argument number 2 given to operator + was of type number "
        "but the only usable types for this argument are text,char.",
    ),
    (
        "true + true",
        "ERROR_WITH_FORMULA",
        "Error with formula: argument number 2 given to operator + was of type "
        "boolean but there are no possible types usable here.",
    ),
    ("UPPER(1,2)", "ERROR_WITH_FORMULA", None),
    ("UPPER(1)", "ERROR_WITH_FORMULA", None),
    ("LOWER(1,2)", "ERROR_WITH_FORMULA", None),
    ("LOWER(1)", "ERROR_WITH_FORMULA", None),
    ("10/LOWER(1)", "ERROR_WITH_FORMULA", None),
    ("'t'/1", "ERROR_WITH_FORMULA", None),
    ("1/'t'", "ERROR_WITH_FORMULA", None),
    ("field(9999)", "ERROR_WITH_FORMULA", None),
    ("field_by_id(9999)", "ERROR_WITH_FORMULA", None),
    (
        "upper(1)",
        "ERROR_WITH_FORMULA",
        (
            "Error with formula: argument number 1 given to function upper was of type "
            "number but the only usable type for this argument is text."
        ),
    ),
    (
        "concat(upper(1), lower('a'))",
        "ERROR_WITH_FORMULA",
        (
            "Error with formula: argument number 1 given to function upper was of type "
            "number but the only usable type for this argument is text."
        ),
    ),
    (
        "concat(upper(1), lower(2))",
        "ERROR_WITH_FORMULA",
        (
            "Error with formula: argument number 1 given to function upper was of type "
            "number but the only usable type for this argument is text, argument "
            "number 1 given to function lower was of type number but the only usable "
            "type for this argument is text."
        ),
    ),
    ("true > true", "ERROR_WITH_FORMULA", None),
    ("true > 1", "ERROR_WITH_FORMULA", None),
    ("'a' > 1", "ERROR_WITH_FORMULA", None),
    ("true < true", "ERROR_WITH_FORMULA", None),
    ("true < 1", "ERROR_WITH_FORMULA", None),
    ("'a' < 1", "ERROR_WITH_FORMULA", None),
    (
        "todate('20200101', 'YYYYMMDD') + todate('20210101', 'YYYYMMDD')",
        "ERROR_WITH_FORMULA",
        "Error with formula: argument number 2 given to operator + was of type date "
        "but the only usable type for this argument is date_interval.",
    ),
    (
        "date_interval('1 second') - todate('20210101', 'YYYYMMDD')",
        "ERROR_WITH_FORMULA",
        "Error with formula: argument number 2 given to operator - was of type date "
        "but the only usable type for this argument is date_interval.",
    ),
    (
        "when_empty(1, 'a')",
        "ERROR_WITH_FORMULA",
        "Error with formula: both inputs for when_empty must be the same type.",
    ),
    (
        "regex_replace(1, 1, 1)",
        "ERROR_WITH_FORMULA",
        "Error with formula: argument number 1 given to function regex_replace was of "
        "type number but the only usable type for this argument is text, argument "
        "number 2 given to function regex_replace was of type number but the only "
        "usable type for this argument is text, argument number 3 given to function "
        "regex_replace was of type number but the only usable type for this argument "
        "is text.",
    ),
]


@pytest.mark.parametrize("test_input,error,detail", INVALID_FORMULA_TESTS)
@pytest.mark.django_db
def test_invalid_formulas(test_input, error, detail, data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": test_input},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    response_json = response.json()
    assert response_json["error"] == error
    if detail:
        assert response_json["detail"] == detail

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    assert response.json() == []
    assert FormulaField.objects.count() == 0


@pytest.mark.django_db
def test_formula_returns_zeros_instead_of_null_if_output_is_decimal(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    number_field = data_fixture.create_number_field(
        table=table_b,
        name="number",
    )

    table_b_rows = data_fixture.create_rows_in_table(
        table=table_b,
        rows=[["Tesla", 5], ["Apple", None], ["Amazon", 11]],
        fields=[table_b.field_set.get(primary=True), number_field],
    )

    data_fixture.create_row_for_many_to_many_field(
        table=table_a, field=link_field, values=[table_b_rows[0].id], user=user
    )
    data_fixture.create_row_for_many_to_many_field(
        table=table_a,
        field=link_field,
        values=[table_b_rows[0].id, table_b_rows[1].id],
        user=user,
    )
    data_fixture.create_row_for_many_to_many_field(
        table=table_a, field=link_field, values=[], user=user
    )

    count_formula = data_fixture.create_formula_field(
        user=user,
        table=table_a,
        formula=f"count(field('{link_field.name}'))",
    )

    sum_formula = data_fixture.create_formula_field(
        user=user,
        table=table_a,
        formula=f"sum(lookup('{link_field.name}', '{number_field.name}'))",
    )

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table_a.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 3
    assert [
        [o[count_formula.db_column], o[sum_formula.db_column]] for o in results
    ] == [["1", "5"], ["2", "5"], ["0", "0"]]


@pytest.mark.django_db
def test_reference_to_null_number_field_acts_as_zero(
    data_fixture,
):
    number_field = data_fixture.create_number_field()
    formula_field = data_fixture.create_formula_field(
        table=number_field.table, formula="1"
    )

    formula_field.formula = f"field('{number_field.name}') + 1"
    formula_field.save(recalculate=True)

    assert (
        formula_field.internal_formula
        == f"error_to_nan(add(when_empty(field('{number_field.db_column}'),0),1))"
    )
    model = number_field.table.get_model()
    row = model.objects.create(**{f"{number_field.db_column}": None})
    assert getattr(row, formula_field.db_column) == 1


@pytest.mark.django_db
def test_can_make_joining_nested_aggregation(
    data_fixture,
):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    table_c, _, link_c_to_a = data_fixture.create_two_linked_tables(
        user=user, table_b=table_a
    )

    formula_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="formula",
        formula=f"field('{link_c_to_a.link_row_related_field.name}') + join(field('{link_a_to_b.name}'), ',')",
    )
    assert formula_field.formula_type == "array"

    table_b_rows = data_fixture.create_rows_in_table(
        table=table_b,
        rows=[["b_1"], ["b_2"]],
        fields=[table_b.field_set.get(primary=True)],
    )
    table_c_rows = data_fixture.create_rows_in_table(
        table=table_c,
        rows=[["c_1"], ["c_2"]],
        fields=[table_c.field_set.get(primary=True)],
    )
    row_1 = RowHandler().create_row(
        user,
        table_a,
        {
            link_a_to_b.db_column: [
                table_b_rows[0].id,
                table_b_rows[1].id,
            ],
            link_c_to_a.link_row_related_field.db_column: [table_c_rows[0].id],
        },
    )
    row_2 = RowHandler().create_row(
        user,
        table_a,
        {
            link_a_to_b.db_column: [
                table_b_rows[1].id,
            ],
            link_c_to_a.link_row_related_field.db_column: [
                table_c_rows[0].id,
                table_c_rows[1].id,
            ],
        },
    )

    assert formula_field.cached_formula_type.is_valid
    rows = data_fixture.get_rows(fields=[formula_field])
    assert rows == [
        [[{"id": 1, "value": "c_1b_1,b_2"}]],
        [[{"id": 1, "value": "c_1b_2"}, {"id": 2, "value": "c_2b_2"}]],
    ]
