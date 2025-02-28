import random

from django.db.models import Q
from django.utils import timezone as django_timezone
from freezegun import freeze_time

import pytest
from datetime import date, timedelta

from pyinstrument import Profiler
from pytz import timezone

from django.utils.timezone import make_aware, datetime

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.contrib.database.views.registries import (
    view_filter_type_registry,
    ViewFilterType,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.view_filters import BaseDateFieldLookupFilterType


@pytest.mark.django_db
def test_can_use_a_callable_in_compatible_field_types(data_fixture):
    class TestViewFilterType(ViewFilterType):
        type = "test"
        compatible_field_types = [lambda field: field.name == "compatible"]

        def get_filter(
            self, field_name, value, model_field, field
        ) -> OptionallyAnnotatedQ:
            return Q()

    not_compatible_field = data_fixture.create_text_field(name="not_compat")
    assert not TestViewFilterType().field_is_compatible(not_compatible_field)

    compatible_field = data_fixture.create_text_field(name="compatible")
    assert TestViewFilterType().field_is_compatible(compatible_field)


@pytest.mark.django_db
def test_can_mix_field_types_and_callables_in_compatible_field_types(data_fixture):
    class TestViewFilterType(ViewFilterType):
        type = "test"
        compatible_field_types = [
            "text",
            lambda field: field.name == "compatible",
        ]

        def get_filter(
            self, field_name, value, model_field, field
        ) -> OptionallyAnnotatedQ:
            return Q()

    not_compatible_field = data_fixture.create_long_text_field(name="not_compat")
    assert not TestViewFilterType().field_is_compatible(not_compatible_field)

    compatible_field = data_fixture.create_text_field(
        name="name doesn't match but type does"
    )
    assert TestViewFilterType().field_is_compatible(compatible_field)


@pytest.mark.django_db
def test_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    integer_field = data_fixture.create_number_field(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table, number_decimal_places=2
    )
    boolean_field = data_fixture.create_boolean_field(table=table)
    formula_field = data_fixture.create_formula_field(table=table, formula="'test'")

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{text_field.id}": "Test",
            f"field_{long_text_field.id}": "Long",
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 20.20,
            f"field_{boolean_field.id}": True,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "",
            f"field_{long_text_field.id}": "",
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
            f"field_{boolean_field.id}": False,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "NOT",
            f"field_{long_text_field.id}": "NOT2",
            f"field_{integer_field.id}": 99,
            f"field_{decimal_field.id}": 99.99,
            f"field_{boolean_field.id}": False,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="equal", value="Test"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = long_text_field
    view_filter.value = "Long"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = integer_field
    view_filter.value = "10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    # Because the value 'test' cannot be accepted no results will be returned.
    view_filter.field = integer_field
    view_filter.value = "test"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = decimal_field
    view_filter.value = "20.20"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = boolean_field
    view_filter.value = "1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = boolean_field
    view_filter.value = "0"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = text_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = long_text_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = integer_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = decimal_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = boolean_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = formula_field
    view_filter.value = "nottest"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = formula_field
    view_filter.value = "test"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = formula_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3


@pytest.mark.django_db
def test_not_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    integer_field = data_fixture.create_number_field(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table, number_decimal_places=2
    )
    boolean_field = data_fixture.create_boolean_field(table=table)
    formula_field = data_fixture.create_formula_field(table=table, formula="'test'")

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{text_field.id}": "Test",
            f"field_{long_text_field.id}": "Long",
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 20.20,
            f"field_{boolean_field.id}": True,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "",
            f"field_{long_text_field.id}": "",
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
            f"field_{boolean_field.id}": False,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "NOT",
            f"field_{long_text_field.id}": "NOT2",
            f"field_{integer_field.id}": 99,
            f"field_{decimal_field.id}": 99.99,
            f"field_{boolean_field.id}": False,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="not_equal", value="Test"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = long_text_field
    view_filter.value = "Long"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = integer_field
    view_filter.value = "10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    # Because the value 'test' cannot be accepted the filter is not applied so it will
    # return all rows.
    view_filter.field = integer_field
    view_filter.value = "test"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = decimal_field
    view_filter.value = "20.20"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = boolean_field
    view_filter.value = "1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = boolean_field
    view_filter.value = "0"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = text_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = long_text_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = integer_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = decimal_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = boolean_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = formula_field
    view_filter.value = "nottest"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = formula_field
    view_filter.value = "test"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = formula_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3


@pytest.mark.django_db
def test_contains_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    date_field = data_fixture.create_date_field(
        table=table, date_include_time=True, date_format="ISO"
    )
    number_field = data_fixture.create_number_field(
        table=table,
        number_negative=True,
        number_decimal_places=2,
    )
    field_handler = FieldHandler()
    single_select_field = data_fixture.create_single_select_field(table=table)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "CC", "color": "blue"},
            {"value": "DC", "color": "blue"},
        ],
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="AC", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="BC", color="red"
    )
    option_c = data_fixture.create_select_option(
        field=multiple_select_field, value="CE", color="green"
    )
    option_d = data_fixture.create_select_option(
        field=multiple_select_field, value="DE", color="yellow"
    )
    formula_field = data_fixture.create_formula_field(table=table, formula="'test'")

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{text_field.id}": "My name is John Doe.",
            f"field_{long_text_field.id}": "Long text that is not empty.",
            f"field_{date_field.id}": "2020-02-01 01:23",
            f"field_{number_field.id}": "98989898",
            f"field_{single_select_field.id}": option_a,
        }
    )
    getattr(row, f"field_{multiple_select_field.id}").set([option_c.id, option_d.id])
    model.objects.create(
        **{
            f"field_{text_field.id}": "",
            f"field_{long_text_field.id}": "",
            f"field_{date_field.id}": None,
            f"field_{number_field.id}": None,
            f"field_{single_select_field.id}": None,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "This is a test field.",
            f"field_{long_text_field.id}": "This text is a bit longer, but it also "
            "contains.\n A multiline approach.",
            f"field_{date_field.id}": "0001-01-01 00:12",
            f"field_{number_field.id}": "10000",
            f"field_{single_select_field.id}": option_b,
        }
    )
    getattr(row_3, f"field_{multiple_select_field.id}").set([option_c.id])

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains", value="john"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "DOE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "test"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.value = " is "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = "random"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = long_text_field
    view_filter.value = "multiLINE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = date_field
    view_filter.value = "2020-02-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_field
    view_filter.value = "01/02/2020"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = date_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = number_field
    view_filter.value = "98"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = number_field
    view_filter.value = "0" + str(row.id)
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = number_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = date_field
    view_filter.value = "00:12"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = single_select_field
    view_filter.value = "A"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = single_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = single_select_field
    view_filter.value = "C"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = multiple_select_field
    view_filter.value = "C"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = multiple_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = multiple_select_field
    view_filter.value = "D"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = formula_field
    view_filter.value = "tes"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = formula_field
    view_filter.value = "xx"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_contains_not_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    date_field = data_fixture.create_date_field(
        table=table, date_include_time=True, date_format="ISO"
    )
    number_field = data_fixture.create_number_field(
        table=table,
        number_negative=True,
        number_decimal_places=2,
    )
    single_select_field = data_fixture.create_single_select_field(table=table)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="AC", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="BC", color="red"
    )
    option_c = data_fixture.create_select_option(
        field=multiple_select_field, value="CE", color="green"
    )
    option_d = data_fixture.create_select_option(
        field=multiple_select_field, value="DE", color="yellow"
    )
    formula_field = data_fixture.create_formula_field(table=table, formula="'test'")

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{text_field.id}": "My name is John Doe.",
            f"field_{long_text_field.id}": "Long text that is not empty.",
            f"field_{date_field.id}": "2020-02-01 01:23",
            f"field_{number_field.id}": "98989898",
            f"field_{single_select_field.id}": option_a,
        }
    )
    getattr(row, f"field_{multiple_select_field.id}").set([option_c.id, option_d.id])

    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "",
            f"field_{long_text_field.id}": "",
            f"field_{date_field.id}": None,
            f"field_{number_field.id}": None,
            f"field_{single_select_field.id}": None,
        }
    )

    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "This is a test field.",
            f"field_{long_text_field.id}": "This text is a bit longer, but it also "
            "contains.\n A multiline approach.",
            f"field_{date_field.id}": "0001-01-01 00:12",
            f"field_{number_field.id}": "10000",
            f"field_{single_select_field.id}": option_b,
        }
    )
    getattr(row_3, f"field_{multiple_select_field.id}").set([option_d.id])

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains_not", value="john"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "DOE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "test"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    view_filter.value = " is "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = "random"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = long_text_field
    view_filter.value = "multiLINE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    view_filter.field = date_field
    view_filter.value = "2020-02-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = date_field
    view_filter.value = "01/02/2020"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = date_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = number_field
    view_filter.value = "98"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = number_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = date_field
    view_filter.value = "00:12"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id not in ids

    view_filter.field = single_select_field
    view_filter.value = "A"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = single_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = single_select_field
    view_filter.value = "C"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.field = multiple_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = multiple_select_field
    view_filter.value = "D"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.field = multiple_select_field
    view_filter.value = "C"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = formula_field
    view_filter.value = "tes"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = formula_field
    view_filter.value = "xx"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3


