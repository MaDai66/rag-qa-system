<script setup>
defineProps({ parts: { type: Array, default: () => [] } })
</script>

<template>
  <template v-for="(p, i) in parts" :key="i">
    <strong v-if="p.t === 'strong'">{{ p.v }}</strong>
    <code v-else-if="p.t === 'code'">{{ p.v }}</code>
    <template v-else>{{ p.v }}</template>
  </template>
</template>
