import type { ReactNode } from "react";

type MetroShellProps = {
  lineCode?: string;
  lineLabel?: string;
  children: ReactNode;
};

export function MetroShell({ lineCode, lineLabel, children }: MetroShellProps) {
  return (
    <div className="metro-shell">
      <header className="metro-header">
        <div className="metro-brand">
          <div className="metro-logo" aria-hidden="true">
            LT
          </div>
          <div className="metro-brand-text">
            <strong>LifeTrip</strong>
            <span>潮流 City Walk · 地铁美学</span>
          </div>
        </div>
        {lineCode ? (
          <div className="metro-line-badge" aria-label={`当前线路 ${lineCode}`}>
            {lineCode}
            {lineLabel ? ` · ${lineLabel}` : ""}
          </div>
        ) : null}
      </header>
      <main className="metro-main">{children}</main>
    </div>
  );
}
