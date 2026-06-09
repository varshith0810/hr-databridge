// frontend/src/pages/Attrition.jsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer
} from 'recharts'
import { api } from '../utils/api'
import { useData } from '../utils/useData'
import { Card, Spinner, ErrorBox } from '../components/ui'

export default function Attrition() {
  const { data, loading, error } = useData(api.attrition)

  const chartData = (data || [])
    .sort((a, b) => a.dimension.localeCompare(b.dimension))
    .map(r => ({ month: r.dimension, rate: parseFloat(r.value.toFixed(2)) }))

  const avg = chartData.length
    ? (chartData.reduce((s, r) => s + r.rate, 0) / chartData.length).toFixed(2)
    : 0

  return (
    <div className="page">
      <div className="page-header">
        <h1>Attrition Rate</h1>
        <p>Monthly employee attrition over the last 12 months · avg {avg}%</p>
      </div>

      {loading && <Spinner />}
      {error   && <ErrorBox message={error} />}

      {!loading && !error && (
        <Card>
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={chartData} margin={{ left: 8, right: 24, top: 16, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} />
              <YAxis
                tickFormatter={v => `${v}%`}
                tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
              />
              <Tooltip
                contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
                formatter={v => [`${v}%`, 'Attrition rate']}
              />
              <ReferenceLine
                y={parseFloat(avg)}
                stroke="#888780"
                strokeDasharray="4 3"
                label={{ value: `Avg ${avg}%`, fill: 'var(--text-secondary)', fontSize: 12 }}
              />
              <Line
                type="monotone"
                dataKey="rate"
                stroke="#D85A30"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#D85A30' }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}
