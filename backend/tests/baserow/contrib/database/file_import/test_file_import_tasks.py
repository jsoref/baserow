import pytest
from pyinstrument import Profiler
from baserow.core.exceptions import UserNotInGroup
from freezegun import freeze_time
from decimal import Decimal

from django.utils import timezone
from django.conf import settings
from django.test.utils import override_settings

from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.dependencies.handler import FieldDependencyHandler
from baserow.contrib.database.fields.models import TextField, LongTextField, NumberField
from baserow.core.jobs.tasks import run_async_job, clean_up_jobs
from baserow.core.jobs.models import Job
from baserow.core.jobs.constants import (
    JOB_FAILED,
    JOB_FINISHED,
    JOB_STARTED,
    JOB_PENDING,
)
from baserow.contrib.database.file_import.exceptions import (
    FileImportMaxErrorCountExceeded,
)
from baserow.contrib.database.fields.exceptions import (
    MaxFieldLimitExceeded,
    MaxFieldNameLengthExceeded,
    ReservedBaserowFieldNameException,
    InvalidBaserowFieldName,
)
from baserow.contrib.database.table.exceptions import (
    InvalidInitialTableData,
    InitialTableDataLimitExceeded,
    InitialTableDataDuplicateName,
)


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task(data_fixture, patch_filefield_storage):

    user = data_fixture.create_user()
    database = data_fixture.create_database_application()

    with patch_filefield_storage(), pytest.raises(UserNotInGroup):
        job = data_fixture.create_file_import_job(user=user, database=database)
        run_async_job(job.id)

    with patch_filefield_storage(), pytest.raises(InvalidInitialTableData):
        job = data_fixture.create_file_import_job(data=[])
        run_async_job(job.id)

    with patch_filefield_storage(), pytest.raises(InvalidInitialTableData):
        job = data_fixture.create_file_import_job(data=[[]])
        run_async_job(job.id)

    with override_settings(
        INITIAL_TABLE_DATA_LIMIT=2
    ), patch_filefield_storage(), pytest.raises(InitialTableDataLimitExceeded):
        job = data_fixture.create_file_import_job(data=[[], [], []])
        run_async_job(job.id)

    with override_settings(MAX_FIELD_LIMIT=2), patch_filefield_storage(), pytest.raises(
        MaxFieldLimitExceeded
    ):
        job = data_fixture.create_file_import_job(data=[["fields"] * 3, ["rows"] * 3])
        run_async_job(job.id)

    too_long_field_name = "x" * 256
    field_name_with_ok_length = "x" * 255

    data = [
        [too_long_field_name, "B", "C", "D"],
        ["1-1", "1-2", "1-3", "1-4", "1-5"],
        ["2-1", "2-2", "2-3"],
        ["3-1", "3-2"],
    ]

    with patch_filefield_storage(), pytest.raises(MaxFieldNameLengthExceeded):
        job = data_fixture.create_file_import_job(data=data)
        run_async_job(job.id)

    data[0][0] = field_name_with_ok_length
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(data=data)
        run_async_job(job.id)

    with patch_filefield_storage(), pytest.raises(ReservedBaserowFieldNameException):
        job = data_fixture.create_file_import_job(data=[["id"]])
        run_async_job(job.id)

    with patch_filefield_storage(), pytest.raises(InitialTableDataDuplicateName):
        job = data_fixture.create_file_import_job(data=[["test", "test"]])
        run_async_job(job.id)

    with patch_filefield_storage(), pytest.raises(InvalidBaserowFieldName):
        job = data_fixture.create_file_import_job(data=[[" "]])
        run_async_job(job.id)

    # Basic use
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=[
                ["A", "B", "C", "D"],
                ["1-1", "1-2", "1-3", "1-4", "1-5"],
                ["2-1", "2-2", "2-3"],
                ["3-1", "3-2"],
            ]
        )
        run_async_job(job.id)

    job.refresh_from_db()

    table = job.table
    assert job.state == JOB_FINISHED
    assert job.progress_percentage == 100

    with pytest.raises(ValueError):
        # Check that the data file has been removed
        job.data_file.path

    text_fields = TextField.objects.filter(table=table)
    assert text_fields[0].name == "A"
    assert text_fields[1].name == "B"
    assert text_fields[2].name == "C"
    assert text_fields[3].name == "D"
    assert text_fields[4].name == "Field 5"

    model = table.get_model()
    rows = model.objects.all()

    assert len(rows) == 3

    # Without first row header
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=[
                ["1-1"],
                ["2-1", "2-2", "2-3"],
                ["3-1", "3-2"],
            ],
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()

    table = job.table

    text_fields = TextField.objects.filter(table=table)
    assert text_fields[0].name == "Field 1"
    assert text_fields[1].name == "Field 2"
    assert text_fields[2].name == "Field 3"

    # Robust to strange names
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=[
                [
                    "TEst 1",
                    "10.00",
                    'Falsea"""',
                    'a"a"a"a"a,',
                    "a",
                    1.3,
                    "/w. r/awr",
                ],
            ],
        )
        run_async_job(job.id)

    job.refresh_from_db()

    table = job.table
    text_fields = TextField.objects.filter(table=table)
    assert text_fields[0].name == "TEst 1"
    assert text_fields[1].name == "10.00"
    assert text_fields[2].name == 'Falsea"""'
    assert text_fields[3].name == 'a"a"a"a"a,'
    assert text_fields[4].name == "a"
    assert text_fields[5].name == "1.3"
    assert text_fields[6].name == "/w. r/awr"

    data = [
        ["1-1", 1, 1.55, "x" * 260, "x"],
        ["2-1", 2, 1, "i", "."],
        ["3-1", 3, 2.4, "i", "."],
        ["3-1", 3, 2.4, "x" * 260, "x" * 260],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4, "x" * 260],
        ["3-1", 3, 2.4, "x" * 260],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4, "x" * 260],
        ["3-1", int("3" * 50), 2.4, None],
        ["3-1", 3, 2.4, "x" * 260],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4, None],
        ["3-1", 3, 2.4888888888, None],
        ["3-1", 3.2, 123445.12345, None],
    ]

    # Test type guessing but low error threshold
    with override_settings(
        BASEROW_IMPORT_TOLERATED_TYPE_ERROR_THRESHOLD=0
    ), patch_filefield_storage():
        job = data_fixture.create_file_import_job(data=data, first_row_header=False)
        run_async_job(job.id)

    job.refresh_from_db()

    table = job.table
    model = table.get_model()
    rows = model.objects.all()
    assert len(rows) == 20

    fields = table.field_set.all()

    assert fields.count() == 5

    field1, field2, field3, field4, field5 = fields

    assert isinstance(field1.specific, TextField)
    assert isinstance(field2.specific, NumberField)
    assert field2.specific.number_decimal_places == 10
    assert isinstance(field3.specific, NumberField)
    assert field3.specific.number_decimal_places == 10
    assert isinstance(field4.specific, LongTextField)
    assert isinstance(field5.specific, LongTextField)

    assert getattr(rows[0], field3.db_column) == Decimal("1.55")

    # Test type guessing with error threshold
    with override_settings(
        BASEROW_IMPORT_TOLERATED_TYPE_ERROR_THRESHOLD=10
    ), patch_filefield_storage():
        job = data_fixture.create_file_import_job(data=data, first_row_header=False)
        run_async_job(job.id)

    job.refresh_from_db()

    table = job.table
    model = table.get_model()
    rows = model.objects.all()
    assert len(rows) == 19

    fields = table.field_set.all()

    assert fields.count() == 5

    field1, field2, field3, field4, field5 = fields

    assert isinstance(field1.specific, TextField)
    assert isinstance(field2.specific, NumberField)
    assert field2.specific.number_decimal_places == 0
    assert isinstance(field3.specific, NumberField)
    assert field3.specific.number_decimal_places == 10
    assert isinstance(field4.specific, LongTextField)
    assert isinstance(field5.specific, TextField)

    # Import data to an existing table
    data = [["baz", 3, -3, "foo", None], ["bob", -4, 2.5, "bar", "a" * 255]]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=job.user, database=table.database, table=table, data=data
        )
        run_async_job(job.id)

    rows = model.objects.all()
    assert len(rows) == 21

    # Import data with error
    data = [
        ["good", "test", "test", "Anything"],
        [],
        [None, None],
        ["good", 2.5, None, "Anything"],
    ]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=job.user, database=table.database, table=table, data=data
        )
        run_async_job(job.id)

    job.refresh_from_db()

    rows = model.objects.all()
    assert len(rows) == 23

    assert sorted(job.report["failing_rows"].keys()) == ["0", "3"]

    assert job.report["failing_rows"]["0"] == {
        f"field_{field2.id}": [
            {"code": "invalid", "error": "A valid number is required."}
        ],
        f"field_{field3.id}": [
            {"code": "invalid", "error": "A valid number is required."}
        ],
    }

    assert job.report["failing_rows"]["3"] == {
        f"field_{field2.id}": [
            {
                "code": "max_decimal_places",
                "error": "Ensure that there are no more than 0 decimal places.",
            }
        ]
    }

    # Change user language to test message i18n
    job.user.profile.language = "fr"
    job.user.profile.save()

    data = [["good", "ugly", "bad"]]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=job.user, database=table.database, table=table, data=data
        )
        run_async_job(job.id)

    job.refresh_from_db()

    assert job.report["failing_rows"]["0"][f"field_{field2.id}"] == [
        {
            "code": "invalid",
            "error": "Un nombre valide est requis.",
        }
    ]

    data = [
        [1.3],
        [1.12345678901],  # this one is too long for decimal field
    ]

    with override_settings(
        BASEROW_IMPORT_TOLERATED_TYPE_ERROR_THRESHOLD=0
    ), patch_filefield_storage():
        job = data_fixture.create_file_import_job(data=data, first_row_header=False)
        run_async_job(job.id)

    job.refresh_from_db()
    fields = job.table.field_set.all()
    assert fields.count() == 1
    field1 = fields[0]
    assert isinstance(field1.specific, TextField)

    data = [
        [1],
        ["1" * 51],  # Too long
    ]

    with override_settings(
        BASEROW_IMPORT_TOLERATED_TYPE_ERROR_THRESHOLD=0
    ), patch_filefield_storage():
        job = data_fixture.create_file_import_job(data=data, first_row_header=False)
        run_async_job(job.id)

    job.refresh_from_db()
    fields = job.table.field_set.all()
    assert fields.count() == 1
    field1 = fields[0]
    assert isinstance(field1.specific, TextField)


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_for_special_fields(data_fixture, patch_filefield_storage):

    user = data_fixture.create_user()
    table, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    # number field updating another table through link & formula
    number_field = data_fixture.create_number_field(
        table=table_b, order=1, name="Number"
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula=f"lookup('{link_field.name}', '{number_field.name}')*2",
        formula_type="number",
    )
    FieldDependencyHandler.rebuild_dependencies(formula_field, FieldCache())

    # single and multiple select fields
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table_b, order=3
    )
    multi_select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    multi_select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=2,
        value="Option 2",
        color="blue",
    )
    multiple_select_field.select_options.set(
        [multi_select_option_1, multi_select_option_2]
    )
    single_select_field = data_fixture.create_single_select_field(
        table=table_b, order=4
    )
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    single_select_option_2 = SelectOption.objects.create(
        field=single_select_field,
        order=2,
        value="Option 2",
        color="blue",
    )
    single_select_field.select_options.set(
        [single_select_option_1, single_select_option_2]
    )

    # file field
    file_field = data_fixture.create_file_field(table=table_b, order=5)
    file1 = data_fixture.create_user_file(
        original_name="test.txt",
        is_image=True,
    )
    file2 = data_fixture.create_user_file(
        original_name="test2.txt",
        is_image=True,
    )

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()

    data = [
        [
            "one",
            10,
            [row_1.id],
            [multi_select_option_1.id],
            single_select_option_1.id,
            [{"name": file1.name, "visible_name": "new name"}],
        ],
        [
            "two",
            20,
            [row_2.id, row_1.id],
            [multi_select_option_1.id, multi_select_option_2.id],
            single_select_option_2.id,
            [{"name": file2.name, "visible_name": "another name"}],
        ],
        [
            "three",
            0,
            [],
            [],
            None,
            [],
        ],
    ]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=user, database=table.database, table=table_b, data=data
        )
        run_async_job(job.id)

    job.refresh_from_db()

    model = table_b.get_model()

    rows = model.objects.all()
    assert len(rows) == 3

    data = [
        [
            "four",
            10,
            [0],
            [0],
            0,
            [{"name": "missing_file.txt", "visible_name": "new name"}],
        ],
        [
            "five",
            -1,
            [row_2.id, 0],
            [multi_select_option_1.id, 0],
            9999,
            [
                {},
                {"name": file2.name, "visible_name": "another name"},
                {"name": "missing_file.txt", "visible_name": "new name"},
            ],
        ],
        [
            "seven",
            10,
            [row_2.id],
            [multi_select_option_2.id],
            single_select_option_2.id,
            [
                {"name": file2.name, "visible_name": "another name"},
            ],
        ],
        [
            "six",
            1.2,
            ["invalid_value", row_2.id],
            ["invalid_value", multi_select_option_2.id],
            "invalid_value",
            [
                {},
                {"name": file2.name, "visible_name": "another name"},
                {"name": "invalidValue", "visible_name": "new name"},
            ],
        ],
        [
            "seven",
            1,
            "bug",
            "bug",
            1.4,
            "bug",
        ],
    ]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=user, database=table.database, table=table_b, data=data
        )
        run_async_job(job.id)

    job.refresh_from_db()

    rows = model.objects.all()
    assert len(rows) == 4

    assert sorted(job.report["failing_rows"].keys()) == ["0", "1", "3", "4"]

    assert sorted(job.report["failing_rows"]["0"].keys()) == sorted(
        [
            f"field_{multiple_select_field.id}",
            f"field_{single_select_field.id}",
            f"field_{file_field.id}",
        ]
    )

    assert sorted(job.report["failing_rows"]["1"].keys()) == sorted(
        [
            f"field_{number_field.id}",
            f"field_{file_field.id}",
        ]
    )

    assert sorted(job.report["failing_rows"]["3"].keys()) == sorted(
        [
            f"field_{number_field.id}",
            f"field_{link_field.id + 1}",
            f"field_{multiple_select_field.id}",
            f"field_{single_select_field.id}",
            f"field_{file_field.id}",
        ]
    )

    assert sorted(job.report["failing_rows"]["4"].keys()) == sorted(
        [
            f"field_{link_field.id + 1}",
            f"field_{multiple_select_field.id}",
            f"field_{single_select_field.id}",
            f"field_{file_field.id}",
        ]
    )