@pytest.mark.django_db
def test_single_select_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_single_select_field(table=table)
    option_a = data_fixture.create_select_option(field=field, value="A", color="blue")
    option_b = data_fixture.create_select_option(field=field, value="B", color="red")

    handler = ViewHandler()
    model = table.get_model()

    row_1 = model.objects.create(
        **{
            f"field_{field.id}_id": option_a.id,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{field.id}_id": option_b.id,
        }
    )
    model.objects.create(
        **{
            f"field_{field.id}_id": None,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, type="single_select_equal", value=""
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = str(option_a.id)
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = str(option_b.id)
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "Test"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3


@pytest.mark.django_db
def test_single_select_equal_filter_type_export_import():
    view_filter_type = view_filter_type_registry.get("single_select_equal")
    id_mapping = {"database_field_select_options": {1: 2}}
    assert view_filter_type.get_export_serialized_value("1") == "1"
    assert view_filter_type.set_import_serialized_value("1", id_mapping) == "2"
    assert view_filter_type.set_import_serialized_value("", id_mapping) == ""
    assert view_filter_type.set_import_serialized_value("wrong", id_mapping) == ""


@pytest.mark.django_db
def test_single_select_not_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_single_select_field(table=table)
    option_a = data_fixture.create_select_option(field=field, value="A", color="blue")
    option_b = data_fixture.create_select_option(field=field, value="B", color="red")

    handler = ViewHandler()
    model = table.get_model()

    row_1 = model.objects.create(
        **{
            f"field_{field.id}_id": option_a.id,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{field.id}_id": option_b.id,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{field.id}_id": None,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, type="single_select_not_equal", value=""
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = str(option_a.id)
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = str(option_b.id)
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = "Test"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3


@pytest.mark.django_db
def test_boolean_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    boolean_field = data_fixture.create_boolean_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{boolean_field.id}": True,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{boolean_field.id}": False,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=boolean_field, type="boolean", value="TRUE"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "Y"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "on"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "false"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "no"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "off"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids


@pytest.mark.django_db
def test_higher_than_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    integer_field = data_fixture.create_number_field(table=table, number_negative=True)
    decimal_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=2,
        number_negative=True,
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 20.20,
        }
    )
    model.objects.create(
        **{
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{integer_field.id}": 99,
            f"field_{decimal_field.id}": 99.99,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{integer_field.id}": -10,
            f"field_{decimal_field.id}": -30.33,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=integer_field, type="higher_than", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "9.4444"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "9.8"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    # with an invalid filter value no results are returned
    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "-5"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "-11"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.value = "-10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "-9.99999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "9.9999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "20.19999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "20.20001"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = decimal_field
    view_filter.value = "99.98"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "1000"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    # with an invalid filter value no results are returned
    view_filter.field = decimal_field
    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_lower_than_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    integer_field = data_fixture.create_number_field(table=table, number_negative=True)
    decimal_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=2,
        number_negative=True,
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 20.20,
        }
    )
    model.objects.create(
        **{
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{integer_field.id}": 99,
            f"field_{decimal_field.id}": 99.99,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{integer_field.id}": -10,
            f"field_{decimal_field.id}": -30.33,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=integer_field, type="lower_than", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "9.4444"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "9.8"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    # with an invalid filter value no results are returned
    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "-5"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "-9"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "-10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "-9.99999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "9.9999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "20.199999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "20.20001"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "99.98"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "1000"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    # with an invalid filter value no results are returned
    view_filter.field = decimal_field
    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_date_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()
    utc = timezone("UTC")

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2020, 6, 17),
            f"field_{date_time_field.id}": make_aware(
                datetime(2020, 6, 17, 1, 30, 0), utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2019, 1, 1),
            f"field_{date_time_field.id}": make_aware(
                datetime(2020, 6, 17, 1, 30, 5), utc
            ),
        }
    )
    model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
            f"field_{date_time_field.id}": make_aware(
                datetime(2010, 2, 4, 2, 45, 45), utc
            ),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_equal", value="2020-06-17"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_field
    view_filter.value = "2019-01-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.field = date_field
    view_filter.value = "2018-01-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = date_field
    view_filter.value = "2019-01-01 12:00:00"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    # If an empty value is provided then the filter will not be applied, so we expect
    # all the rows.
    view_filter.field = date_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.field = date_time_field
    view_filter.value = " 2020-06-17 01:30:00 "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17 01:30:05"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17 01:30:10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    view_filter.field = date_time_field
    view_filter.value = "  2020-06-17  "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    # If an empty value is provided then the filter will not be applied, so we expect
    # all the rows.
    view_filter.field = date_time_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4


@pytest.mark.django_db
def test_last_modified_date_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    last_modified_field_date = data_fixture.create_last_modified_field(
        table=table, date_include_time=False, timezone="Europe/Berlin"
    )
    last_modified_field_datetime = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/Berlin"
    )
    model = table.get_model()

    with freeze_time("2021-08-04 21:59", tz_offset=+2):
        row = model.objects.create(**{})

    with freeze_time("2021-08-04 22:01", tz_offset=+2):
        row_1 = model.objects.create(**{})

    with freeze_time("2021-08-04 23:01", tz_offset=+2):
        row_2 = model.objects.create(**{})

    handler = ViewHandler()
    model = table.get_model()

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime,
        type="date_equal",
        value="2021-08-04",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    filter.field = last_modified_field_date
    filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids
    assert row_1.id not in ids
    assert row_2.id not in ids


