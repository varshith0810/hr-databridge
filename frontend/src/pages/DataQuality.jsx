// frontend/src/pages/DataQuality.jsx
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ResponsiveContainer
} from 'recharts'
import { api } from '../utils/api'
import { useData } from '../utils/useData'
import { Card, Spinner, ErrorBox } from '../components/ui'

export default function DataQuality() {
  const { data, loading, error } = useData(api.dataQuality)

  // Transform → { field, greenhouse: %, workday: % }
  const byField = {}
  ;(data || []).forEach(r => {
    const field = r.kpi_name.replace('data_quality_', '')
    if (!byField[field]) byField[field] = { field }
    byField[field][r.dimension] = parseFloat(r.value.toFixed(1))
  })
  const chartData = Object.values(byField)

  return (
    <div className="page">
      <div className="page-header">
        <h1>Data Quality</h1>
        <p>Field completeness % per source system — target is 90%+</p>
      </div>

      {loading && <Spinner />}
      {error   && <ErrorBox message={error} />}

      {!loading && !error && (
        <Card>
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={chartData} margin={{ left: 8, right: 24, top: 16, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis dataKey="field" tick={{ fontSize: 13, fill: 'var(--text-primary)' }} />
              <YAxis
                domain={[0, 100]}
                tickFormatter={v => `${v}%`}
                tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
              />
              <Tooltip
                contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
                formatter={v => [`${v}%`]}
              />
              <Legend wrapperStyle={{ fontSize: 13 }} />
              <ReferenceLine
                y={90}
                stroke="#E24B4A"
                strokeDasharray="4 3"
                label={{ value: '90% target', fill: '#E24B4A', fontSize: 12, position: 'right' }}
              />
              <Bar dataKey="greenhouse" name="Greenhouse" fill="#1D9E75" radius={[4, 4, 0, 0]} />
              <Bar dataKey="workday"    name="Workday"    fill="#534AB7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}
