<template>
  <div class="ab-builder">
    <div class="ab-canvas-area">
      <div class="ab-topbar">
        <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="goBack">← Back</button>
        <input type="text" v-model="automationName" placeholder="Automation Name" />
        <label>
          <input type="checkbox" v-model="enabled" />
          Enabled
        </label>
        <div class="ab-topbar-actions">
          <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="showRuns" v-if="automationId">Run History</button>
          <button class="ab-btn ab-btn-primary ab-btn-sm" @click="save" :disabled="saving">
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>

      <div class="ab-canvas-wrapper">
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :fit-view-on-init="true"
          :default-edge-options="{ type: 'smoothstep', animated: false }"
          :snap-to-grid="true"
          :snap-grid="[15, 15]"
        >
          <template #node-trigger="nodeProps">
            <div class="ab-node ab-node-trigger" @click="selectNode('trigger', nodeProps.data)">
              <Handle type="source" :position="Position.Bottom" />
              <div class="ab-node-header">
                <span class="ab-node-icon">⚡</span>
                <span class="ab-node-title">Trigger</span>
              </div>
              <div class="ab-node-body">
                <div>{{ nodeProps.data.trigger_doctype || 'Select DocType' }}</div>
                <div class="ab-node-summary">{{ nodeProps.data.trigger_event || 'Select Event' }}</div>
              </div>
            </div>
          </template>

          <template #node-condition="nodeProps">
            <div class="ab-node ab-node-condition" @click="selectNode('condition', nodeProps.data)">
              <Handle type="target" :position="Position.Top" />
              <Handle type="source" :position="Position.Bottom" />
              <div class="ab-node-header">
                <span class="ab-node-icon">◆</span>
                <span class="ab-node-title">Condition</span>
              </div>
              <div class="ab-node-body">
                <span v-if="!nodeProps.data.condition_field">Click to configure</span>
                <template v-else>
                  <div>{{ nodeProps.data.condition_field }}</div>
                  <div class="ab-node-summary">{{ nodeProps.data.condition_operator }} {{ nodeProps.data.condition_value }}</div>
                </template>
              </div>
            </div>
          </template>

          <template #node-action="nodeProps">
            <div class="ab-node ab-node-action" @click="selectNode('action', nodeProps.data, nodeProps.id)">
              <Handle type="target" :position="Position.Top" />
              <div class="ab-node-header">
                <span class="ab-node-icon">⚙</span>
                <span class="ab-node-title">Action</span>
              </div>
              <div class="ab-node-body">
                <span v-if="!nodeProps.data.action_type">Click to configure</span>
                <template v-else>
                  <div>{{ actionLabel(nodeProps.data) }}</div>
                  <div class="ab-node-summary">{{ actionSummary(nodeProps.data) }}</div>
                </template>
              </div>
            </div>
          </template>

          <template #node-add-trigger="nodeProps">
            <div class="ab-node-add-wrapper">
              <div class="ab-node-add-line"></div>
              <button class="ab-add-node-btn" @click.stop="toggleAddMenu(nodeProps.id)">+</button>
              <div v-if="showAddMenu === nodeProps.id" class="ab-add-node-menu">
                <button
                  v-for="at in actionTypes"
                  :key="at.key"
                  class="ab-add-node-menu-item"
                  @click.stop="addNewAction(at.key)"
                >
                  <span class="ab-add-node-menu-item-icon ab-add-node-menu-item-icon--action">⚙</span>
                  {{ at.label }}
                </button>
              </div>
            </div>
          </template>

          <Background :gap="15" :size="1" :pattern-color="'var(--gray-300)'" />
          <Controls />
        </VueFlow>
      </div>
    </div>

    <div class="ab-sidebar" v-if="selectedNode">
      <ConfigPanel
        :node-type="selectedNodeType"
        :node-data="selectedNodeData"
        :node-id="selectedNodeId"
        :trigger-doctype="triggerDoctype"
        @update="updateNodeData"
        @close="selectedNode = null"
        @add-action="addActionNode"
        @remove-action="removeActionNode"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueFlow, Handle, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import ConfigPanel from '../components/ConfigPanel.vue'
import { getAutomation, saveAutomation, getActionTypes } from '../composables/api.js'

import '@vue-flow/controls/dist/style.css'

const route = useRoute()
const router = useRouter()
const automationId = ref(route.params.name || null)
const automationName = ref('')
const enabled = ref(true)
const saving = ref(false)
const showAddMenu = ref(null)
const actionTypes = ref([])

