<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from './api'
import { toast, notify } from './toast'
import ChatView from './views/ChatView.vue'
import DocsView from './views/DocsView.vue'
import SettingsDrawer from './views/SettingsDrawer.vue'

// 对话历史用 PostgresChatMessageHistory，session_id 必须是合法 UUID，
// 普通字符串会在提问时被后端拒绝，所以选之前先挡掉
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const isUuid = (id) => UUID_RE.test(id || '')

const collections = ref([])
const activeId = ref('')
const tab = ref(
  new URLSearchParams(window.location.search).get('tab') === 'docs' ? 'docs' : 'chat'
)
const users = ref([])
const userId = ref('')
const creating = ref(false)
const newName = ref('')
const nameInput = ref(null)
const settingsOpen = ref(false)

const activeCollection = computed(
  () => collections.value.find((c) => c.uuid === activeId.value) || null
)

async function loadCollections() {
  try {
    collections.value = (await api.listCollections()) || []
    if (!collections.value.some((c) => c.uuid === activeId.value)) {
      activeId.value = collections.value[0]?.uuid || ''
    }
  } catch (e) {
    notify(e.message, 'error')
  }
}

async function loadUsers() {
  try {
    users.value = (await api.listUsers()) || []
    if (!users.value.some((u) => u.id === userId.value && isUuid(u.id))) {
      userId.value = users.value.find((u) => isUuid(u.id))?.id || ''
    }
  } catch (e) {
    notify(e.message, 'error')
  }
}

function startCreate() {
  creating.value = true
  newName.value = ''
  nextTick(() => nameInput.value?.focus())
}

async function submitNewCollection() {
  const name = newName.value.trim()
  if (!name) {
    creating.value = false
    return
  }
  try {
    const created = await api.createCollection(name)
    creating.value = false
    await loadCollections()
    if (created?.uuid) activeId.value = created.uuid
  } catch (e) {
    notify(e.message, 'error')
  }
}

async function removeCollection(c) {
  if (!confirm(`删除知识库「${c.name}」？库里的文件记录会一起删掉，不能恢复。`)) return
  try {
    await api.deleteCollection(c.uuid)
    if (activeId.value === c.uuid) activeId.value = ''
    await loadCollections()
  } catch (e) {
    notify(e.message, 'error')
  }
}

function selectCollection(uuid) {
  activeId.value = uuid
}

onMounted(() => {
  loadCollections()
  loadUsers()
})
</script>

<template>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">知识库</div>
      <div class="section-label">知识库列表</div>

      <ul class="kb-list">
        <li
          v-for="c in collections"
          :key="c.uuid"
          :class="{ active: c.uuid === activeId }"
          @click="selectCollection(c.uuid)"
        >
          <span class="kb-name">{{ c.name }}</span>
          <button class="icon-btn" title="删除知识库" @click.stop="removeCollection(c)">×</button>
        </li>
        <li v-if="!collections.length" class="empty-hint">还没有知识库</li>
      </ul>

      <form v-if="creating" class="new-kb" @submit.prevent="submitNewCollection">
        <input
          ref="nameInput"
          v-model="newName"
          placeholder="名称，回车确认"
          @blur="creating = false"
          @keydown.esc="creating = false"
        />
      </form>
      <button v-else class="ghost-btn" @click="startCreate">+ 新建知识库</button>

      <div class="sidebar-foot">
        <label v-if="users.length" class="user-pick">
          <span>当前用户</span>
          <select v-model="userId">
            <option v-for="u in users" :key="u.id" :value="u.id" :disabled="!isUuid(u.id)">
              {{ u.name }}<template v-if="!isUuid(u.id)">（id 不是 UUID，用不了）</template>
            </option>
          </select>
        </label>
        <div v-else class="hint">
          数据库里没有用户，先在库中插一条，<strong>id 必须是 UUID</strong>：
          <code
            >INSERT INTO "user"(id, name) VALUES
            ('b3f1c2d4-5e6a-4b7c-8d9e-0f1a2b3c4d5e', '刘洋');</code
          >
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <h1>{{ activeCollection ? activeCollection.name : '未选择知识库' }}</h1>
        <nav class="tabs">
          <button :class="{ on: tab === 'chat' }" @click="tab = 'chat'">对话</button>
          <button :class="{ on: tab === 'docs' }" @click="tab = 'docs'">文档</button>
        </nav>
        <button class="settings-btn" @click="settingsOpen = true">设置</button>
      </header>

      <ChatView
        v-if="tab === 'chat'"
        :key="'chat-' + activeId + '-' + userId"
        :collection-id="activeId"
        :user-id="userId"
      />
      <DocsView v-else :key="'docs-' + activeId" :collection-id="activeId" />
    </main>

    <SettingsDrawer v-if="settingsOpen" @close="settingsOpen = false" />

    <div v-if="toast.text" class="toast" :class="toast.kind">{{ toast.text }}</div>
  </div>
</template>
