import { useCallback, useEffect, useState } from 'react';
import { errorMessage } from '../api/client';
import { formatTime } from '../utils/time';
import { reportsApi } from '../api/reports';
import type { ReportListItem, TestReport } from '../types';

const REC_COLOR: Record<string, string> = { GO: '#16a34a', CONDITIONAL_GO: '#ca8a04', NO_GO: '#dc2626' };

export default function ReportsPanel({ projectId }: { projectId: number }) {
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [detail, setDetail] = useState<TestReport | null>(null);
  const [error, setError] = useState('');
  const [summarizing, setSummarizing] = useState(false);

  const load = useCallback(async () => {
    try {
      setReports(await reportsApi.list(projectId));
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const openReport = async (runId: number) => {
    try {
      setDetail(await reportsApi.get(runId));
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const generateSummary = async () => {
    if (!detail) return;
    setSummarizing(true);
    setError('');
    try {
      const summary = await reportsApi.generateQualitySummary(detail.id);
      setDetail({ ...detail, quality_summary: summary });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSummarizing(false);
    }
  };

  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>报告</h2>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <table style={{ marginTop: 12 }}>
        <thead>
          <tr>
            <th>Run</th>
            <th>通过率</th>
            <th>通过/失败</th>
            <th>推荐结论</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((r) => (
            <tr key={r.id}>
              <td>{r.run_id} · {r.summary.run_name}</td>
              <td>{(r.summary.pass_rate * 100).toFixed(1)}%</td>
              <td>{r.summary.passed}/{r.summary.failed}</td>
              <td>
                {r.recommendation ? (
                  <span className="badge" style={{ background: REC_COLOR[r.recommendation] ?? '#6b7280', color: '#fff' }}>
                    {r.recommendation}
                  </span>
                ) : (
                  <span className="hint">—</span>
                )}
              </td>
              <td className="hint">{formatTime(r.created_at)}</td>
              <td>
                <button className="link" onClick={() => openReport(r.run_id)}>详情</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {detail && (
        <div className="card" style={{ marginTop: 12, background: '#fafbff' }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>
            报告 Run #{detail.run_id} — {detail.summary.run_name}
          </h3>
          <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
            <span>总数 {detail.summary.total}</span>
            <span className="hint">通过 {detail.summary.passed}</span>
            <span className="hint">失败 {detail.summary.failed}</span>
            <span className="hint">阻塞 {detail.summary.blocked}</span>
            <span>通过率 {(detail.summary.pass_rate * 100).toFixed(1)}%</span>
          </div>

          {detail.stats && (
            <div style={{ marginTop: 8 }}>
              <h4 style={{ margin: '8px 0 4px', fontSize: 13 }}>失败分类分布</h4>
              <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                {Object.entries(detail.stats.failure_categories).map(([cat, n]) => (
                  <span key={cat} className="hint">{cat}: {n}</span>
                ))}
              </div>
              <h4 style={{ margin: '8px 0 4px', fontSize: 13 }}>用例明细</h4>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {detail.stats.cases.map((c, i) => (
                  <li key={i}>
                    <span className={`badge ${c.status === 'passed' ? 'status-approved' : 'status-needs_work'}`}>{c.status}</span>{' '}
                    {c.case_label}
                    {c.failure_analysis && (
                      <span className="hint"> · {c.failure_analysis.category}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {detail.quality_summary && (
            <div className="card" style={{ marginTop: 8 }}>
              <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>质量总结</h4>
              <div className="row" style={{ gap: 8, marginBottom: 6 }}>
                <span className="badge" style={{ background: REC_COLOR[detail.quality_summary.recommendation] ?? '#6b7280', color: '#fff' }}>
                  {detail.quality_summary.recommendation}
                </span>
                <span className="hint">综合分 {detail.quality_summary.overall_score}</span>
              </div>
              <div>{detail.quality_summary.reasoning}</div>
              {detail.quality_summary.risk_factors.length > 0 && (
                <ul style={{ margin: '6px 0 0', paddingLeft: 20 }}>
                  {detail.quality_summary.risk_factors.map((r, i) => (
                    <li key={i} className="hint">{r}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="row" style={{ gap: 8, marginTop: 12 }}>
            <a className="button primary" href={reportsApi.htmlUrl(detail.run_id)} target="_blank" rel="noreferrer">
              打开 HTML 报告
            </a>
            <a className="button" href={reportsApi.exportUrl(detail.run_id, 'json')} download>
              导出 JSON
            </a>
            <a className="button" href={reportsApi.exportUrl(detail.run_id, 'markdown')} download>
              导出 Markdown
            </a>
            {!detail.quality_summary && (
              <button className="primary" onClick={generateSummary} disabled={summarizing}>
                {summarizing ? '生成中…' : '生成质量总结'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