const nodes = ref([
  {
    id: 'trigger',
    type: 'trigger',
    position: { x: 250, y: 50 },
    data: {
      trigger_doctype: '',
      trigger_event: 'On Update',
    },
  },
  {
    id: 'condition',
    type: 'condition',
    position: { x: 250, y: 250 },
    data: {
      condition_field: '',
      condition_operator: '=',
      condition_value: '',
    },
  },
  {
    id: 'action-1',
    type: 'action',
    position: { x: 250, y: 450 },
    data: {
      action_type: 'create_document',
      target_doctype: '',
      field_mapping: [{ target_field: '', source_value: '' }],
    },
  },
  {
    id: 'action-2',
    type: 'action',
    position: { x: 250, y: 620 },
    data: {
      action_type: 'send_email',
      recipient: '',
      subject: '',
      body: '',
    },
  },
  {
    id: 'add-trigger',
    type: 'add-trigger',
    position: { x: 250, y: 790 },
    data: {},
  },
])

const edges = ref([
  {
    id: 'e-trigger-condition',
    source: 'trigger',
    target: 'condition',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
  },
  {
    id: 'e-condition-action1',
    source: 'condition',
    target: 'action-1',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
  },
  {
    id: 'e-action1-action2',
    source: 'action-1',
    target: 'action-2',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
  },
  {
    id: 'e-action2-add',
    source: 'action-2',
    target: 'add-trigger',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
  },
])

const selectedNode = ref(null)
const selectedNodeType = ref('')
const selectedNodeData = ref({})
const selectedNodeId = ref('')

const triggerDoctype = computed(() => {
  const trigger = nodes.value.find(n => n.id === 'trigger')
  return trigger?.data?.trigger_doctype || ''
})

function actionLabel(data) {
  const at = actionTypes.value.find(a => a.key === data.action_type)
  return at ? at.label : data.action_type || 'Unknown'
}

function actionSummary(data) {
  if (data.action_type === 'create_document') {
    return data.target_doctype || 'No target DocType'
  }
  if (data.action_type === 'send_email') {
    return `To: ${data.recipient || '...'}`
  }
  return 'Click to configure'
}

function selectNode(type, data, id) {
  selectedNodeType.value = type
  selectedNodeData.value = { ...data }
  selectedNodeId.value = id || type
  selectedNode.value = true
}

function updateNodeData(newData) {
  const nodeId = selectedNodeId.value
  const node = nodes.value.find(n => n.id === nodeId || n.id === selectedNodeType.value)
  if (node) {
    node.data = { ...node.data, ...newData }
  }
  selectedNode.value = null
}

function toggleAddMenu(nodeId) {
  showAddMenu.value = showAddMenu.value === nodeId ? null : nodeId
}

function closeAddMenu() {
  showAddMenu.value = null
}

function addNewAction(actionType) {
  const lastAction = [...nodes.value].filter(n => n.type === 'action').pop()
  const lastY = lastAction ? lastAction.position.y + 170 : 450
  const newId = `action-${Date.now()}`

  // Build default data from the action type's config_schema
  const at = actionTypes.value.find(a => a.key === actionType)
  const defaultData = { action_type: actionType }
  if (at && at.config_schema) {
    for (const field of at.config_schema) {
      if (field.type === 'field_mapping_table') {
        defaultData[field.name] = [{ target_field: '', source_value: '' }]
      } else {
        defaultData[field.name] = ''
      }
    }
  }

  // Insert new action node before the add-trigger node
  const addTriggerIdx = nodes.value.findIndex(n => n.id === 'add-trigger')
  nodes.value.splice(addTriggerIdx, 0, {
    id: newId,
    type: 'action',
    position: { x: 250, y: lastY },
    data: defaultData,
  })

  // Update edges: remove old action→add edge, add new edges
  const lastNodeId = lastAction?.id || 'action-1'
  const oldAddEdge = edges.value.find(e => e.source === lastAction?.id && e.target === 'add-trigger')
  if (oldAddEdge) {
    edges.value = edges.value.filter(e => e !== oldAddEdge)
  }

  edges.value.push({
    id: `e-${lastNodeId}-${newId}`,
    source: lastNodeId,
    target: newId,
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
  })
  edges.value.push({
    id: `e-${newId}-add-trigger`,
    source: newId,
    target: 'add-trigger',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
  })

  // Update add-trigger position
  const addTriggerNode = nodes.value.find(n => n.id === 'add-trigger')
  if (addTriggerNode) {
    addTriggerNode.position.y = lastY + 170
  }

  showAddMenu.value = null
}

