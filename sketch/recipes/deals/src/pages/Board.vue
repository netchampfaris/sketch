<script setup lang="ts">
import { reactive, onBeforeUnmount, useTemplateRef } from 'vue'
import { Button, ScrollArea } from 'frappe-ui'
import DealCard from '../components/DealCard.vue'
import DealsHeader from '../components/DealsHeader.vue'
import { columns, logo, owners, statusDot } from '../data'

/* -- Drag and drop (pointer events) ---------------------------------------
   A mouse lifts a card after 4px of movement. A touch lifts after it holds
   still for 250ms. A touch that drifts earlier stays a native scroll.

   The dragged deal never leaves the data model. Once lifted it shows as an
   empty slot in place, while a ghost follows the pointer. Dragging reorders
   the deal into the slot under the pointer, so the same element glides (FLIP)
   instead of a placeholder that fades in and out. A drop only stops the drag.
   The deal is already where it belongs, so a release in the same spot
   animates nothing. */

const LIFT_DELAY = 250 // ms a touch must hold still before it becomes a drag
const DRIFT_TOLERANCE = 8 // px a held touch may drift before it counts as a scroll
const MOUSE_THRESHOLD = 4 // px a mouse must move before the drag starts
const EDGE = 48 // px-wide edge zones that start auto-scroll
const SETTLE_MS = 150 // ms the ghost glides onto the slot on release

const boardRef = useTemplateRef<HTMLElement>('boardRef')
const columnRefs: any[] = [] // per-column ScrollArea instances, indexed by column
const boardEl = () => boardRef.value
const columnEl = (col: number) => columnRefs[col]?.viewportElement

const pointer = { x: 0, y: 0 }
let pending: any = null // pointerdown that may still become a drag
let rafId = 0
let settleTimer = 0 // the release settle animation timer

const drag = reactive({
  active: false,
  settling: false, // release animation: the ghost glides onto its slot
  deal: null as any, // the deal in the drag. It stays inside `columns`.
  from: null as any, // { col, index }. The restore point if the drag stops.
  overCol: 0, // column under the pointer, drives vertical auto-scroll
  width: 0,
  height: 0,
  offsetX: 0,
  offsetY: 0,
  x: 0,
  y: 0,
})

// Where the dragged deal sits in the data model now.
function locate() {
  for (let col = 0; col < columns.value.length; col++) {
    const index = columns.value[col].deals.indexOf(drag.deal)
    if (index !== -1) return { col, index }
  }
  return null
}

function onCardPointerDown(event: any, col: number, deal: any) {
  if (drag.active || pending) return
  if (event.pointerType === 'mouse' && event.button !== 0) return
  // A grab on a control inside the card (dropdown, owner hover card) is a
  // click, not a drag.
  if (event.target.closest('button')) return
  pointer.x = event.clientX
  pointer.y = event.clientY
  const mouse = event.pointerType === 'mouse'
  pending = {
    col,
    deal,
    el: event.currentTarget,
    startX: event.clientX,
    startY: event.clientY,
    mouse,
    timer: mouse ? 0 : window.setTimeout(lift, LIFT_DELAY),
  }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerCancel)
}

function lift() {
  const { col, deal, el, timer } = pending
  clearTimeout(timer)
  pending = null
  const rect = el.getBoundingClientRect()
  drag.deal = deal
  drag.from = { col, index: columns.value[col].deals.indexOf(deal) }
  drag.overCol = col
  drag.width = rect.width
  drag.height = rect.height
  drag.offsetX = pointer.x - rect.left
  drag.offsetY = pointer.y - rect.top
  drag.x = rect.left
  drag.y = rect.top
  drag.active = true
  // The gesture belongs to this code now. A passive:false touchmove listener
  // is the only way to stop the browser from starting a scroll, which would
  // fire pointercancel and kill the drag.
  window.addEventListener('touchmove', preventScroll, { passive: false })
  navigator.vibrate?.(10)
  rafId = requestAnimationFrame(tick)
}

function onPointerMove(event: any) {
  pointer.x = event.clientX
  pointer.y = event.clientY
  if (!pending) return
  const drift = Math.hypot(
    event.clientX - pending.startX,
    event.clientY - pending.startY,
  )
  if (pending.mouse) {
    if (drift > MOUSE_THRESHOLD) lift()
  } else if (drift > DRIFT_TOLERANCE) {
    cancelPending() // the finger scrolls, it does not hold
  }
}

