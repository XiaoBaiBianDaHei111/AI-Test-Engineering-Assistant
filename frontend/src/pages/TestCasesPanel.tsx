import {
  Fragment,
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from 'react';
import { requirementsApi, testCaseReviewsApi, testCasesApi, testPointsApi } from '../api/assets';
import { aiApi } from '../api/ai';
import { errorMessage } from '../api/client';
import { formatTime } from '../utils/time';
import type {
  Requirement,
  TestCase,
  TestCaseCreate,
  TestCasePriority,
  TestCaseReview,
  TestCaseStepCreate,
  TestCaseType,
} from '../types';

interface StepDraft {
  step_number: number;
  action: string;
  expected_result: string;
}

interface FormValues {
  title: string;
  case_id: string;
  priority: TestCasePriority;
  type: TestCaseType;
  precondition: string;
  expected_result: string;
  requirement_id: string; // '' = none
  steps: StepDraft[];
}

const emptyForm: FormValues = {
  title: '',
  case_id: '',
  priority: 'P2',
  type: 'functional',
  precondition: '',
  expected_result: '',
  requirement_id: '',
  steps: [{ step_number: 1, action: '', expected_result: '' }],
};

function toForm(tc: TestCase): FormValues {
  return {
    title: tc.title,
    case_id: tc.case_id,
    priority: tc.priority,
    type: tc.type,
    precondition: tc.precondition,
    expected_result: tc.expected_result,
    requirement_id: tc.requirement_id === null ? '' : String(tc.requirement_id),
    steps: tc.steps.length
      ? tc.steps.map((s) => ({
          step_number: s.step_number,
          action: s.action,
          expected_result: s.expected_result,
        }))
      : [{ step_number: 1, action: '', expected_result: '' }],
  };
}

function toPayload(f: FormValues): TestCaseCreate {
  const steps: TestCaseStepCreate[] = f.steps
    .filter((s) => s.action.trim().length > 0)
    .map((s, i) => ({
      step_number: i + 1,
      action: s.action.trim(),
      expected_result: s.expected_result.trim(),
    }));
  return {
    title: f.title,
    case_id: f.case_id.trim() || null,
    priority: f.priority,
    type: f.type,
    precondition: f.precondition,
    expected_result: f.expected_result,
    requirement_id: f.requirement_id ? Number(f.requirement_id) : null,
    steps,
  };
}

export default function TestCasesPanel({ projectId }: { projectId: number }) {
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormValues>(emptyForm);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [reviewsId, setReviewsId] = useState<number | null>(null);
  const [reviews, setReviews] = useState<Record<number, TestCaseReview[]>>({});

  // AI generation workflow
  const [confirmedTestPointIds, setConfirmedTestPointIds] = useState<number[]>([]);
  const [testPointTitles, setTestPointTitles] = useState<Record<number, string>>({});
  const [generating, setGenerating] = useState(false);
  const [generationWarnings, setGenerationWarnings] = useState<string[]>([]);
  const [reviewingId, setReviewingId] = useState<number | null>(null);

  // R003-A003 SUGGESTION-3: abort polling state updates after unmount.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    try {
      const [cases, reqs] = await Promise.all([
        testCasesApi.list(projectId),
        requirementsApi.list(projectId),
      ]);
      setTestCases(cases);
      setRequirements(reqs);
      const confirmedIds: number[] = [];
      const titles: Record<number, string> = {};
      await Promise.all(
        reqs.map(async (r) => {
          const points = await testPointsApi.list(r.id);
          for (const tp of points) {
            titles[tp.id] = tp.title;
            if (tp.status === 'confirmed') confirmedIds.push(tp.id);
          }
        }),
      );
      setConfirmedTestPointIds(confirmedIds);
      setTestPointTitles(titles);
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const set = (patch: Partial<FormValues>) => setForm((f) => ({ ...f, ...patch }));

  const setStep = (index: number, patch: Partial<StepDraft>) =>
    setForm((f) => ({
      ...f,
      steps: f.steps.map((s, i) => (i === index ? { ...s, ...patch } : s)),
    }));

  const addStep = () =>
    setForm((f) => ({
      ...f,
      steps: [...f.steps, { step_number: f.steps.length + 1, action: '', expected_result: '' }],
    }));

  const removeStep = (index: number) =>
    setForm((f) => ({ ...f, steps: f.steps.filter((_, i) => i !== index) }));

  const resetForm = () => {
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(false);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    try {
      if (editingId === null) {
        await testCasesApi.create(projectId, toPayload(form));
      } else {
        await testCasesApi.update(editingId, toPayload(form));
      }
      resetForm();
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const startCreate = () => {
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(true);
  };

  const startEdit = (tc: TestCase) => {
    setForm(toForm(tc));
    setEditingId(tc.id);
    setShowForm(true);
  };

  const remove = async (tc: TestCase) => {
    if (!window.confirm(`删除用例「${tc.case_id} ${tc.title}」？`)) return;
    try {
      await testCasesApi.remove(tc.id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const runGenerate = async () => {
    if (confirmedTestPointIds.length === 0) return;
    setGenerating(true);
    setError('');
    setGenerationWarnings([]);
    try {
      const { run_id } = await aiApi.generateTestCases(projectId, confirmedTestPointIds);
      let run = await aiApi.getGenerationRun(run_id);
      while (!['completed', 'partial', 'failed'].includes(run.status) && mountedRef.current) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        run = await aiApi.getGenerationRun(run_id);
      }
      if (mountedRef.current) {
        setGenerationWarnings(run.warnings);
        await load();
      }
    } catch (err) {
      if (mountedRef.current) setError(errorMessage(err));
    } finally {
      if (mountedRef.current) setGenerating(false);
    }
  };

  // --- Review actions (M1) ---

  const submitReview = async (tc: TestCase) => {
    try {
      await testCaseReviewsApi.submit(tc.id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const approveCase = async (tc: TestCase) => {
    try {
      await testCaseReviewsApi.review(tc.id, { verdict: 'approved', issues: [], suggestions: [] });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const rejectCase = async (tc: TestCase) => {
    try {
      await testCaseReviewsApi.review(tc.id, {
        verdict: 'needs_work',
        issues: [],
        suggestions: [],
      });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const resubmitCase = async (tc: TestCase) => {
    try {
      await testCaseReviewsApi.resubmit(tc.id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const archiveCase = async (tc: TestCase) => {
    if (!window.confirm(`归档用例「${tc.title}」？`)) return;
    try {
      await testCasesApi.update(tc.id, { status: 'archived' });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const loadReviews = async (tc: TestCase) => {
    if (reviewsId === tc.id) {
      setReviewsId(null);
      return;
    }
    try {
      const revs = await testCaseReviewsApi.list(tc.id);
      setReviews((prev) => ({ ...prev, [tc.id]: revs }));
      setReviewsId(tc.id);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const aiReviewCase = async (tc: TestCase) => {
    setReviewingId(tc.id);
    setError('');
    try {
      const result = await aiApi.reviewTestCases([tc.id]);
      if (result.failed.length > 0) setError(result.failed[0].reason ?? 'AI 评审失败');
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setReviewingId(null);
    }
  };

  const aiReviewAll = async () => {
    const ids = testCases
      .filter((tc) => tc.status === 'draft' || tc.status === 'pending_review')
      .map((tc) => tc.id);
    if (ids.length === 0) {
      setError('暂无待审（draft / pending_review）用例');
      return;
    }
    setReviewingId(-1);
    setError('');
    try {
      await aiApi.reviewTestCases(ids);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setReviewingId(null);
    }
  };

  const reviewActions = (tc: TestCase) => {
    const buttons = [];
    if (tc.status === 'draft') {
      buttons.push(
        <button key="submit" className="primary" onClick={() => submitReview(tc)}>
          提交评审
        </button>,
      );
    } else if (tc.status === 'pending_review') {
      buttons.push(
        <button key="approve" className="primary" onClick={() => approveCase(tc)}>
          通过
        </button>,
        <button key="reject" className="danger" onClick={() => rejectCase(tc)}>
          退回
        </button>,
      );
    } else if (tc.status === 'needs_work') {
      buttons.push(
        <button key="resubmit" className="primary" onClick={() => resubmitCase(tc)}>
          重新提交
        </button>,
      );
    }
    if (tc.status !== 'archived' && tc.status !== 'executed') {
      buttons.push(
        <button key="archive" className="link" onClick={() => archiveCase(tc)}>
          归档
        </button>,
      );
    }
    if (tc.status !== 'archived') {
      buttons.push(
        <button
          key="ai"
          className="link"
          onClick={() => aiReviewCase(tc)}
          disabled={reviewingId === tc.id}
        >
          {reviewingId === tc.id ? 'AI 评审中…' : 'AI 评审'}
        </button>,
      );
    }
    return buttons;
  };

  const pendingCount = testCases.filter(
    (tc) => tc.status === 'draft' || tc.status === 'pending_review',
  ).length;

  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>测试用例</h2>
        <div className="spacer" />
        {!showForm && (
          <button className="primary" onClick={startCreate}>
            + 新建用例
          </button>
        )}
      </div>

      <div className="card" style={{ background: '#fafbff', marginTop: 12 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>AI 用例生成</h3>
        <p className="hint" style={{ margin: '0 0 8px' }}>
          为项目内全部已确认测试点（当前 {confirmedTestPointIds.length} 个）批量生成用例；生成后用例停留 draft 待评审。
        </p>
        <button
          className="primary"
          onClick={runGenerate}
          disabled={generating || confirmedTestPointIds.length === 0}
        >
          {generating ? '生成中…' : '开始生成'}
        </button>
        {confirmedTestPointIds.length === 0 && !generating && (
          <p className="hint" style={{ margin: '8px 0 0' }}>
            暂无已确认测试点，请先在「测试点」Tab 完成 Gate 2 确认。
          </p>
        )}
        {generationWarnings.length > 0 && (
          <div className="warn-banner" style={{ marginTop: 12 }}>
            <strong>生成提示：</strong>
            <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
              {generationWarnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="card" style={{ background: '#fafbff', marginTop: 12 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>AI 用例评审（辅助，不改变状态）</h3>
        <button className="primary" onClick={aiReviewAll} disabled={reviewingId === -1 || pendingCount === 0}>
          {reviewingId === -1 ? '评审中…' : `AI 评审全部待审（${pendingCount}）`}
        </button>
        <p className="hint" style={{ margin: '8px 0 0' }}>
          AI 评审仅给出三维评分与缺失场景，最终通过/退回由人工决定。
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showForm && (
        <form onSubmit={submit} style={{ marginTop: 16 }}>
          <div className="row">
            <div className="field" style={{ flex: 2 }}>
              <label>标题（必填）</label>
              <input value={form.title} onChange={(e) => set({ title: e.target.value })} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>用例编号（留空自动生成 TC-xxx）</label>
              <input
                value={form.case_id}
                onChange={(e) => set({ case_id: e.target.value })}
                placeholder="TC-001"
                disabled={editingId !== null}
              />
            </div>
          </div>

          <div className="row">
            <div className="field" style={{ flex: 1 }}>
              <label>优先级</label>
              <select
                value={form.priority}
                onChange={(e) => set({ priority: e.target.value as TestCasePriority })}
              >
                <option value="P0">P0</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
                <option value="P3">P3</option>
              </select>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>类型</label>
              <select value={form.type} onChange={(e) => set({ type: e.target.value as TestCaseType })}>
                <option value="smoke">smoke</option>
                <option value="functional">functional</option>
                <option value="boundary">boundary</option>
                <option value="exception">exception</option>
                <option value="performance">performance</option>
                <option value="security">security</option>
                <option value="compatibility">compatibility</option>
              </select>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>关联需求</label>
              <select value={form.requirement_id} onChange={(e) => set({ requirement_id: e.target.value })}>
                <option value="">（无）</option>
                {requirements.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="field">
            <label>前置条件</label>
            <textarea rows={1} value={form.precondition} onChange={(e) => set({ precondition: e.target.value })} />
          </div>

          <div className="field">
            <label>步骤（每步一个动作 + 预期结果）</label>
            <div className="steps-editor">
              <div className="step-row" style={{ fontWeight: 600, fontSize: 12, color: '#6b7280' }}>
                <span>#</span>
                <span>动作</span>
                <span>预期结果</span>
                <span />
              </div>
              {form.steps.map((step, i) => (
                <div className="step-row" key={i}>
                  <input value={step.step_number} disabled />
                  <textarea
                    rows={1}
                    placeholder="操作"
                    value={step.action}
                    onChange={(e) => setStep(i, { action: e.target.value })}
                  />
                  <textarea
                    rows={1}
                    placeholder="预期结果"
                    value={step.expected_result}
                    onChange={(e) => setStep(i, { expected_result: e.target.value })}
                  />
                  <button type="button" onClick={() => removeStep(i)} title="删除步骤">
                    ×
                  </button>
                </div>
              ))}
              <button type="button" onClick={addStep}>
                + 添加步骤
              </button>
            </div>
          </div>

          <div className="field">
            <label>预期结果（整体）</label>
            <textarea rows={1} value={form.expected_result} onChange={(e) => set({ expected_result: e.target.value })} />
          </div>

          <div className="row">
            <button type="submit" className="primary" disabled={!form.title.trim()}>
              {editingId === null ? '创建' : '保存'}
            </button>
            <button type="button" onClick={resetForm}>
              取消
            </button>
          </div>
        </form>
      )}

      {testCases.length === 0 && !showForm ? (
        <div className="empty">暂无测试用例</div>
      ) : (
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>编号</th>
              <th>标题</th>
              <th>优先级</th>
              <th>状态</th>
              <th>来源</th>
              <th>关联测试点</th>
              <th>步骤数</th>
              <th style={{ width: 280 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {testCases.map((tc) => (
              <Fragment key={tc.id}>
                <tr>
                  <td>{tc.case_id}</td>
                  <td>{tc.title}</td>
                  <td>
                    <span className={`badge ${tc.priority.toLowerCase()}`}>{tc.priority}</span>
                  </td>
                  <td>
                    <span className={`badge status-${tc.status}`}>{tc.status}</span>
                    {tc.status === 'approved' && <span className="badge status-approved">可执行</span>}
                  </td>
                  <td>
                    <span className={`badge source-${tc.source}`}>{tc.source}</span>
                  </td>
                  <td className="hint">
                    {tc.test_point_id !== null
                      ? testPointTitles[tc.test_point_id] ?? `#${tc.test_point_id}`
                      : '—'}
                  </td>
                  <td>{tc.steps.length}</td>
                  <td>
                    <div className="row">
                      {reviewActions(tc)}
                      <button className="link" onClick={() => setExpandedId(expandedId === tc.id ? null : tc.id)}>
                        {expandedId === tc.id ? '收起' : '步骤'}
                      </button>
                      <button className="link" onClick={() => loadReviews(tc)}>
                        {reviewsId === tc.id ? '收起' : '评审'}
                      </button>
                      <button className="link" onClick={() => startEdit(tc)}>
                        编辑
                      </button>
                      <button className="danger" onClick={() => remove(tc)}>
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
                {expandedId === tc.id && (
                  <tr>
                    <td colSpan={8} style={{ background: '#fafafa' }}>
                      {tc.steps.length === 0 ? (
                        <div className="hint">无步骤</div>
                      ) : (
                        <ol style={{ margin: 0, paddingLeft: 20 }}>
                          {tc.steps.map((s) => (
                            <li key={s.id ?? s.step_number}>
                              <strong>{s.action}</strong>
                              {s.expected_result && (
                                <span className="hint"> → 预期：{s.expected_result}</span>
                              )}
                            </li>
                          ))}
                        </ol>
                      )}
                    </td>
                  </tr>
                )}
                {reviewsId === tc.id && (
                  <tr>
                    <td colSpan={8} style={{ background: '#fafafa' }}>
                      {(reviews[tc.id] ?? []).length === 0 ? (
                        <div className="hint">暂无评审记录</div>
                      ) : (
                        <div>
                          {(reviews[tc.id] ?? []).map((r) => (
                            <div key={r.id} style={{ marginBottom: 8 }}>
                              <span className={`badge ${r.reviewer_type === 'ai' ? 'source-ai' : 'source-manual'}`}>
                                {r.reviewer_type}
                              </span>{' '}
                              <span className={`badge ${r.verdict === 'approved' ? 'status-approved' : 'status-needs_work'}`}>
                                {r.verdict}
                              </span>{' '}
                              {r.scores && (
                                <span className="hint">
                                  完整性 {r.scores.completeness} · 准确性 {r.scores.accuracy} · 可执行性 {r.scores.executability}
                                </span>
                              )}
                              <span className="hint"> · {formatTime(r.created_at)}</span>
                              {r.issues.length > 0 && (
                                <div className="hint">问题：{r.issues.join('；')}</div>
                              )}
                              {r.missing_scenarios.length > 0 && (
                                <div className="hint">缺失场景：{r.missing_scenarios.join('；')}</div>
                              )}
                              {r.suggestions.length > 0 && (
                                <div className="hint">建议：{r.suggestions.join('；')}</div>
                              )}
                            </div>
                          ))}
                        </div>
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
