<template>
  <div>
    <FieldFormulaInitialSubForm
      :default-values="mergedTypeOptions"
      :formula="values.formula"
      :error="formulaError"
      :formula-type="localOrServerFormulaType"
      :table="table"
      :loading="refreshingFormula"
      :formula-type-refresh-needed="formulaTypeRefreshNeeded"
      @open-advanced-context="
        $refs.advancedFormulaEditContext.openContext($event)
      "
      @refresh-formula-type="refreshFormulaType"
    >
    </FieldFormulaInitialSubForm>
    <FormulaAdvancedEditContext
      ref="advancedFormulaEditContext"
      v-model="values.formula"
      :table="table"
      :fields="fieldsUsableInFormula"
      :error="formulaError"
      @blur="$v.values.formula.$touch()"
      @hidden="$v.values.formula.$touch()"
    >
    </FormulaAdvancedEditContext>
  </div>
</template>

<script>
import { required } from 'vuelidate/lib/validators'
import { mapGetters } from 'vuex'

import form from '@baserow/modules/core/mixins/form'
import { notifyIf } from '@baserow/modules/core/utils/error'

import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FieldFormulaInitialSubForm from '@baserow/modules/database/components/formula/FieldFormulaInitialSubForm'
import FormulaAdvancedEditContext from '@baserow/modules/database/components/formula/FormulaAdvancedEditContext'
import FormulaService from '@baserow/modules/database/services/formula'
import parseBaserowFormula from '@baserow/modules/database/formula/parser/parser'

export default {
  name: 'FieldFormulaSubForm',
  components: {
    FieldFormulaInitialSubForm,
    FormulaAdvancedEditContext,
  },
  mixins: [form, fieldSubForm],
  props: {
    name: {
      required: true,
      type: String,
    },
  },
  data() {
    return {
      allowedValues: ['formula'],
      values: {
        formula: '',
      },
      fetchedTypeOptions: {},
      mergedTypeOptions: { ...this.defaultValues },
      parsingError: null,
      previousValidParsedFormula: this.defaultValues.formula,
      formulaTypeRefreshNeeded: false,
      refreshingFormula: false,
    }
  },
  computed: {
    ...mapGetters({
      rawFields: 'field/getAllWithPrimary',
    }),
    localOrServerFormulaType() {
      return (
        this.mergedTypeOptions.array_formula_type ||
        this.mergedTypeOptions.formula_type
      )
    },
    fieldsUsableInFormula() {
      return this.rawFields.filter((f) => {
        const isNotThisField = f.id !== this.defaultValues.id
        const canBeReferencedByFormulaField = this.$registry
          .get('field', f.type)
          .canBeReferencedByFormulaField()
        return isNotThisField && canBeReferencedByFormulaField
      })
    },
    formulaError() {
      const dirty = this.$v.values.formula.$dirty
      if (dirty && !this.$v.values.formula.required) {
        return 'Please enter a formula'
      } else if (dirty && !this.$v.values.formula.parseFormula) {
        return (
          `Error in the formula on line ${this.parsingError.line} starting at
        letter ${this.parsingError.character}` +
          '\n' +
          this.toHumanReadableErrorMessage(this.parsingError)
        )
      } else if (this.mergedTypeOptions.error) {
        return this.mergedTypeOptions.error
      } else {
        return null
      }
    },
  },
  watch: {
    defaultValues(newValue) {
      this.mergedTypeOptions = { ...newValue, ...this.fetchedTypeOptions }
    },
    fetchedTypeOptions(newValue) {
      this.mergedTypeOptions = { ...this.defaultValues, ...newValue }
    },
  },
  methods: {
    parseFormula(value) {
      if (value == null) {
        return false
      }
      if (!value.trim()) {
        return false
      }
      try {
        parseBaserowFormula(value)
        this.parsingError = null
        if (this.previousValidParsedFormula !== value) {
          this.formulaTypeRefreshNeeded = true
          this.previousValidParsedFormula = value
        }
        return true
      } catch (e) {
        this.parsingError = e
        return false
      }
    },
    toHumanReadableErrorMessage(error) {
      const s = error.message
        .replace('extraneous', 'Invalid')
        .replace('input', 'letters')
        .replace(' expecting', ', was instead expecting ')
        .replace("'<EOF>'", 'the end of the formula')
        .replace('<EOF>', 'the end of the formula')
        .replace('mismatched letters', 'Unexpected')
        .replace('Unexpected the', 'Unexpected')
        .replace('SINGLEQ_STRING_LITERAL', 'a single quoted string')
        .replace('DOUBLEQ_STRING_LITERAL', 'a double quoted string')
        .replace('IDENTIFIER', 'a function')
        .replace('IDENTIFIER_UNICODE', '')
        .replace('{', '')
        .replace('}', '')
      return s + '.'
    },
    handleErrorByForm(error) {
      if (
        [
          'ERROR_WITH_FORMULA',
          'ERROR_FIELD_SELF_REFERENCE',
          'ERROR_FIELD_CIRCULAR_REFERENCE',
        ].includes(error.handler.code)
      ) {
        this.$set(this.fetchedTypeOptions, 'error', error.handler.detail)
        this.formulaTypeRefreshNeeded = false
        return true
      } else {
        return false
      }
    },
    reset() {
      const formula = this.values.formula
      this.fetchedTypeOptions = {}
      this.formulaTypeRefreshNeeded = false
      Object.assign(this.mergedTypeOptions, this.defaultValues)
      form.methods.reset.call(this)
      this.values.formula = formula
    },
    async refreshFormulaType() {
      if (!this.name) {
        this.$emit('validate')
        return
      }
      try {
        this.refreshingFormula = true
        const { data } = await FormulaService(this.$client).type(
          this.table.id,
          this.name,
          this.values.formula
        )

        this.fetchedTypeOptions = data
        this.formulaTypeRefreshNeeded = false
      } catch (e) {
        if (!this.handleErrorByForm(e)) {
          notifyIf(e, 'field')
        } else {
          this.formulaTypeRefreshNeeded = false
        }
      }
      this.refreshingFormula = false
    },
  },
  validations() {
    return {
      values: {
        formula: {
          required,
          parseFormula: this.parseFormula,
        },
      },
    }
  },
}
</script>
