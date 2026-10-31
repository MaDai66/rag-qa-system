<script setup>
import RichInline from './RichInline.vue'

defineProps({ blocks: { type: Array, default: () => [] } })
</script>

<template>
  <template v-for="(b, i) in blocks" :key="i">
    <h3 v-if="b.type === 'h'" :class="'rt-h rt-h' + b.level">
      <RichInline :parts="b.inline" />
    </h3>

    <ol v-else-if="b.type === 'ol'" class="rt-list" :start="b.start">
      <li v-for="(item, j) in b.items" :key="j"><RichInline :parts="item" /></li>
    </ol>

    <ul v-else-if="b.type === 'ul'" class="rt-list">
      <li v-for="(item, j) in b.items" :key="j"><RichInline :parts="item" /></li>
    </ul>

    <pre v-else-if="b.type === 'code'" class="rt-code">{{ b.text }}</pre>

    <hr v-else-if="b.type === 'hr'" class="rt-hr" />

    <p v-else class="rt-p"><RichInline :parts="b.inline" /></p>
  </template>
</template>
