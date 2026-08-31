import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { projectsApi } from '../api/assets';
import { errorMessage } from '../api/client';
import type { Project } from '../types';
import ApiTestCasesPanel from './ApiTestCasesPanel';
import ReportsPanel from './ReportsPanel';
import RequirementsPanel from './RequirementsPanel';
import TestCasesPanel from './TestCasesPanel';
import TestPointsPanel from './TestPointsPanel';
import TestRunsPanel from './TestRunsPanel';

type Tab = 'requirements' | 'testpoints' | 'testcases' | 'runs' | 'reports' | 'apitestcases';

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('requirements');

  useEffect(() => {
    projectsApi
      .get(projectId)
      .then(setProject)
      .catch((err) => setError(errorMessage(err)));
  }, [projectId]);

  if (error) {
    return (
      <div>
        <div className="crumbs">
          <Link to="/">项目列表</Link>
        </div>
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!project) {
    return <div className="empty">加载中…</div>;
  }

  return (
    <div>
      <div className="crumbs">
        <Link to="/">项目列表</Link> / {project.name}
      </div>

      <div className="card">
        <div className="row">
          <div>
            <h2 style={{ margin: 0 }}>{project.name}</h2>
            <p className="subtitle" style={{ marginTop: 4 }}>
              {project.description || '（无描述）'} · ID {project.id}
            </p>
          </div>
        </div>
      </div>

      <div className="tabs">
        <button
          className={tab === 'requirements' ? 'active' : ''}
          onClick={() => setTab('requirements')}
        >
          需求
        </button>
        <button
          className={tab === 'testpoints' ? 'active' : ''}
          onClick={() => setTab('testpoints')}
        >
          测试点
        </button>
        <button
          className={tab === 'testcases' ? 'active' : ''}
          onClick={() => setTab('testcases')}
        >
          测试用例
        </button>
        <button
          className={tab === 'runs' ? 'active' : ''}
          onClick={() => setTab('runs')}
        >
          执行
        </button>
        <button
          className={tab === 'reports' ? 'active' : ''}
          onClick={() => setTab('reports')}
        >
          报告
        </button>
        <button
          className={tab === 'apitestcases' ? 'active' : ''}
          onClick={() => setTab('apitestcases')}
        >
          接口用例
        </button>
      </div>

      {tab === 'requirements' ? (
        <RequirementsPanel projectId={project.id} />
      ) : tab === 'testpoints' ? (
        <TestPointsPanel projectId={project.id} />
      ) : tab === 'testcases' ? (
        <TestCasesPanel projectId={project.id} />
      ) : tab === 'runs' ? (
        <TestRunsPanel projectId={project.id} onOpenReports={() => setTab('reports')} />
      ) : tab === 'reports' ? (
        <ReportsPanel projectId={project.id} />
      ) : (
        <ApiTestCasesPanel projectId={project.id} />
      )}
    </div>
  );
}
