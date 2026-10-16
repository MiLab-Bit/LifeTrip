import { useState } from "react";
import { rateWalk, publishCommunityRoute } from "../lib/api";

type RatingFormProps = {
  taskId: string;
  onDone?: () => void;
};

export function RatingForm({ taskId, onDone }: RatingFormProps) {
  const [overall, setOverall] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [published, setPublished] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (overall === 0) {
      setError("请先选择评分");
      return;
    }
    try {
      setError(null);
      await rateWalk(taskId, overall, {}, comment);
      setSubmitted(true);
    } catch {
      setError("评分提交失败");
    }
  };

  const handlePublish = async () => {
    try {
      setError(null);
      await publishCommunityRoute(taskId);
      setPublished(true);
    } catch {
      setError("发布失败");
    }
  };

  if (submitted) {
    return (
      <div className="rating-form-done">
        <p className="metro-note">✓ 评分已提交 · 感谢你的反馈</p>
        {!published && (
          <button
            type="button"
            className="metro-btn metro-btn--small"
            onClick={handlePublish}
          >
            📢 发布到社区线路
          </button>
        )}
        {published && (
          <p className="metro-note">✓ 已发布到社区 · 其他探索者可以看到你的线路了</p>
        )}
        {onDone && (
          <button type="button" className="metro-btn metro-btn--small" onClick={onDone}>
            完成
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="rating-form">
      <p className="metro-kicker">给这条线打个分</p>
      <div className="star-input-row">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            className={`star-input ${(hover || overall) >= star ? "active" : ""}`}
            onMouseEnter={() => setHover(star)}
            onMouseLeave={() => setHover(0)}
            onClick={() => setOverall(star)}
          >
            ⭐
          </button>
        ))}
      </div>
      <textarea
        className="rating-comment"
        placeholder="留一句话给后来的探索者…（可选）"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={2}
      />
      {error && <p className="metro-error">{error}</p>}
      <button
        type="button"
        className="metro-btn metro-btn--primary metro-btn--small"
        onClick={handleSubmit}
      >
        提交评分
      </button>
    </div>
  );
}
