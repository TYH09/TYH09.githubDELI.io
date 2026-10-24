export default function Alerte({ type = 'info', children }) {
  if (!children) return null
  return <div className={`alerte alerte--${type}`}>{children}</div>
}
