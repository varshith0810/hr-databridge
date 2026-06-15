// frontend/src/pages/Overview.jsx
import { api } from '../utils/api'
import { useData } from '../utils/useData'
import { StatCard, Card, Badge, Spinner, ErrorBox } from '../components/ui'

export default function Overview() {
  const { data: health,    loading: hl } = useData(api.health)
  const { data: syncData,  loading: sl } = useData(api.syncStatus)
  const { data: headcount, loading: hcl } = useData(api.headcount)

  const totalHeadcount = headcount?.reduce((s, r) => s + r.value, 0) ?? '—'
  const lastSync = syncData?.[0]?.last_synced_at?.slice(0, 19).replace('T', ' ') ?? '—'
  const dbStatus = health?.database?.status ?? '—'

  return (
    <div className="page">
      <div className="page-header">
        <h1>Overview</h1>
        <p>Live workforce data from Greenhouse ATS + Workday HRIS</p>
      </div>

      {/* Top stats */}
      <div className="stat-grid">
        <StatCard
          label="Total headcount"
          value={hcl ? '…' : totalHeadcount}
          unit=" employees"
          sub="Active only"
        />
        <StatCard
          label="Active sources"
          value="2"
          unit=" systems"
          sub="Greenhouse · Workday"
        />
        <StatCard
          label="Last sync"
          value={sl ? '…' : lastSync}
          sub="UTC"
        />
        <StatCard
          label="Database"
          value={hl ? '…' : dbStatus}
          sub="PostgreSQL"
        />
      </div>

      {/* Sync status cards */}
      <h2 className="section-title">Sync status</h2>
      {sl ? <Spinner /> : (
        <div className="sync-grid">
          {(syncData || []).map(s => (
            <Card key={s.source_system} className="sync-card">
              <div className="sync-card-header">
                <span className="sync-source">{s.source_system}</span>
                <Badge status={s.status} />
              </div>
              <div className="sync-meta">
                <span>↓ {s.records_pulled} pulled</span>
                <span>+ {s.records_inserted} inserted</span>
                <span>✏ {s.records_updated} updated</span>
                <span>⚠ {s.conflicts_detected} conflicts</span>
                <span>⏱ {s.duration_seconds?.toFixed(1)}s</span>
              </div>
              <div className="sync-time">
                {s.last_synced_at?.slice(0, 19).replace('T', ' ')} UTC
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
