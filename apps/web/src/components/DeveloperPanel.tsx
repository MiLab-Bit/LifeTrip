import { useEffect, useState } from "react";

type ApiKey = {
  id: string;
  key_prefix: string;
  name: string;
  created_at: string;
  is_active: boolean;
  rate_limit: number;
};

type Usage = {
  active_keys: number;
  total_keys: number;
  quota_hourly: number;
  walks_created: number;
  endpoints_available: number;
};

type DevPanelProps = {
  onBack: () => void;
};

export function DeveloperPanel({ onBack }: DevPanelProps) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [newKeyName, setNewKeyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [docs, setDocs] = useState<Array<Record<string, string>>>([]);

  const sid = localStorage.getItem("lifetrip_session_id") || crypto.randomUUID();
  if (!localStorage.getItem("lifetrip_session_id")) localStorage.setItem("lifetrip_session_id", sid);

  const refresh = () => {
    fetch(`/v1/dev/api-keys?session_id=${sid}`)
      .then((r) => r.json())
      .then((d) => setKeys(d.keys ?? []))
      .catch(() => {});
    fetch(`/v1/dev/usage?session_id=${sid}`)
      .then((r) => r.json())
      .then((d) => setUsage(d))
      .catch(() => {});
    fetch("/v1/dev/docs")
      .then((r) => r.json())
      .then((d) => setDocs(d.endpoints ?? []))
      .catch(() => {});
  };

  useEffect(() => { refresh(); }, []);

  const handleCreate = async () => {
    if (!newKeyName.trim()) return;
    setCreating(true);
    try {
      const r = await fetch(`/v1/dev/api-keys?session_id=${sid}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newKeyName }),
      });
      const data = await r.json();
      setCreatedKey(data.key);
      setNewKeyName("");
      refresh();
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    await fetch(`/v1/dev/api-keys/${keyId}?session_id=${sid}`, { method: "DELETE" });
    refresh();
  };

  return (
    <section className="metro-panel developer-panel">
      <p className="metro-kicker">API · 开发者平台</p>
      <h2 className="metro-title">Developer API</h2>
      <p className="metro-lead">用 API Key 接入 LifeTrip 规划引擎，把 city walk 能力集成到你的应用。</p>

      {/* Usage stats */}
      {usage && (
        <div className="dev-stats-strip">
          <div className="dev-stat">
            <span className="dev-stat-val">{usage.active_keys}</span>
            <span className="dev-stat-lbl">活跃 Key</span>
          </div>
          <div className="dev-stat">
            <span className="dev-stat-val">{usage.quota_hourly}</span>
            <span className="dev-stat-lbl">小时配额</span>
          </div>
          <div className="dev-stat">
            <span className="dev-stat-val">{usage.endpoints_available}</span>
            <span className="dev-stat-lbl">API 端点</span>
          </div>
          <div className="dev-stat">
            <span className="dev-stat-val">{usage.walks_created}</span>
            <span className="dev-stat-lbl">漫步记录</span>
          </div>
        </div>
      )}

      {/* Create key */}
      <div className="dev-create-key">
        <h3 className="metro-subtitle">创建 API Key</h3>
        <div className="key-create-row">
          <input
            className="metro-input"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            placeholder="给 key 起个名字"
          />
          <button type="button" className="metro-btn metro-btn--primary" onClick={handleCreate} disabled={creating}>
            {creating ? "生成中…" : "🔑 生成 Key"}
          </button>
        </div>
        {createdKey && (
          <div className="key-created-alert">
            <p>⚠️ 这是唯一一次显示完整密钥，请立即保存：</p>
            <code className="key-full">{createdKey}</code>
            <button type="button" className="metro-btn metro-btn--sm" onClick={() => {
              navigator.clipboard?.writeText(createdKey);
            }}>📋 复制</button>
          </div>
        )}
      </div>

      {/* Key list */}
      {keys.length > 0 && (
        <div className="dev-key-list">
          <h3 className="metro-subtitle">我的 API Keys</h3>
          {keys.map((k) => (
            <div key={k.id} className="dev-key-item">
              <div className="dev-key-info">
                <span className="dev-key-name">{k.name}</span>
                <code className="dev-key-prefix">{k.key_prefix}…</code>
                <span className={`dev-key-status ${k.is_active ? "active" : "revoked"}`}>
                  {k.is_active ? "✓ 活跃" : "✗ 已吊销"}
                </span>
              </div>
              {k.is_active && (
                <button type="button" className="metro-btn metro-btn--sm metro-btn--ghost" onClick={() => handleRevoke(k.id)}>
                  吊销
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* API docs */}
      <div className="dev-docs">
        <h3 className="metro-subtitle">API 端点文档</h3>
        <p className="metro-lead" style={{ fontSize: 14 }}>认证方式：请求头 <code>Authorization: Bearer YOUR_KEY</code> 或 query <code>?api_key=YOUR_KEY</code></p>
        <div className="api-endpoint-list">
          {docs.map((ep, i) => (
            <div key={i} className="api-endpoint-item">
              <span className={`api-method api-method--${ep.method}`}>{ep.method}</span>
              <code className="api-path">{ep.path}</code>
              <span className="api-desc">{ep.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Code example */}
      <div className="dev-code-example">
        <h3 className="metro-subtitle">快速开始</h3>
        <pre className="code-block">{`# 1. 规划一条漫步
curl -X POST https://lifetrip.sy-realm.ltd/v1/walks/plan \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"vibe":"coffee","district_id":"anfu-wukang","duration_min":90}'

# 2. 查看探索图谱
curl https://lifetrip.sy-realm.ltd/v1/explore/SESSION_ID \\
  -H "Authorization: Bearer YOUR_API_KEY"`}</pre>
      </div>

      <div className="metro-actions" style={{ marginTop: 16 }}>
        <button type="button" className="metro-btn metro-btn--ghost" onClick={onBack}>返回</button>
      </div>
    </section>
  );
}
