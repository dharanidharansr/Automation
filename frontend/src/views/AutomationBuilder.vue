<template>
  <div class="ab-builder">
    <!-- Left sidebar: node palette -->
    <NodePalette :actionTypes="actionTypes" />

    <div class="ab-canvas-area">
      <div class="ab-topbar">
        <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="goBack">← Back</button>
        <input type="text" v-model="automationName" placeholder="Automation Name" />
        <label>
          <input type="checkbox" v-model="enabled" />
          Enabled
        </label>
        <div class="ab-status-toggle" :class="{ 'ab-status-published': status === 'Published' }">
          <button 
            class="ab-status-btn" 
            :class="{ 'ab-status-btn-active': status === 'Draft' }"
            @click="status = 'Draft'"
          >
            Draft
          </button>
          <button 
            class="ab-status-btn" 
            :class="{ 'ab-status-btn-active': status === 'Published' }"
            @click="publish"
            :disabled="!canPublish"
          >
            Published
          </button>
        </div>
        <div class="ab-topbar-actions">
          <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="showRuns" v-if="automationId">Run History</button>
          <button class="ab-btn ab-btn-primary ab-btn-sm" @click="save" :disabled="saving">
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>

      <div
        class="ab-canvas-wrapper"
        @drop="onDrop"
        @dragover="onDragOver"
      >
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :fit-view-on-init="true"
          :default-edge-options="{ type: 'smoothstep', animated: false }"
          :snap-to-grid="true"
          :snap-grid="[15, 15]"
          :connectable="true"
          :connection-line-style="{ stroke: 'var(--blue-500)', strokeWidth: 2 }"
          :is-valid-connection="isValidConnection"
          @connect="onConnect"
          @connect-start="onConnectStart"
          @connect-end="onConnectEnd"
        >
          <template #node-trigger="nodeProps">
            <div class="ab-node ab-node-trigger" :class="{ 'ab-node-selected': selectedNodeId === 'trigger' }" @click="selectNode('trigger', nodeProps.data)">
              <Handle type="source" :position="Position.Bottom" id="trigger-out" />
              <Handle type="source" :position="Position.Right" id="trigger-out-right" />
              <div class="ab-node-header">
                <div class="ab-node-icon-wrap ab-node-icon-wrap--trigger">
                  <svg class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                </div>
                <span class="ab-node-title">Trigger</span>
              </div>
              <div class="ab-node-divider"></div>
              <div class="ab-node-body">
                <div>{{ nodeProps.data.trigger_doctype || 'Select DocType' }}</div>
                <div class="ab-node-summary">{{ nodeProps.data.trigger_event || 'Select Event' }}</div>
              </div>
            </div>
          </template>

          <template #node-condition="nodeProps">
            <div class="ab-node ab-node-condition" :class="{ 'ab-node-selected': selectedNodeId === 'condition' }" @click="selectNode('condition', nodeProps.data)">
              <Handle type="target" :position="Position.Top" id="condition-in" />
              <Handle type="target" :position="Position.Left" id="condition-in-left" />
              <Handle type="source" :position="Position.Bottom" id="condition-out" />
              <Handle type="source" :position="Position.Right" id="condition-out-right" />
              <div class="ab-node-header">
                <div class="ab-node-icon-wrap ab-node-icon-wrap--condition">
                  <svg class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
                </div>
                <span class="ab-node-title">Condition</span>
              </div>
              <div class="ab-node-divider"></div>
              <div class="ab-node-body">
                <span v-if="!nodeProps.data.condition_field" class="ab-node-placeholder">Click to configure</span>
                <template v-else>
                  <div>{{ nodeProps.data.condition_field }}</div>
                  <div class="ab-node-summary">{{ nodeProps.data.condition_operator }} {{ nodeProps.data.condition_value }}</div>
                </template>
              </div>
            </div>
          </template>

          <template #node-action="nodeProps">
            <div class="ab-node ab-node-action" :class="{ 'ab-node-selected': selectedNodeId === nodeProps.id }" @click="selectNode('action', nodeProps.data, nodeProps.id)">
              <Handle type="target" :position="Position.Top" :id="nodeProps.id + '-in'" />
              <Handle type="target" :position="Position.Left" :id="nodeProps.id + '-in-left'" />
              <Handle type="source" :position="Position.Bottom" :id="nodeProps.id + '-out'" />
              <Handle type="source" :position="Position.Right" :id="nodeProps.id + '-out-right'" />
              <div class="ab-node-header">
                <div class="ab-node-icon-wrap ab-node-icon-wrap--action">
                  <svg v-if="nodeProps.data.action_type === 'send_email'" class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
                  <svg v-else-if="nodeProps.data.action_type === 'http_request'" class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                  <svg v-else-if="nodeProps.data.action_type === 'telegram'" class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
                  <svg v-else-if="nodeProps.data.action_type === 'update_field'" class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>
                  <svg v-else class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M9 15h6"/><path d="M9 11h6"/></svg>
                </div>
                <span class="ab-node-title">Action</span>
              </div>
              <div class="ab-node-divider"></div>
              <div class="ab-node-body">
                <span v-if="!nodeProps.data.action_type" class="ab-node-placeholder">Click to configure</span>
                <template v-else>
                  <div>{{ actionLabel(nodeProps.data) }}</div>
                  <div class="ab-node-summary">{{ actionSummary(nodeProps.data) }}</div>
                </template>
              </div>
            </div>
          </template>

          <template #node-if="nodeProps">
            <div class="ab-node ab-node-if" :class="{ 'ab-node-selected': selectedNodeId === nodeProps.id }" @click="selectNode('if', nodeProps.data, nodeProps.id)">
              <Handle type="target" :position="Position.Top" id="if-in" />
              <div class="ab-node-header">
                <div class="ab-node-icon-wrap ab-node-icon-wrap--if">
                  <svg class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 13L2 9Z"/></svg>
                </div>
                <span class="ab-node-title">IF</span>
              </div>
              <div class="ab-node-divider"></div>
              <div class="ab-node-body">
                <span v-if="!nodeProps.data.field_to_check" class="ab-node-placeholder">Click to configure</span>
                <template v-else>
                  <div>{{ nodeProps.data.field_to_check }} {{ nodeProps.data.operator }} {{ nodeProps.data.value }}</div>
                  <div class="ab-node-summary">Evaluates condition</div>
                </template>
              </div>
              <div class="ab-node-outputs">
                <div class="ab-node-output-label ab-node-output-label--true">True</div>
                <Handle type="source" :position="Position.Right" id="if-true" :style="{ top: '30%' }" />
                <div class="ab-node-output-label ab-node-output-label--false">False</div>
                <Handle type="source" :position="Position.Right" id="if-false" :style="{ top: '70%' }" />
              </div>
            </div>
          </template>

          <template #node-switch="nodeProps">
            <div class="ab-node ab-node-switch" :class="{ 'ab-node-selected': selectedNodeId === nodeProps.id }" @click="selectNode('switch', nodeProps.data, nodeProps.id)">
              <Handle type="target" :position="Position.Top" id="switch-in" />
              <div class="ab-node-header">
                <div class="ab-node-icon-wrap ab-node-icon-wrap--switch">
                  <svg class="ab-node-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>
                </div>
                <span class="ab-node-title">Switch</span>
              </div>
              <div class="ab-node-divider"></div>
              <div class="ab-node-body">
                <span v-if="!nodeProps.data.field_to_check" class="ab-node-placeholder">Click to configure</span>
                <template v-else>
                  <div>{{ nodeProps.data.field_to_check }}</div>
                  <div class="ab-node-summary">{{ (nodeProps.data.cases || []).length }} cases + default</div>
                </template>
              </div>
              <div class="ab-node-outputs">
                <template v-for="(caseItem, idx) in (nodeProps.data.cases || [])" :key="'case-'+idx">
                  <div class="ab-node-output-label" :style="{ top: (20 + idx * (60 / Math.max((nodeProps.data.cases || []).length + 1, 2))) + '%' }">
                    {{ caseItem.case_value || 'Case ' + (idx + 1) }}
                  </div>
                  <Handle type="source" :position="Position.Right" :id="'case-'+idx" :style="{ top: (20 + idx * (60 / Math.max((nodeProps.data.cases || []).length + 1, 2))) + '%' }" />
                </template>
                <div class="ab-node-output-label ab-node-output-label--default">Default</div>
                <Handle type="source" :position="Position.Right" id="default" :style="{ top: '85%' }" />
              </div>
            </div>
          </template>

          <template #node-add-trigger="nodeProps">
            <div class="ab-node-add-wrapper">
              <Handle type="target" :position="Position.Top" id="add-trigger-in" />
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

          <Background :gap="15" :size="2" :pattern-color="'#d4d4d4'" />
          <Controls />
        </VueFlow>

        <!-- Node Type Picker (shown on drag-to-empty-canvas) -->
        <div
          v-if="pickerVisible"
          class="ab-type-picker"
          :style="{ left: pickerPosition.x + 'px', top: pickerPosition.y + 'px' }"
        >
          <button
            v-for="item in pickerItems"
            :key="item.key"
            class="ab-type-picker-item"
            @click="onPickerSelect(item)"
          >
            <span class="ab-type-picker-icon" :class="item.iconClass">
              <svg v-if="item.key === 'condition'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
              <svg v-else-if="item.key === 'if_condition'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 13L2 9Z"/></svg>
              <svg v-else-if="item.key === 'switch_case'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>
              <svg v-else-if="item.key === 'send_email'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
              <svg v-else-if="item.key === 'http_request'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
              <svg v-else-if="item.key === 'telegram'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
              <svg v-else-if="item.key === 'update_field'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M9 15h6"/><path d="M9 11h6"/></svg>
            </span>
            <span class="ab-type-picker-label">{{ item.label }}</span>
          </button>
        </div>
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
import { VueFlow, Handle, Position, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import ConfigPanel from '../components/ConfigPanel.vue'
import NodePalette from '../components/NodePalette.vue'
import { getAutomation, saveAutomation, getActionTypes, canPublish as checkCanPublish } from '../composables/api.js'

import '@vue-flow/controls/dist/style.css'

// screenToFlowCoordinate and setCenter are called at runtime after VueFlow mounts,
// so we get them from the injected instance (available in onMounted)
let screenToFlowCoordinate = (pos) => pos
let setCenterFn = null

const route = useRoute()
const router = useRouter()
const automationId = ref(route.params.name || null)
const automationName = ref('')
const enabled = ref(true)
const status = ref('Draft')
const saving = ref(false)
const showAddMenu = ref(null)
const actionTypes = ref([])

// Type picker state (for drag-to-empty-canvas)
const pickerVisible = ref(false)
const pickerPosition = ref({ x: 0, y: 0 })
const pickerSourceNodeId = ref('')
const pickerSourceHandleId = ref('')

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
    sourceHandle: 'trigger-out',
    targetHandle: 'condition-in',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-500)' },
  },
  {
    id: 'e-condition-action1',
    source: 'condition',
    target: 'action-1',
    sourceHandle: 'condition-out',
    targetHandle: 'action-1-in',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-500)' },
  },
  {
    id: 'e-action1-action2',
    source: 'action-1',
    target: 'action-2',
    sourceHandle: 'action-1-out',
    targetHandle: 'action-2-in',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-500)' },
  },
  {
    id: 'e-action2-add',
    source: 'action-2',
    target: 'add-trigger',
    sourceHandle: 'action-2-out',
    targetHandle: 'add-trigger-in',
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-500)' },
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

