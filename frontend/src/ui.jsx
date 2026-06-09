// frontend/src/components/ui.jsx
// Reusable primitive components used across all pages

export function Card({ children, className = '' }) {
  return (
    <div className={`card ${className}`}>{children}</div>
  )
}

export function Badge({ status }) {
  const map = {
    success: 'badge badge-success',
    partial:  'badge badge-warning',
    failed:   'badge badge-error',
    ok:       'badge badge-success',
    error:    'badge badge-error',
  }
  return <span className={map[status] || 'badge'}>{status}</span>
}

export function Spinner() {
  return <div className="spinner" aria-label="Loading" />
}

export function ErrorBox({ message }) {
  return (
    <div className="error-box">
      <span>⚠ {message}</span>
    </div>
  )
}

export function SectionHeader({ title, subtitle }) {
  return (
    <div className="section-header">
      <h2>{title}</h2>
      {subtitle && <p>{subtitle}</p>}
    </div>
  )
}

export function StatCard({ label, value, unit, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}<span className="stat-unit">{unit}</span></div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

export function Table({ columns, rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map(c => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => <td key={j}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
