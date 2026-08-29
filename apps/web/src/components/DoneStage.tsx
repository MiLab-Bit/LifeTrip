type DoneStageProps = {
  lineCode: string;
  title: string;
  onRestart: () => void;
};

export function DoneStage({ lineCode, title, onRestart }: DoneStageProps) {
  return (
    <section className="metro-panel done-stage">
      <p className="metro-kicker">{lineCode} · 终到站</p>
      <h2 className="metro-title">今日线路已走完</h2>
      <p className="metro-lead">
        「{title}」——潮流 city walk 不在清单里打勾，在街角多停的那一分钟。
      </p>
      <div className="metro-actions" style={{ justifyContent: "center" }}>
        <button
          type="button"
          className="metro-btn metro-btn--primary"
          onClick={onRestart}
        >
          再选一条线 · Transfer
        </button>
      </div>
    </section>
  );
}
