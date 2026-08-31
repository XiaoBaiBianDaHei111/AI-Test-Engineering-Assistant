// 任务管理系统（Demo 目标应用）
// qaMode 通过 URL 参数 ?qaMode= 注入，并持久化到 sessionStorage（仅当前标签页）。
// 合法凭据：testuser / Test@1234

(function () {
  var VALID_USER = 'testuser';
  var VALID_PASS = 'Test@1234';

  var params = new URLSearchParams(window.location.search);
  if (params.get('qaMode')) {
    sessionStorage.setItem('qaMode', params.get('qaMode'));
  }
  var qaMode = sessionStorage.getItem('qaMode') || 'none';

  // selector-change：data-testid 改名（演示 BROKEN_LOCATOR）
  var renameMap = {
    username: 'user-name',
    password: 'pass-word',
    'login-btn': 'login-button',
    flash: 'flash-msg',
    'task-title': 'task-title-input',
    'add-task-btn': 'add-task',
    'task-filter': 'filter',
  };
  function tid(name) {
    if (qaMode === 'selector-change') {
      return renameMap[name] || name;
    }
    return name;
  }

  function el(testid) {
    return document.querySelector('[data-testid="' + tid(testid) + '"]');
  }

  var loginSection = document.getElementById('login-section');
  var taskSection = document.getElementById('task-section');
  var tasks = [];

  function setFlash(text, ok) {
    var flash = el('flash');
    if (flash) {
      flash.textContent = text;
      flash.className = 'flash ' + (ok ? 'ok' : 'err');
    }
  }

  function renderTasks() {
    var filter = el('task-filter') ? el('task-filter').value : 'all';
    var list = el('task-list');
    if (!list) return;
    list.innerHTML = '';
    var items = tasks.filter(function (t) {
      if (filter === 'done') return t.done;
      if (filter === 'todo') return !t.done;
      return true;
    });
    items.forEach(function (t, idx) {
      var li = document.createElement('li');
      li.setAttribute('data-testid', tid('task-item'));
      li.textContent = t.title + (t.done ? '（完成）' : '');
      var doneBtn = document.createElement('button');
      doneBtn.textContent = t.done ? '取消完成' : '标记完成';
      doneBtn.addEventListener('click', function () {
        t.done = !t.done;
        renderTasks();
      });
      li.appendChild(doneBtn);
      list.appendChild(li);
    });
  }

  function handleLogin() {
    var username = el('username').value;
    var password = el('password').value;

    var submit = function () {
      // auth-break：任意凭据登录恒失败
      if (qaMode === 'auth-break') {
        setFlash('用户名或密码错误', false);
        return;
      }
      if (!username || !password) {
        setFlash('用户名或密码不能为空', false);
        return;
      }
      if (username !== VALID_USER || password !== VALID_PASS) {
        setFlash('用户名或密码错误', false);
        return;
      }
      // logic-bug：登录成功但不跳转（不显示任务区）
      if (qaMode === 'logic-bug') {
        setFlash('登录成功', true);
        return;
      }
      setFlash('登录成功', true);
      loginSection.hidden = true;
      taskSection.hidden = false;
    };

    // slow-network：人为延迟 ~2s（演示 FLAKY）
    if (qaMode === 'slow-network') {
      setTimeout(submit, 2000);
    } else {
      submit();
    }
  }

  function handleAddTask() {
    var input = el('task-title');
    var title = input.value.trim();
    if (!title) {
      setFlash('任务标题不能为空', false);
      return;
    }
    tasks.push({ title: title, done: false });
    input.value = '';
    // logic-bug：任务添加不渲染
    if (qaMode !== 'logic-bug') {
      renderTasks();
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    el('login-btn').addEventListener('click', handleLogin);
    el('add-task-btn').addEventListener('click', handleAddTask);
    el('task-filter').addEventListener('change', renderTasks);
  });
})();