function removeActionNode(nodeId) {
  const idx = nodes.value.findIndex(n => n.id === nodeId)
  if (idx > -1) {
    const prevEdge = edges.value.find(e => e.target === nodeId)
    const nextEdge = edges.value.find(e => e.source === nodeId)

    nodes.value.splice(idx, 1)
    edges.value = edges.value.filter(e => e.source !== nodeId && e.target !== nodeId)

    if (prevEdge && nextEdge) {
      edges.value.push({
        id: `e-${prevEdge.source}-${nextEdge.target}`,
        source: prevEdge.source,
        target: nextEdge.target,
        type: 'smoothstep',
        markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
      })
    }
  }
  selectedNode.value = null
}

async function save() {
  if (!automationName.value.trim()) {
    frappe.msgprint('Please enter an automation name')
    return
  }
  saving.value = true
  try {
    const trigger = nodes.value.find(n => n.id === 'trigger')
    const condition = nodes.value.find(n => n.id === 'condition')
    const actions = nodes.value.filter(n => n.type === 'action').map(n => ({
      type: n.data.action_type,
      config: { ...n.data },
    }))

    const workflowJson = JSON.stringify({
      nodes: nodes.value
        .filter(n => n.id !== 'add-trigger')
        .map(n => ({ id: n.id, type: n.type, position: n.position, data: n.data })),
      edges: edges.value.filter(e => e.source !== 'add-trigger' && e.target !== 'add-trigger'),
      actions,
    })

    const result = await saveAutomation({
      name: automationId.value,
      automation_name: automationName.value,
      trigger_doctype: trigger?.data?.trigger_doctype,
      trigger_event: trigger?.data?.trigger_event,
      condition_field: condition?.data?.condition_field,
      condition_operator: condition?.data?.condition_operator,
      condition_value: condition?.data?.condition_value,
      enabled: enabled.value ? 1 : 0,
      workflow_json: workflowJson,
    })

    automationId.value = result.name
    frappe.show_alert({ message: 'Automation saved', indicator: 'green' })
  } catch (e) {
    frappe.msgprint('Save failed: ' + (e.message || e))
  } finally {
    saving.value = false
  }
}

function goBack() {
  router.push({ name: 'list' })
}

function showRuns() {
  router.push({ name: 'runs', params: { name: automationId.value } })
}

function handleClickOutside(e) {
  if (showAddMenu.value && !e.target.closest('.ab-add-node-menu') && !e.target.closest('.ab-add-node-btn')) {
    showAddMenu.value = null
  }
}

onMounted(async () => {
  document.addEventListener('click', handleClickOutside)

  // Load action types from registry for the "+" dropdown
  try {
    actionTypes.value = await getActionTypes()
  } catch (e) {
    console.error('Failed to load action types', e)
  }

  if (automationId.value) {
    try {
      const auto = await getAutomation(automationId.value)
      automationName.value = auto.automation_name
      enabled.value = !!auto.enabled

      if (auto.workflow_json) {
        try {
          const wf = JSON.parse(auto.workflow_json)
          if (wf.nodes && wf.nodes.length) {
            nodes.value = wf.nodes.map(n => ({ ...n }))
          }
          if (wf.edges && wf.edges.length) {
            edges.value = wf.edges.map(e => ({ ...e }))
          }

          const lastAction = [...nodes.value].filter(n => n.type === 'action').pop()
          const addY = lastAction ? lastAction.position.y + 170 : 790
          nodes.value.push({
            id: 'add-trigger',
            type: 'add-trigger',
            position: { x: 250, y: addY },
            data: {},
          })
          const lastId = lastAction ? lastAction.id : 'condition'
          edges.value.push({
            id: `e-${lastId}-add-trigger`,
            source: lastId,
            target: 'add-trigger',
            type: 'smoothstep',
            markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
          })
        } catch (e) {
          console.error('Failed to parse workflow_json', e)
        }
      } else {
        const trigger = nodes.value.find(n => n.id === 'trigger')
        const condition = nodes.value.find(n => n.id === 'condition')
        if (trigger) {
          trigger.data.trigger_doctype = auto.trigger_doctype || ''
          trigger.data.trigger_event = auto.trigger_event || 'On Update'
        }
        if (condition) {
          condition.data.condition_field = auto.condition_field || ''
          condition.data.condition_operator = auto.condition_operator || '='
          condition.data.condition_value = auto.condition_value || ''
        }
      }
    } catch (e) {
      frappe.msgprint('Failed to load automation')
    }
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.ab-node-add-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 40px;
}

.ab-node-add-line {
  width: 1px;
  height: 20px;
  background: var(--gray-400);
}
</style>
