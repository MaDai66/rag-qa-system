<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../api'
import { notify } from '../toast'
import { parseBlocks } from '../markdown'
import RichText from '../components/RichText.vue'

const props = defineProps({
  collectionId: { type: String, default: '' },
  userId: { type: String, default: '' },
})

const messages = ref([])
const draft = ref('')
const sending = ref(false)
const scroller = ref(null)
const popup = ref(null)

const canSend = computed(() => !!props.userId && !!props.collectionId && !sending.value)
const placeholder = computed(() => {
  if (!props.userId) return '先选择一个用户'
  if (!props.collectionId) return '先在左侧选择一个知识库'
  return '向当前知识库提问，Enter 发送，Shift + Enter 换行'
})

function textOf(content) {
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content.map((p) => (typeof p === 'string' ? p : p?.text || '')).join('')
  }
  return content == null ? '' : String(content)
}

function toView(m) {
  if (!m || typeof m !== 'object') return null
  const role = m.type === 'human' ? 'user' : m.type === 'ai' ? 'assistant' : null
  if (!role) return null
  const content = textOf(m.content)
  return {
    role,
    content,
    // 模型的回答是 Markdown，用户输入和报错不是，只给回答解析
    blocks: role === 'assistant' ? parseBlocks(content) : [],
    sources: m.response_metadata?.file_info_list || [],
  }
}

async function loadHistory() {
  if (!props.userId) return
  try {
    const raw = await api.history(props.userId)
    messages.value = (raw || []).map(toView).filter(Boolean)
    scrollToEnd()
  } catch (e) {
    notify(e.message, 'error')
  }
}

function scrollToEnd() {
  nextTick(() => {
    const el = scroller.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function autosize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 180) + 'px'
}

async function send() {
  if (!canSend.value) return
  const text = draft.value.trim()
  if (!text) return

  messages.value.push({ role: 'user', content: text, blocks: [], sources: [] })
  draft.value = ''
  sending.value = true
  scrollToEnd()

  try {
    const res = await api.chat(props.userId, text, props.collectionId)
    const content = textOf(res?.content)
    messages.value.push({
      role: 'assistant',
      content,
      blocks: parseBlocks(content),
      sources: res?.file_info_list || [],
    })
  } catch (e) {
    messages.value.push({ role: 'error', content: e.message, blocks: [], sources: [] })
  } finally {
    sending.value = false
    scrollToEnd()
  }
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}

async function openSource(s) {
  try {
    const chunk = await api.getChunk(s.chunk_id)
    popup.value = { title: s.file_name, content: chunk?.context || '（这一段没有正文）' }
  } catch (e) {
    notify(e.message, 'error')
  }
}

async function clearHistory() {
  if (!props.userId) return
  if (!confirm('清空这个用户的全部对话记录？')) return
  try {
    await api.clearHistory(props.userId)
    messages.value = []
  } catch (e) {
    notify(e.message, 'error')
  }
}

onMounted(loadHistory)
</script>

<template>
  <section class="chat">
    <div ref="scroller" class="chat-list">
      <div class="chat-inner">
        <div v-if="!messages.length" class="placeholder">
          <span>{{ placeholder }}</span>
          <span v-if="collectionId">回答下面会列出引用的文档，点开能看原文</span>
        </div>

        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="msg-label">
            {{ m.role === 'user' ? '你' : m.role === 'assistant' ? '回答' : '出错了' }}
          </div>
          <div v-if="m.role === 'assistant'" class="msg-body rich">
            <RichText :blocks="m.blocks" />
          </div>
          <div v-else class="msg-body">{{ m.content }}</div>

          <div v-if="m.sources.length" class="sources">
            <span class="sources-label">引用</span>
            <button
              v-for="(s, j) in m.sources"
              :key="j"
              class="source-chip"
              :title="s.file_name"
              @click="openSource(s)"
            >
              {{ s.file_name }}
            </button>
          </div>
        </div>

        <div v-if="sending" class="msg">
          <div class="msg-label">回答</div>
          <div class="msg-body muted">检索中…</div>
        </div>
      </div>
    </div>

    <div class="composer">
      <div class="composer-inner">
        <div class="composer-box">
          <textarea
            v-model="draft"
            :placeholder="placeholder"
            :disabled="!canSend"
            @input="autosize"
            @keydown="onKeydown"
          ></textarea>
          <div class="composer-bar">
            <span class="composer-tip"></span>
            <button class="btn" @click="clearHistory">清空对话</button>
            <button class="btn btn-primary" :disabled="!canSend || !draft.trim()" @click="send">
              {{ sending ? '发送中' : '发送' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="popup" class="modal-mask" @click.self="popup = null">
      <div class="modal">
        <div class="modal-head">
          <h2>{{ popup.title }}</h2>
          <button class="close-btn" @click="popup = null">×</button>
        </div>
        <div class="modal-body">{{ popup.content }}</div>
      </div>
    </div>
  </section>
</template>
