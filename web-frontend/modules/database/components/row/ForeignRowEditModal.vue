<template>
  <RowEditModal
    ref="modal"
    :read-only="true"
    :database="database"
    :table="table"
    :rows="[]"
    :visible-fields="fields"
    :primary="primary"
    @hidden="$emit('hidden', $event)"
  ></RowEditModal>
</template>

<script>
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal'
import FieldService from '@baserow/modules/database/services/field'
import RowService from '@baserow/modules/database/services/row'
import { populateField } from '@baserow/modules/database/store/field'

/**
 * This component can open the row edit modal having the fields of that table in the
 * fields store. It will make a request to the backend fetching the missing
 * information.
 */
export default {
  name: 'ForeignRowEditModal',
  components: { RowEditModal },
  props: {
    tableId: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      fetchedTableAndFields: false,
      table: {},
      fields: [],
      primary: undefined,
    }
  },
  computed: {
    database() {
      const databaseType = DatabaseApplicationType.getType()
      for (const application of this.$store.getters['application/getAll']) {
        if (application.type !== databaseType) {
          continue
        }

        const foundTable = application.tables.find(
          ({ id }) => id === this.tableId
        )

        if (foundTable) {
          return application
        }
      }

      return undefined
    },
  },
  methods: {
    async fetchTableAndFields() {
      // Find the table in the applications to prevent a request to the backend and to
      // maintain reactivity with the real time updates.
      const databaseType = DatabaseApplicationType.getType()
      for (const application of this.$store.getters['application/getAll']) {
        if (application.type !== databaseType) {
          continue
        }

        const foundTable = application.tables.find(
          ({ id }) => id === this.tableId
        )

        if (foundTable) {
          this.table = foundTable
          break
        }
      }

      // Because we don't have the fields in the store we need to fetch those for this
      // table.
      const { data: fieldData } = await FieldService(this.$client).fetchAll(
        this.tableId
      )
      fieldData.forEach((part, index) => {
        populateField(fieldData[index], this.$registry)
      })
      const primaryIndex = fieldData.findIndex((item) => item.primary === true)
      if (primaryIndex !== -1) {
        this.primary = fieldData.splice(primaryIndex, 1)[0]
        this.fields = [this.primary, ...fieldData]
      } else {
        this.fields = fieldData
      }

      // Mark the table and fields as fetched, so that we don't have to do that a
      // second time when the user opens another row.
      this.fetchedTableAndFields = true
    },

    async show(rowId) {
      if (!this.fetchedTableAndFields) {
        await this.fetchTableAndFields()
      }

      const { data: rowData } = await RowService(this.$client).get(
        this.tableId,
        rowId
      )
      this.$refs.modal.show(rowData.id, rowData)
    },
  },
}
</script>