@pytest.mark.django_db(transaction=True)
def test_run_file_import_test_chunk(data_fixture, patch_filefield_storage):

    row_count = 1024 + 5

    user = data_fixture.create_user()

    table, _, _ = data_fixture.build_table(
        columns=[
            (f"col1", "text"),
            (f"col2", "number"),
        ],
        rows=[],
        user=user,
    )

    single_select_field = data_fixture.create_single_select_field(table=table, order=4)
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    single_select_option_2 = SelectOption.objects.create(
        field=single_select_field,
        order=2,
        value="Option 2",
        color="blue",
    )

    data = [["test", 1, single_select_option_1.id]] * row_count
    # 5 erroneous values
    data[5] = ["test", "bad", single_select_option_2.id]
    data[50] = ["test", "bad", 0]
    data[100] = ["test", "bad", ""]
    data[1024] = ["test", 2, 99999]
    data[1027] = ["test", "bad", single_select_option_2.id]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(table=table, data=data, user=user)
        run_async_job(job.id)

    job.refresh_from_db()

    model = job.table.get_model()
    assert model.objects.count() == row_count - 5

    assert sorted(job.report["failing_rows"].keys()) == sorted(
        ["5", "50", "100", "1024", "1027"]
    )

    assert job.state == JOB_FINISHED
    assert job.progress_percentage == 100


