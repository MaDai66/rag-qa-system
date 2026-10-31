// 模型返回的是 Markdown，直接当纯文本渲染会把 ** 和编号原样露出来。
// 这里只解析它真会用的几种：标题、有序/无序列表、代码块、分隔线、加粗、行内代码。
// 产出的是结构化数据，模板用 v-for 渲染，不碰 v-html，所以不存在注入问题。

const INLINE_RE = /(\*\*[^*]+\*\*|`[^`]+`)/g

export function parseInline(text) {
  const parts = []
  let last = 0
  for (const m of String(text).matchAll(INLINE_RE)) {
    if (m.index > last) parts.push({ t: 'text', v: text.slice(last, m.index) })
    const raw = m[0]
    if (raw.startsWith('**')) parts.push({ t: 'strong', v: raw.slice(2, -2) })
    else parts.push({ t: 'code', v: raw.slice(1, -1) })
    last = m.index + raw.length
  }
  if (last < text.length) parts.push({ t: 'text', v: text.slice(last) })
  return parts
}

const RE_H = /^(#{1,6})\s+(.*)$/
const RE_OL = /^\s*(\d+)[.、)]\s+(.*)$/
const RE_UL = /^\s*[-*+]\s+(.*)$/
const RE_FENCE = /^\s*```/

function skipBlank(lines, i) {
  while (i < lines.length && !lines[i].trim()) i++
  return i
}

export function parseBlocks(src) {
  const lines = String(src || '').replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (!line.trim()) {
      i++
      continue
    }

    if (RE_FENCE.test(line)) {
      const buf = []
      i++
      while (i < lines.length && !RE_FENCE.test(lines[i])) buf.push(lines[i++])
      i++
      blocks.push({ type: 'code', text: buf.join('\n') })
      continue
    }

    const h = line.match(RE_H)
    if (h) {
      blocks.push({ type: 'h', level: h[1].length, inline: parseInline(h[2]) })
      i++
      continue
    }

    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      blocks.push({ type: 'hr' })
      i++
      continue
    }

    const ol = line.match(RE_OL)
    if (ol) {
      const items = []
      while (i < lines.length) {
        const m = lines[i].match(RE_OL)
        if (m) {
          items.push(parseInline(m[2]))
          i++
          continue
        }
        // 列表项之间经常夹空行，只要空行后还是列表项就接着算同一条列表
        if (!lines[i].trim()) {
          const j = skipBlank(lines, i)
          if (j < lines.length && RE_OL.test(lines[j])) {
            i = j
            continue
          }
        }
        break
      }
      blocks.push({ type: 'ol', start: Number(ol[1]) || 1, items })
      continue
    }

    const ul = line.match(RE_UL)
    if (ul) {
      const items = []
      while (i < lines.length) {
        const m = lines[i].match(RE_UL)
        if (m) {
          items.push(parseInline(m[1]))
          i++
          continue
        }
        if (!lines[i].trim()) {
          const j = skipBlank(lines, i)
          if (j < lines.length && RE_UL.test(lines[j])) {
            i = j
            continue
          }
        }
        break
      }
      blocks.push({ type: 'ul', items })
      continue
    }

    // 普通段落：把连续的非空、非特殊行拼成一段
    const buf = []
    while (i < lines.length) {
      const l = lines[i]
      if (!l.trim() || RE_H.test(l) || RE_OL.test(l) || RE_UL.test(l) || RE_FENCE.test(l)) break
      buf.push(l)
      i++
    }
    if (buf.length) blocks.push({ type: 'p', inline: parseInline(buf.join('\n')) })
    else i++ // 兜底，别死循环
  }

  return blocks
}
