/**
 * One poller for the whole app.
 *
 * Two screens watch server state that only the agent changes: the gallery
 * waits for the first Prototype (`PrototypesScreen.vue`) and Settings waits
 * for the first /mcp request (`SettingsScreen.vue`). They had two different
 * loops with two different intervals, two backoff rules (one of them none)
 * and two visibility APIs. This is the one loop.
 *
 * What it guarantees, in order of what went wrong before:
 *
 * 1. Requests never stack. The delay is measured from the end of a read, not
 *    from the start, so a slow endpoint stretches the loop instead of piling
 *    reads on top of each other. `setInterval` cannot do this.
 * 2. A hidden tab costs nothing, and a tab that comes back reads at once.
 * 3. A failed read doubles the wait up to `maxInterval`, so a dead endpoint
 *    costs one request a minute instead of one every few seconds forever.
 * 4. The loop retires itself when `done()` turns true, which is how a screen
 *    stops watching something that cannot change again. `restart()` arms it
 *    again, for the screen that finds out the state came back.
 * 5. Unmount clears the timer and removes the listener.
 */
import { onMounted, onUnmounted } from 'vue'

/** The gallery's interval, and the default for everything else. */
const DEFAULT_INTERVAL = 4000
/** The ceiling the backoff climbs to. */
const DEFAULT_MAX_INTERVAL = 60000

export interface PollOptions {
  /** Milliseconds between the end of one read and the start of the next. */
  interval?: number
  /** The longest the backoff may grow to after repeated failures. */
  maxInterval?: number
  /**
   * True when there is nothing left to watch. Checked before every read, so
   * a read that answers the question also ends the loop.
   */
  done?: () => boolean
}

export interface Poll {
  /** End the loop early. Idempotent, and unmount calls it anyway. */
  stop: () => void
  /**
   * Arm a retired loop again. Idempotent, and dead after unmount.
   *
   * `done()` is read inside the loop and nowhere else, so a loop that has
   * retired has nothing left running to notice that the watched state came
   * back. Settings hits exactly that: the token screen retires on the first
   * agent request, and regenerating the token clears that stamp again
   * (`sketch_token.regenerate`). The screen owns that knowledge, so the screen
   * is what says so.
   */
  restart: () => void
}

/**
 * Read the watched state on a loop.
 *
 * `read` resolves `false` to report a failed read, which is what starts the
 * backoff. Anything else counts as good and resets the wait. It is a return
 * value rather than a throw because `useCall.reload()` is `useFetch.execute`
 * called without `throwOnFailed`, so it resolves on a failed request and the
 * handle's `error` ref is the only signal (frappe-ui
 * data-fetching/useCall/useCall.ts, `reload: execute`).
 *
 * `read` is handed an `alive()` it can check after its own awaits. A request
 * that was already out when the screen left still resolves, and a reader that
 * writes a shared store must not commit that answer to a store the next
 * screen reads.
 *
 * There is no read on mount. Both screens already load their own data in
 * `onMounted`, and a second read in the same tick would be the stacked
 * request this composable exists to prevent.
 *
 * Call it from `setup`: it registers `onMounted` and `onUnmounted`.
 */
export function usePoll(
  read: (alive: () => boolean) => Promise<boolean | void>,
  options: PollOptions = {},
): Poll {
  const interval = options.interval ?? DEFAULT_INTERVAL
  const maxInterval = options.maxInterval ?? DEFAULT_MAX_INTERVAL
  const done = options.done ?? (() => false)

  let timer: number | undefined
  let wait = interval
  /**
   * False outside the mounted window.
   *
   * Clearing the timer does not cancel a request already in flight, and that
   * request's own `schedule()` would start the loop again with nothing left
   * to stop it. This flag is the only thing that ends that last lap.
   */
  let live = false
  /**
   * True between mount and unmount.
   *
   * `live` is false both after `done()` retired the loop and after the screen
   * went. Only this flag tells the two apart, and `restart` needs the
   * difference: it must revive a retired loop and must not revive a dead one.
   */
  let mounted = false
  /** True while a read is out. The guard that stops requests stacking. */
  let running = false

  function clear(): void {
    if (timer !== undefined) window.clearTimeout(timer)
    timer = undefined
  }

  function stop(): void {
    live = false
    clear()
    document.removeEventListener('visibilitychange', onVisibility)
  }

  function restart(): void {
    if (!mounted || live) return
    live = true
    // The backoff a dead endpoint built up before the retirement is stale.
    wait = interval
    document.addEventListener('visibilitychange', onVisibility)
    // One interval, not zero. The caller has just read the state that made it
    // restart, and a read in the same tick is the stacked request guarantee 1
    // exists to prevent.
    schedule()
  }

  function schedule(delay = wait): void {
    // Clear first, so two callers can never leave two timers running.
    clear()
    if (!live || running || document.hidden) return
    // Retire, and take the listener with it: a screen that has nothing left
    // to watch must not wake up when the tab does.
    if (done()) {
      stop()
      return
    }
    timer = window.setTimeout(tick, delay)
  }

  async function tick(): Promise<void> {
    timer = undefined
    if (!live || running || document.hidden) return
    running = true
    let ok: boolean | void
    try {
      ok = await read(() => live)
    } catch {
      ok = false
    } finally {
      running = false
    }
    // The screen may have gone while the request was out.
    if (!live) return
    wait = ok === false ? Math.min(wait * 2, maxInterval) : interval
    schedule()
  }

  function onVisibility(): void {
    if (document.hidden) {
      clear()
      return
    }
    // A tab that was away may have missed several writes, so drop whatever
    // backoff the failures built up and read once, now. The zero delay still
    // goes through `tick`, so it obeys the `running` guard.
    wait = interval
    schedule(0)
  }

  onMounted(() => {
    mounted = true
    live = true
    document.addEventListener('visibilitychange', onVisibility)
    schedule()
  })

  onUnmounted(() => {
    mounted = false
    stop()
  })

  return { stop, restart }
}