@pytest.mark.django_db()
def test_run_file_import_limit(data_fixture, patch_filefield_storage):

    row_count = 2000
    max_error = settings.BASEROW_MAX_FILE_IMPORT_ERROR_COUNT

    user = data_fixture.create_user()

    table, _, _ = data_fixture.build_table(
        columns=[
            (f"col1", "text"),
            (f"col2", "number"),
        ],
        rows=[],
        user=user,
    )

    single_select_field = data_fixture.create_single_select_field(table=table, order=4)
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )

    # Validation errors
    data = [["test", 1, single_select_option_1.id]] * row_count
    data += [["test", "bad", single_select_option_1.id]] * (max_error + 5)

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(table=table, data=data, user=user)

        with pytest.raises(FileImportMaxErrorCountExceeded):
            run_async_job(job.id)

    job.refresh_from_db()

    model = job.table.get_model()
    assert model.objects.count() == 0

    assert job.state == JOB_FAILED
    assert job.error == "Too many errors"
    assert job.human_readable_error == "This file import has raised too many errors."

    assert len(job.report["failing_rows"]) == max_error

    # Row creation errors
    data = [["test", 1, single_select_option_1.id]] * row_count
    data += [["test", 1, 0]] * (max_error + 5)

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(table=table, data=data, user=user)

        with pytest.raises(FileImportMaxErrorCountExceeded):
            run_async_job(job.id)

    job.refresh_from_db()

    assert model.objects.count() == 0

    assert job.state == JOB_FAILED
    assert job.error == "Too many errors"
    assert job.human_readable_error == "This file import has raised too many errors."

    assert (
        len(job.report["failing_rows"]) == settings.BASEROW_MAX_FILE_IMPORT_ERROR_COUNT
    )

    assert len(job.report["failing_rows"]) == max_error


