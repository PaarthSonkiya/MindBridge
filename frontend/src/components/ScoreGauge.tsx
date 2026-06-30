function bandColor(score: number): string {
  if (score >= 80) return "var(--ok)";
  if (score >= 70) return "var(--warn)";
  return "var(--danger)";
}

/** Circular Understanding Score™ gauge. */
export function ScoreGauge({ score, size = 132 }: { score: number; size?: number }) {
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score / 100);
  const color = bandColor(score);

  return (
    <div className="gauge" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 0.8s ease" }}
        />
      </svg>
      <div className="gauge-label">
        <span className="gauge-value" style={{ color }}>
          {score}
        </span>
        <span className="gauge-unit">/ 100</span>
      </div>
    </div>
  );
}