// Runs every frame while the drag is active. pointermove alone is not enough,
// because a pointer held still at an edge keeps the auto-scroll going, which
// moves the containers and the slots under it.
function tick() {
  drag.x = pointer.x - drag.offsetX
  drag.y = pointer.y - drag.offsetY
  autoscroll()
  updateDropSlot()
  rafId = requestAnimationFrame(tick)
}

// Move the dragged deal into the slot under the pointer. The insertion index
// counts the other cards only, because the dragged slot is skipped. That makes
// it a no-op when nothing changed, and stable otherwise: an insert pushes the
// boundary card away from the pointer, so the choice never oscillates between
// two neighbours.
function updateDropSlot() {
  for (let col = 0; col < columns.value.length; col++) {
    const el = columnEl(col)
    if (!el) continue
    const rect = el.getBoundingClientRect()
    if (pointer.x < rect.left || pointer.x > rect.right) continue
    drag.overCol = col
    let index = 0
    for (const card of el.querySelectorAll(
      '[data-deal-card]:not([data-dragging])',
    )) {
      const r = card.getBoundingClientRect()
      if (pointer.y > r.top + r.height / 2) index++
    }
    moveDealTo(col, index)
    return
  }
  // The pointer is in a gap between columns. Leave the deal where it is.
}

function moveDealTo(col: number, index: number) {
  const cur = locate()
  if (!cur || (cur.col === col && cur.index === index)) return
  columns.value[cur.col].deals.splice(cur.index, 1)
  columns.value[col].deals.splice(index, 0, drag.deal)
}

function autoscroll() {
  const scrollSpeed = (overshoot: number) =>
    Math.ceil((Math.min(overshoot, EDGE) / EDGE) * 14)
  const b = boardEl()
  if (b) {
    const r = b.getBoundingClientRect()
    if (pointer.x < r.left + EDGE)
      b.scrollLeft -= scrollSpeed(r.left + EDGE - pointer.x)
    else if (pointer.x > r.right - EDGE)
      b.scrollLeft += scrollSpeed(pointer.x - (r.right - EDGE))
  }
  const colEl = columnEl(drag.overCol)
  if (colEl) {
    const r = colEl.getBoundingClientRect()
    if (pointer.y < r.top + EDGE)
      colEl.scrollTop -= scrollSpeed(r.top + EDGE - pointer.y)
    else if (pointer.y > r.bottom - EDGE)
      colEl.scrollTop += scrollSpeed(pointer.y - (r.bottom - EDGE))
  }
}

// Land the ghost on the slot, then show the real card. The slot is the same
// element that held the deal's place all along, so it just swaps dashed for
// card. There is no enter animation and nothing else moves.
function onPointerUp() {
  if (pending) return cancelPending()
  if (!drag.active || drag.settling) return
  cancelAnimationFrame(rafId)
  removeGestureListeners()
  const slot = document.querySelector('[data-dragging]')
  if (!slot) return endDrag()
  const rect = slot.getBoundingClientRect()
  drag.settling = true
  drag.x = rect.left
  drag.y = rect.top
  settleTimer = window.setTimeout(endDrag, SETTLE_MS)
}

function onPointerCancel() {
  if (pending) return cancelPending()
  if (!drag.active) return
  const cur = locate()
  if (cur && (cur.col !== drag.from.col || cur.index !== drag.from.index)) {
    columns.value[cur.col].deals.splice(cur.index, 1)
    columns.value[drag.from.col].deals.splice(drag.from.index, 0, drag.deal)
  }
  endDrag()
}

function cancelPending() {
  clearTimeout(pending?.timer)
  pending = null
  removeGestureListeners()
}

function endDrag() {
  cancelAnimationFrame(rafId)
  clearTimeout(settleTimer)
  removeGestureListeners()
  drag.active = false
  drag.settling = false
  drag.deal = null
  drag.from = null
}

function removeGestureListeners() {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerCancel)
  window.removeEventListener('touchmove', preventScroll)
}

function preventScroll(event: Event) {
  event.preventDefault()
}

