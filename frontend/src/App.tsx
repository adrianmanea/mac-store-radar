import { Navigate, Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { ChartPage } from './pages/ChartPage'
import { DiscoveryPage } from './pages/DiscoveryPage'
import { WatchlistPage } from './pages/WatchlistPage'

export default function App() {
  return (
    <div className="flex min-h-screen bg-zinc-950 text-zinc-100">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-5xl px-8 py-10">
          <Routes>
            <Route path="/" element={<Navigate to="/discovery" replace />} />
            <Route path="/discovery" element={<DiscoveryPage />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
            <Route path="/chart" element={<ChartPage />} />
            <Route path="*" element={<Navigate to="/discovery" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
