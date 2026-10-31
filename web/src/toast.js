import { reactive } from 'vue'

export const toast = reactive({ text: '', kind: 'info' })

let timer = null

export function notify(text, kind = 'info') {
  toast.text = text
  toast.kind = kind
  clearTimeout(timer)
  timer = setTimeout(() => (toast.text = ''), 4000)
}
