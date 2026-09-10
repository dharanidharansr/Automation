<template>
  <div class="ab-config">
    <div class="ab-config-header">
      <h3>{{ title }}</h3>
      <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="$emit('close')">&#x2715;</button>
    </div>

    <!-- Trigger Config (multi-trigger) -->
    <template v-if="nodeType === 'trigger'">
      <div class="ab-config-hint ab-config-trigger-hint">
        Triggers fire when ANY trigger row matches (OR across rows).
        Within each row, conditions can use AND or OR logic.
      </div>

      <div v-for="(triggerRow, tIdx) in local.trigger_rows" :key="tIdx" class="ab-trigger-row">
        <div class="ab-trigger-row-header">
          <span class="ab-trigger-row-label">Trigger {{ tIdx + 1 }}</span>
          <button
            v-if="local.trigger_rows.length > 1"
            class="ab-btn ab-btn-ghost ab-btn-sm ab-condition-remove"
            @click="removeTriggerRow(tIdx)"
          >&#x2715;</button>
        </div>

        <div class="ab-config-group">
          <label>DocType</label>
          <select v-model="triggerRow.trigger_doctype" @change="onTriggerDocTypeChange(tIdx)">
            <option value="">Select DocType</option>
            <option v-for="dt in doctypes" :key="dt.name" :value="dt.name">{{ dt.name }}</option>
          </select>
        </div>
        <div class="ab-config-group">
          <label>Event</label>
          <select v-model="triggerRow.trigger_event">
            <option>After Insert</option>
            <option>On Update</option>
            <option>On Submit</option>
            <option>On Cancel</option>
          </select>
        </div>

        <!-- Condition Group -->
        <div class="ab-config-section">
          <label>Conditions</label>
          <div class="ab-condition-logic-row">
            <select v-model="triggerRow.condition_logic" class="ab-condition-logic">
              <option>All must match (AND)</option>
              <option>Any must match (OR)</option>
            </select>
          </div>
          <div v-for="(cond, idx) in triggerRow.conditions" :key="idx" class="ab-condition-row">
            <select v-model="cond.condition_field" class="ab-condition-field">
              <option value="">Field</option>
              <option v-for="f in triggerFields[tIdx]" :key="f.fieldname" :value="f.fieldname">{{ f.label }}</option>
            </select>
            <select v-model="cond.condition_operator" class="ab-condition-operator" @change="onOperatorChange(tIdx, idx)">
              <option>=</option>
              <option>!=</option>
              <option>></option>
              <option>&lt;</option>
              <option>>=</option>
              <option>&lt;=</option>
              <option>like</option>
              <option>not like</option>
              <option>in</option>
              <option>not in</option>
              <option>is set</option>
              <option>is not set</option>
            </select>
            <input
              v-if="!isUnaryOperator(cond.condition_operator)"
              type="text"
              v-model="cond.condition_value"
              class="ab-condition-value"
              :placeholder="valuePlaceholder(cond.condition_operator)"
            />
            <button class="ab-btn ab-btn-ghost ab-btn-sm ab-condition-remove" @click="removeCondition(tIdx, idx)">&#x2715;</button>
          </div>
          <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="addCondition(tIdx)">+ Add Condition</button>
        </div>
      </div>

      <button class="ab-btn ab-btn-ghost ab-btn-sm ab-add-trigger-btn" @click="addTriggerRow">+ Add Trigger</button>
    </template>

    <!-- Condition Config (graph node) -->
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
        <select v-model="local.condition_operator" @change="onNodeOperatorChange">
          <option>=</option>
          <option>!=</option>
          <option>></option>
          <option>&lt;</option>
          <option>>=</option>
          <option>&lt;=</option>
          <option>like</option>
          <option>not like</option>
          <option>in</option>
          <option>not in</option>
          <option>is set</option>
          <option>is not set</option>
        </select>
      </div>
      <div v-if="!isUnaryOperator(local.condition_operator)" class="ab-config-group">
        <label>Value</label>
        <input type="text" v-model="local.condition_value" placeholder="e.g. Qualified" />
      </div>
    </template>

    <!-- IF Config -->
    <template v-if="nodeType === 'if'">
      <div class="ab-config-group">
        <label>Field to Check</label>
        <select v-model="local.field_to_check">
          <option value="">Select Field</option>
          <option v-for="f in fields" :key="f.fieldname" :value="f.fieldname">{{ f.label }} ({{ f.fieldname }})</option>
        </select>
      </div>
      <div class="ab-config-group">
        <label>Operator</label>
        <select v-model="local.operator" @change="onIfOperatorChange">
          <option>=</option>
          <option>!=</option>
          <option>></option>
          <option>&lt;</option>
          <option>>=</option>
          <option>&lt;=</option>
          <option>like</option>
          <option>not like</option>
          <option>in</option>
          <option>not in</option>
          <option>is set</option>
          <option>is not set</option>
        </select>
      </div>
      <div v-if="!isUnaryOperator(local.operator)" class="ab-config-group">
        <label>Value</label>
        <input type="text" v-model="local.value" placeholder="e.g. Qualified" />
        <p class="ab-config-hint">Supports {{triggerDoctype}} tokens</p>
      </div>
      <div class="ab-config-hint ab-config-if-hint">
        Routes to <strong>True</strong> branch if condition matches, <strong>False</strong> otherwise.
        Connect each handle to a different action.
      </div>
    </template>

    <!-- Switch Config -->
    <template v-if="nodeType === 'switch'">
      <div class="ab-config-group">
        <label>Field to Check</label>
        <select v-model="local.field_to_check">
          <option value="">Select Field</option>
          <option v-for="f in fields" :key="f.fieldname" :value="f.fieldname">{{ f.label }} ({{ f.fieldname }})</option>
        </select>
      </div>
      <div class="ab-config-group">
        <label>Cases</label>
        <div v-for="(caseItem, idx) in local.cases" :key="idx" class="ab-mapping-row">
          <input
            type="text"
            class="ab-mapping-source"
            :value="caseItem.case_value"
            placeholder="Match value"
            @input="updateCase(idx, $event.target.value)"
          />
          <button class="ab-btn ab-btn-ghost ab-btn-sm ab-mapping-remove" @click="removeCase(idx)">&#x2715;</button>
        </div>
        <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="addCase">+ Add Case</button>
      </div>
      <div class="ab-config-hint">
        Each case creates an output handle. The <strong>Default</strong> handle is used when no case matches.
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
        v-if="nodeType === 'action' || nodeType === 'if' || nodeType === 'switch'"
        class="ab-btn ab-btn-danger ab-btn-sm"
        @click="$emit('remove-action', nodeId)"
      >Remove {{ nodeType === 'action' ? 'Action' : nodeType === 'if' ? 'IF' : 'Switch' }}</button>
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
const triggerFields = ref([])  // Array of field arrays, one per trigger row
const actionTypes = ref([])