@pytest.mark.django_db
def test_last_modified_datetime_equals_days_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    tzone = "Europe/Berlin"
    last_modified_field_date = data_fixture.create_last_modified_field(
        table=table, date_include_time=False, timezone=tzone
    )
    last_modified_field_datetime = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone=tzone
    )

    model = table.get_model()

    days_ago = 1
    when = datetime.utcnow().astimezone(timezone(tzone)) - timedelta(days=days_ago)

    # the first and only object created with the correct amount of days ago
    with freeze_time(when.replace(hour=4, minute=59)):
        row = model.objects.create(**{})

    # one day after the filter
    day_after = when + timedelta(days=1)
    with freeze_time(day_after):
        row_2 = model.objects.create(**{})

    # one day before the filter
    with freeze_time(when - timedelta(hours=(when.hour + 1))):
        row_3 = model.objects.create(**{})

    with freeze_time(when.strftime("%Y-%m-%d")):
        row_4 = model.objects.create(**{})

    with freeze_time(day_after.strftime("%Y-%m-%d")):
        row_5 = model.objects.create(**{})

    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime,
        type="date_equals_days_ago",
        value=f"{tzone}?{days_ago}",
    )

    ids = apply_filter()
    assert len(ids) == 2
    assert row.id in ids
    assert row_4.id in ids

    filter.field = last_modified_field_date
    filter.save()
    ids = apply_filter()
    assert len(ids) == 2
    assert row.id in ids
    assert row_4.id in ids

    # an invalid value results in an empty filter
    for invalid_value in ["", f"?", f"{tzone}?1?", f"{tzone}?"]:
        filter.value = invalid_value
        filter.save()
        ids = apply_filter()
        assert len(ids) == 5
        for r in [row, row_2, row_3, row_4, row_5]:
            assert r.id in ids

    # if `days_ago` value results in a BC date, no results are returned
    max_days_ago = (datetime.utcnow() - datetime(1, 1, 1)).days
    filter.value = f"UTC?{max_days_ago + 1}"
    filter.save()
    ids = apply_filter()
    assert len(ids) == 0


@pytest.mark.django_db
def test_last_modified_date_equals_days_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    tzone = "Europe/Berlin"

    handler = ViewHandler()
    model = table.get_model()

    test_date = date(2021, 2, 1)

    row = model.objects.create(
        **{
            f"field_{date_field.id}": test_date,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 1),
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 2),
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": None,
        }
    )
    row_5 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
        }
    )

    test_datetime = datetime.combine(test_date, datetime.min.time())
    days_ago = (datetime.utcnow() - test_datetime).days

    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=date_field,
        type="date_equals_days_ago",
        value=f"{tzone}?{days_ago}",
    )

    ids = apply_filter()
    assert len(ids) == 1
    assert row.id in ids

    filter.value = f"?{days_ago + 1}"
    filter.save()
    ids = apply_filter()
    assert len(ids) == 0

    filter.value = f"?"
    filter.save()
    ids = apply_filter()
    assert len(ids) == 5
    for r in [row, row_2, row_3, row_4, row_5]:
        assert r.id in ids

    # an invalid value results in an empty filter
    for invalid_value in ["", f"?", f"{tzone}?1?", f"{tzone}?"]:
        filter.value = invalid_value
        filter.save()
        ids = apply_filter()
        assert len(ids) == 5
        for r in [row, row_2, row_3, row_4, row_5]:
            assert r.id in ids

    # if `days_ago` value results in a BC date, no results are returned
    max_days_ago = (datetime.utcnow() - datetime(1, 1, 1)).days
    filter.value = f"UTC?{max_days_ago + 1}"
    filter.save()
    ids = apply_filter()
    assert len(ids) == 0


