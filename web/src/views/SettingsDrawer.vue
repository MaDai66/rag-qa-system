<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { notify } from '../toast'

const emit = defineEmits(['close'])

// 这些值在 data_dictionary 表里全是字符串，存回去也必须是字符串
const DEFAULTS = {
  temperature: '0.5',
  search_mode: 'hybrid',
  top_n: '5',
  threshold_vector: '0.6',
  threshold_fulltext: '0',
  rrf_enabled: '0',
  rerank_enabled: '0',
}

const FIELDS = [
  {
    group: '回答',
    key: 'temperature',
    label: '温度',
    hint: '越大越发散，检索问答一般不用调高',
    type: 'number',
    min: 0,
    max: 2,
    step: 0.1,
  },
  {
    group: '检索',
    key: 'search_mode',
    label: '检索方式',
    type: 'select',
    options: [
      ['hybrid', '混合（向量 + 全文）'],
      ['embedding', '只用向量'],
      ['fulltext', '只用全文'],
    ],
  },
  { group: '检索', key: 'top_n', label: '引用条数', hint: '答案下面最多列几条', type: 'number', min: 1, max: 20, step: 1 },
  {
    group: '检索',
    key: 'threshold_vector',
    label: '向量阈值',
    hint: '相似度低于它的直接丢掉，调高更容易答「无法回答」',
    type: 'number',
    min: 0,
    max: 1,
    step: 0.01,
  },
  { group: '检索', key: 'threshold_fulltext', label: '全文得分阈值', type: 'number', min: 0, max: 1, step: 0.01 },
  {
    group: '后处理',
    key: 'rrf_enabled',
    label: '名次融合',
    hint: '混合检索时按名次合并两路结果',
    type: 'switch',
  },
  {
    group: '后处理',
    key: 'rerank_enabled',
    label: '交叉编码器重排',
    hint: '更准，但每次提问慢几秒，第一次还要加载模型',
    type: 'switch',
  },
]

const form = ref({ ...DEFAULTS })
const loading = ref(true)
const saving = ref(false)

const groups = FIELDS.reduce((acc, f) => {
  const g = acc.find((x) => x.name === f.group)
  if (g) g.fields.push(f)
  else acc.push({ name: f.group, fields: [f] })
  return acc
}, [])

onMounted(async () => {
  try {
    const rows = await Promise.all(FIELDS.map((f) => api.getDict(f.key)))
    FIELDS.forEach((f, i) => {
      const v = rows[i]?.value
      if (v !== undefined && v !== null) form.value[f.key] = String(v)
    })
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    loading.value = false
  }
})

const isOn = (k) => form.value[k] === '1'
function toggle(k, on) {
  form.value[k] = on ? '1' : '0'
}

function validate() {
  for (const f of FIELDS) {
    if (f.type !== 'number') continue
    const v = Number(form.value[f.key])
    if (!Number.isFinite(v)) return `「${f.label}」要填数字`
    if (v < f.min || v > f.max) return `「${f.label}」要在 ${f.min} 到 ${f.max} 之间`
  }
  return ''
}

async function save() {
  const bad = validate()
  if (bad) {
    notify(bad, 'error')
    return
  }
  saving.value = true
  try {
    await api.saveDicts(FIELDS.map((f) => ({ key: f.key, value: String(form.value[f.key]) })))
    notify('设置已保存')
    emit('close')
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="drawer-mask" @click.self="emit('close')">
    <div class="drawer">
      <div class="drawer-head">
        <h2>设置</h2>
        <button class="close-btn" @click="emit('close')">×</button>
      </div>

      <div class="drawer-body">
        <p v-if="loading" class="muted">读取中…</p>

        <template v-else>
          <div v-for="g in groups" :key="g.name" class="field-group">
            <h3>{{ g.name }}</h3>

            <div v-for="f in g.fields" :key="f.key" class="field">
              <div class="field-label">
                {{ f.label }}
                <span v-if="f.hint" class="field-hint">{{ f.hint }}</span>
              </div>

              <div class="field-control">
                <select v-if="f.type === 'select'" v-model="form[f.key]">
                  <option v-for="[v, text] in f.options" :key="v" :value="v">{{ text }}</option>
                </select>

                <label v-else-if="f.type === 'switch'" class="switch">
                  <input
                    type="checkbox"
                    :checked="isOn(f.key)"
                    @change="toggle(f.key, $event.target.checked)"
                  />
                  <span>{{ isOn(f.key) ? '开' : '关' }}</span>
                </label>

                <input
                  v-else
                  v-model="form[f.key]"
                  type="number"
                  :min="f.min"
                  :max="f.max"
                  :step="f.step"
                />
              </div>
            </div>
          </div>

          <p class="muted">保存后立即生效，不用重启后端。</p>
        </template>
      </div>

      <div class="drawer-foot">
        <button class="btn" @click="emit('close')">取消</button>
        <button class="btn btn-primary" :disabled="loading || saving" @click="save">
          {{ saving ? '保存中' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>
