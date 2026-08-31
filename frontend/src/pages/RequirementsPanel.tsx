import { Fragment, useCallback, useEffect, useState, type FormEvent } from 'react';
import { requirementsApi } from '../api/assets';
import { aiApi } from '../api/ai';
import { errorMessage } from '../api/client';
import type { AssetSource, Requirement, RequirementStatus } from '../types';

const toLines = (arr: string[]) => arr.join('\n');
const fromLines = (s: string) =>
  s.split('\n').map((x) => x.trim()).filter((x) => x.length > 0);

interface FormValues {
  title: string;
  description: string;
  acceptance_criteria: string;
  risks: string;
  status: RequirementStatus;
  source: AssetSource;
}

const emptyForm: FormValues = {
  title: '',
  description: '',
  acceptance_criteria: '',
  risks: '',
  status: 'parsed',
  source: 'manual',
};

function toForm(r: Requirement): FormValues {
  return {
    title: r.title,
    description: r.description,
    acceptance_criteria: toLines(r.acceptance_criteria),
    risks: toLines(r.risks),
    status: r.status,
    source: r.source,
  };
}

function toPayload(f: FormValues) {
  return {
    title: f.title,
    description: f.description,
    acceptance_criteria: fromLines(f.acceptance_criteria),
    risks: fromLines(f.risks),
    status: f.status,
    source: f.source,
  };
}

