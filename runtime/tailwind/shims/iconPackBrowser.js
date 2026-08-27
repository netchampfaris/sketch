import plugin from 'tailwindcss/plugin'
import icons from '../lucide-map.json'
export default plugin(({ matchComponents }) => {
  const values = Object.fromEntries(Object.keys(icons).map((n) => [n, n]))
  matchComponents({
    lucide: (value) => {
      const uri = icons[value]
      if (!uri) return {}
      return { display: 'block', width: '1em', height: '1em', 'background-color': 'currentColor', '-webkit-mask-image': `url("${uri}")`, 'mask-image': `url("${uri}")`, '-webkit-mask-repeat': 'no-repeat', 'mask-repeat': 'no-repeat', '-webkit-mask-position': 'center', 'mask-position': 'center', '-webkit-mask-size': 'contain', 'mask-size': 'contain', 'flex-shrink': '0' }
    },
  }, { values, type: 'any' })
})