@pytest.mark.django_db
def test_last_modified_day_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    last_modified_field_datetime_berlin = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/Berlin"
    )
    last_modified_field_datetime_london = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/London"
    )
    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    with freeze_time("2021-08-04 21:59"):
        row = model.objects.create(**{})

    with freeze_time("2021-08-04 22:01"):
        row_1 = model.objects.create(**{})

    with freeze_time("2021-08-04 23:01"):
        row_2 = model.objects.create(**{})

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime_london,
        type="date_equals_today",
        value="Europe/London",
    )

    with freeze_time("2021-08-04 01:00"):

        # LastModified Column is based on London Time
        # Filter value is based on London Time
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id in ids
        assert row_1.id in ids
        assert row_2.id not in ids

    with freeze_time("2021-08-04 22:59"):

        # LastModified Column is based on London Time
        # Filter value is based on London Time
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id in ids
        assert row_1.id in ids
        assert row_2.id not in ids

    with freeze_time("2021-08-04 23:59"):

        # LastModified Column is based on London Time
        # Filter value is based on London Time
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id not in ids
        assert row_1.id not in ids
        assert row_2.id in ids

    with freeze_time("2021-08-04"):

        # LastModified Column is based on London Time
        # Filter value is based on London Time
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id in ids
        assert row_1.id in ids
        assert row_2.id not in ids

        # LastModified Column is based on London Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id in ids
        assert row_1.id not in ids
        assert row_2.id not in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_berlin
        filter.value = "Europe/London"
        filter.save()

        ids = apply_filter()
        assert len(ids) == 2
        assert row.id in ids
        assert row_1.id in ids
        assert row_2.id not in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id in ids
        assert row_1.id not in ids
        assert row_2.id not in ids

    with freeze_time("2021-08-05"):
        # LastModified Column is based on London Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_london
        filter.value = "Europe/London"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id not in ids
        assert row_1.id not in ids
        assert row_2.id in ids

        # LastModified Column is based on London Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id not in ids
        assert row_1.id in ids
        assert row_2.id in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_berlin
        filter.value = "Europe/London"
        filter.save()

        ids = apply_filter()
        assert len(ids) == 1
        assert row.id not in ids
        assert row_1.id not in ids
        assert row_2.id in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id not in ids
        assert row_1.id in ids
        assert row_2.id in ids


@pytest.mark.django_db
def test_last_modified_month_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    last_modified_field_datetime_berlin = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/Berlin"
    )
    last_modified_field_datetime_london = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/London"
    )
    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    with freeze_time("2021-08-31 21:59"):
        row = model.objects.create(**{})

    with freeze_time("2021-08-31 22:01"):
        row_1 = model.objects.create(**{})

    with freeze_time("2021-08-31 23:01"):
        row_2 = model.objects.create(**{})

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime_london,
        type="date_equals_month",
        value="Europe/London",
    )

    with freeze_time("2021-08-31"):

        # LastModified Column is based on London Time
        # Filter value is based on London Time
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id in ids
        assert row_1.id in ids
        assert row_2.id not in ids

        # LastModified Column is based on London Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id in ids
        assert row_1.id not in ids
        assert row_2.id not in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_berlin
        filter.value = "Europe/London"
        filter.save()

        ids = apply_filter()
        assert len(ids) == 2
        assert row.id in ids
        assert row_1.id in ids
        assert row_2.id not in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id in ids
        assert row_1.id not in ids
        assert row_2.id not in ids

    with freeze_time("2021-09-01"):
        # LastModified Column is based on London Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_london
        filter.value = "Europe/London"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id not in ids
        assert row_1.id not in ids
        assert row_2.id in ids

        # LastModified Column is based on London Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id not in ids
        assert row_1.id in ids
        assert row_2.id in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_berlin
        filter.value = "Europe/London"
        filter.save()

        ids = apply_filter()
        assert len(ids) == 1
        assert row.id not in ids
        assert row_1.id not in ids
        assert row_2.id in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id not in ids
        assert row_1.id in ids
        assert row_2.id in ids


@pytest.mark.django_db
def test_last_modified_year_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    last_modified_field_datetime_berlin = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/Berlin"
    )
    last_modified_field_datetime_london = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/London"
    )
    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    with freeze_time("2021-12-31 22:59"):
        row = model.objects.create(**{})

    with freeze_time("2021-12-31 23:01"):
        row_1 = model.objects.create(**{})

    with freeze_time("2022-01-01 00:01"):
        row_2 = model.objects.create(**{})

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime_london,
        type="date_equals_year",
        value="Europe/London",
    )

    with freeze_time("2021-12-31"):

        # LastModified Column is based on London Time
        # Filter value is based on London Time
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id in ids
        assert row_1.id in ids
        assert row_2.id not in ids

        # LastModified Column is based on London Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id in ids
        assert row_1.id not in ids
        assert row_2.id not in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_berlin
        filter.value = "Europe/London"
        filter.save()

        ids = apply_filter()
        assert len(ids) == 2
        assert row.id in ids
        assert row_1.id in ids
        assert row_2.id not in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id in ids
        assert row_1.id not in ids
        assert row_2.id not in ids

    with freeze_time("2022-01-01"):
        # LastModified Column is based on London Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_london
        filter.value = "Europe/London"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 1
        assert row.id not in ids
        assert row_1.id not in ids
        assert row_2.id in ids

        # LastModified Column is based on London Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id not in ids
        assert row_1.id in ids
        assert row_2.id in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on London Time
        filter.field = last_modified_field_datetime_berlin
        filter.value = "Europe/London"
        filter.save()

        ids = apply_filter()
        assert len(ids) == 1
        assert row.id not in ids
        assert row_1.id not in ids
        assert row_2.id in ids

        # LastModified Column is based on Berlin Time
        # Filter value is based on Berlin Time
        filter.value = "Europe/Berlin"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 2
        assert row.id not in ids
        assert row_1.id in ids
        assert row_2.id in ids


