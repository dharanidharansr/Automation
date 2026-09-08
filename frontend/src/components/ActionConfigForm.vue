<template>
  <div class="ab-action-config">
    <div v-for="field in schema" :key="field.name" class="ab-config-group" v-show="isFieldVisible(field)">
      <label>{{ field.label }}</label>
      <p v-if="field.description" class="ab-config-hint">{{ field.description }}</p>

      <!-- data: plain text input -->
      <input
        v-if="field.type === 'data'"
        type="text"
        :value="config[field.name]"
        @input="update(field.name, $event.target.value)"
      />

      <!-- textarea: multi-line -->
      <textarea
        v-else-if="field.type === 'textarea'"
        :value="config[field.name]"
        @input="update(field.name, $event.target.value)"
        rows="4"
      ></textarea>

      <!-- select: fixed options from field.options -->
      <select
        v-else-if="field.type === 'select'"
        :value="config[field.name]"
        @change="update(field.name, $event.target.value)"
      >
        <option value="">Select...</option>
        <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
      </select>

      <!-- doctype_link: dropdown of DocTypes -->
      <select
        v-else-if="field.type === 'doctype_link'"
        :value="config[field.name]"
        @change="onDoctypeChange(field.name, $event.target.value)"
      >
        <option value="">Select DocType...</option>
        <option v-for="dt in doctypes" :key="dt.name" :value="dt.name">{{ dt.name }}</option>
      </select>

      <!-- field_mapping_table: repeatable target_field / source_value rows -->
      <template v-else-if="field.type === 'field_mapping_table'">
        <div v-if="config[field.name] && config[field.name].length" class="ab-mapping-rows">
          <div v-for="(row, idx) in config[field.name]" :key="idx" class="ab-mapping-row">
            <select
              class="ab-mapping-target"
              :value="row.target_field"
              @change="updateMapping(field.name, idx, 'target_field', $event.target.value)"
            >
              <option value="">Select field</option>
              <option v-for="f in targetFields" :key="f.fieldname" :value="f.fieldname">
                {{ f.label }}
              </option>
            </select>
            <input
              type="text"
              class="ab-mapping-source"
              :value="row.source_value"
              :placeholder="tokenPlaceholder"
              @input="updateMapping(field.name, idx, 'source_value', $event.target.value)"
            />
            <button class="ab-btn ab-btn-ghost ab-btn-sm ab-mapping-remove" @click="removeMapping(field.name, idx)">✕</button>
          </div>
        </div>
        <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="addMapping(field.name)">+ Add Field</button>
      </template>

      <!-- template_picker: dropdown of email templates -->
      <select
        v-else-if="field.type === 'template_picker'"
        :value="config[field.name]"
        @change="update(field.name, $event.target.value)"
      >
        <option value="">None (use manual fields below)</option>
        <option v-for="tpl in emailTemplates" :key="tpl.name" :value="tpl.name">
          {{ tpl.template_name }}
        </option>
      </select>

      <!-- fallback: plain text input -->
      <input
        v-else
        type="text"
        :value="config[field.name]"
        @input="update(field.name, $event.target.value)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getDoctypeList, getDoctypeFields, listEmailTemplates } from '../composables/api.js'

const props = defineProps({
  schema: { type: Array, required: true },
  config: { type: Object, required: true },
  triggerDoctype: { type: String, default: '' },
})

const emit = defineEmits(['update:config'])

const doctypes = ref([])
const targetFields = ref([])
const emailTemplates = ref([])
const tokenPlaceholder = '{{trigger.fieldname}}'

function isFieldVisible(field) {
  if (!field.depends_on) return true
  const depValue = props.config[field.depends_on]
  if (field.depends_on_value !== undefined) {
    return depValue === field.depends_on_value
  }
  return !!depValue
}

function update(fieldName, value) {
  emit('update:config', { ...props.config, [fieldName]: value })
}

function onDoctypeChange(fieldName, value) {
  const newConfig = { ...props.config, [fieldName]: value }
  if (fieldName === 'target_doctype') {
    newConfig.field_mapping = [{ target_field: '', source_value: '' }]
    loadTargetFields(value)
  }
  emit('update:config', newConfig)
}

function loadTargetFields(doctype) {
  if (!doctype) {
    targetFields.value = []
    return
  }
  getDoctypeFields(doctype).then(fields => {
    targetFields.value = fields
  }).catch(() => {
    targetFields.value = []
  })
}

function addMapping(fieldName) {
  const mappings = [...(props.config[fieldName] || [])]
  mappings.push({ target_field: '', source_value: '' })
  emit('update:config', { ...props.config, [fieldName]: mappings })
}

function removeMapping(fieldName, idx) {
  const mappings = [...(props.config[fieldName] || [])]
  mappings.splice(idx, 1)
  emit('update:config', { ...props.config, [fieldName]: mappings })
}

function updateMapping(fieldName, idx, key, value) {
  const mappings = [...(props.config[fieldName] || [])]
  mappings[idx] = { ...mappings[idx], [key]: value }
  emit('update:config', { ...props.config, [fieldName]: mappings })
}

onMounted(async () => {
  try {
    doctypes.value = await getDoctypeList()
  } catch (e) {
    console.error('Failed to load doctypes', e)
  }

  try {
    emailTemplates.value = await listEmailTemplates()
  } catch (e) {
    console.error('Failed to load email templates', e)
  }

  if (props.config.target_doctype) {
    loadTargetFields(props.config.target_doctype)
  }
})

watch(() => props.config.target_doctype, (val) => {
  if (val) loadTargetFields(val)
})
</script>
