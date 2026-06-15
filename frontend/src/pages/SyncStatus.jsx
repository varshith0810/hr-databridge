// frontend/src/pages/SyncStatus.jsx
import { useState } from 'react'
import { api } from '../utils/api'
import { useData } from '../utils/useData'
import { Card, Badge, Spinner, ErrorBox, Table } from '../components/ui'

export default function SyncStatus() {
  const { data: logs, loading, error, refetch } = useData(api.syncLogs)
  const [triggering, setTriggering] = useState(false)
  const [triggerMsg, setTriggerMsg] = useState(null)

  async function handleTrigger() {
    setTriggering(true)
    setTriggerMsg(null)
    try {
      const res = await api.triggerSync()
      setTriggerMsg({ ok: true, text: res.message })
      setTimeout(refetch, 3000)
    } catch (e) {
      setTriggerMsg({ ok: false, text: e.message })
    } finally {
      setTriggering(false)
    }
  }

  const rows = (logs?.results || []).map(r => [
    r.synced_at?.slice(0, 19).replace('T', ' '),
    r.source_system,
    <Badge key={r.id} status={r.status} />,
    r.records_pulled,
    r.records_inserted,
    r.records_updated,
    r.conflicts_detected,
    r.duration_seconds?.toFixed(2) + 's',
    r.error_message || '—',
  ])

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Sync Status</h1>
          <p>Audit log of every API pull from Greenhouse and Workday</p>
        </div>
        <div className="header-actions">
          <button
            className="btn btn-primary"
            onClick={handleTrigger}
            disabled={triggering}
          >
            {triggering ? 'Triggering…' : '▶ Trigger Sync'}
          </button>
          <button className="btn btn-ghost" onClick={refetch}>↻ Refresh</button>
        </div>
      </div>

      {triggerMsg && (
        <div className={triggerMsg.ok ? 'alert alert-success' : 'alert alert-error'}>
          {triggerMsg.text}
        </div>
      )}

      {loading && <Spinner />}
      {error   && <ErrorBox message={error} />}

      {!loading && !error && (
        <Card>
          <Table
            columns={['Time (UTC)', 'Source', 'Status', 'Pulled', 'Inserted', 'Updated', 'Conflicts', 'Duration', 'Error']}
            rows={rows}
          />
        </Card>
      )}
    </div>
  )
}
