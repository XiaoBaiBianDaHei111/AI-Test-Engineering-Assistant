# qaMode 真实报错样本（Phase 7 规则签名 Golden 数据）

此目录用于存放各 qaMode 下 demo 应用登录用例的**真实 Python Playwright 报错文本**，
由 `backend/scripts/capture_qa_mode_errors.py` 在浏览器可用时采集，命名约定：

- `selector-change.txt`
- `logic-bug.txt`
- `slow-network.txt`
- `auth-break.txt`

## 当前状态：验证缺口（环境门控）

本沙箱环境无 chromium 子进程（Phase 5 D6 / R005-A005 环境门控前置），
因此**样本尚未采集**。Phase 7 将以「已知 Python 报错模式 + 规则层单测」兜底：

- `waiting for get_by_test_id(...)`
- `resolved to 0 elements`
- `strict mode violation`
- `Timeout ...ms exceeded`

待浏览器就绪环境（Docker / 本地 `playwright install chromium`）时，运行：

```bash
cd backend
python scripts/capture_qa_mode_errors.py
```

生成样本后，`tests/test_qa_mode_error_fixtures.py` 会锁定每个样本非空。
