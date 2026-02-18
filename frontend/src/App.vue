<template>
  <template v-if="route.path === '/login'">
    <router-view />
  </template>
  <MainLayout v-else>
    <router-view />
  </MainLayout>
</template>

<script setup>
import { useRoute } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const route = useRoute()
</script>

<style>
#app {
  width: 100%;
  min-height: 100vh;
}
</style>
