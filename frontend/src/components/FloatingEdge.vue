<script setup>
import { computed } from 'vue'
import { getBezierPath, getSmoothStepPath } from '@vue-flow/core'

const props = defineProps({
  id: { type: String, required: true },
  source: { type: String, required: true },
  target: { type: String, required: true },
  sourceX: { type: Number, required: true },
  sourceY: { type: Number, required: true },
  targetX: { type: Number, required: true },
  targetY: { type: Number, required: true },
  sourcePosition: { type: String },
  targetPosition: { type: String },
  data: { type: Object },
  markerEnd: { type: Object },
  style: { type: Object },
})

const path = computed(() => {
  return getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
    borderRadius: 8,
  })
})
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path"
    :d="path[0]"
    :marker-end="markerEnd"
  />
</template>