const canPublish = ref(false)

function publish() {
  if (canPublish.value) {
    status.value = 'Published'
  }
}

// Which source handles already have an outgoing edge (linear-only enforcement)
const connectedSourceHandles = computed(() => {
  const connected = new Set()
  for (const e of edges.value) {
    if (e.sourceHandle) {
      connected.add(`${e.source}:${e.sourceHandle}`)
    }
  }
  return connected
})

// Picker items depend on which node we're dragging from
const pickerItems = computed(() => {
  const sourceNode = nodes.value.find(n => n.id === pickerSourceNodeId.value)
  if (!sourceNode) return []

  if (sourceNode.type === 'trigger') {
    return [
      { key: 'condition', label: 'Condition', iconClass: 'ab-type-picker-icon--condition' },
      { key: 'if_condition', label: 'IF', iconClass: 'ab-type-picker-icon--logic' },
      { key: 'switch_case', label: 'Switch', iconClass: 'ab-type-picker-icon--logic' },
    ]
  }

  // Condition, IF, Switch, or Action: show all action types + logic types
  const items = []
  for (const at of actionTypes.value) {
    items.push({
      key: at.key,
      label: at.label,
      iconClass: at.node_category === 'logic' ? 'ab-type-picker-icon--logic' : 'ab-type-picker-icon--action',
    })
  }
  return items
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
  if (data.action_type === 'http_request') {
    return data.url || 'No URL'
  }
  if (data.action_type === 'telegram') {
    return data.chat_id ? `Chat: ${data.chat_id}` : 'No chat ID'
  }
  if (data.action_type === 'update_field') {
    return data.target || 'Select target'
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

function isValidConnection(params) {
  if (params.id) return true
  const { source, sourceHandle, target, targetHandle } = params
  if (source === target) return false
  if (target === 'trigger') return false
  if (source === 'add-trigger') return false

  // Linear-only: reject if source handle already has an outgoing edge
  if (sourceHandle && connectedSourceHandles.value.has(`${source}:${sourceHandle}`)) {
    return false
  }

  const existingTarget = edges.value.find(e => e.target === target && e.targetHandle === targetHandle)
  if (existingTarget) return false
  return true
}

function onConnect(params) {
  if (!isValidConnection(params)) return
  const newEdge = {
    id: `e-${params.source}-${params.target}-${Date.now()}`,
    source: params.source,
    target: params.target,
    sourceHandle: params.sourceHandle,
    targetHandle: params.targetHandle,
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
  }
  edges.value.push(newEdge)
}

/**
 * Unified node creation + edge connection.
 * Single source of truth for adding nodes to the canvas.
 * When sourceNodeId is null (sidebar drop), creates a free-floating node at dropPosition.
 */
function createNodeAndConnect(nodeType, actionType, sourceNodeId, sourceHandleId, dropPosition) {
  let newNodeId, newNodeData, newNodePosition

  if (nodeType === 'condition') {
    newNodeId = nodes.value.some(n => n.id === 'condition') ? `condition-${Date.now()}` : 'condition'
    newNodeData = { condition_field: '', condition_operator: '=', condition_value: '' }
  } else if (nodeType === 'if') {
    newNodeId = `if-${Date.now()}`
    newNodeData = { field_to_check: '', operator: '=', value: '' }
  } else if (nodeType === 'switch') {
    newNodeId = `switch-${Date.now()}`
    newNodeData = { field_to_check: '', cases: [{ case_value: '' }] }
  } else {
    newNodeId = `action-${Date.now()}`
    const at = actionTypes.value.find(a => a.key === actionType)
    newNodeData = { action_type: actionType }
    if (at && at.config_schema) {
      for (const field of at.config_schema) {
        if (field.type === 'field_mapping_table') {
          newNodeData[field.name] = [{ target_field: '', source_value: '' }]
        } else {
          newNodeData[field.name] = field.default !== undefined ? field.default : ''
        }
      }
    }
  }

  if (sourceNodeId) {
    // Connected node: position below the source node
    const sourceNode = nodes.value.find(n => n.id === sourceNodeId)
    newNodePosition = dropPosition || (sourceNode ? { x: sourceNode.position.x, y: sourceNode.position.y + 170 } : { x: 250, y: 250 })
  } else {
    // Free-floating node from sidebar drop: use drop position
    newNodePosition = dropPosition || { x: 250, y: 250 }
  }

  nodes.value.push({
    id: newNodeId,
    type: nodeType,
    position: newNodePosition,
    data: newNodeData,
  })

  // If we have a source node, connect to it
  if (sourceNodeId) {
    const sourceNode = nodes.value.find(n => n.id === sourceNodeId)
    if (sourceNode) {
      edges.value.push({
        id: `e-${sourceNodeId}-${newNodeId}`,
        source: sourceNodeId,
        target: newNodeId,
        sourceHandle: sourceHandleId,
        targetHandle: nodeType === 'condition' ? 'condition-in'
          : nodeType === 'if' ? 'if-in'
          : nodeType === 'switch' ? 'switch-in'
          : `${newNodeId}-in`,
        type: 'smoothstep',
        markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
      })
    }
  }

  // If adding an action, also connect it to the add-trigger button (if it exists)
  // Skip for branching nodes (IF/Switch) — user connects manually from handles
  if (nodeType === 'action') {
    const addTriggerNode = nodes.value.find(n => n.id === 'add-trigger')
    if (addTriggerNode) {
      edges.value.push({
        id: `e-${newNodeId}-add-trigger`,
        source: newNodeId,
        target: 'add-trigger',
        sourceHandle: `${newNodeId}-out`,
        targetHandle: 'add-trigger-in',
        type: 'smoothstep',
        markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
      })
      addTriggerNode.position.y = newNodePosition.y + 170
    }
  }

  return newNodePosition
}

function addNewAction(actionType) {
  const lastAction = [...nodes.value].filter(n => n.type === 'action').pop()
  const sourceNodeId = lastAction?.id || 'condition'
  const sourceHandleId = lastAction ? `${lastAction.id}-out` : 'condition-out'

  createNodeAndConnect('action', actionType, sourceNodeId, sourceHandleId)
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
        sourceHandle: prevEdge.sourceHandle,
        targetHandle: nextEdge.targetHandle,
        type: 'smoothstep',
        markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
      })
    }
  }
  selectedNode.value = null
}

