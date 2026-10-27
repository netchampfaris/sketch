<script setup lang="ts">
// A commenter's avatar: their picture, or their first letter on a colour that is the same for the
// same username everywhere (pin, panel and thread).
import { computed } from 'vue'
import { Avatar } from 'frappe-ui'
import { personOf } from './comments'

const props = defineProps<{ username: string; size?: 'xs' | 'sm' | 'md' | 'lg' }>()

const THEMES = ['blue', 'green', 'amber', 'violet', 'red'] as const
const theme = computed(() => THEMES[[...props.username].reduce((n, c) => n + c.charCodeAt(0), 0) % THEMES.length])
const person = computed(() => personOf(props.username))
</script>

<template>
	<Avatar :image="person.image || undefined" :label="person.name || username" :theme="theme" :size="size ?? 'sm'" />
</template>
