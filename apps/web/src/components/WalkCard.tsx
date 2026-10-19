import { useCallback, useRef, useState } from "react";
import type { WalkCardData, Stop } from "../types";

type WalkCardProps = {
  cardData: WalkCardData;
};

export function WalkCard({ cardData }: WalkCardProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [imageReady, setImageReady] = useState(false);
  const [shareLink, setShareLink] = useState<string | null>(null);

  const { task, profile, card_id } = cardData;
  const route = task.route;
  const stops = route.stops;

  const generateImage = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = 750;
    const H = 1100;
    canvas.width = W;
    canvas.height = H;

    // Background gradient
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, "#1a1a2e");
    grad.addColorStop(0.5, "#16213e");
    grad.addColorStop(1, "#0f3460");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);

    // Top brand
    ctx.fillStyle = "#e94560";
    ctx.font = "bold 22px sans-serif";
    ctx.fillText("LifeTrip · 城市漫步", 40, 60);

    // Card ID
    ctx.fillStyle = "rgba(255,255,255,0.4)";
    ctx.font = "14px monospace";
    ctx.fillText(`#${card_id}`, W - 100, 60);

    // Line code badge
    ctx.fillStyle = "#e94560";
    ctx.beginPath();
    ctx.roundRect(40, 90, 120, 36, 8);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "bold 18px sans-serif";
    ctx.fillText(route.lineCode, 55, 114);

    // Title
    ctx.fillStyle = "#fff";
    ctx.font = "bold 36px sans-serif";
    ctx.fillText(route.lineName.slice(0, 14), 40, 175);
    ctx.font = "20px sans-serif";
    ctx.fillStyle = "rgba(255,255,255,0.7)";
    ctx.fillText(route.title.slice(0, 20), 40, 210);

    // Stats row
    const statsY = 270;
    ctx.fillStyle = "rgba(255,255,255,0.15)";
    ctx.fillRect(40, statsY, W - 80, 80);
    ctx.fillStyle = "#fff";
    ctx.textAlign = "center";
    const stats = [
      { label: "站点", value: `${stops.length}` },
      { label: "时长", value: `${route.totalMin}分钟` },
      { label: "距离", value: `${((route.distanceM ?? 0) / 1000).toFixed(1)}km` },
    ];
    stats.forEach((s, i) => {
      const x = W * (0.25 + i * 0.25);
      ctx.font = "bold 28px sans-serif";
      ctx.fillText(s.value, x, statsY + 38);
      ctx.font = "14px sans-serif";
      ctx.fillStyle = "rgba(255,255,255,0.5)";
      ctx.fillText(s.label, x, statsY + 62);
      ctx.fillStyle = "#fff";
    });
    ctx.textAlign = "left";

    // Stops list
    let yPos = 400;
    ctx.font = "15px sans-serif";
    (stops as Stop[]).forEach((stop: Stop) => {
      if (yPos > H - 200) return;
      // Bullet
      ctx.beginPath();
      ctx.arc(55, yPos - 5, 5, 0, Math.PI * 2);
      ctx.fillStyle = stop.skipped ? "rgba(255,255,255,0.2)" : "#e94560";
      ctx.fill();
      // Stop name
      ctx.fillStyle = stop.skipped ? "rgba(255,255,255,0.3)" : "#fff";
      ctx.fillText(`${stop.code} ${stop.name}`, 75, yPos);
      yPos += 35;
    });

    // WalkDNA teaser
    if (profile && profile.completed_walks > 0) {
      yPos = H - 180;
      ctx.fillStyle = "rgba(233,69,96,0.15)";
      ctx.fillRect(40, yPos - 25, W - 80, 60);
      ctx.fillStyle = "#e94560";
      ctx.font = "14px sans-serif";
      ctx.fillText(`🧬 WalkDNA · ${profile.completed_walks} 次漫步 · ${profile.badges.length} 枚徽章`, 55, yPos + 5);
    }

    // Footer
    ctx.fillStyle = "rgba(255,255,255,0.3)";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("LifeTrip — 帮你办完一件事的城市漫步", W / 2, H - 30);
    ctx.textAlign = "left";

    setImageReady(true);
    setShareLink(canvas.toDataURL("image/png"));
  }, [card_id, route, stops, profile]);

  const handleDownload = () => {
    if (!shareLink) return;
    const a = document.createElement("a");
    a.href = shareLink;
    a.download = `lifetrip-${route.lineCode}.png`;
    a.click();
  };

  const handleShare = async () => {
    if (!canvasRef.current) return;
    canvasRef.current.toBlob(async (blob: Blob | null) => {
      if (!blob) return;
      const file = new File([blob], `lifetrip-${route.lineCode}.png`, { type: "image/png" });
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: route.lineName });
      } else {
        handleDownload();
      }
    }, "image/png");
  };

  return (
    <div className="walk-card-section">
      <canvas ref={canvasRef} style={{ display: "none" }} />
      {!imageReady && (
        <button
          type="button"
          className="metro-btn metro-btn--primary walk-card-generate"
          onClick={generateImage}
        >
          🎴 生成漫步卡片
        </button>
      )}
      {imageReady && shareLink && (
        <div className="walk-card-preview">
          <img src={shareLink} alt="漫步卡片" className="walk-card-img" />
          <div className="walk-card-actions">
            <button type="button" className="metro-btn metro-btn--primary" onClick={handleShare}>
              📤 分享
            </button>
            <button type="button" className="metro-btn" onClick={handleDownload}>
              💾 保存图片
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