// Initialize trigger_rows from legacy single-trigger data if needed
function ensureTriggerRows() {
  if (!local.value.trigger_rows) {
    // Convert legacy single-trigger format to multi-trigger format
    const triggers = []
    if (local.value.trigger_doctype) {
      triggers.push({
        trigger_doctype: local.value.trigger_doctype,
        trigger_event: local.value.trigger_event || 'On Update',
        condition_logic: local.value.condition_logic || 'All must match',
        conditions: local.value.conditions || [],
      })
    }
    if (!triggers.length) {
      triggers.push({
        trigger_doctype: '',
        trigger_event: 'On Update',
        condition_logic: 'All must match',
        conditions: [],
      })
    }
    local.value = { ...local.value, trigger_rows: triggers }
  }
  // Ensure triggerFields array matches trigger_rows length
  while (triggerFields.value.length < local.value.trigger_rows.length) {
    triggerFields.value.push([])
  }
}

const title = computed(() => {
  const titles = {
    trigger: 'Configure Trigger',
    condition: 'Configure Condition',
    action: 'Configure Action',
    if: 'Configure IF',
    switch: 'Configure Switch',
  }
  return titles[props.nodeType] || 'Configure'
})

const currentSchema = computed(() => {
  if (!local.value.action_type) return []
  const at = actionTypes.value.find(a => a.key === local.value.action_type)
  return at ? at.config_schema : []
})

function isUnaryOperator(op) {
  return op === 'is set' || op === 'is not set'
}

function valuePlaceholder(op) {
  if (op === 'in' || op === 'not in') return 'val1, val2, ...'
  if (op === 'like' || op === 'not like') return '%pattern%'
  return 'Value'
}

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
  const schema = currentSchema.value
  const newLocal = { action_type: local.value.action_type }
  for (const field of schema) {
    if (field.type === 'field_mapping_table') {
      newLocal[field.name] = [{ target_field: '', source_value: '' }]
    } else if (field.type === 'case_list') {
      newLocal[field.name] = [{ case_value: '' }]
    } else {
      newLocal[field.name] = field.default !== undefined ? field.default : ''
    }
  }
  local.value = newLocal
}

function onConfigUpdate(newConfig) {
  local.value = { ...local.value, ...newConfig }
}

