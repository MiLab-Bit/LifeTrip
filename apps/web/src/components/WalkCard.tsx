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

    const W = 1080;
    const H = 1400;
    canvas.width = W;
    canvas.height = H;

    // ═══ Background: deep space with grid ═══
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    bgGrad.addColorStop(0, "#0a0a0f");
    bgGrad.addColorStop(0.5, "#0f0f1a");
    bgGrad.addColorStop(1, "#1a0f1a");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // Neon grid lines (subtle)
    ctx.strokeStyle = "rgba(45, 212, 191, 0.08)";
    ctx.lineWidth = 1;
    for (let i = 0; i < H; i += 60) {
      ctx.beginPath();
      ctx.moveTo(0, i);
      ctx.lineTo(W, i);
      ctx.stroke();
    }
    for (let i = 0; i < W; i += 60) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i, H);
      ctx.stroke();
    }

    // Helper: hex to rgb for stroke
    function hexToRgb(hex: string): string {
      const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      return result
        ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
        : "255, 255, 255";
    }

    // ═══ Top brand with glow ═══
    ctx.shadowColor = "#2dd4bf";
    ctx.shadowBlur = 20;
    ctx.fillStyle = "#2dd4bf";
    ctx.font = "bold 28px 'Segoe UI', sans-serif";
    ctx.fillText("LifeTrip", 60, 80);
    ctx.shadowBlur = 0;

    ctx.fillStyle = "rgba(255,255,255,0.4)";
    ctx.font = "16px 'Segoe UI', sans-serif";
    ctx.fillText("· 城市漫步", 180, 80);

    // Card ID (top right)
    ctx.fillStyle = "rgba(255,255,255,0.3)";
    ctx.font = "14px monospace";
    ctx.textAlign = "right";
    ctx.fillText(`#${card_id}`, W - 60, 80);
    ctx.textAlign = "left";

    // ═══ Line code badge (neon pill) ═══
    const badgeX = 60;
    const badgeY = 120;
    const badgeW = 160;
    const badgeH = 50;
    
    // Glow
    ctx.shadowColor = "#e94560";
    ctx.shadowBlur = 25;
    ctx.fillStyle = "#e94560";
    ctx.beginPath();
    ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 25);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Text
    ctx.fillStyle = "#fff";
    ctx.font = "bold 24px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(route.lineCode, badgeX + badgeW / 2, badgeY + 32);
    ctx.textAlign = "left";

    // ═══ Main title ═══
    ctx.fillStyle = "#fff";
    ctx.font = "bold 48px 'Segoe UI', sans-serif";
    ctx.shadowColor = "rgba(255,255,255,0.3)";
    ctx.shadowBlur = 10;
    ctx.fillText(route.lineName.slice(0, 18), 60, 230);
    ctx.shadowBlur = 0;

    // Subtitle
    ctx.fillStyle = "rgba(255,255,255,0.6)";
    ctx.font = "22px 'Segoe UI', sans-serif";
    ctx.fillText(route.title.slice(0, 28), 60, 270);

    // ═══ Stats row (neon cards) ═══
    const statsY = 340;
    const statsData = [
      { label: "站点", value: `${stops.length}`, color: "#2dd4bf" },
      { label: "时长", value: `${route.totalMin}分钟`, color: "#e94560" },
      { label: "距离", value: `${((route.distanceM ?? 0) / 1000).toFixed(1)} km`, color: "#fbbf24" },
    ];

    statsData.forEach((s, i) => {
      const x = 60 + i * 300;
      const cardW = 260;
      const cardH = 90;

      // Card bg
      ctx.fillStyle = "rgba(255,255,255,0.05)";
      ctx.strokeStyle = `rgba(${hexToRgb(s.color)}, 0.3)`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(x, statsY, cardW, cardH, 12);
      ctx.fill();
      ctx.stroke();

      // Value (neon)
      ctx.shadowColor = s.color;
      ctx.shadowBlur = 15;
      ctx.fillStyle = s.color;
      ctx.font = "bold 36px 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(s.value, x + cardW / 2, statsY + 45);
      ctx.shadowBlur = 0;

      // Label
      ctx.fillStyle = "rgba(255,255,255,0.5)";
      ctx.font = "14px 'Segoe UI', sans-serif";
      ctx.fillText(s.label, x + cardW / 2, statsY + 70);
    });
    ctx.textAlign = "left";

    // ═══ Route line visualization ═══
    const routeY = 480;
    
    // Route track
    ctx.strokeStyle = "rgba(45, 212, 191, 0.3)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(60, routeY + 60);
    ctx.lineTo(W - 60, routeY + 60);
    ctx.stroke();

    // Stop dots
    const dotSpacing = (W - 140) / Math.max(stops.length - 1, 1);
    stops.forEach((stop: Stop, i: number) => {
      const x = 60 + i * dotSpacing;
      
      // Outer glow
      ctx.shadowColor = stop.skipped ? "rgba(255,255,255,0.2)" : "#2dd4bf";
      ctx.shadowBlur = 15;
      
      // Dot
      ctx.fillStyle = stop.skipped ? "rgba(255,255,255,0.2)" : "#2dd4bf";
      ctx.beginPath();
      ctx.arc(x, routeY + 60, 8, 0, Math.PI * 2);
      ctx.fill();
      
      // Number
      ctx.shadowBlur = 0;
      ctx.fillStyle = "#0a0a0f";
      ctx.font = "bold 11px 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`${i + 1}`, x, routeY + 64);
    });
    ctx.textAlign = "left";

    // ═══ Stops list (neon list items) ═══
    let yPos = 650;
    ctx.font = "18px 'Segoe UI', sans-serif";
    
    (stops as Stop[]).forEach((stop: Stop, i: number) => {
      if (yPos > H - 280) return;
      
      const opacity = stop.skipped ? 0.3 : 1;
      const nameColor = stop.skipped ? "rgba(255,255,255,0.3)" : "#fff";
      
      // Stop number badge
      ctx.fillStyle = stop.skipped ? "rgba(255,255,255,0.2)" : "#e94560";
      ctx.shadowColor = stop.skipped ? "none" : "#e94560";
      ctx.shadowBlur = stop.skipped ? 0 : 12;
      ctx.beginPath();
      ctx.arc(75, yPos - 8, 14, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      
      // Number
      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`${i + 1}`, 75, yPos - 4);
      
      // Stop name
      ctx.fillStyle = nameColor;
      ctx.font = `${stop.skipped ? "italic " : ""}18px 'Segoe UI', sans-serif`;
      ctx.textAlign = "left";
      ctx.globalAlpha = opacity;
      ctx.fillText(stop.name, 110, yPos);
      
      // Walk time (if available)
      if (stop.walkMin && !stop.skipped) {
        ctx.fillStyle = "rgba(255,255,255,0.4)";
        ctx.font = "14px 'Segoe UI', sans-serif";
        ctx.fillText(`${stop.walkMin}分钟`, W - 80, yPos);
      }
      
      ctx.globalAlpha = 1;
      yPos += 42;
    });

    // ═══ WalkDNA section (bottom neon card) ═══
    if (profile && profile.completed_walks > 0) {
      const dnaY = H - 240;
      const dnaH = 140;
      
      // Card bg with gradient
      const dnaGrad = ctx.createLinearGradient(60, dnaY, 60, dnaY + dnaH);
      dnaGrad.addColorStop(0, "rgba(45, 212, 191, 0.1)");
      dnaGrad.addColorStop(1, "rgba(45, 212, 191, 0.03)");
      ctx.fillStyle = dnaGrad;
      ctx.strokeStyle = "rgba(45, 212, 191, 0.3)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(60, dnaY, W - 120, dnaH, 16);
      ctx.fill();
      ctx.stroke();
      
      // Label
      ctx.shadowColor = "#2dd4bf";
      ctx.shadowBlur = 10;
      ctx.fillStyle = "#2dd4bf";
      ctx.font = "bold 18px 'Segoe UI', sans-serif";
      ctx.textAlign = "left";
      ctx.fillText("🧬 WalkDNA", 80, dnaY + 40);
      ctx.shadowBlur = 0;
      
      // Stats
      ctx.fillStyle = "#fff";
      ctx.font = "16px 'Segoe UI', sans-serif";
      ctx.fillText(`${profile.completed_walks} 次漫步`, 80, dnaY + 75);
      ctx.fillText(`${profile.badges.length} 枚徽章`, 240, dnaY + 75);
      
      // DNA bars
      const dnaPrefs = profile.dna_prefs || {};
      const prefs = [
        { key: "coffee", label: "咖啡", color: "#92400e" },
        { key: "neon", label: "夜行", color: "#e94560" },
        { key: "vintage", label: "复古", color: "#7c3aed" },
        { key: "gallery", label: "艺文", color: "#2dd4bf" },
      ];
      
      let barX = 80;
      prefs.forEach((p) => {
        const val = (dnaPrefs as any)[p.key] || 0;
        const barW = 100;
        const barH = 8;
        
        // Track
        ctx.fillStyle = "rgba(255,255,255,0.1)";
        ctx.beginPath();
        ctx.roundRect(barX, dnaY + 95, barW, barH, 4);
        ctx.fill();
        
        // Fill
        ctx.fillStyle = p.color;
        ctx.shadowColor = p.color;
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.roundRect(barX, dnaY + 95, barW * val, barH, 4);
        ctx.fill();
        ctx.shadowBlur = 0;
        
        // Label
        ctx.fillStyle = "rgba(255,255,255,0.5)";
        ctx.font = "12px 'Segoe UI', sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(p.label, barX + barW / 2, dnaY + 120);
        
        barX += 140;
      });
    }

    // ═══ Footer ═══
    ctx.fillStyle = "rgba(255,255,255,0.3)";
    ctx.font = "14px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("LifeTrip — 帮你办完一件事的城市漫步", W / 2, H - 35);
    
    // QR placeholder (bottom right)
    ctx.fillStyle = "rgba(255,255,255,0.1)";
    ctx.fillRect(W - 120, H - 80, 60, 60);
    ctx.fillStyle = "rgba(255,255,255,0.3)";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    ctx.fillText("QR", W - 90, H - 45);
    
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
