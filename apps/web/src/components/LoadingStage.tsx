const TICKERS = [
  "SIGNAL · 扫描街区热度",
  "ROUTE · 拼接步行段",
  "SYNC · 对齐当下店招",
  "READY · 即将进站",
];

type LoadingStageProps = {
  lineCode: string;
  title: string;
};

export function LoadingStage({ lineCode, title }: LoadingStageProps) {
  const ticker = TICKERS[Math.floor(Date.now() / 1800) % TICKERS.length];

  return (
    <section className="loading-stage" aria-busy="true" aria-live="polite">
      <div className="metro-doors" aria-hidden="true">
        <div className="metro-doors__panel metro-doors__panel--left" />
        <div className="metro-doors__panel metro-doors__panel--right" />
      </div>
      <p className="metro-kicker">{lineCode}</p>
      <h2 className="metro-title">{title}</h2>
      <p className="loading-ticker">{ticker}</p>
    </section>
  );
}
