// frontend/src/components/Sidebar.jsx
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/',              icon: '⬡', label: 'Overview'     },
  { to: '/sync',          icon: '↻',  label: 'Sync Status'  },
  { to: '/headcount',     icon: '👥', label: 'Headcount'    },
  { to: '/attrition',     icon: '📉', label: 'Attrition'    },
  { to: '/diversity',     icon: '🌍', label: 'Diversity'     },
  { to: '/data-quality',  icon: '✅', label: 'Data Quality'  },
]

export default function Sidebar() {
  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-icon">🔗</span>
        <span className="logo-text">HR DataBridge</span>
      </div>
      <ul className="sidebar-links">
        {links.map(({ to, icon, label }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}
            >
              <span className="nav-icon">{icon}</span>
              <span>{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="sidebar-footer">
        <a
          href={`${import.meta.env.VITE_API_BASE || '/api'}/docs`}
          target="_blank"
          rel="noreferrer"
          className="nav-link"
        >
          <span className="nav-icon">📖</span>
          <span>API Docs</span>
        </a>
      </div>
    </nav>
  )
}
