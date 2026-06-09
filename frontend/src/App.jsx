// frontend/src/App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Overview    from './pages/Overview'
import SyncStatus  from './pages/SyncStatus'
import Headcount   from './pages/Headcount'
import Attrition   from './pages/Attrition'
import Diversity   from './pages/Diversity'
import DataQuality from './pages/DataQuality'

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/"             element={<Overview />}    />
            <Route path="/sync"         element={<SyncStatus />}  />
            <Route path="/headcount"    element={<Headcount />}   />
            <Route path="/attrition"    element={<Attrition />}   />
            <Route path="/diversity"    element={<Diversity />}   />
            <Route path="/data-quality" element={<DataQuality />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
