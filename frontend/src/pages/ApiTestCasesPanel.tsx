import { useCallback, useEffect, useState } from 'react';
import { apiTestCasesApi } from '../api/apiTestCases';
import { errorMessage } from '../api/client';
import type { ApiTestCase } from '../types';

export default function ApiTestCasesPanel({ projectId }: { projectId: number }) {
  const [cases, setCases] = useState<ApiTestCase[]>([]);
  const [description, setDescription] = useState('');
  const [generating, setGenerating] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [method, setMethod] = useState('POST');
  const [url, setUrl] = useState('/api/demo-api/login');
  const [assertionsJson, setAssertionsJson] = useState('[{"type":"status","expected":200}]');

  const load = useCallback(async () => {
    try {
      setCases(await apiTestCasesApi.list(projectId));
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const generate = async () => {
    if (!description.trim()) return;
    setGenerating(true);
    setError('');
    setWarnings([]);
    try {
      const result = await apiTestCasesApi.generate(projectId, description);
      setWarnings(result.warnings);
      await load();
    } catch (err) {
      // B-2: AI 输出偶发不确定（非确定性模型），给出可重试引导而非笼统失败。
      setError(`${errorMessage(err)}（AI 输出偶发不确定，可直接重试生成）`);
    } finally {
      setGenerating(false);
    }
  };

  const createManual = async () => {
    setError('');
    try {
      const assertions = JSON.parse(assertionsJson);
      await apiTestCasesApi.create(projectId, { name, method, url, assertions });
      setName('');
      await load();
    } catch (err) {
      setError(errorMessage(err) + '（断言 JSON 需合法）');
    }
  };

  const toggleArchive = async (c: ApiTestCase) => {
    try {
      await apiTestCasesApi.update(c.id, { status: c.status === 'active' ? 'archived' : 'active' });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>接口用例</h2>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ background: '#fafbff', marginTop: 12 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>粘贴接口描述，AI 生成用例</h3>
        <div className="field">
          <textarea
            rows={4}
            placeholder="例如：登录接口 POST /api/demo-api/login，成功返回 token；错误凭据返回 401；缺失参数返回 400"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <button className="primary" onClick={generate} disabled={generating || !description.trim()}>
          {generating ? '生成中…' : 'AI 生成'}
        </button>
        {warnings.length > 0 && (
          <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
            {warnings.map((w, i) => <li key={i} className="hint">{w}</li>)}
          </ul>
        )}
      </div>

      <div className="card" style={{ background: '#fafbff', marginTop: 12 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>手动创建</h3>
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <input placeholder="名称" value={name} onChange={(e) => setName(e.target.value)} />
          <select value={method} onChange={(e) => setMethod(e.target.value)}>
            {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <input placeholder="URL（相对路径）" value={url} onChange={(e) => setUrl(e.target.value)} />
        </div>
        <div className="field">
          <label>断言（JSON）</label>
          <textarea rows={3} value={assertionsJson} onChange={(e) => setAssertionsJson(e.target.value)} />
        </div>
        <button className="primary" onClick={createManual} disabled={!name.trim()}>创建</button>
      </div>

      <table style={{ marginTop: 12 }}>
        <thead>
          <tr><th>method</th><th>url</th><th>名称</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr key={c.id}>
              <td>{c.method}</td>
              <td>{c.url}</td>
              <td>{c.name}</td>
              <td><span className={`badge ${c.status === 'active' ? 'status-approved' : 'status-archived'}`}>{c.status}</span></td>
              <td>
                <button className="link" onClick={() => toggleArchive(c)}>
                  {c.status === 'active' ? '归档' : '恢复'}
                </button>
                <button className="link" onClick={() => apiTestCasesApi.del(c.id).then(load)}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
