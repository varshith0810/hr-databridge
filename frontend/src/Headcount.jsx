// frontend/src/pages/Headcount.jsx
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import { api } from '../utils/api'
import { useData } from '../utils/useData'
import { Card, Spinner, ErrorBox } from '../components/ui'

const COLORS = ['#1D9E75','#534AB7','#D85A30','#378ADD','#BA7517','#639922','#D4537E','#E24B4A','#888780']

export default function Headcount() {
  const { data, loading, error } = useData(api.headcount)

  const chartData = (data || [])
    .sort((a, b) => b.value - a.value)
    .map(r => ({ name: r.dimension, value: Math.round(r.value) }))

  const total = chartData.reduce((s, r) => s + r.value, 0)

  return (
    <div className="page">
      <div className="page-header">
        <h1>Headcount</h1>
        <p>Active employees by department — {total} total</p>
      </div>

      {loading && <Spinner />}
      {error   && <ErrorBox message={error} />}

      {!loading && !error && (
        <Card>
          <ResponsiveContainer width="100%" height={380}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 24, right: 32, top: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
              <XAxis type="number" tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} />
              <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 13, fill: 'var(--text-primary)' }} />
              <Tooltip
                cursor={{ fill: 'var(--hover)' }}
                contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
                formatter={v => [v, 'employees']}
              />
              <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}
