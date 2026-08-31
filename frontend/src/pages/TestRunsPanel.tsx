import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { apiTestCasesApi } from '../api/apiTestCases';
import { testCaseReviewsApi } from '../api/assets';
import { errorMessage } from '../api/client';
import { formatTime } from '../utils/time';
import { evidenceApi } from '../api/evidence';
import { failureAnalysisApi } from '../api/failureAnalysis';
import { runsApi } from '../api/runs';
import type {
  ApiTestCase,
  ConsoleEntry,
  Evidence,
  NetworkEntry,
  QaMode,
  TestCase,
  TestRun,
  TestRunCase,
  TraceParse,
} from '../types';

const QA_MODES: QaMode[] = ['none', 'selector-change', 'logic-bug', 'slow-network', 'auth-break'];

export default function TestRunsPanel({ projectId, onOpenReports }: { projectId: number; onOpenReports?: () => void }) {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [executable, setExecutable] = useState<TestCase[]>([]);
  const [apiCases, setApiCases] = useState<ApiTestCase[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectedApiIds, setSelectedApiIds] = useState<number[]>([]);
  const [baseUrl, setBaseUrl] = useState('http://localhost:8000');
  const [qaMode, setQaMode] = useState<QaMode>('none');
  const [headless, setHeadless] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const [expandedCaseId, setExpandedCaseId] = useState<number | null>(null);
  const [caseDetail, setCaseDetail] = useState<TestRunCase | null>(null);
  const [scriptText, setScriptText] = useState('');
  const [viewingScriptCaseId, setViewingScriptCaseId] = useState<number | null>(null);
  const [rerunningId, setRerunningId] = useState<number | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [consoleEntries, setConsoleEntries] = useState<ConsoleEntry[]>([]);
  const [networkEntries, setNetworkEntries] = useState<NetworkEntry[]>([]);
  const [traceParse, setTraceParse] = useState<TraceParse | null>(null);
  const [traceTab, setTraceTab] = useState<'actions' | 'network' | 'console'>('actions');

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    try {
      const [runList, exec, apiList] = await Promise.all([
        runsApi.list(projectId),
        testCaseReviewsApi.executable(projectId),
        apiTestCasesApi.list(projectId),
      ]);
      setRuns(runList);
      setExecutable(exec);
      setApiCases(apiList.filter((c) => c.status === 'active'));
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleSelect = (id: number) =>
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  const toggleApiSelect = (id: number) =>
    setSelectedApiIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  const createRun = async () => {
    if (selectedIds.length === 0 && selectedApiIds.length === 0) return;
    setCreating(true);
    setError('');
    try {
      const { run_id } = await runsApi.create({
        project_id: projectId,
        test_case_ids: selectedIds,
        api_case_ids: selectedApiIds,
        config: { base_url: baseUrl, qa_mode: qaMode, browser: 'chromium', headless },
      });
      let run = await runsApi.get(run_id);
      while (!['completed', 'failed', 'cancelled'].includes(run.status) && mountedRef.current) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        run = await runsApi.get(run_id);
      }
      setSelectedIds([]);
      setSelectedApiIds([]);
      await load();
    } catch (err) {
      if (mountedRef.current) setError(errorMessage(err));
    } finally {
      if (mountedRef.current) setCreating(false);
    }
  };

  const openCase = async (runId: number, caseId: number) => {
    if (expandedCaseId === caseId) {
      setExpandedCaseId(null);
      setCaseDetail(null);
      setEvidence([]);
      setTraceParse(null);
      return;
    }
    try {
      const detail = await runsApi.getCase(runId, caseId);
      setCaseDetail(detail);
      setExpandedCaseId(caseId);
      setError('');

      const rows = await evidenceApi.listCase(runId, caseId);
      setEvidence(rows);
      const consoleEv = rows.find((e) => e.kind === 'console');
      const networkEv = rows.find((e) => e.kind === 'network');
      const traceEv = rows.find((e) => e.kind === 'trace');
      setConsoleEntries(consoleEv ? await evidenceApi.getConsole(consoleEv.id) : []);
      setNetworkEntries(networkEv ? await evidenceApi.getNetwork(networkEv.id) : []);
      setTraceParse(traceEv ? await evidenceApi.getTraceParse(traceEv.id) : null);
      setTraceTab('actions');
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const viewScript = async (runId: number, caseId: number) => {
    try {
      const text = await runsApi.getScript(runId, caseId);
      setScriptText(text);
      setViewingScriptCaseId(caseId);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const saveScript = async (runId: number, caseId: number) => {
    try {
      await runsApi.putScript(runId, caseId, scriptText);
      setViewingScriptCaseId(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const rerun = async (runId: number, caseId: number) => {
    setRerunningId(caseId);
    setError('');
    try {
      const detail = await runsApi.rerun(runId, caseId);
      setCaseDetail(detail);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRerunningId(null);
    }
  };

  const reloadCase = async (runId: number, caseId: number) => {
    try {
      const detail = await runsApi.getCase(runId, caseId);
      setCaseDetail(detail);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const confirmAnalysis = async (runId: number, caseId: number, analysisId: number) => {
    setError('');
    try {
      await failureAnalysisApi.confirm(analysisId);
      await reloadCase(runId, caseId);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const retryAnalysis = async (runId: number, caseId: number) => {
    setError('');
    try {
      await failureAnalysisApi.retry(caseId);
      await reloadCase(runId, caseId);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const categoryColor = (c: string) =>
    ({ BROKEN_LOCATOR: '#dc2626', REAL_BUG: '#ea580c', FLAKY: '#ca8a04', ENV_ISSUE: '#6b7280' })[c] || '#6b7280';

  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>执行</h2>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ background: '#fafbff', marginTop: 12 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>发起执行（仅 approved 用例）</h3>
        <div className="field">
          <label>目标地址</label>
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </div>
        <div className="row">
          <div className="field" style={{ flex: 1 }}>
            <label>故障注入（qaMode）</label>
            <select value={qaMode} onChange={(e) => setQaMode(e.target.value as QaMode)}>
              {QA_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>headless</label>
            <select value={headless ? 'true' : 'false'} onChange={(e) => setHeadless(e.target.value === 'true')}>
              <option value="true">是</option>
              <option value="false">否</option>
            </select>
          </div>
        </div>
        <div className="field">
          <label>选择 UI 用例（{selectedIds.length} 已选）</label>
          {executable.length === 0 ? (
            <p className="hint">暂无 approved 用例，请先在「测试用例」Tab 完成评审（Gate 3）。</p>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {executable.map((tc) => (
                <li key={tc.id} style={{ marginBottom: 4 }}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(tc.id)}
                      onChange={() => toggleSelect(tc.id)}
                    />{' '}
                    {tc.case_id} {tc.title}（{tc.priority}）
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="field">
          <label>选择接口用例（{selectedApiIds.length} 已选）</label>
          {apiCases.length === 0 ? (
            <p className="hint">暂无 active 接口用例，请先在「接口用例」Tab 生成/创建。</p>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {apiCases.map((ac) => (
                <li key={ac.id} style={{ marginBottom: 4 }}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedApiIds.includes(ac.id)}
                      onChange={() => toggleApiSelect(ac.id)}
                    />{' '}
                    {ac.method} {ac.url}（{ac.name}）
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button className="primary" onClick={createRun} disabled={creating || (selectedIds.length === 0 && selectedApiIds.length === 0)}>
          {creating ? '执行中…' : '开始执行'}
        </button>
      </div>

      <table style={{ marginTop: 12 }}>
        <thead>
          <tr>
            <th>ID</th>
            <th>名称</th>
            <th>状态</th>
            <th>通过/失败</th>
            <th>创建时间</th>
            <th style={{ width: 120 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <Fragment key={run.id}>
              <tr>
                <td>{run.id}</td>
                <td>{run.name}</td>
                <td>
                  <span className={`badge status-${run.status}`}>{run.status}</span>
                </td>
                <td>
                  {run.passed_count}/{run.failed_count}
                </td>
                <td className="hint">{formatTime(run.created_at)}</td>
                <td>
                  <div className="row">
                    <button className="link" onClick={() => setExpandedRunId(expandedRunId === run.id ? null : run.id)}>
                      {expandedRunId === run.id ? '收起' : '用例'}
                    </button>
                    {['completed', 'failed'].includes(run.status) && onOpenReports && (
                      <button className="link" onClick={onOpenReports}>
                        报告
                      </button>
                    )}
                    {['pending', 'running'].includes(run.status) && (
                      <button className="danger" onClick={() => runsApi.cancel(run.id).then(load)}>
                        取消
                      </button>
                    )}
                  </div>
                </td>
              </tr>
              {expandedRunId === run.id &&
                (run.cases ?? []).map((rc) => (
                  <Fragment key={rc.id}>
                    <tr>
                      <td colSpan={5} style={{ paddingLeft: 24 }}>
                        <span className={`badge status-${rc.status}`}>{rc.status}</span>{' '}
                        <span className="badge status-archived">{rc.kind === 'api' ? 'API' : 'UI'}</span>{' '}
                        {rc.case_label}
                        {rc.error && <span className="hint"> · {rc.error.slice(0, 120)}</span>}
                      </td>
                      <td>
                        <div className="row">
                          <button className="link" onClick={() => openCase(run.id, rc.id)}>
                            {expandedCaseId === rc.id ? '收起' : '步骤'}
                          </button>
                          {rc.kind !== 'api' && (
                            <button className="link" onClick={() => viewScript(run.id, rc.id)}>
                              脚本
                            </button>
                          )}
                          {(rc.status === 'failed' || rc.status === 'blocked') && (
                            <button className="link" onClick={() => rerun(run.id, rc.id)} disabled={rerunningId === rc.id}>
                              {rerunningId === rc.id ? '重跑中…' : '重跑'}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expandedCaseId === rc.id && caseDetail && (
                      <tr>
                        <td colSpan={6} style={{ background: '#fafafa' }}>
                          {caseDetail.failure_analysis ? (
                            <div style={{ marginBottom: 12, border: '1px solid #e5e7eb', borderRadius: 6, padding: 10, background: '#fff' }}>
                              <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>失败分析</h4>
                              <div className="row" style={{ gap: 8, marginBottom: 6 }}>
                                <span className="badge" style={{ background: categoryColor(caseDetail.failure_analysis.category), color: '#fff' }}>
                                  {caseDetail.failure_analysis.category}
                                </span>
                                <span className="hint">置信度 {(caseDetail.failure_analysis.confidence * 100).toFixed(0)}%</span>
                                <span className="badge">{caseDetail.failure_analysis.decision_source === 'rule' ? '规则' : 'LLM'}</span>
                                {caseDetail.failure_analysis.status === 'confirmed' && (
                                  <span className="badge status-approved">confirmed</span>
                                )}
                              </div>
                              <div><strong>原因：</strong>{caseDetail.failure_analysis.reason}</div>
                              <div style={{ marginTop: 4 }}><strong>建议：</strong>{caseDetail.failure_analysis.suggested_fix}</div>
                              {caseDetail.failure_analysis.needs_human && caseDetail.failure_analysis.status !== 'confirmed' && (
                                <div className="row" style={{ gap: 8, marginTop: 8 }}>
                                  <span className="hint" style={{ color: '#b45309' }}>低置信度，请人工确认</span>
                                  <button className="primary" onClick={() => confirmAnalysis(run.id, rc.id, caseDetail.failure_analysis!.id)}>
                                    确认分析
                                  </button>
                                </div>
                              )}
                            </div>
                          ) : (
                            (caseDetail.status === 'failed' || caseDetail.status === 'blocked') && (
                              <div style={{ marginBottom: 12 }}>
                                <button className="link" onClick={() => retryAnalysis(run.id, rc.id)}>重试分析</button>
                              </div>
                            )
                          )}
                          {caseDetail.step_results && caseDetail.step_results.length > 0 ? (
                            <ol style={{ margin: 0, paddingLeft: 20 }}>
                              {caseDetail.step_results.map((s) => (
                                <li key={s.id}>
                                  <strong>{s.description}</strong>
                                  <span className={`badge ${s.status === 'passed' ? 'status-approved' : 'status-needs_work'}`}>
                                    {s.status}
                                  </span>
                                  <span className="hint"> · {s.duration_ms}ms</span>
                                  {s.message && <span className="hint"> · {s.message.slice(0, 160)}</span>}
                                </li>
                              ))}
                            </ol>
                          ) : (
                            <div className="hint">无步骤结果</div>
                          )}
                          {evidence.filter((e) => e.kind === 'screenshot').length > 0 && (
                            <div style={{ marginTop: 12 }}>
                              <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>截图</h4>
                              <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                                {evidence
                                  .filter((e) => e.kind === 'screenshot')
                                  .map((e) => (
                                    <a key={e.id} href={evidenceApi.contentUrl(e.id)} target="_blank" rel="noreferrer">
                                      <img
                                        src={evidenceApi.contentUrl(e.id)}
                                        alt={`步骤 ${String(e.meta.step_number ?? '')}`}
                                        style={{ width: 120, border: '1px solid #ddd', borderRadius: 4 }}
                                      />
                                    </a>
                                  ))}
                              </div>
                            </div>
                          )}
                          {consoleEntries.length > 0 && (
                            <div style={{ marginTop: 12 }}>
                              <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>Console</h4>
                              <ul style={{ margin: 0, paddingLeft: 20 }}>
                                {consoleEntries.map((c, i) => (
                                  <li key={i}>
                                    <span className={`badge ${c.type === 'error' ? 'status-needs_work' : 'status-approved'}`}>
                                      {c.type}
                                    </span>{' '}
                                    <span className="hint">{c.text}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {networkEntries.length > 0 && (
                            <div style={{ marginTop: 12 }}>
                              <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>Network</h4>
                              <table>
                                <thead>
                                  <tr>
                                    <th>method</th>
                                    <th>url</th>
                                    <th>status</th>
                                    <th>resource</th>
                                    <th>duration</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {networkEntries.map((n, i) => (
                                    <tr key={i}>
                                      <td>{n.method}</td>
                                      <td>{n.url}</td>
                                      <td>{n.status}</td>
                                      <td>{n.resource_type}</td>
                                      <td>{n.duration_ms}ms</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                          {traceParse && (
                            <div style={{ marginTop: 12 }}>
                              <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>Trace</h4>
                              <div className="row" style={{ gap: 8, marginBottom: 6 }}>
                                {(['actions', 'network', 'console'] as const).map((tab) => (
                                  <button
                                    key={tab}
                                    className={traceTab === tab ? 'primary' : 'link'}
                                    onClick={() => setTraceTab(tab)}
                                  >
                                    {tab === 'actions' ? '动作' : tab === 'network' ? '网络' : '控制台'}
                                  </button>
                                ))}
                              </div>
                              {traceTab === 'actions' && (
                                <ul style={{ margin: 0, paddingLeft: 20 }}>
                                  {traceParse.actions.map((a, i) => (
                                    <li key={i}>
                                      <strong>{a.api_name}</strong>
                                      <span className="hint"> · {a.duration_ms ?? 0}ms</span>
                                      {a.error && <span className="badge status-needs_work">error</span>}
                                    </li>
                                  ))}
                                </ul>
                              )}
                              {traceTab === 'network' && (
                                <ul style={{ margin: 0, paddingLeft: 20 }}>
                                  {traceParse.network.map((n, i) => (
                                    <li key={i}>
                                      <strong>{n.method}</strong> {n.url}{' '}
                                      <span className="hint">{n.status} · {n.duration_ms ?? 0}ms</span>
                                    </li>
                                  ))}
                                </ul>
                              )}
                              {traceTab === 'console' && (
                                <ul style={{ margin: 0, paddingLeft: 20 }}>
                                  {traceParse.console.map((c, i) => (
                                    <li key={i}>
                                      <span className={`badge ${c.type === 'error' ? 'status-needs_work' : 'status-approved'}`}>
                                        {c.type}
                                      </span>{' '}
                                      {c.text}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                    {viewingScriptCaseId === rc.id && (
                      <tr>
                        <td colSpan={6} style={{ background: '#fafafa' }}>
                          <div className="field">
                            <label>脚本（可编辑后保存并重跑）</label>
                            <textarea rows={14} value={scriptText} onChange={(e) => setScriptText(e.target.value)} />
                          </div>
                          <div className="row">
                            <button className="primary" onClick={() => saveScript(run.id, rc.id)}>
                              保存脚本
                            </button>
                            <button onClick={() => setViewingScriptCaseId(null)}>取消</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