@pytest.mark.django_db
def test_date_day_month_year_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 2, 1),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 1),
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 2),
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": None,
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_equals_today", value="UTC"
    )

    with freeze_time("2021-01-01 01:01"):
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row.id not in ids

        view_filter.type = "date_equals_month"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 2
        assert row_2.id in ids
        assert row_3.id in ids

        view_filter.type = "date_equals_year"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 3
        assert row.id in ids
        assert row_2.id in ids
        assert row_3.id in ids

    view_filter.type = "date_equals_today"
    view_filter.save()

    with freeze_time("2021-01-02 01:01"):
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row_3.id in ids

        view_filter.value = "Etc/GMT+2"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row.id not in ids

        view_filter.value = "NOT_EXISTING_SO_WILL_BE_UTC"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row_3.id in ids


@pytest.mark.django_db
def test_date_not_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()
    utc = timezone("UTC")

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2020, 6, 17),
            f"field_{date_time_field.id}": make_aware(
                datetime(2020, 6, 17, 1, 30, 0), utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2019, 1, 1),
            f"field_{date_time_field.id}": make_aware(
                datetime(2020, 6, 17, 1, 30, 5), utc
            ),
        }
    )
    row_3 = model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
            f"field_{date_time_field.id}": make_aware(
                datetime(2010, 2, 4, 2, 45, 45), utc
            ),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_not_equal", value="2020-06-17"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_field
    view_filter.value = "2019-01-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_field
    view_filter.value = "2018-01-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.field = date_field
    view_filter.value = "2019-01-01 12:00:00"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    # If an empty value is provided then the filter will not be applied, so we expect
    # all the rows.
    view_filter.field = date_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.field = date_time_field
    view_filter.value = " 2020-06-17 01:30:00 "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17 01:30:05"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_2.id not in ids

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17 01:30:10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "  2020-06-17  "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_4.id in ids

    # If an empty value is provided then the filter will not be applied, so we expect
    # all the rows.
    view_filter.field = date_time_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4


def test_date_parser_mixin():
    date_parser = BaseDateFieldLookupFilterType()
    date_string = "2021-07-05"
    parsed_date = date_parser.parse_date(date_string)
    assert parsed_date.year == 2021
    assert parsed_date.month == 7
    assert parsed_date.day == 5

    date_string = " 2021-07-06 "
    parsed_date = date_parser.parse_date(date_string)
    assert parsed_date.year == 2021
    assert parsed_date.month == 7
    assert parsed_date.day == 6

    date_string = ""
    with pytest.raises(ValueError):
        date_parser.parse_date(date_string)

    date_string = "2021-15-15"
    with pytest.raises(ValueError):
        date_parser.parse_date(date_string)


@pytest.mark.django_db
def test_date_before_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()
    utc = timezone("UTC")

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 7, 5),
            f"field_{date_time_field.id}": make_aware(
                datetime(2021, 7, 5, 1, 30, 0), utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 7, 6),
            f"field_{date_time_field.id}": make_aware(
                datetime(2021, 7, 6, 1, 30, 5), utc
            ),
        }
    )
    row_3 = model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 8, 1),
            f"field_{date_time_field.id}": make_aware(
                datetime(2021, 8, 1, 2, 45, 45), utc
            ),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_before", value="2021-07-06"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-06"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row.id in ids
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids


@pytest.mark.django_db
def test_date_after_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()
    utc = timezone("UTC")

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 7, 5),
            f"field_{date_time_field.id}": make_aware(
                datetime(2021, 7, 5, 1, 30, 0), utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 7, 6),
            f"field_{date_time_field.id}": make_aware(
                datetime(2021, 7, 6, 2, 40, 5), utc
            ),
        }
    )
    row_3 = model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 8, 1),
            f"field_{date_time_field.id}": make_aware(
                datetime(2021, 8, 1, 2, 45, 45), utc
            ),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_after", value="2021-07-06"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-06"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row.id in ids
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids


@pytest.mark.django_db
def test_empty_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    integer_field = data_fixture.create_number_field(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table, number_decimal_places=2
    )
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    boolean_field = data_fixture.create_boolean_field(table=table)
    file_field = data_fixture.create_file_field(table=table)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(field=single_select_field)
    populated_formula_field = data_fixture.create_formula_field(
        table=table, formula="'test'"
    )
    empty_formula_field = data_fixture.create_formula_field(table=table, formula="''")
    populated_date_interval_formula_field = data_fixture.create_formula_field(
        table=table, formula="date_interval('1 year')"
    )

    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_2 = data_fixture.create_select_option(field=multiple_select_field)
    option_3 = data_fixture.create_select_option(field=multiple_select_field)

    tmp_table = data_fixture.create_database_table(database=table.database)
    tmp_field = data_fixture.create_text_field(table=tmp_table, primary=True)
    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Link row",
        type_name="link_row",
        link_row_table=tmp_table,
    )
    tmp_row = tmp_table.get_model().objects.create(**{f"field_{tmp_field.id}": "Test"})

    handler = ViewHandler()
    model = table.get_model()
    utc = timezone("UTC")

    row = model.objects.create(
        **{
            f"field_{text_field.id}": "",
            f"field_{long_text_field.id}": "",
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
            f"field_{date_field.id}": None,
            f"field_{date_time_field.id}": None,
            f"field_{boolean_field.id}": False,
            f"field_{file_field.id}": [],
            f"field_{single_select_field.id}_id": None,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Value",
            f"field_{long_text_field.id}": "Value",
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 1022,
            f"field_{date_field.id}": date(2020, 6, 17),
            f"field_{date_time_field.id}": make_aware(
                datetime(2020, 6, 17, 1, 30, 0), utc
            ),
            f"field_{boolean_field.id}": True,
            f"field_{file_field.id}": [{"name": "test_file.png"}],
            f"field_{single_select_field.id}_id": option_1.id,
        }
    )
    getattr(row_2, f"field_{link_row_field.id}").add(tmp_row.id)
    getattr(row_2, f"field_{multiple_select_field.id}").add(option_2.id)
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": " ",
            f"field_{long_text_field.id}": " ",
            f"field_{integer_field.id}": 0,
            f"field_{decimal_field.id}": 0.00,
            f"field_{date_field.id}": date(1970, 1, 1),
            f"field_{date_time_field.id}": make_aware(
                datetime(1970, 1, 1, 0, 0, 0), utc
            ),
            f"field_{boolean_field.id}": True,
            f"field_{file_field.id}": [
                {"name": "test_file.png"},
                {"name": "another_file.jpg"},
            ],
            f"field_{single_select_field.id}_id": option_1.id,
        }
    )
    getattr(row_3, f"field_{link_row_field.id}").add(tmp_row.id)
    getattr(row_3, f"field_{multiple_select_field.id}").add(option_2.id, option_3.id)

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="empty", value=""
    )
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = long_text_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = integer_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = decimal_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = date_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = date_time_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = link_row_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = boolean_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = file_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = single_select_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = multiple_select_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = empty_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = populated_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = populated_date_interval_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0


