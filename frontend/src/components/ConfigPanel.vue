<template>
  <div class="ab-config">
    <div class="ab-config-header">
      <h3>{{ title }}</h3>
      <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="$emit('close')">✕</button>
    </div>

    <!-- Trigger Config -->
    <template v-if="nodeType === 'trigger'">
      <div class="ab-config-group">
        <label>DocType</label>
        <select v-model="local.trigger_doctype" @change="onDocTypeChange">
          <option value="">Select DocType</option>
          <option v-for="dt in doctypes" :key="dt.name" :value="dt.name">{{ dt.name }}</option>
        </select>
      </div>
      <div class="ab-config-group">
        <label>Event</label>
        <select v-model="local.trigger_event">
          <option>After Insert</option>
          <option>On Update</option>
          <option>On Submit</option>
          <option>On Cancel</option>
        </select>
      </div>
    </template>

    <!-- Condition Config -->
    <template v-if="nodeType === 'condition'">
      <div class="ab-config-group">
        <label>Field</label>
        <select v-model="local.condition_field">
          <option value="">Select Field</option>
          <option v-for="f in fields" :key="f.fieldname" :value="f.fieldname">{{ f.label }} ({{ f.fieldname }})</option>
        </select>
      </div>
      <div class="ab-config-group">
        <label>Operator</label>
        <select v-model="local.condition_operator">
          <option>=</option>
          <option>!=</option>
          <option>></option>
          <option><</option>
          <option>>=</option>
          <option><=</option>
        </select>
      </div>
      <div class="ab-config-group">
        <label>Value</label>
        <input type="text" v-model="local.condition_value" placeholder="e.g. Qualified" />
      </div>
    </template>

    <!-- Action Config — schema-driven -->
    <template v-if="nodeType === 'action'">
      <div class="ab-config-group">
        <label>Action Type</label>
        <select v-model="local.action_type" @change="onActionTypeChange">
          <option value="">Select Action...</option>
          <option v-for="at in actionTypes" :key="at.key" :value="at.key">{{ at.label }}</option>
        </select>
      </div>

      <ActionConfigForm
        v-if="currentSchema.length"
        :schema="currentSchema"
        :config="local"
        :trigger-doctype="triggerDoctype"
        @update:config="onConfigUpdate"
      />

      <button
        v-if="nodeType === 'action'"
        class="ab-btn ab-btn-danger ab-btn-sm"
        @click="$emit('remove-action', nodeId)"
      >Remove Action</button>
    </template>

    <div class="ab-config-actions">
      <button class="ab-btn ab-btn-primary" @click="apply">Apply</button>
      <button class="ab-btn ab-btn-ghost" @click="$emit('close')">Cancel</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getDoctypeFields, getDoctypeList, getActionTypes } from '../composables/api.js'
import ActionConfigForm from './ActionConfigForm.vue'

const props = defineProps({
  nodeType: String,
  nodeData: Object,
  nodeId: String,
  triggerDoctype: String,
})

const emit = defineEmits(['update', 'close', 'add-action', 'remove-action'])

const local = ref({ ...props.nodeData })
const doctypes = ref([])
const fields = ref([])
const actionTypes = ref([])

const title = computed(() => {
  const titles = { trigger: 'Configure Trigger', condition: 'Configure Condition', action: 'Configure Action' }
  return titles[props.nodeType] || 'Configure'
})

const currentSchema = computed(() => {
  if (!local.value.action_type) return []
  const at = actionTypes.value.find(a => a.key === local.value.action_type)
  return at ? at.config_schema : []
})

async function onDocTypeChange() {
  if (local.value.trigger_doctype) {
    try {
      fields.value = await getDoctypeFields(local.value.trigger_doctype)
    } catch (e) {
      fields.value = []
    }
  }
}

function onActionTypeChange() {
  // Reset config to only action_type + schema defaults for the new type
  const schema = currentSchema.value
  const newLocal = { action_type: local.value.action_type }
  for (const field of schema) {
    if (field.type === 'field_mapping_table') {
      newLocal[field.name] = [{ target_field: '', source_value: '' }]
    } else {
      newLocal[field.name] = field.default !== undefined ? field.default : ''
    }
  }
  local.value = newLocal
}

function onConfigUpdate(newConfig) {
  local.value = { ...local.value, ...newConfig }
}

async function loadFields() {
  const dt = props.triggerDoctype || local.value.trigger_doctype
  if (dt) {
    try {
      fields.value = await getDoctypeFields(dt)
    } catch (e) {
      fields.value = []
    }
  }
}

function apply() {
  emit('update', { ...local.value })
}

onMounted(async () => {
  try {
    doctypes.value = await getDoctypeList()
  } catch (e) {
    console.error(e)
  }
  try {
    actionTypes.value = await getActionTypes()
  } catch (e) {
    console.error(e)
  }
  await loadFields()
})

watch(() => props.nodeData, (val) => {
  local.value = { ...val }
}, { deep: true })
</script>
