import type { WalkTask } from "../types";

type ResumeBannerProps = {
  task: WalkTask;
  onResume: () => void;
  onDismiss: () => void;
};

export function ResumeBanner({ task, onResume, onDismiss }: ResumeBannerProps) {
  const stop = task.route.stops[task.current_stop_index];
  return (
    <aside className="resume-banner" role="status">
      <p>
        你有未完成的走线：<strong>{task.route.title}</strong>
        {stop ? ` · 当前 ${stop.code} ${stop.name}` : ""}
      </p>
      <div className="resume-banner__actions">
        <button type="button" className="metro-btn metro-btn--primary metro-btn--sm" onClick={onResume}>
          继续
        </button>
        <button type="button" className="metro-btn metro-btn--ghost metro-btn--sm" onClick={onDismiss}>
          新建
        </button>
      </div>
    </aside>
  );
}