@pytest.mark.django_db
def test_not_empty_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    integer_field = data_fixture.create_number_field(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table, number_decimal_places=2
    )
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    boolean_field = data_fixture.create_boolean_field(table=table)
    file_field = data_fixture.create_file_field(table=table)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(field=single_select_field)
    populated_formula_field = data_fixture.create_formula_field(
        table=table, formula="'test'"
    )
    empty_formula_field = data_fixture.create_formula_field(table=table, formula="''")
    populated_date_interval_formula_field = data_fixture.create_formula_field(
        table=table, formula="date_interval('1 year')"
    )

    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_2 = data_fixture.create_select_option(field=multiple_select_field)
    option_3 = data_fixture.create_select_option(field=multiple_select_field)

    tmp_table = data_fixture.create_database_table(database=table.database)
    tmp_field = data_fixture.create_text_field(table=tmp_table, primary=True)
    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Link row",
        type_name="link_row",
        link_row_table=tmp_table,
    )
    tmp_row = tmp_table.get_model().objects.create(**{f"field_{tmp_field.id}": "Test"})

    handler = ViewHandler()
    model = table.get_model()
    utc = timezone("UTC")

    model.objects.create(
        **{
            f"field_{text_field.id}": "",
            f"field_{long_text_field.id}": "",
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
            f"field_{date_field.id}": None,
            f"field_{date_time_field.id}": None,
            f"field_{boolean_field.id}": False,
            f"field_{file_field.id}": [],
            f"field_{single_select_field.id}": None,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Value",
            f"field_{long_text_field.id}": "Value",
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 1022,
            f"field_{date_field.id}": date(2020, 6, 17),
            f"field_{date_time_field.id}": make_aware(
                datetime(2020, 6, 17, 1, 30, 0), utc
            ),
            f"field_{boolean_field.id}": True,
            f"field_{file_field.id}": [{"name": "test_file.png"}],
            f"field_{single_select_field.id}_id": option_1.id,
        }
    )
    getattr(row_2, f"field_{link_row_field.id}").add(tmp_row.id)
    getattr(row_2, f"field_{multiple_select_field.id}").add(option_2.id)
    getattr(row_2, f"field_{multiple_select_field.id}").add(option_3.id)

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="not_empty", value=""
    )
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = long_text_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = integer_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = decimal_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = date_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = date_time_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = link_row_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = boolean_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = file_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = single_select_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = empty_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = populated_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 2

    view_filter.field = populated_date_interval_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 2


@pytest.mark.django_db
def test_filename_contains_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    file_field = data_fixture.create_file_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{file_field.id}": [{"visible_name": "test_file.png"}],
        }
    )
    row_with_multiple_files = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test.doc"},
                {"visible_name": "test.txt"},
            ],
        }
    )
    row_with_no_files = model.objects.create(
        **{
            f"field_{file_field.id}": [],
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="filename_contains",
        value="test_file.png",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = ".jpg"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = ".png"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "test."
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_with_multiple_files.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_with_multiple_files.id in ids
    assert row_with_no_files.id in ids

    results = model.objects.all().filter_by_fields_object(
        filter_object={
            f"filter__field_{file_field.id}__filename_contains": [".png"],
        },
        filter_type="AND",
    )
    assert len(results) == 1


@pytest.mark.django_db
def test_has_file_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    file_field = data_fixture.create_file_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row_with_single_image = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test_file.jpg", "is_image": True}
            ],
        }
    )
    row_with_single_document = model.objects.create(
        **{
            f"field_{file_field.id}": [{"visible_name": "doc.doc", "is_image": False}],
        }
    )
    row_with_multiple_documents = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test.doc", "is_image": False},
                {"visible_name": "test.txt", "is_image": False},
                {"visible_name": "test.doc", "is_image": False},
                {"visible_name": "test.txt", "is_image": False},
            ],
        }
    )
    row_with_multiple_images = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test.jpg", "is_image": True},
                {"visible_name": "test.png", "is_image": True},
            ],
        }
    )
    row_with_single_image_and_multiple_documents = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test_doc.doc", "is_image": False},
                {"visible_name": "test_doc.doc", "is_image": False},
                {"visible_name": "test_image.jpg", "is_image": True},
                {"visible_name": "test_doc.doc", "is_image": False},
            ],
        }
    )
    row_with_single_document_and_multiple_images = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "image1.jpg", "is_image": True},
                {"visible_name": "image2.png", "is_image": True},
                {"visible_name": "doc.doc", "is_image": False},
                {"visible_name": "image3.jpg", "is_image": True},
            ],
        }
    )
    model.objects.create(**{f"field_{file_field.id}": []})

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="has_file_type",
        value="",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 7

    view_filter.value = "image"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row_with_single_image.id in ids
    assert row_with_multiple_images.id in ids
    assert row_with_single_image_and_multiple_documents.id in ids
    assert row_with_single_document_and_multiple_images.id in ids

    view_filter.value = "document"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row_with_single_document.id in ids
    assert row_with_multiple_documents.id in ids
    assert row_with_single_image_and_multiple_documents.id in ids
    assert row_with_single_document_and_multiple_images.id in ids

    data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="has_file_type",
        value="image",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_with_single_image_and_multiple_documents.id in ids
    assert row_with_single_document_and_multiple_images.id in ids


