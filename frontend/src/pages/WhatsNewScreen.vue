<script setup lang="ts">
/**
 * /whats-new: every entry, newest first, a release under its date (decision 72).
 *
 * The reading measure, not the gallery's column: it is a page of prose and clips. Each clip loops silently while it is
 * on screen.
 */
import { computed } from 'vue'
import WhatsNewClip from '../components/WhatsNewClip.vue'
import { releaseDate, whatsNew } from '../whatsnew'

const releases = computed(() => {
  const dates = [...new Set(whatsNew.map((entry) => entry.date))]
  return dates.map((date) => ({ date, entries: whatsNew.filter((entry) => entry.date === date) }))
})
</script>

<template>
  <div class="max-w-[640px] px-3 pb-12 pt-6 sm:px-5">
    <h1 class="text-2xl-semibold text-ink-gray-8">What's new</h1>

    <section v-for="release in releases" :key="release.date" class="mt-8">
      <h2 class="text-sm text-ink-gray-5">{{ releaseDate(release.date) }}</h2>
      <article v-for="entry in release.entries" :key="entry.id" class="mt-6">
        <h3 class="text-lg-semibold text-ink-gray-8">{{ entry.title }}</h3>
        <p class="mt-1 text-p-base text-ink-gray-6">{{ entry.line }}</p>
        <WhatsNewClip class="mt-3" :entry="entry" play="visible" />
      </article>
    </section>
  </div>
</template>
