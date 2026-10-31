<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { notify } from '../toast'

const props = defineProps({
  collectionId: { type: String, default: '' },
})

const files = ref([])
const loading = ref(false)
const uploading = ref(false)
const uploadText = ref('')
const dragging = ref(false)
const fileInput = ref(null)
const drawer = ref(null)

const canUpload = computed(() => !!props.collectionId && !uploading.value)

async function load() {
  if (!props.collectionId) {
    files.value = []
    return
  }
  loading.value = true
  try {
    files.value = (await api.listFiles(props.collectionId)) || []
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}

function pick() {
  if (canUpload.value) fileInput.value?.click()
}

async function onPick(e) {
  const list = Array.from(e.target.files || [])
  e.target.value = ''
  await upload(list)
}

async function onDrop(e) {
  dragging.value = false
  if (!canUpload.value) return
  const list = Array.from(e.dataTransfer?.files || [])
  await upload(list)
}

async function upload(list) {
  if (!list.length) return
  uploading.value = true
  let ok = 0
  for (let i = 0; i < list.length; i++) {
    uploadText.value = `正在处理 ${i + 1}/${list.length}：${list[i].name}`
    try {
      await api.uploadFile(list[i], props.collectionId)
      ok++
    } catch (e) {
      notify(`${list[i].name}：${e.message}`, 'error')
    }
  }
  uploading.value = false
  uploadText.value = ''
  if (ok) notify(`已入库 ${ok} 个文件`, 'success')
  await load()
}

async function remove(f) {
  if (!confirm(`删除「${f.file_name}」？它的切分块和向量会一起删掉。`)) return
  try {
    await api.deleteFile(f.uuid)
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}

async function viewChunks(f) {
  try {
    const list = (await api.listChunks(f.uuid)) || []
    drawer.value = {
      title: f.file_name,
      chunks: [...list].sort((a, b) => (a.index ?? 0) - (b.index ?? 0)),
    }
  } catch (e) {
    notify(e.message, 'error')
  }
}

function shortTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 16)
}

onMounted(load)
</script>

<template>
  <section class="docs">
    <div class="docs-inner">
      <div v-if="!collectionId" class="placeholder" style="height: 240px">
        先在左侧选择一个知识库
      </div>

      <template v-else>
        <div class="toolbar">
          <span class="grow">
            {{ loading ? '读取中…' : `共 ${files.length} 个文件` }}
            <template v-if="uploading">· {{ uploadText }}</template>
          </span>
          <button class="btn" :disabled="loading" @click="load">刷新</button>
          <button class="btn btn-primary" :disabled="!canUpload" @click="pick">
            {{ uploading ? '处理中' : '上传文件' }}
          </button>
        </div>

        <div
          class="dropzone"
          :class="{ over: dragging }"
          @click="pick"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="onDrop"
        >
          把文件拖到这里，或点击选择。支持 docx、pdf、txt、csv、xlsx
        </div>

        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".docx,.pdf,.txt,.csv,.xlsx"
          hidden
          @change="onPick"
        />

        <table v-if="files.length" class="files">
          <thead>
            <tr>
              <th>文件名</th>
              <th style="width: 70px">类型</th>
              <th style="width: 150px">入库时间</th>
              <th style="width: 130px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in files" :key="f.uuid">
              <td>{{ f.file_name }}</td>
              <td class="muted">{{ f.file_extension }}</td>
              <td class="muted">{{ shortTime(f.create_time) }}</td>
              <td class="actions">
                <button @click="viewChunks(f)">切分结果</button>
                <button class="danger" @click="remove(f)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-else-if="!loading" class="muted" style="padding: 18px 0">
          这个知识库还没有文件。
        </div>
      </template>
    </div>

    <div v-if="drawer" class="drawer-mask" @click.self="drawer = null">
      <aside class="drawer">
        <div class="drawer-head">
          <h2>{{ drawer.title }}</h2>
          <span class="muted">{{ drawer.chunks.length }} 段</span>
          <button class="close-btn" @click="drawer = null">×</button>
        </div>
        <div class="drawer-body">
          <div v-if="!drawer.chunks.length" class="muted">
            没有切分出内容，检查一下文件是不是空的。
          </div>
          <div v-for="(c, i) in drawer.chunks" :key="c.uuid || i" class="chunk-item">
            <div class="chunk-index">第 {{ (c.index ?? i) }} 段</div>
            <div class="chunk-text">{{ c.context }}</div>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>
