<script setup lang="ts">
import { Button, Dropdown, PageHeader, PageHeaderTitle } from 'frappe-ui'
import DiscussionList from '../components/DiscussionList.vue'
import { discussions, spaceActions } from '../data'
</script>

<template>
  <!-- Declared by the page. It teleports into the shell's pinned header target. -->
  <PageHeader>
    <div class="flex items-center gap-1">
      <PageHeaderTitle>Home</PageHeaderTitle>
      <Dropdown :options="spaceActions">
        <Button variant="ghost" icon="lucide-ellipsis" label="Feed actions" />
      </Dropdown>
    </div>
    <Button label="Add new" icon-left="lucide-plus" />
  </PageHeader>

  <!-- Body container: max-w-[940px] px-3 sm:px-5 mx-auto -->
  <div class="mx-auto mt-5 w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <DiscussionList :items="discussions" />
  </div>
</template>