// Condition group methods (per trigger row)
function addCondition(tIdx) {
  const triggerRows = [...(local.value.trigger_rows || [])]
  const row = { ...triggerRows[tIdx] }
  const conditions = [...(row.conditions || [])]
  conditions.push({ condition_field: '', condition_operator: '=', condition_value: '' })
  row.conditions = conditions
  triggerRows[tIdx] = row
  local.value = { ...local.value, trigger_rows: triggerRows }
}

function removeCondition(tIdx, idx) {
  const triggerRows = [...(local.value.trigger_rows || [])]
  const row = { ...triggerRows[tIdx] }
  const conditions = [...(row.conditions || [])]
  conditions.splice(idx, 1)
  row.conditions = conditions
  triggerRows[tIdx] = row
  local.value = { ...local.value, trigger_rows: triggerRows }
}

function onOperatorChange(tIdx, idx) {
  const triggerRows = [...(local.value.trigger_rows || [])]
  const row = { ...triggerRows[tIdx] }
  const conditions = [...(row.conditions || [])]
  const cond = { ...conditions[idx] }
  if (isUnaryOperator(cond.condition_operator)) {
    cond.condition_value = ''
  }
  conditions[idx] = cond
  row.conditions = conditions
  triggerRows[tIdx] = row
  local.value = { ...local.value, trigger_rows: triggerRows }
}

// Trigger row methods
function addTriggerRow() {
  const triggerRows = [...(local.value.trigger_rows || [])]
  triggerRows.push({
    trigger_doctype: '',
    trigger_event: 'On Update',
    condition_logic: 'All must match',
    conditions: [],
  })
  triggerFields.value.push([])
  local.value = { ...local.value, trigger_rows: triggerRows }
}

function removeTriggerRow(tIdx) {
  const triggerRows = [...(local.value.trigger_rows || [])]
  triggerRows.splice(tIdx, 1)
  triggerFields.value.splice(tIdx, 1)
  local.value = { ...local.value, trigger_rows: triggerRows }
}

async function onTriggerDocTypeChange(tIdx) {
  const triggerRows = local.value.trigger_rows || []
  const dt = triggerRows[tIdx]?.trigger_doctype
  if (dt) {
    try {
      const f = await getDoctypeFields(dt)
      triggerFields.value[tIdx] = f
    } catch (e) {
      triggerFields.value[tIdx] = []
    }
  }
}

function onNodeOperatorChange() {
  if (isUnaryOperator(local.value.condition_operator)) {
    local.value = { ...local.value, condition_value: '' }
  }
}

function onIfOperatorChange() {
  if (isUnaryOperator(local.value.operator)) {
    local.value = { ...local.value, value: '' }
  }
}

// Case methods (for Switch)
function addCase() {
  const cases = [...(local.value.cases || [])]
  cases.push({ case_value: '' })
  local.value = { ...local.value, cases }
}

function removeCase(idx) {
  const cases = [...(local.value.cases || [])]
  cases.splice(idx, 1)
  local.value = { ...local.value, cases }
}

function updateCase(idx, value) {
  const cases = [...(local.value.cases || [])]
  cases[idx] = { ...cases[idx], case_value: value }
  local.value = { ...local.value, cases }
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
  // Convert trigger_rows back to the flat format expected by the parent
  const data = { ...local.value }
  if (data.trigger_rows && data.trigger_rows.length) {
    // Use first trigger row for backward-compatible flat fields
    const first = data.trigger_rows[0]
    data.trigger_doctype = first.trigger_doctype
    data.trigger_event = first.trigger_event
    data.condition_logic = first.condition_logic
    data.conditions = first.conditions
    // Keep trigger_rows for multi-trigger support
    data.trigger_rows = data.trigger_rows
  }
  emit('update', data)
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

  // Initialize trigger rows and load fields for each (trigger node only)
  if (props.nodeType === 'trigger') {
    ensureTriggerRows()
    for (let i = 0; i < (local.value.trigger_rows || []).length; i++) {
      const dt = local.value.trigger_rows[i]?.trigger_doctype
      if (dt) {
        try {
          triggerFields.value[i] = await getDoctypeFields(dt)
        } catch (e) {
          triggerFields.value[i] = []
        }
      }
    }
  }

  // Also load fields for legacy single-trigger mode (condition/if/switch nodes)
  await loadFields()
})

watch(() => props.nodeData, (val) => {
  local.value = { ...val }
  if (props.nodeType === 'trigger') {
    ensureTriggerRows()
    // Reload fields for each trigger row
    for (let i = 0; i < (local.value.trigger_rows || []).length; i++) {
      const dt = local.value.trigger_rows[i]?.trigger_doctype
      if (dt) {
        getDoctypeFields(dt).then(f => { triggerFields.value[i] = f }).catch(() => { triggerFields.value[i] = [] })
      }
    }
  }
}, { deep: true })
</script>
