<script setup lang="ts">
// A commenter's avatar: their picture, or their first letter on a colour that is the same for the
// same username everywhere (pin, panel and thread).
import { computed } from 'vue'
import { Avatar } from 'frappe-ui'
import { avatarTheme } from '../shared/avatarTheme'
import { personOf } from './comments'

const props = defineProps<{ username: string; size?: 'xs' | 'sm' | 'md' | 'lg' }>()

const theme = computed(() => avatarTheme(props.username))
const person = computed(() => personOf(props.username))
</script>

<template>
	<Avatar :image="person.image || undefined" :label="person.name || username" :theme="theme" :size="size ?? 'sm'" />
</template>