/**
 * Handle connection drag end. Fixed: improved empty-canvas detection.
 * Vue Flow's pane element can intercept elementFromPoint, so we check
 * for the handle class explicitly and treat everything else as empty canvas.
 */
function onConnectEnd(event) {
  if (!event) return

  // Use elementFromPoint to check what's under the cursor
  const target = document.elementFromPoint(event.clientX, event.clientY)

  // If we hit a handle, Vue Flow handles the connection natively
  if (target && target.closest('.vue-flow__handle')) {
    return
  }

  // If we hit the pane/viewport/background, it's empty canvas — show picker
  // Also show picker for any other element (handles the case where Vue Flow's
  // pane intercepts the event before the handle is detected)
  const sourceNode = nodes.value.find(n => n.id === connectionStartNodeId.value)
  if (!sourceNode) return

  pickerSourceNodeId.value = connectionStartNodeId.value
  pickerSourceHandleId.value = connectionStartHandleId.value
  pickerPosition.value = {
    x: event.clientX,
    y: event.clientY,
  }
  pickerVisible.value = true
}

// Track which handle the connection drag started from
const connectionStartNodeId = ref('')
const connectionStartHandleId = ref('')

function onConnectStart(params) {
  connectionStartNodeId.value = params.nodeId
  connectionStartHandleId.value = params.handleId
}