@pytest.mark.django_db
def test_link_row_preload_values(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table, primary=True)
    related_primary_field = data_fixture.create_text_field(
        table=related_table, primary=True
    )
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 1",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_row_1.id],
        },
    )
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"",
    )
    assert view_filter.preload_values["display_name"] is None

    view_filter.value = "test"
    view_filter.save()
    assert view_filter.preload_values["display_name"] is None

    view_filter.value = "-1"
    view_filter.save()
    assert view_filter.preload_values["display_name"] is None

    with django_assert_num_queries(4):
        view_filter.value = f"{related_row_1.id}"
        view_filter.save()
        assert view_filter.preload_values["display_name"] == "Related row 1"


@pytest.mark.django_db
def test_link_row_has_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    related_primary_field = data_fixture.create_text_field(table=related_table)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 1",
        },
    )
    related_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 2",
        },
    )
    related_row_3 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 3",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_row_1.id],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_row_2.id],
        },
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 3",
            f"field_{link_row_field.id}": [related_row_3.id],
        },
    )
    row_with_all_relations = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 4",
            f"field_{link_row_field.id}": [
                related_row_1.id,
                related_row_2.id,
                related_row_3.id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = f"{related_row_1.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = f"{related_row_2.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = f"{related_row_3.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_with_all_relations.id in ids

    # Chaining filters should also work
    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"{related_row_1.id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_with_all_relations.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_3.id in ids
    assert row_with_all_relations.id in ids


@pytest.mark.django_db
def test_link_row_reference_same_table_has_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=table,
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_0 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [row_0.id],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [row_0.id, row_1.id],
        },
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 3",
            f"field_{link_row_field.id}": [row_2.id],
        },
    )
    row_with_all_relations = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 4",
            f"field_{link_row_field.id}": [
                row_0.id,
                row_1.id,
                row_2.id,
                row_3.id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = f"{row_0.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = f"{row_2.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = f"{row_3.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_with_all_relations.id in ids

    # Chaining filters should also work
    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"{row_1.id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_with_all_relations.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_relations.id in ids


@pytest.mark.django_db
def test_link_row_has_not_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    related_primary_field = data_fixture.create_text_field(table=related_table)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 1",
        },
    )
    related_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 2",
        },
    )
    related_row_3 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 3",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_row_1.id],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_row_2.id],
        },
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 3",
            f"field_{link_row_field.id}": [related_row_3.id],
        },
    )
    row_with_all_relations = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 4",
            f"field_{link_row_field.id}": [
                related_row_1.id,
                related_row_2.id,
                related_row_3.id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has_not",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = f"{related_row_1.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id not in ids
    assert row_with_all_relations.id not in ids

    view_filter.value = f"{related_row_2.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_2.id not in ids
    assert row_with_all_relations.id not in ids

    view_filter.value = f"{related_row_3.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_3.id not in ids
    assert row_with_all_relations.id not in ids

    # Chaining filters should also work
    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has_not",
        value=f"{related_row_1.id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_with_all_relations.id not in ids


@pytest.mark.django_db
def test_multiple_select_has_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi Select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "red"},
        ],
    )

    row_handler = RowHandler()
    model = table.get_model()

    select_options = multiple_select_field.select_options.all()
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[0].id,
                select_options[1].id,
            ],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [],
        },
    )

    row_with_all_select_options = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[0].id,
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = f"{select_options[0].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_with_all_select_options.id in ids

    view_filter.value = f"{select_options[1].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_with_all_select_options.id in ids

    view_filter.value = f"{select_options[2].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_select_options.id in ids

    # chaining filters should also work
    view_filter.value = f"{select_options[2].id}"
    view_filter.save()

    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has",
        value=f"{select_options[1].id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_select_options.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_with_all_select_options.id in ids


@pytest.mark.django_db
def test_multiple_select_has_filter_type_export_import():
    view_filter_type = view_filter_type_registry.get("multiple_select_has")
    id_mapping = {"database_field_select_options": {1: 2}}
    assert view_filter_type.get_export_serialized_value("1") == "1"
    assert view_filter_type.set_import_serialized_value("1", id_mapping) == "2"
    assert view_filter_type.set_import_serialized_value("", id_mapping) == ""
    assert view_filter_type.set_import_serialized_value("wrong", id_mapping) == ""


