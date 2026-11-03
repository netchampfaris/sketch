// The Viewer shell's entry (frontend/viewer.html). The UI lives in runtime/shell, beside the frame side
// it talks to (runtime/agent), and it is drawn with the SPA's own frappe-ui and tokens.
import { createApp } from 'vue'
import { FrappeUI } from 'frappe-ui'
import Shell from '../../../runtime/shell/Shell.vue'
import { readBoot } from '../../../runtime/shell/boot'
import '../style.css'

const app = createApp(Shell, { boot: readBoot() })
app.use(FrappeUI)
app.mount('#shell')