function onPickerSelect(item) {
  const isLogicType = item.key === 'if_condition' || item.key === 'switch_case'
  const isCondition = item.key === 'condition'
  createNodeAndConnect(
    isCondition ? 'condition' : isLogicType ? (item.key === 'if_condition' ? 'if' : 'switch') : 'action',
    isCondition || isLogicType ? null : item.key,
    pickerSourceNodeId.value,
    pickerSourceHandleId.value,
    null,
  )
  pickerVisible.value = false
}

function closePicker() {
  pickerVisible.value = false
}

// Drag-and-drop from left sidebar palette
function onDragOver(event) {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
}

function onDrop(event) {
  console.log('[AB-DnD] onDrop fired', event)
  const data = event.dataTransfer.getData('application/automation-builder-node') || event.dataTransfer.getData('text/plain')
  console.log('[AB-DnD] dataTransfer data:', data)
  if (!data) {
    console.log('[AB-DnD] No data in dataTransfer, returning')
    return
  }

  try {
    const { nodeType, actionType } = JSON.parse(data)
    console.log('[AB-DnD] Parsed:', { nodeType, actionType })

    // Use Vue Flow's screenToFlowCoordinate for proper coordinate conversion
    // that accounts for pan/zoom
    const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
    console.log('[AB-DnD] Flow position:', flowPos)

    const newNodePosition = createNodeAndConnect(nodeType, actionType, null, null, flowPos)
    console.log('[AB-DnD] Node created successfully')

    // Center viewport on the new node so it's always visible (especially when zoomed in)
    if (setCenterFn && newNodePosition) {
      setCenterFn(newNodePosition.x, newNodePosition.y, { duration: 200 })
    }
  } catch (e) {
    console.error('[AB-DnD] Failed to parse drop data', e)
  }
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

    const graphDefinition = JSON.stringify({
      nodes: nodes.value
        .filter(n => n.id !== 'add-trigger')
        .map(n => ({ id: n.id, type: n.type, position: n.position, data: n.data })),
      edges: edges.value.filter(e => e.source !== 'add-trigger' && e.target !== 'add-trigger'),
    })

    // Build triggers array from trigger node data
    const triggers = []
    if (trigger?.data?.trigger_doctype) {
      // Build conditions from the trigger node's condition data
      const conditions = []
      if (trigger.data.conditions && trigger.data.conditions.length) {
        for (const cond of trigger.data.conditions) {
          if (cond.condition_field) {
            conditions.push({
              condition_field: cond.condition_field,
              condition_operator: cond.condition_operator || '=',
              condition_value: cond.condition_value || '',
            })
          }
        }
      } else if (condition?.data?.condition_field) {
        // Legacy single condition from graph condition node
        conditions.push({
          condition_field: condition.data.condition_field,
          condition_operator: condition.data.condition_operator || '=',
          condition_value: condition.data.condition_value || '',
        })
      }

      triggers.push({
        trigger_doctype: trigger.data.trigger_doctype,
        trigger_event: trigger.data.trigger_event || 'On Update',
        condition_logic: trigger.data.condition_logic || 'All must match',
        conditions: conditions,
        // Legacy flat fields for backward compat
        condition_field: condition?.data?.condition_field || '',
        condition_operator: condition?.data?.condition_operator || '=',
        condition_value: condition?.data?.condition_value || '',
      })
    }

    const result = await saveAutomation({
      name: automationId.value,
      automation_name: automationName.value,
      status: status.value,
      enabled: enabled.value ? 1 : 0,
      graph_definition: graphDefinition,
      triggers: triggers,
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
  if (pickerVisible.value && !e.target.closest('.ab-type-picker')) {
    pickerVisible.value = false
  }
  if (showAddMenu.value && !e.target.closest('.ab-add-node-menu') && !e.target.closest('.ab-add-node-btn')) {
    showAddMenu.value = null
  }
}

onMounted(async () => {
  // Get screenToFlowCoordinate from the VueFlow instance (now mounted and injected)
  try {
    const vf = useVueFlow()
    if (vf && vf.screenToFlowCoordinate) {
      screenToFlowCoordinate = vf.screenToFlowCoordinate
    }
    if (vf && vf.setCenter) {
      setCenterFn = vf.setCenter
    }
  } catch (e) {
    console.warn('[AB] Could not get useVueFlow instance, using fallback coordinate conversion')
  }

  document.addEventListener('click', handleClickOutside)

  try {
    actionTypes.value = await getActionTypes()
  } catch (e) {
    console.error('Failed to load action types', e)
  }

  // Check publish permission
  try {
    canPublish.value = await checkCanPublish()
  } catch (e) {
    console.error('Failed to check publish permission', e)
  }

  if (automationId.value) {
    try {
      const auto = await getAutomation(automationId.value)
      automationName.value = auto.automation_name
      enabled.value = !!auto.enabled
      status.value = auto.status || 'Draft'

      if (auto.graph_definition) {
        try {
          const graph = JSON.parse(auto.graph_definition)
          if (graph.nodes && graph.nodes.length) {
            nodes.value = graph.nodes.map(n => ({ ...n }))
          }
          if (graph.edges && graph.edges.length) {
            edges.value = graph.edges.map(e => ({
              ...e,
              sourceHandle: e.sourceHandle || null,
              targetHandle: e.targetHandle || null,
            }))
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
            sourceHandle: `${lastId}-out`,
            targetHandle: 'add-trigger-in',
            type: 'smoothstep',
            markerEnd: { type: 'arrowclosed', color: 'var(--gray-400)' },
          })
        } catch (e) {
          console.error('Failed to parse graph_definition', e)
        }
      } else if (auto.triggers && auto.triggers.length) {
        // Fallback: populate from triggers table
        const trigger = nodes.value.find(n => n.id === 'trigger')
        const condition = nodes.value.find(n => n.id === 'condition')
        const firstTrigger = auto.triggers[0]
        if (trigger) {
          trigger.data.trigger_doctype = firstTrigger.trigger_doctype || ''
          trigger.data.trigger_event = firstTrigger.trigger_event || 'On Update'
          // Load condition group data
          trigger.data.condition_logic = firstTrigger.condition_logic || 'All must match'
          trigger.data.conditions = firstTrigger.conditions || []
        }
        // Also populate legacy graph condition node if it exists
        if (condition) {
          condition.data.condition_field = firstTrigger.condition_field || ''
          condition.data.condition_operator = firstTrigger.condition_operator || '='
          condition.data.condition_value = firstTrigger.condition_value || ''
        }
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

.ab-status-toggle {
  display: flex;
  gap: 4px;
  padding: 2px;
  background: var(--gray-100);
  border-radius: 6px;
}

.ab-status-btn {
  padding: 4px 12px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  color: var(--gray-600);
  transition: all 0.2s;
}

.ab-status-btn:hover:not(:disabled) {
  background: var(--gray-200);
}

.ab-status-btn-active {
  background: white;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  color: var(--gray-900);
}

.ab-status-published .ab-status-btn-active {
  background: var(--green-500);
  color: white;
}

.ab-status-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