@pytest.mark.django_db
def test_multiple_select_has_not_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi Select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "red"},
        ],
    )

    row_handler = RowHandler()
    model = table.get_model()

    select_options = multiple_select_field.select_options.all()
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[0].id,
                select_options[1].id,
            ],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [],
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[0].id,
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has_not",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = f"{select_options[0].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = f"{select_options[1].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.value = f"{select_options[2].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids

    # chaining filters should also work
    view_filter.value = f"{select_options[2].id}"
    view_filter.save()

    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has_not",
        value=f"{select_options[1].id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids


@pytest.mark.django_db
def test_length_is_lower_than_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    url_field = data_fixture.create_url_field(table=table)
    email_field = data_fixture.create_email_field(table=table)
    phone_number_field = data_fixture.create_phone_number_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "t",
            f"field_{long_text_field.id}": "t",
            f"field_{url_field.id}": "t@test.com",
            f"field_{email_field.id}": "t@baserow.com",
            f"field_{phone_number_field.id}": "+44 1",
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "te",
            f"field_{long_text_field.id}": "te",
            f"field_{url_field.id}": "te@test.com",
            f"field_{email_field.id}": "te@baserow.com",
            f"field_{phone_number_field.id}": "+44 12",
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "tes",
            f"field_{long_text_field.id}": "tes",
            f"field_{url_field.id}": "tes@test.com",
            f"field_{email_field.id}": "te@baserow.com",
            f"field_{phone_number_field.id}": "+44 123",
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="length_is_lower_than", value=12
    )

    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = 2
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = 3
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids

    view_filter.value = 4
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids

    # with an invalid filter value no results are returned
    view_filter.value = "a"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = 2
    view_filter.field = long_text_field
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = 11
    view_filter.field = url_field
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = 6
    view_filter.field = phone_number_field
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids


@pytest.mark.django_db
def test_date_equals_day_of_month_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    last_modified_field_datetime_berlin = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/Berlin"
    )
    last_modified_field_datetime_london = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, timezone="Europe/London"
    )

    handler = ViewHandler()
    model = table.get_model()

    with freeze_time("2020-1-03 22:01"):
        row_1 = model.objects.create(
            **{
                f"field_{date_field.id}": date(2021, 8, 11),
            }
        )
        row_2 = model.objects.create(
            **{
                f"field_{date_field.id}": date(2020, 1, 1),
            }
        )
        row_3 = model.objects.create(
            **{
                f"field_{date_field.id}": date(2019, 11, 1),
            }
        )
        model.objects.create(
            **{
                f"field_{date_field.id}": None,
            }
        )

    # Date Field (No timezone)
    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_equals_day_of_month", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "11"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    # Datetime (With timezone)

    # Jan 1st UTC, Jan 1st Germany, Jan 1st London
    with freeze_time("2020-1-01 22:01"):
        row_2_tz = model.objects.create(**{})

    # Jan 1st UTC, Jan 2nd Germany, Jan 1st London
    with freeze_time("2019-1-01 23:01"):
        row_3_tz = model.objects.create(**{})

    # Testing with Berlin time, only one row should be accepted
    view_filter.field = last_modified_field_datetime_berlin
    view_filter.value = "1"
    view_filter.save()

    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2_tz.id in ids
    assert row_3_tz.id not in ids

    # Testing with London time, both rows should be accepted
    view_filter.field = last_modified_field_datetime_london
    view_filter.save()

    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2_tz.id in ids
    assert row_3_tz.id in ids


@pytest.mark.django_db
def test_link_row_contains_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    related_primary_field = data_fixture.create_text_field(
        primary=True, table=related_table
    )
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 1",
        },
    )
    related_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 2",
        },
    )
    related_row_3 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 3",
        },
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_row_1.id],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_row_2.id],
        },
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 3",
            f"field_{link_row_field.id}": [related_row_3.id],
        },
    )
    row_with_all_relations = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 4",
            f"field_{link_row_field.id}": [
                related_row_1.id,
                related_row_2.id,
                related_row_3.id,
            ],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 5

    view_filter.value = "nonsense"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 0

    view_filter.value = "row"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 4

    view_filter.value = "1"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = "2"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = "3"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_with_all_relations.id in ids

    # Chaining filters should also work
    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value="1",
    )
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1
    assert row_with_all_relations.id in ids

    # Changing the view to use "OR" for multiple filters
    view_handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_3.id in ids
    assert row_with_all_relations.id in ids


@pytest.mark.django_db
def test_link_row_contains_filter_type_date_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_date_field = data_fixture.create_date_field(
        primary=True, table=related_table, date_format="ISO"
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_date_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_date_field.id}": "2020-02-01 01:23"},
    )

    related_date_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_date_field.id}": "2021-02-01 01:23"},
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_date_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_date_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = "2020"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1

    view_filter.value = "01"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
def test_link_row_contains_filter_type_created_on_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    now = django_timezone.now()

    related_primary_created_on_field = data_fixture.create_created_on_field(
        primary=True, table=related_table
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_created_on_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
    )

    related_created_on_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_created_on_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_created_on_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = now.year
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
def test_link_row_contains_filter_type_file_field(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_file_field = data_fixture.create_file_field(
        primary=True, table=related_table
    )

    file_one = data_fixture.create_user_file(original_name="target 1")
    file_two = data_fixture.create_user_file(original_name="target 2")

    model = table.get_model()
    related_model = related_table.get_model()

    related_file_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_file_field.id}": [{"name": file_one.name}]},
    )

    related_file_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_file_field.id}": [{"name": file_two.name}]},
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_file_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_file_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = "target 1"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1

    view_filter.value = "target"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
def test_link_row_contains_filter_type_single_select_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_single_select_field = data_fixture.create_single_select_field(
        primary=True, table=related_table
    )

    option_a = data_fixture.create_select_option(
        field=related_primary_single_select_field, value="target 1", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=related_primary_single_select_field, value="target 2", color="red"
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_single_select_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_single_select_field.id}": option_a.id},
    )

    related_single_select_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_single_select_field.id}": option_b.id},
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_single_select_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_single_select_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = "target 1"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1

    view_filter.value = "target"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
def test_link_row_contains_filter_type_multiple_select_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_multiple_select_field = data_fixture.create_multiple_select_field(
        primary=True, table=related_table
    )

    option_a = data_fixture.create_select_option(
        field=related_primary_multiple_select_field, value="target 1", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=related_primary_multiple_select_field, value="target 2", color="red"
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_multiple_select_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_multiple_select_field.id}": [option_a.id]},
    )

    related_multiple_select_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_multiple_select_field.id}": [option_b.id]},
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_multiple_select_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_multiple_select_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = "target 1"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1

    view_filter.value = "target"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_link_row_contains_filter_type_performance(data_fixture):
    rows_count = 5000
    related_rows_count = 5000
    relations_count = 50

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    related_primary_field = data_fixture.create_text_field(
        primary=True, table=related_table
    )
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_rows = []
    for i in range(related_rows_count):
        row = row_handler.create_row(
            user=user,
            table=related_table,
            model=related_model,
            values={
                f"field_{related_primary_field.id}": f"Related row {i}",
            },
        )
        related_rows.append(row)

    for i in range(rows_count):
        related_rows_chosen = random.sample(related_rows, relations_count)
        related_rows_chosen_ids = [row.id for row in related_rows_chosen]
        row_handler.create_row(
            user=user,
            table=table,
            model=model,
            values={
                f"field_{primary_field.id}": f"Row {i}",
                f"field_{link_row_field.id}": related_rows_chosen_ids,
            },
        )

    view_handler = ViewHandler()
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"related row",
    )

    profiler = Profiler()
    profiler.start()
    view_handler.apply_filters(grid_view, model.objects.all()).all()
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))
