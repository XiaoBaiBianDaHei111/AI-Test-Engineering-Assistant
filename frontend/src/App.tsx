import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ProjectsPage from './pages/ProjectsPage';
import ProjectDetailPage from './pages/ProjectDetailPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="app-header">
          <div>
            <h1>AI Test Workflow Automation</h1>
            <p className="subtitle">测试工程师全流程 AI 辅助平台</p>
          </div>
          <span className="phase-badge">Phase 1 · 测试资产管理</span>
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<ProjectsPage />} />
            <Route path="/projects/:id" element={<ProjectDetailPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