export default function RequirementsPanel({ projectId }: { projectId: number }) {
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<FormValues>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // AI requirements-analysis workflow
  const [prdText, setPrdText] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [aiWarnings, setAiWarnings] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      setRequirements(await requirementsApi.list(projectId));
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const set = (patch: Partial<FormValues>) => setForm((f) => ({ ...f, ...patch }));

  const runAnalyze = async () => {
    if (!prdText.trim()) return;
    setAnalyzing(true);
    setError('');
    setAiWarnings([]);
    try {
      const result = await aiApi.analyzeRequirement(projectId, prdText);
      setAiWarnings(result.warnings);
      setPrdText('');
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  };

  const confirmRequirement = async (r: Requirement) => {
    try {
      await requirementsApi.update(r.id, { status: 'confirmed' });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    try {
      await requirementsApi.create(projectId, toPayload(form));
      setForm(emptyForm);
      setShowCreate(false);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const startEdit = (r: Requirement) => {
    setEditingId(r.id);
    setForm(toForm(r));
  };

  const saveEdit = async (e: FormEvent) => {
    e.preventDefault();
    if (editingId === null) return;
    try {
      await requirementsApi.update(editingId, toPayload(form));
      setEditingId(null);
      setForm(emptyForm);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const remove = async (r: Requirement) => {
    if (!window.confirm(`删除需求「${r.title}」？关联用例将解除关联（不删除）。`)) return;
    try {
      await requirementsApi.remove(r.id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const formView = (
    <form onSubmit={editingId === null ? create : saveEdit}>
      <div className="field">
        <label>标题（必填）</label>
        <input value={form.title} onChange={(e) => set({ title: e.target.value })} />
      </div>
      <div className="field">
        <label>描述</label>
        <textarea rows={2} value={form.description} onChange={(e) => set({ description: e.target.value })} />
      </div>
      <div className="field">
        <label>验收标准（每行一条）</label>
        <textarea
          rows={3}
          value={form.acceptance_criteria}
          onChange={(e) => set({ acceptance_criteria: e.target.value })}
        />
      </div>
      <div className="field">
        <label>风险（每行一条）</label>
        <textarea rows={2} value={form.risks} onChange={(e) => set({ risks: e.target.value })} />
      </div>
      <div className="row">
        <div className="field" style={{ flex: 1 }}>
          <label>状态</label>
          <select value={form.status} onChange={(e) => set({ status: e.target.value as RequirementStatus })}>
            <option value="parsed">parsed</option>
            <option value="confirmed">confirmed</option>
            <option value="archived">archived</option>
          </select>
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label>来源</label>
          <select value={form.source} onChange={(e) => set({ source: e.target.value as AssetSource })}>
            <option value="manual">manual</option>
            <option value="ai">ai</option>
          </select>
        </div>
      </div>
      <div className="row">
        <button type="submit" className="primary" disabled={!form.title.trim()}>
          {editingId === null ? '创建' : '保存'}
        </button>
        <button
          type="button"
          onClick={() => {
            setEditingId(null);
            setForm(emptyForm);
            setShowCreate(false);
          }}
        >
          取消
        </button>
      </div>
    </form>
  );

  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>需求</h2>
        <div className="spacer" />
        {!showCreate && editingId === null && (
          <button className="primary" onClick={() => setShowCreate(true)}>
            + 新建需求
          </button>
        )}
      </div>

      <div className="card" style={{ background: '#fafbff', marginTop: 16 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>AI 需求分析</h3>
        <p className="hint" style={{ margin: '0 0 8px' }}>
          粘贴 PRD / 用户故事，AI 将解析为结构化需求（含验收标准 / 风险 / gap / 歧义），人工确认后进入 Gate 1。
        </p>
        <div className="field">
          <textarea
            rows={6}
            value={prdText}
            onChange={(e) => setPrdText(e.target.value)}
            placeholder="在此粘贴 PRD 文本…"
            disabled={analyzing}
          />
        </div>
        <button className="primary" onClick={runAnalyze} disabled={analyzing || !prdText.trim()}>
          {analyzing ? '分析中…' : '开始分析'}
        </button>
        {aiWarnings.length > 0 && (
          <div className="warn-banner" style={{ marginTop: 12 }}>
            <strong>分析提示：</strong>
            <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
              {aiWarnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {(showCreate || editingId !== null) && <div style={{ marginTop: 16 }}>{formView}</div>}

      {requirements.length === 0 && !showCreate && editingId === null ? (
        <div className="empty">暂无需求</div>
      ) : (
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>标题</th>
              <th>状态</th>
              <th>来源</th>
              <th>验收标准</th>
              <th style={{ width: 170 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {requirements.map((r) => (
              <Fragment key={r.id}>
                <tr>
                  <td>
                    <strong>{r.title}</strong>
                    {r.description && <div className="hint">{r.description}</div>}
                  </td>
                  <td>
                    <span className={`badge req-${r.status}`}>{r.status}</span>
                  </td>
                  <td>
                    <span className={`badge source-${r.source}`}>{r.source}</span>
                  </td>
                  <td>
                    {r.acceptance_criteria.length > 0 ? (
                      <ul style={{ margin: 0, paddingLeft: 18 }}>
                        {r.acceptance_criteria.map((ac, i) => (
                          <li key={i}>{ac}</li>
                        ))}
                      </ul>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    <div className="row">
                      {r.status === 'parsed' && (
                        <button className="primary" onClick={() => confirmRequirement(r)}>
                          确认
                        </button>
                      )}
                      <button
                        className="link"
                        onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                      >
                        {expandedId === r.id ? '收起' : '详情'}
                      </button>
                      <button className="link" onClick={() => startEdit(r)}>
                        编辑
                      </button>
                      <button className="danger" onClick={() => remove(r)}>
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
                {expandedId === r.id && (
                  <tr>
                    <td colSpan={5} style={{ background: '#fafafa' }}>
                      {r.risks.length > 0 && (
                        <div style={{ marginBottom: 6 }}>
                          <strong>风险：</strong>
                          <span className="hint">{r.risks.join('；')}</span>
                        </div>
                      )}
                      {r.gaps.length > 0 && (
                        <div style={{ marginBottom: 6 }}>
                          <strong>Gap：</strong>
                          <span className="hint">{r.gaps.join('；')}</span>
                        </div>
                      )}
                      {r.ambiguities.length > 0 && (
                        <div style={{ marginBottom: 6 }}>
                          <strong>歧义：</strong>
                          <span className="hint">{r.ambiguities.join('；')}</span>
                        </div>
                      )}
                      {r.doc_ref && (
                        <div className="hint">来源：{r.doc_ref}</div>
                      )}
                      {r.risks.length === 0 && r.gaps.length === 0 && r.ambiguities.length === 0 && (
                        <div className="hint">（无额外分析信息）</div>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