// The board is a route now, so the teardown also runs on a route change.
onBeforeUnmount(() => {
  clearTimeout(pending?.timer)
  clearTimeout(settleTimer)
  cancelAnimationFrame(rafId)
  removeGestureListeners()
})
</script>

<template>
  <DealsHeader />

  <!-- App.vue passes `:scroll="false"` to DesktopShell, so the content area
       fills the height below the header and never page-scrolls. The board owns
       horizontal overflow and each column owns vertical overflow. -->
  <div ref="boardRef" class="min-h-0 flex-1 overflow-x-auto overflow-y-hidden">
    <div class="flex h-full select-none gap-3 p-4">
      <div
        v-for="(column, ci) in columns"
        :key="column.status"
        class="flex min-h-0 w-72 shrink-0 flex-col rounded-6 bg-surface-gray-1 dark:bg-transparent dark:border"
      >
        <div class="flex items-center justify-between pl-3 pr-1 pt-1">
          <div class="flex items-center gap-2">
            <span
              class="size-2 rounded-full"
              :class="statusDot[column.theme]"
              aria-hidden="true"
            />
            <span class="text-sm font-medium text-ink-gray-8">
              {{ column.status }}
            </span>
            <span class="text-sm text-ink-gray-5">
              {{ column.deals.length }}
            </span>
          </div>
          <Button variant="ghost" icon="lucide-plus" label="Add deal" />
        </div>

        <!-- The card list carries its own padding, not the column, so a card
             shadow is not clipped by the edge of the viewport. -->
        <ScrollArea :ref="(r) => (columnRefs[ci] = r)" class="min-h-0 flex-1">
          <TransitionGroup
            name="deals"
            tag="div"
            class="flex flex-col gap-2 p-2"
          >
            <div
              v-for="deal in column.deals"
              :key="deal.org"
              class="shrink-0"
              data-deal-card
              :data-dragging="deal === drag.deal ? '' : null"
              @pointerdown="onCardPointerDown($event, ci, deal)"
              @dragstart.prevent
              @contextmenu="drag.active && $event.preventDefault()"
            >
              <!-- The dragged card leaves an empty slot in place. The ghost
                   carries its content while it is lifted. -->
              <div
                v-if="deal === drag.deal"
                class="rounded-6 border-2 border-dashed border-outline-gray-2 bg-surface-gray-2"
                :style="{ height: drag.height + 'px' }"
              />
              <div
                v-else
                class="group cursor-grab rounded-6 border bg-surface-elevation-1 p-3 transition hover:shadow-sm"
              >
                <DealCard :deal="deal" :owners="owners" :logo="logo" />
              </div>
            </div>
          </TransitionGroup>

          <!-- An empty column still reads as a drop target. -->
          <div
            v-if="!column.deals.length"
            class="mx-2 mb-2 rounded-6 border border-dashed border-outline-gray-2 px-3 py-6 text-center text-sm text-ink-gray-5"
          >
            No deals here
          </div>
        </ScrollArea>
      </div>
    </div>
  </div>

  <!-- The lifted card: a fixed-position ghost that tracks the pointer. It
       ignores pointer events, so hit tests see the board below it. -->
  <Teleport to="body">
    <div
      v-if="drag.active"
      class="pointer-events-none fixed left-0 top-0 z-50 will-change-transform"
      :class="drag.settling ? 'transition-transform duration-150 ease-out' : ''"
      :style="{
        width: drag.width + 'px',
        transform: `translate(${drag.x}px, ${drag.y}px)`,
      }"
    >
      <div
        class="drag-ghost rounded-6 border bg-surface-elevation-1 p-3 transition-[transform,box-shadow] duration-150 ease-out"
        :class="drag.settling ? '' : 'rotate-2 scale-[1.02] shadow-xl'"
      >
        <DealCard :deal="drag.deal" :owners="owners" :logo="logo" ghost />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* The only motion in the list is FLIP: as the dragged deal is reordered, the
   slot and the cards around it slide to their new positions. The lifted ghost
   pops up on grab. There is no enter or leave, because the dragged card never
   leaves the list. */
.deals-move {
  transition: transform 0.2s ease;
}
.drag-ghost {
  animation: drag-lift 0.15s ease-out;
}
@keyframes drag-lift {
  from {
    transform: none;
    box-shadow: none;
  }
}
</style>
