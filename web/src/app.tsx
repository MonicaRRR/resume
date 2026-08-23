export function App() {
  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="简历证据工作台首页">
          <span className="brand-mark" aria-hidden="true">证</span>
          <span>简历证据工作台</span>
        </a>
        <div className="local-badge">
          <span className="status-dot" aria-hidden="true" />
          简历默认只保存在本机
        </div>
      </header>

      <section className="empty-canvas" aria-labelledby="workspace-title">
        <p className="eyebrow">RESUME EVIDENCE DESK</p>
        <h1 id="workspace-title">简历证据工作台</h1>
        <p className="lead">把岗位要求、真实经历和每一次修改放在同一条证据链上。</p>
        <button type="button" disabled>正在准备项目工作区</button>
      </section>
    </main>
  );
}
