// `dayjs` resolves to the instance frappe-ui already configured, so a
// Prototype and the library share one instance and one set of plugins.
// frappe-ui extends it with relativeTime, localizedFormat, updateLocale,
// isToday, duration, utc, timezone, advancedFormat and customParseFormat.
import { dayjs } from 'frappe-ui'
export default dayjs
export { dayjs }
export { dayjsLocal } from 'frappe-ui'
