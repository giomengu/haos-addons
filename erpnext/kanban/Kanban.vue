<template>
  <div class="overflow-x-auto">
    <div v-if="error" class="mb-2 rounded bg-surface-red-1 p-2 text-sm text-ink-red-3">{{ error }}</div>
    <div v-if="loading" class="p-3 text-sm text-ink-gray-5">Loading board…</div>
    <div v-else-if="!doctype" class="p-3 text-sm text-ink-gray-5">Set a DocType to load this board.</div>
    <div v-else class="flex min-h-48 gap-3">
      <section v-for="column in columnList" :key="column" class="w-64 shrink-0 rounded-lg bg-surface-gray-2 p-3" @dragover.prevent @drop.prevent="drop($event, column)">
        <div class="mb-3 flex justify-between text-sm font-semibold text-ink-gray-8"><span>{{ column }}</span><span>{{ cards(column).length }}</span></div>
        <div v-for="record in cards(column)" :key="record.name" draggable="true" class="mb-2 cursor-grab rounded border border-outline-gray-2 bg-surface-white p-3 text-sm text-ink-gray-9" @dragstart="drag($event, record.name)">
          <div>{{ record[titleField] || record.name }}</div><div class="mt-1 text-xs text-ink-gray-5">{{ record.name }}</div>
        </div>
      </section>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { createResource } from "frappe-ui"

const props = withDefaults(defineProps<{ doctype?: string; statusField?: string; titleField?: string; columns?: string; limit?: number }>(), {
  doctype: "", statusField: "status", titleField: "name", columns: "Open,Working,Completed", limit: 100,
})
const records = ref<Record<string, any>[]>([])
const loading = ref(false)
const error = ref("")
const columnList = computed(() => [...new Set(props.columns.split(",").map((s) => s.trim()).filter(Boolean))])
const cards = (column: string) => records.value.filter((record) => record[props.statusField] === column)
let requestId = 0
async function load() {
  const id = ++requestId
  if (!props.doctype || !props.statusField || !props.titleField) { records.value = []; return }
  loading.value = true; error.value = ""
  try {
    const resource = createResource({ url: "frappe.client.get_list" })
    const result = await resource.submit({ doctype: props.doctype, fields: [...new Set(["name", props.statusField, props.titleField])], limit_page_length: Math.min(Math.max(props.limit, 1), 500) })
    if (id === requestId) records.value = result || []
  } catch (e: any) { if (id === requestId) error.value = e?.messages?.join(" ") || e?.message || "Could not load records." }
  finally { if (id === requestId) loading.value = false }
}
function drag(event: DragEvent, name: string) { event.dataTransfer?.setData("text/plain", name) }
async function drop(event: DragEvent, column: string) {
  const name = event.dataTransfer?.getData("text/plain")
  const record = records.value.find((row) => row.name === name)
  if (!record || record[props.statusField] === column) return
  error.value = ""
  try {
    const resource = createResource({ url: "frappe.client.set_value" })
    await resource.submit({ doctype: props.doctype, name, fieldname: props.statusField, value: column })
    await load()
  } catch (e: any) { error.value = e?.messages?.join(" ") || e?.message || "Could not move the card." }
}
watch(() => [props.doctype, props.statusField, props.titleField, props.limit], load, { immediate: true })
</script>
