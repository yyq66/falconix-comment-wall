<script setup lang="ts">
defineProps<{ name: string; size?: number }>()
</script>

<template>
  <span class="icon" aria-hidden="true" :style="{ width: `${size || 24}px`, height: `${size || 24}px`, maskImage: `url(/assets/${name}.svg)`, WebkitMaskImage: `url(/assets/${name}.svg)` }" />
</template>

<style scoped>
.icon { display: inline-block; flex-shrink: 0; background: currentColor; mask-size: contain; mask-repeat: no-repeat; mask-position: center; vertical-align: middle; }
</style>
