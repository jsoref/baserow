<template>
  <div>
    <div class="control">
      <label class="control__label">{{
        $t('tableXMLImporter.fileLabel')
      }}</label>
      <div class="control__description">
        {{ $t('tableXMLImporter.fileDescription') }}
        <pre>
&lt;notes&gt;
  &lt;note&gt;
    &lt;to&gt;Tove&lt;/to&gt;
    &lt;from&gt;Jani&lt;/from&gt;
    &lt;heading&gt;Reminder&lt;/heading&gt;
    &lt;body&gt;Don't forget me this weekend!&lt;/body&gt;
  &lt;/note&gt;
  &lt;note&gt;
    &lt;heading&gt;Reminder&lt;/heading&gt;
    &lt;heading2&gt;Reminder2&lt;/heading2&gt;
    &lt;to&gt;Tove&lt;/to&gt;
    &lt;from&gt;Jani&lt;/from&gt;
    &lt;body&gt;Don't forget me this weekend!&lt;/body&gt;
  &lt;/note&gt;
&lt;/notes&gt;</pre
        >
      </div>
      <div class="control__elements">
        <div class="file-upload">
          <input
            v-show="false"
            ref="file"
            type="file"
            accept=".xml"
            @change="select($event)"
          />
          <a
            class="button button--large button--ghost file-upload__button"
            :class="{ 'button--loading': state !== null }"
            @click.prevent="$refs.file.click($event)"
          >
            <i class="fas fa-cloud-upload-alt"></i>
            {{ $t('tableXMLImporter.chooseButton') }}
          </a>
          <div v-if="state === null" class="file-upload__file">
            {{ filename }}
          </div>
          <template v-else>
            <ProgressBar
              :value="fileLoadingProgress"
              :show-value="state === 'loading'"
              :status="
                state === 'loading' ? $t('importer.loading') : stateTitle
              "
            />
          </template>
        </div>
        <div v-if="$v.filename.$error" class="error">
          {{ $t('error.fieldRequired') }}
        </div>
      </div>
    </div>
    <Alert
      v-if="error !== ''"
      :title="$t('common.wrong')"
      type="error"
      icon="exclamation"
    >
      {{ error }}
    </Alert>
    <TableImporterPreview
      v-if="error === '' && Object.keys(preview).length !== 0"
      :preview="preview"
    ></TableImporterPreview>
  </div>
</template>

<script>
import { required } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'
import importer from '@baserow/modules/database/mixins/importer'
import TableImporterPreview from '@baserow/modules/database/components/table/TableImporterPreview'
import { XMLParser } from '@baserow/modules/database/utils/xml'

export default {
  name: 'TableXMLImporter',
  components: { TableImporterPreview },
  mixins: [form, importer],
  data() {
    return {
      values: {
        getData: null,
        firstRowHeader: true,
      },
      filename: '',
      error: '',
      rawData: null,
      preview: {},
    }
  },
  validations: {
    values: {
      getData: { required },
    },
    filename: { required },
  },
  methods: {
    /**
     * Method that is called when a file has been chosen. It will check if the file is
     * not larger than 15MB. Otherwise it will take a long time and possibly a crash
     * if so many entries have to be loaded into memory. If the file is valid, the
     * contents will be loaded into memory and the reload method will be called which
     * parses the content.
     */
    select(event) {
      if (event.target.files.length === 0) {
        return
      }

      const file = event.target.files[0]
      const maxSize =
        parseInt(this.$env.BASEROW_MAX_IMPORT_FILE_SIZE_MB, 10) * 1024 * 1024

      if (file.size > maxSize) {
        this.filename = ''
        this.values.getData = null
        this.error = this.$t('tableXMLImporter.limitFileSize', {
          limit: this.$env.BASEROW_MAX_IMPORT_FILE_SIZE_MB,
        })
        this.preview = {}
      } else {
        this.$emit('changed')
        this.state = 'loading'
        this.filename = file.name
        const reader = new FileReader()
        reader.addEventListener('progress', (event) => {
          this.fileLoadingProgress = (event.loaded / event.total) * 100
        })
        reader.addEventListener('load', (event) => {
          this.rawData = event.target.result
          this.fileLoadingProgress = 100
          this.reload()
        })
        reader.readAsBinaryString(event.target.files[0])
      }
    },
    async reload() {
      this.state = 'parsing'
      await this.$ensureRender()
      const xmlParser = new XMLParser()
      xmlParser.parse(this.rawData)

      await this.$ensureRender()
      xmlParser.loadXML(3)
      await this.$ensureRender()
      const [header, xmlData, errors] = xmlParser.transform()

      if (errors.length > 0) {
        this.values.getData = null
        this.error = this.$t('tableXMLImporter.processingError', {
          errors: errors.join('\n'),
        })
        this.preview = {}
        return
      }

      if (xmlData.length === 0) {
        this.values.getData = null
        this.error = this.$t('tableXMLImporter.emptyError')
        this.preview = {}
        return
      }

      let hasHeader = false
      if (header.length > 0) {
        xmlData.unshift(header)
        hasHeader = true
      }

      const limit = this.$env.INITIAL_TABLE_DATA_LIMIT
      if (limit !== null && xmlData.length > limit) {
        this.values.getData = null
        this.error = this.$t('tableXMLImporter.limitError', { limit })
        this.preview = {}
        return
      }

      const dataWithHeader = this.ensureHeaderExistsAndIsValid(
        xmlData,
        hasHeader
      )
      this.values.getData = async () => {
        await this.$ensureRender()
        xmlParser.loadXML()
        await this.$ensureRender()
        const [header, xmlData, errors] = xmlParser.transform()

        if (errors.length > 0) {
          throw new Error(errors)
        }

        let hasHeader = false
        if (header.length > 0) {
          xmlData.unshift(header)
          hasHeader = true
        }
        const dataWithHeader = this.ensureHeaderExistsAndIsValid(
          xmlData,
          hasHeader
        )
        return dataWithHeader
      }
      this.state = null
      this.parsing = false
      this.error = ''
      this.preview = this.getPreview(dataWithHeader)
    },
  },
}
</script>
