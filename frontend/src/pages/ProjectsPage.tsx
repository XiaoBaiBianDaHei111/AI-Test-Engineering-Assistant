import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { projectsApi } from '../api/assets';
import { errorMessage } from '../api/client';
import { formatTime } from '../utils/time';
import type { Project } from '../types';

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      setProjects(await projectsApi.list());
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await projectsApi.create({ name: name.trim(), description: description.trim() });
      setName('');
      setDescription('');
      setError('');
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const remove = async (id: number, projectName: string) => {
    if (!window.confirm(`删除项目「${projectName}」将同时删除其下所有需求与用例，确认？`)) return;
    try {
      await projectsApi.remove(id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div>
      <div className="card">
        <h2>新建项目</h2>
        <form onSubmit={create}>
          <div className="field">
            <label>项目名称（必填，唯一）</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="如：电商平台" />
          </div>
          <div className="field">
            <label>项目描述</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="简要描述被测系统"
            />
          </div>
          <button type="submit" className="primary" disabled={!name.trim()}>
            创建项目
          </button>
        </form>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <h2>项目列表</h2>
        {loading ? (
          <div className="empty">加载中…</div>
        ) : projects.length === 0 ? (
          <div className="empty">暂无项目，请先创建</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>名称</th>
                <th>描述</th>
                <th>创建时间</th>
                <th style={{ width: 160 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>{p.name}</td>
                  <td>{p.description || '—'}</td>
                  <td>{formatTime(p.created_at)}</td>
                  <td>
                    <div className="row">
                      <Link to={`/projects/${p.id}`}>
                        <button className="link">进入</button>
                      </Link>
                      <button className="danger" onClick={() => remove(p.id, p.name)}>
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