@pytest.mark.django_db(transaction=True)
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
# ~5 min (320s) on a 6 x i5-8400 CPU @ 2.80GHz (5599 bogomips)
def test_run_file_import_task_big_data(data_fixture, patch_filefield_storage):

    row_count = 100_000

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(column_count=100, row_count=row_count)

        profiler = Profiler()
        profiler.start()
        run_async_job(job.id)
        profiler.stop()

    job.refresh_from_db()

    model = job.table.get_model()
    assert model.objects.count() == row_count

    assert job.state == JOB_FINISHED
    assert job.progress_percentage == 100

    # A print we want to keep to show the performance statistics
    print(profiler.output_text(unicode=True, color=True, show_all=True))


@pytest.mark.django_db
def test_cleanup_file_import_job(data_fixture, settings, patch_filefield_storage):
    now = timezone.now()
    time_before_soft_limit = now - timezone.timedelta(
        minutes=settings.BASEROW_JOB_SOFT_TIME_LIMIT + 1
    )
    time_before_expiration = now - timezone.timedelta(
        minutes=settings.BASEROW_JOB_EXPIRATION_TIME_LIMIT + 1
    )
    # create recent job
    with freeze_time(now):
        job1 = data_fixture.create_file_import_job()

    with patch_filefield_storage() as storage:
        # Create old jobs
        with freeze_time(time_before_soft_limit):
            job1bis = data_fixture.create_file_import_job()
            job2 = data_fixture.create_file_import_job(state=JOB_STARTED)
            job3 = data_fixture.create_file_import_job(state=JOB_FINISHED)

        with freeze_time(time_before_expiration):
            job4 = data_fixture.create_file_import_job(state=JOB_FINISHED)
            job4_path = job4.data_file.path

        assert storage.exists(job4_path)

        with freeze_time(now):
            clean_up_jobs()

        # Check the file for job4 has been deleted
        assert not storage.exists(job4_path)

    assert Job.objects.count() == 4

    job1.refresh_from_db()
    assert job1.state == JOB_PENDING

    job1bis.refresh_from_db()
    assert job1.state == JOB_PENDING

    job2.refresh_from_db()
    assert job2.state == JOB_FAILED
    assert job2.updated_on == now

    job3.refresh_from_db()
    assert job3.state == JOB_FINISHED
    assert job3.updated_on == time_before_soft_limit
