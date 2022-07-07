# Generated by Django 3.2.13 on 2022-07-02 16:12

import baserow.contrib.database.file_import.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0079_table_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="fileimportjob",
            name="database",
            field=models.ForeignKey(
                help_text="The database where we want to create the table",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="table_import_jobs",
                to="database.database",
            ),
        ),
        migrations.AddField(
            model_name="fileimportjob",
            name="first_row_header",
            field=models.BooleanField(
                default=False,
                help_text="Is the first row of the provided data the header?",
            ),
        ),
        migrations.AddField(
            model_name="fileimportjob",
            name="name",
            field=models.CharField(
                default="", help_text="The name the created table.", max_length=255
            ),
        ),
        migrations.AddField(
            model_name="fileimportjob",
            name="user_session_id",
            field=models.CharField(
                default="",
                help_text="The user session id to register the action when the action "
                "is complete.",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="fileimportjob",
            name="data_file",
            field=models.FileField(
                help_text="The data file to import.",
                null=True,
                upload_to=baserow.contrib.database.file_import.models.file_import_directory_path,
            ),
        ),
        migrations.AlterField(
            model_name="fileimportjob",
            name="report",
            field=models.JSONField(
                default=baserow.contrib.database.file_import.models.default_report,
                help_text="The import error report.",
            ),
        ),
        migrations.AlterField(
            model_name="fileimportjob",
            name="table",
            field=models.ForeignKey(
                help_text="If provided the job will be a data import only job. "
                "Otherwise it will be the created table.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="import_jobs",
                to="database.table",
            ),
        ),
    ]
