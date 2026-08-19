import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

function App() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-xl p-8 rounded-2xl bg-white shadow-sm border border-slate-200">
        <h1 className="text-2xl font-semibold text-brand-700">CareerFit</h1>
        <p className="mt-3 text-slate-600">
          Phase 1 skeleton. 실제 UI 는 Phase 9 이후에 채워집니다.
        </p>
        <p className="mt-2 text-xs text-slate-400">
          SPEC · PLAN · Design Review 는 <code>docs/</code> 아래.
        </p>
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
