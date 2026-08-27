function mm() { return [] }
mm.isMatch = () => false
mm.scan = (p) => ({ isGlob: false, base: p, glob: '' })
export default mm
