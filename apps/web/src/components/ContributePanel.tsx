import { useEffect, useState } from "react";
import type { VibeId } from "../types";

const VIBES: { id: VibeId; label: string }[] = [
  { id: "coffee", label: "咖啡巡游" },
  { id: "vintage", label: "古着淘街" },
  { id: "gallery", label: "画廊串游" },
  { id: "neon", label: "夜行霓虹" },
];

type ContributePanelProps = {
  onBack: () => void;
};

export function ContributePanel({ onBack }: ContributePanelProps) {
  const [form, setForm] = useState({
    name: "",
    vibe: "coffee" as VibeId,
    city: "上海",
    district: "",
    lat: "",
    lng: "",
    headline: "",
    body: "",
    tip: "",
    tags: "",
    indoor: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [contributions, setContributions] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    fetch("/v1/poi/contributions?limit=10")
      .then((r) => r.json())
      .then((d) => setContributions(d.contributions ?? []))
      .catch(() => {});
  }, [result]);

  const handleSubmit = async () => {
    if (!form.name || !form.headline || !form.body || !form.lat || !form.lng) {
      setResult("请填写名称、亮点、理由和坐标");
      return;
    }
    setSubmitting(true);
    try {
      const sid = localStorage.getItem("lifetrip_session_id") || crypto.randomUUID();
      localStorage.setItem("lifetrip_session_id", sid);
      const r = await fetch(`/v1/poi/contribute?session_id=${sid}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          vibe: form.vibe,
          city: form.city,
          district: form.district,
          lat: parseFloat(form.lat),
          lng: parseFloat(form.lng),
          headline: form.headline,
          body: form.body,
          tip: form.tip,
          tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
          indoor: form.indoor,
        }),
      });
      const data = await r.json();
      setResult(`✅ ${data.message || "投稿成功！"}`);
      setForm({ ...form, name: "", headline: "", body: "", tip: "", tags: "" });
    } catch {
      setResult("投稿失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="metro-panel contribute-panel">
      <p className="metro-kicker">UGC · POI 投稿</p>
      <h2 className="metro-title">推荐一个好地方</h2>
      <p className="metro-lead">你发现的宝藏地点，投稿后审核通过即可出现在漫步线路中。</p>

      <div className="contribute-form">
        <div className="form-row">
          <label>名称 *</label>
          <input
            className="metro-input"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="比如：安福路的小众咖啡馆"
          />
        </div>

        <div className="form-row form-row--2col">
          <div>
            <label>主题</label>
            <select className="metro-select" value={form.vibe} onChange={(e) => setForm({ ...form, vibe: e.target.value as VibeId })}>
              {VIBES.map((v) => (
                <option key={v.id} value={v.id}>{v.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label>城市</label>
            <select className="metro-select" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })}>
              <option value="上海">上海</option>
              <option value="北京">北京</option>
              <option value="杭州">杭州</option>
              <option value="成都">成都</option>
            </select>
          </div>
        </div>

        <div className="form-row form-row--2col">
          <div>
            <label>纬度 *</label>
            <input className="metro-input" value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} placeholder="31.2102" />
          </div>
          <div>
            <label>经度 *</label>
            <input className="metro-input" value={form.lng} onChange={(e) => setForm({ ...form, lng: e.target.value })} placeholder="121.4401" />
          </div>
        </div>

        <div className="form-row">
          <label>一句话亮点 *</label>
          <input className="metro-input" value={form.headline} onChange={(e) => setForm({ ...form, headline: e.target.value })} placeholder="窗口位最适合拍照" />
        </div>

        <div className="form-row">
          <label>推荐理由 *</label>
          <textarea className="metro-textarea" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} placeholder="为什么值得走一趟..." rows={3} />
        </div>

        <div className="form-row">
          <label>小贴士</label>
          <input className="metro-input" value={form.tip} onChange={(e) => setForm({ ...form, tip: e.target.value })} placeholder="下午 4 点前最好" />
        </div>

        <div className="form-row">
          <label>标签（逗号分隔）</label>
          <input className="metro-input" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="手冲, 安静, 窗口位" />
        </div>

        {result && <p className="contribute-result">{result}</p>}

        <div className="metro-actions">
          <button type="button" className="metro-btn metro-btn--primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "提交中…" : "📝 投稿"}
          </button>
          <button type="button" className="metro-btn metro-btn--ghost" onClick={onBack}>
            返回
          </button>
        </div>
      </div>

      {contributions.length > 0 && (
        <div className="contributions-list">
          <h3 className="metro-subtitle">最近投稿</h3>
          {contributions.map((c, i) => (
            <div key={i} className="contribution-item">
              <span className="contrib-name">{c.name as string}</span>
              <span className="contrib-city">{c.city as string}</span>
              <span className={`contrib-status contrib-status--${c.status as string}`}>{c.status as string}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
