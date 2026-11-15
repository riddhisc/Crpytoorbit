import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import type { Summary } from "@/api/client";
import { formatInr, formatQty, prefersReducedMotion } from "@/lib/format";

export function OrbitView({ summary }: { summary: Summary }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const navigate = useNavigate();
  const holdings = summary.holdings;

  useEffect(() => {
    const node = canvas.current;
    if (!node) return;
    const context = node.getContext("2d");
    if (!context) return;
    let frame = 0;
    let running = true;
    const reduced = prefersReducedMotion();
    const observer = new IntersectionObserver(([entry]) => {
      running = entry?.isIntersecting ?? true;
    });
    observer.observe(node);
    const onHide = () => {
      running = document.visibilityState === "visible";
    };
    document.addEventListener("visibilitychange", onHide);

    const draw = (time: number) => {
      if (!running && !reduced) {
        frame = requestAnimationFrame(draw);
        return;
      }
      const ratio = window.devicePixelRatio || 1;
      const width = node.clientWidth;
      const height = 420;
      node.width = width * ratio;
      node.height = height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--bg") || "#070912";
      context.fillRect(0, 0, width, height);
      const cx = width / 2;
      const cy = height / 2;
      context.beginPath();
      context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--accent") || "#b3a6ff";
      context.arc(cx, cy, 28, 0, Math.PI * 2);
      context.fill();
      context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text") || "#fff";
      context.font = "12px Inter";
      context.textAlign = "center";
      context.fillText("Ledger", cx, cy + 4);
      const ranked = [...holdings].sort((a, b) => Number(b.value_inr) - Number(a.value_inr));
      ranked.forEach((holding, index) => {
        const radius = 70 + index * 42;
        const speed = reduced ? 0 : 0.0004 / (index + 1);
        const angle = reduced ? index : time * speed + index;
        const x = cx + Math.cos(angle) * radius;
        const y = cy + Math.sin(angle) * radius * 0.62;
        context.beginPath();
        context.strokeStyle = "rgba(180,180,220,0.35)";
        context.ellipse(cx, cy, radius, radius * 0.62, 0, 0, Math.PI * 2);
        context.stroke();
        const size = Math.max(8, Math.min(22, Math.sqrt(Math.max(Number(holding.value_inr), 0)) / 18));
        context.beginPath();
        context.fillStyle = holding.open_exceptions ? "#ff8fa3" : "#8d7cff";
        context.arc(x, y, size, 0, Math.PI * 2);
        context.fill();
        context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text") || "#fff";
        context.fillText(holding.asset, x, y - size - 6);
      });
      if (!reduced) frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [holdings]);

  return (
    <div>
      <canvas ref={canvas} className="h-[420px] w-full rounded-lg border border-line" role="img" aria-label="Holdings orbit" />
      <div className="mt-2 flex flex-wrap gap-2">
        {holdings.map((holding) => (
          <button key={holding.asset} className="min-h-11 rounded-md border border-line px-3 text-sm" onClick={() => navigate(`/exceptions?asset=${holding.asset}`)}>
            {holding.asset} · {formatQty(holding.qty)} · {formatInr(holding.value_inr)}
            {holding.open_exceptions ? ` · ${holding.open_exceptions} open` : ""}
          </button>
        ))}
      </div>
      <table className="sr-only">
        <caption>Holdings</caption>
        <thead>
          <tr><th>Asset</th><th>Quantity</th><th>Value</th><th>Open exceptions</th></tr>
        </thead>
        <tbody>
          {holdings.map((holding) => (
            <tr key={holding.asset}>
              <td>{holding.asset}</td>
              <td>{formatQty(holding.qty)}</td>
              <td>{formatInr(holding.value_inr)}</td>
              <td>{holding.open_exceptions}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
