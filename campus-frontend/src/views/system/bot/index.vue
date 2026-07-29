<template>
  <div class="page-shell">
    <PageHeader title="Bot management" description="Credentials are sent once to the backend and stored encrypted. They are never returned to this page.">
      <template #actions><el-button type="primary" :icon="Plus" @click="openCreate">Add bot</el-button></template>
    </PageHeader>
    <section class="content-card table-card"><div class="table-card__body">
      <el-table :data="bots" v-loading="loading" row-key="id">
        <el-table-column prop="name" label="Name" min-width="160" />
        <el-table-column prop="platform" label="Platform" min-width="130" />
        <el-table-column label="Status" min-width="160"><template #default="{ row }"><StatusTag :label="row.status" :tone="tone(row.status)" /><small v-if="row.status_detail" class="detail">{{ row.status_detail }}</small></template></el-table-column>
        <el-table-column label="Group rule" min-width="145"><template #default="{ row }">{{ row.mention_required ? 'Mention or prefix required' : 'Reply directly' }}</template></el-table-column>
        <el-table-column label="Actions" width="320" fixed="right"><template #default="{ row }"><div class="actions"><el-button link type="primary" @click="start(row)">Start</el-button><el-button link @click="stop(row)">Stop</el-button><el-button link type="primary" @click="showLogin(row)">Login guide</el-button><el-button link @click="showHealth(row)">Health</el-button><el-popconfirm title="Delete this bot?" @confirm="remove(row)"><template #reference><el-button link type="danger">Delete</el-button></template></el-popconfirm></div></template></el-table-column>
        <template #empty><EmptyState title="No bots configured" description="Generate BOT_CREDENTIALS_ENCRYPTION_KEY first, then add a platform account." /></template>
      </el-table>
    </div></section>
    <el-dialog v-model="editorVisible" title="Add bot" width="620px" @closed="resetEditor"><el-form :model="editor" label-position="top"><div class="grid"><el-form-item label="Platform" required><el-select v-model="editor.platform" style="width:100%"><el-option label="WeChat ClawBot / OpenClaw" value="WEIXIN_OC" /><el-option label="DingTalk" value="DINGTALK" /><el-option label="QQ OneBot v11" value="QQ_ONEBOT" /></el-select></el-form-item><el-form-item label="Name" required><el-input v-model="editor.name" maxlength="120" /></el-form-item></div><el-form-item label="Group rule"><el-switch v-model="editor.mention_required" active-text="Mention or prefix required" inactive-text="Reply directly" /></el-form-item><el-form-item label="Command prefix (optional)"><el-input v-model="editor.command_prefix" maxlength="32" /></el-form-item><el-form-item label="Credentials JSON"><el-input v-model="credentialsJson" type="textarea" :rows="7" placeholder='{"api_base_url":"...","token":"..."}' /><div class="hint">Credentials are encrypted by the backend and cannot be viewed later.</div></el-form-item></el-form><template #footer><el-button @click="editorVisible=false">Cancel</el-button><el-button type="primary" :loading="saving" @click="save">Save</el-button></template></el-dialog>
    <el-dialog v-model="infoVisible" :title="infoTitle" width="620px"><pre class="info">{{ infoText }}</pre></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { createBot, getBotHealth, getBotLoginQr, listBots, removeBot, startBot, stopBot, type BotInstance, type BotPlatform } from '@/api/bot'
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'

const bots = ref<BotInstance[]>([])
const loading = ref(false), saving = ref(false), editorVisible = ref(false), infoVisible = ref(false)
const infoTitle = ref(''), infoText = ref('')
const editor = reactive<{ platform: BotPlatform; name: string; mention_required: boolean; command_prefix: string }>({ platform: 'WEIXIN_OC', name: '', mention_required: true, command_prefix: '' })
const credentialsJson = ref('{}')
const tone = (status: string): 'success' | 'warning' | 'danger' | 'info' => status === 'RUNNING' ? 'success' : status === 'ERROR' ? 'danger' : status === 'QR_REQUIRED' ? 'warning' : 'info'

async function load() { loading.value = true; try { bots.value = (await listBots()).data } finally { loading.value = false } }
function resetEditor() { Object.assign(editor, { platform: 'WEIXIN_OC', name: '', mention_required: true, command_prefix: '' }); credentialsJson.value = '{}' }
function openCreate() { resetEditor(); editorVisible.value = true }
async function save() { let credentials: Record<string, string>; try { credentials = JSON.parse(credentialsJson.value); if (!credentials || Array.isArray(credentials) || typeof credentials !== 'object') throw new Error() } catch { ElMessage.error('Credentials must be a JSON object.'); return }; saving.value = true; try { await createBot({ ...editor, credentials }); ElMessage.success('Bot saved.'); editorVisible.value = false; await load() } finally { saving.value = false } }
async function start(row: BotInstance) { await startBot(row.id); ElMessage.success('Start requested.'); await load() }
async function stop(row: BotInstance) { await stopBot(row.id); ElMessage.success('Bot stopped.'); await load() }
async function remove(row: BotInstance) { await removeBot(row.id); ElMessage.success('Bot deleted.'); await load() }
async function showLogin(row: BotInstance) { const response = await getBotLoginQr(row.id); infoTitle.value = 'Login guide'; infoText.value = JSON.stringify(response.data, null, 2); infoVisible.value = true }
async function showHealth(row: BotInstance) { const response = await getBotHealth(row.id); infoTitle.value = 'Health'; infoText.value = JSON.stringify(response.data, null, 2); infoVisible.value = true }
onMounted(load)
</script>

<style scoped>
.grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.actions { display:flex; gap:4px; flex-wrap:wrap; }
.detail { display:block; margin-top:5px; color:var(--text-light); }
.hint { margin-top:7px; color:var(--text-light); font-size:12px; }
.info { max-height:420px; overflow:auto; white-space:pre-wrap; word-break:break-word; }
</style>
