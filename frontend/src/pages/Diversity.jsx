// frontend/src/pages/Diversity.jsx
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { api } from '../utils/api'
import { useData } from '../utils/useData'
import { Card, Spinner, ErrorBox } from '../components/ui'

const GENDER_COLORS = {
  'Male':             '#378ADD',
  'Female':           '#D4537E',
  'Non-binary':       '#534AB7',
  'Prefer not to say':'#888780',
  'Not Disclosed':    '#B4B2A9',
}

export default function Diversity() {
  const { data, loading, error } = useData(api.diversity)

  // Transform flat rows → stacked bar format { dept, Male: %, Female: %, ... }
  const byDept = {}
  const genders = new Set()
  ;(data || []).forEach(r => {
    const [dept, gender] = r.dimension.split('::')
    if (!byDept[dept]) byDept[dept] = { dept }
    byDept[dept][gender] = parseFloat(r.value.toFixed(1))
    genders.add(gender)
  })
  const chartData = Object.values(byDept)

  return (
    <div className="page">
      <div className="page-header">
        <h1>Gender Diversity</h1>
        <p>Gender distribution as % of each department's active headcount</p>
      </div>

      {loading && <Spinner />}
      {error   && <ErrorBox message={error} />}

      {!loading && !error && (
        <Card>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={chartData} margin={{ left: 8, right: 24, top: 16, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="dept"
                tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
                angle={-30}
                textAnchor="end"
                interval={0}
              />
              <YAxis
                tickFormatter={v => `${v}%`}
                tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
                domain={[0, 100]}
              />
              <Tooltip
                contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
                formatter={v => [`${v}%`]}
              />
              <Legend wrapperStyle={{ fontSize: 13 }} />
              {[...genders].map(g => (
                <Bar
                  key={g}
                  dataKey={g}
                  stackId="a"
                  fill={GENDER_COLORS[g] || '#B4B2A9'}
                  radius={genders.size === 1 ? [4, 4, 4, 4] : [0, 0, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}
