export default function Carte({ titre, action, children }) {
  return (
    <section className="carte">
      {(titre || action) && (
        <header className="carte__entete">
          {titre && <h2>{titre}</h2>}
          {action}
        </header>
      )}
      <div className="carte__corps">{children}</div>
    </section>
  )
}
