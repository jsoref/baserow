import dataclasses

from django.db.models import Q


NO_FORMULAS = Q(pk__in=[])
ALL_FORMULAS = ~NO_FORMULAS


@dataclasses.dataclass
class FormulaMigration:
    """
    Represents how to migrate to a particular version of the Baserow formula language.
    """

    """
    The formula version id.
    """
    version: int

    """
    If this version requires formulas from older versions to have their FormulaField
    attributes to be recalculated set the filter which matches FormulaField's here.

    Normally for most formula upgrades this should be ALL_FORMULAS (see

    Specifically this will control which FormulaField's have `.save(recaculate=True)`
    called on them (which recalculates their attributes given the current formula
    version)
    """
    recalculate_formula_attributes_for: Q

    """
    If this version requires formulas from older versions to have their field
    dependencies recalculated using FieldDependencyHandler.rebuild_depedencies then
    provide a filter here matching the formula fields that should have this done.

    Most

    This will be done prior to any attribute or cell value recalculation in the
    migration.
    """
    recalculate_field_dependencies_for: Q

    """
    If this version requires formulas from older versions to have their actual cell
    values to be recalculated then provide a filter here matching the formula fields
    that should have this done.
    """
    recalculate_cell_values_for: Q


class FormulaMigrations(list):
    def get_latest_version(self) -> int:
        return super().__getitem__(-1).version


# A list containing all Baserow formula versions and how to migrate to them. The last
# item in the last is always the latest formula version. The versions in this list
# must increment by one per version.
#
# When migrating from one version to another the FormulaMigrationHandler will use this
# list to calculate which formulas to recalculate attributes/cell values/
# field dependencies for. It will OR together all Q filters in the versions being
# updated through/to.
FORMULA_MIGRATIONS = FormulaMigrations(
    [
        FormulaMigration(
            version=1,
            recalculate_formula_attributes_for=ALL_FORMULAS,
            recalculate_field_dependencies_for=NO_FORMULAS,
            recalculate_cell_values_for=NO_FORMULAS,
        ),
        FormulaMigration(
            version=2,
            recalculate_formula_attributes_for=ALL_FORMULAS,
            recalculate_field_dependencies_for=NO_FORMULAS,
            recalculate_cell_values_for=NO_FORMULAS,
        ),
        FormulaMigration(
            version=3,
            recalculate_formula_attributes_for=ALL_FORMULAS,
            # v3 fixes various dep graph issues.
            recalculate_field_dependencies_for=ALL_FORMULAS,
            # v3 fixes a bug where a date cell could contain a BC date unsupported by
            # python.
            recalculate_cell_values_for=(
                Q(formula_type="date") | Q(array_formula_type="date")
            ),
        ),
    ]
)
# The current version is the last migration.
BASEROW_FORMULA_VERSION = FORMULA_MIGRATIONS.get_latest_version()
