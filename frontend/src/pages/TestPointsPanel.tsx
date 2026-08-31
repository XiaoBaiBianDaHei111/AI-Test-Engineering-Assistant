import { useCallback, useEffect, useState } from 'react';
import { requirementsApi, testCaseReviewsApi, testPointsApi } from '../api/assets';
import { aiApi } from '../api/ai';
import { errorMessage } from '../api/client';
import type { Requirement, TestPoint, TestPointTechnique, UncoveredTestPoint } from '../types';

const TECHNIQUES: TestPointTechnique[] = [
  'equivalence',
  'boundary',
  'state_transition',
  'exception',
  'error_guessing',
];

const emptyForm = { title: '', technique: 'equivalence' as TestPointTechnique, description: '' };

export default function TestPointsPanel({ projectId }: { projectId: number }) {
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [testPoints, setTestPoints] = useState<Record<number, TestPoint[]>>({});
  const [error, setError] = useState('');
  const [extractingId, setExtractingId] = useState<number | null>(null);
  const [warnings, setWarnings] = useState<Record<number, string[]>>({});
  const [creatingReqId, setCreatingReqId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [uncovered, setUncovered] = useState<UncoveredTestPoint[]>([]);

  const load = useCallback(async () => {
    try {
      const reqs = await requirementsApi.list(projectId);
      setRequirements(reqs);
      const map: Record<number, TestPoint[]> = {};
      for (const r of reqs) {
        map[r.id] = await testPointsApi.list(r.id);
      }
      setTestPoints(map);
      const uncov = await testCaseReviewsApi.uncovered(projectId);
      setUncovered(uncov);
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const extract = async (r: Requirement) => {
    setExtractingId(r.id);
    setError('');
    try {
      const result = await aiApi.extractTestPoints(r.id);
      setWarnings((prev) => ({ ...prev, [r.id]: result.warnings }));
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setExtractingId(null);
    }
  };

  const confirmPoint = async (tp: TestPoint) => {
    try {
      await testPointsApi.update(tp.id, { status: 'confirmed' });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const remove = async (tp: TestPoint) => {
    if (!window.confirm(`删除测试点「${tp.title}」？`)) return;
    try {
      await testPointsApi.remove(tp.id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const startCreate = (reqId: number) => {
    setCreatingReqId(reqId);
    setEditingId(null);
    setForm(emptyForm);
  };

  const startEdit = (tp: TestPoint) => {
    setEditingId(tp.id);
    setCreatingReqId(null);
    setForm({ title: tp.title, technique: tp.technique, description: tp.description });
  };

  const submit = async (requirementId: number) => {
    if (!form.title.trim()) return;
    try {
      if (editingId === null) {
        await testPointsApi.create(requirementId, { ...form, title: form.title.trim() });
      } else {
        await testPointsApi.update(editingId, { ...form, title: form.title.trim() });
      }
      setEditingId(null);
      setCreatingReqId(null);
      setForm(emptyForm);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const formView = (requirementId: number) => (
    <div className="steps-editor" style={{ margin: '8px 0' }}>
      <div className="row" style={{ alignItems: 'flex-end' }}>
        <div className="field" style={{ flex: 2 }}>
          <label>标题（必填）</label>
          <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label>技术类型</label>
          <select
            value={form.technique}
            onChange={(e) => setForm((f) => ({ ...f, technique: e.target.value as TestPointTechnique }))}
          >
            {TECHNIQUES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="field">
        <label>说明</label>
        <textarea rows={2} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
      </div>
      <div className="row">
        <button className="primary" onClick={() => submit(requirementId)} disabled={!form.title.trim()}>
          {editingId === null ? '创建' : '保存'}
        </button>
        <button
          onClick={() => {
            setCreatingReqId(null);
            setEditingId(null);
            setForm(emptyForm);
          }}
        >
          取消
        </button>
      </div>
    </div>
  );

  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>测试点</h2>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ background: '#fffbeb', marginTop: 12 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>未覆盖测试点（{uncovered.length}）</h3>
        {uncovered.length === 0 ? (
          <div className="hint">全部测试点均已有用例覆盖</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {uncovered.map((tp) => (
              <li key={tp.id}>
                <strong>{tp.title}</strong>
                <span className="badge neutral" style={{ marginLeft: 6 }}>{tp.technique}</span>
                <span className="hint"> · 需求：{tp.requirement_title}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="hint" style={{ margin: '8px 0 0' }}>
          可在「测试用例」Tab 为这些测试点生成/补录用例。
        </p>
      </div>

      {requirements.length === 0 ? (
        <div className="empty">暂无需求，请先在「需求」页确认需求</div>
      ) : (
        requirements.map((r) => {
          const points = testPoints[r.id] ?? [];
          return (
            <div key={r.id} className="card" style={{ marginTop: 12, background: '#fcfcfd' }}>
              <div className="row">
                <strong>{r.title}</strong>
                <span className={`badge req-${r.status}`}>{r.status}</span>
                <div className="spacer" />
                {r.status === 'confirmed' && (
                  <button className="primary" onClick={() => extract(r)} disabled={extractingId === r.id}>
                    {extractingId === r.id ? '提取中…' : '提取测试点'}
                  </button>
                )}
                {creatingReqId !== r.id && (
                  <button onClick={() => startCreate(r.id)}>+ 手动添加</button>
                )}
              </div>

              {warnings[r.id] && warnings[r.id].length > 0 && (
                <div className="warn-banner" style={{ marginTop: 8 }}>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {warnings[r.id].map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {creatingReqId === r.id && formView(r.id)}

              {points.length === 0 && creatingReqId !== r.id ? (
                <div className="empty">
                  {r.status === 'confirmed' ? '暂无测试点，点击「提取测试点」' : '需求未确认，确认后可提取测试点'}
                </div>
              ) : (
                <table style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th>标题</th>
                      <th>技术</th>
                      <th>状态</th>
                      <th>说明</th>
                      <th style={{ width: 170 }}>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {points.map((tp) => (
                      <tr key={tp.id}>
                        <td>{tp.title}</td>
                        <td>
                          <span className="badge neutral">{tp.technique}</span>
                        </td>
                        <td>
                          <span className={`badge req-${tp.status}`}>{tp.status}</span>
                        </td>
                        <td className="hint">{tp.description || '—'}</td>
                        <td>
                          <div className="row">
                            {tp.status === 'extracted' && (
                              <button className="primary" onClick={() => confirmPoint(tp)}>
                                确认
                              </button>
                            )}
                            <button className="link" onClick={() => startEdit(tp)}>
                              编辑
                            </button>
                            <button className="danger" onClick={() => remove(tp)}>
                              删除
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {editingId !== null && points.some((tp) => tp.id === editingId) && formView(r.id)}
            </div>
          );
        })
      )}
    </div>
  );
}
