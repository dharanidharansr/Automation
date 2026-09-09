<template>
  <div class="ab-node-palette" :class="{ 'ab-node-palette--collapsed': collapsed }">
    <div class="ab-node-palette-header">
      <span v-if="!collapsed" class="ab-node-palette-title">Nodes</span>
      <button class="ab-node-palette-toggle" @click="collapsed = !collapsed" :title="collapsed ? 'Expand' : 'Collapse'">
        <svg v-if="collapsed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="m9 18 6-6-6-6"/></svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="m15 18-6-6 6-6"/></svg>
      </button>
    </div>
    <div v-if="!collapsed" class="ab-node-palette-items">
      <div
        v-for="item in paletteItems"
        :key="item.key"
        class="ab-node-palette-item"
        draggable="true"
        @dragstart="onDragStart($event, item)"
      >
        <span class="ab-node-palette-icon" :class="item.iconClass">
          <svg v-if="item.key === 'condition'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
          <svg v-else-if="item.key === 'send_email'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
          <svg v-else-if="item.key === 'http_request'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
          <svg v-else-if="item.key === 'telegram'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
          <svg v-else-if="item.key === 'update_field'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M9 15h6"/><path d="M9 11h6"/></svg>
        </span>
        <span class="ab-node-palette-label">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  actionTypes: { type: Array, default: () => [] },
})

const collapsed = ref(false)

const paletteItems = computed(() => {
  const items = [
    { key: 'condition', label: 'Condition', iconClass: 'ab-node-palette-icon--condition' },
  ]
  for (const at of props.actionTypes) {
    items.push({
      key: at.key,
      label: at.label,
      iconClass: 'ab-node-palette-icon--action',
    })
  }
  return items
})

function onDragStart(event, item) {
  const payload = JSON.stringify({
    nodeType: item.key === 'condition' ? 'condition' : 'action',
    actionType: item.key === 'condition' ? null : item.key,
  })
  console.log('[AB-DnD] dragstart fired, setting data:', payload)
  event.dataTransfer.setData('application/automation-builder-node', payload)
  event.dataTransfer.effectAllowed = 'move'
  // Also set text/plain as a fallback — some browsers require this
  event.dataTransfer.setData('text/plain', payload)
}
</script>
