<template>
  <div class="ab-templates">
    <div class="ab-list-header">
      <h1>Email Templates</h1>
      <div style="display: flex; gap: 8px;">
        <button class="ab-btn ab-btn-ghost ab-btn-sm" @click="goBack">← Back</button>
        <button class="ab-btn ab-btn-primary ab-btn-sm" @click="createNew">New Template</button>
      </div>
    </div>

    <div v-if="loading" class="ab-loading">Loading...</div>

    <div v-else-if="templates.length === 0 && !editing" class="ab-empty">
      <p>No email templates yet. Create one to reuse across automations.</p>
    </div>

    <!-- Edit form -->
    <div v-if="editing" class="ab-template-form">
      <div class="ab-config-group">
        <label>Template Name</label>
        <input type="text" v-model="form.template_name" placeholder="e.g. Lead Qualified Notification" />
      </div>
      <div class="ab-config-group">
        <label>Subject</label>
        <input type="text" v-model="form.subject" placeholder="Use {{trigger.fieldname}} for tokens" />
      </div>
      <div class="ab-config-group">
        <label>Body</label>
        <textarea v-model="form.body" rows="8" placeholder="HTML body. Use {{trigger.fieldname}} for tokens."></textarea>
      </div>
      <p class="ab-config-hint">Use <code v-pre>{{trigger.fieldname}}</code> to reference the triggering document's fields.</p>
      <div class="ab-config-actions">
        <button class="ab-btn ab-btn-primary" @click="saveTemplate" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
        <button class="ab-btn ab-btn-ghost" @click="cancelEdit">Cancel</button>
      </div>
    </div>

    <!-- List -->
    <div v-else>
      <div v-for="tpl in templates" :key="tpl.name" class="ab-list-row" @click="editTemplate(tpl)">
        <div class="ab-list-row-left">
          <div class="ab-list-row-subject">
            <a href="#">{{ tpl.template_name }}</a>
          </div>
          <div class="ab-list-row-meta">{{ tpl.subject }}</div>
        </div>
        <div class="ab-list-row-right">
          <div class="ab-row-actions">
            <button class="ab-row-action-btn" @click.stop="editTemplate(tpl)">Edit</button>
            <button class="ab-row-action-btn ab-row-action-btn--danger" @click.stop="deleteTemplate(tpl)">Delete</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listEmailTemplates, getEmailTemplate, saveEmailTemplate } from '../composables/api.js'

const router = useRouter()
const templates = ref([])
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const form = ref({ template_name: '', subject: '', body: '' })
const editingName = ref(null)

async function load() {
  try {
    templates.value = await listEmailTemplates()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function createNew() {
  form.value = { template_name: '', subject: '', body: '' }
  editingName.value = null
  editing.value = true
}

async function editTemplate(tpl) {
  try {
    const full = await getEmailTemplate(tpl.name)
    form.value = { template_name: full.template_name, subject: full.subject, body: full.body }
    editingName.value = full.name
    editing.value = true
  } catch (e) {
    frappe.msgprint('Failed to load template')
  }
}

function cancelEdit() {
  editing.value = false
  editingName.value = null
  form.value = { template_name: '', subject: '', body: '' }
}

async function saveTemplate() {
  if (!form.value.template_name.trim()) {
    frappe.msgprint('Please enter a template name')
    return
  }
  saving.value = true
  try {
    await saveEmailTemplate({
      name: editingName.value,
      template_name: form.value.template_name,
      subject: form.value.subject,
      body: form.value.body,
    })
    frappe.show_alert({ message: 'Template saved', indicator: 'green' })
    editing.value = false
    await load()
  } catch (e) {
    frappe.msgprint('Save failed: ' + (e.message || e))
  } finally {
    saving.value = false
  }
}

async function deleteTemplate(tpl) {
  if (!confirm(`Delete template "${tpl.template_name}"?`)) return
  try {
    await frappe.call({
      method: 'frappe.client.delete',
      args: { doctype: 'Automation Email Template', name: tpl.name },
    })
    frappe.show_alert({ message: 'Template deleted', indicator: 'green' })
    await load()
  } catch (e) {
    frappe.msgprint('Delete failed: ' + (e.message || e))
  }
}

function goBack() {
  router.push({ name: 'list' })
}

onMounted(load)
</script>

<style scoped>
.ab-template-form {
  max-width: 600px;
}

.ab-template-form textarea {
  width: 100%;
  padding: var(--input-padding);
  border: none;
  border-radius: var(--border-radius-sm);
  font-size: var(--text-base);
  background: var(--control-bg);
  color: var(--text-color);
  outline: none;
  resize: vertical;
  font-family: var(--font-family-monospace);
}

.ab-template-form textarea:focus {
  box-shadow: var(--focus-blue);
}
</style>
