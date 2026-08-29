import type { PendingAction } from "../types";

type ConfirmStageProps = {
  action: PendingAction;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
};

export function ConfirmStage({ action, onConfirm, onCancel, loading }: ConfirmStageProps) {
  return (
    <section className="metro-panel confirm-stage" aria-labelledby="confirm-title">
      <p className="metro-kicker">Permission · {action.level}</p>
      <h2 id="confirm-title" className="metro-title">
        需要你确认
      </h2>
      <p className="metro-lead">{action.message}</p>
      <div className="metro-actions">
        <button type="button" className="metro-btn metro-btn--ghost" onClick={onCancel} disabled={loading}>
          取消
        </button>
        <button type="button" className="metro-btn metro-btn--primary" onClick={onConfirm} disabled={loading}>
          {loading ? "处理中…" : "确认 · Proceed"}
        </button>
      </div>
    </section>
  );
}
