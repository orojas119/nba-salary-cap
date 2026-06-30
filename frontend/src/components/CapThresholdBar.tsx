import { THRESHOLDS } from "../types";

interface Props {
  payroll: number;
  height?: number;
  showLabels?: boolean;
}

// Domain for the bar: a little below the cap to a little above the second apron,
// so every team's marker lands somewhere sensible.
const DOMAIN_MIN = 140_000_000;
const DOMAIN_MAX = 235_000_000;
const VB_WIDTH = 1000;

const ZONES = [
  { from: DOMAIN_MIN, to: THRESHOLDS.SALARY_CAP, color: "#16a34a", label: "Under Cap" },
  { from: THRESHOLDS.SALARY_CAP, to: THRESHOLDS.LUXURY_TAX, color: "#2563eb", label: "Cap" },
  { from: THRESHOLDS.LUXURY_TAX, to: THRESHOLDS.FIRST_APRON, color: "#f59e0b", label: "Tax" },
  { from: THRESHOLDS.FIRST_APRON, to: THRESHOLDS.SECOND_APRON, color: "#ea580c", label: "1st Apron" },
  { from: THRESHOLDS.SECOND_APRON, to: DOMAIN_MAX, color: "#dc2626", label: "2nd Apron" },
];

function scaleX(value: number): number {
  const clamped = Math.max(DOMAIN_MIN, Math.min(DOMAIN_MAX, value));
  return ((clamped - DOMAIN_MIN) / (DOMAIN_MAX - DOMAIN_MIN)) * VB_WIDTH;
}

export default function CapThresholdBar({
  payroll,
  height = 28,
  showLabels = false,
}: Props) {
  const markerX = scaleX(payroll);
  const barHeight = height;
  const vbHeight = showLabels ? barHeight + 22 : barHeight + 12;

  return (
    <svg
      viewBox={`0 0 ${VB_WIDTH} ${vbHeight}`}
      width="100%"
      height={vbHeight}
      preserveAspectRatio="none"
      role="img"
      aria-label={`Payroll $${payroll.toLocaleString()} relative to cap thresholds`}
    >
      {/* colored zones */}
      {ZONES.map((z) => {
        const x = scaleX(z.from);
        const w = scaleX(z.to) - x;
        return (
          <rect
            key={z.label}
            x={x}
            y={0}
            width={w}
            height={barHeight}
            fill={z.color}
            opacity={0.85}
          />
        );
      })}

      {/* threshold divider lines */}
      {[THRESHOLDS.SALARY_CAP, THRESHOLDS.LUXURY_TAX, THRESHOLDS.FIRST_APRON, THRESHOLDS.SECOND_APRON].map(
        (t) => (
          <line
            key={t}
            x1={scaleX(t)}
            x2={scaleX(t)}
            y1={0}
            y2={barHeight}
            stroke="#0f172a"
            strokeWidth={2}
          />
        )
      )}

      {/* payroll marker */}
      <line
        x1={markerX}
        x2={markerX}
        y1={-2}
        y2={barHeight + 6}
        stroke="#ffffff"
        strokeWidth={4}
      />
      <polygon
        points={`${markerX - 6},${barHeight + 6} ${markerX + 6},${barHeight + 6} ${markerX},${barHeight + 12}`}
        fill="#ffffff"
      />

      {showLabels && (
        <>
          <text x={scaleX(THRESHOLDS.SALARY_CAP)} y={vbHeight - 4} fill="#94a3b8" fontSize="11" textAnchor="middle">
            Cap
          </text>
          <text x={scaleX(THRESHOLDS.LUXURY_TAX)} y={vbHeight - 4} fill="#94a3b8" fontSize="11" textAnchor="middle">
            Tax
          </text>
          <text x={scaleX(THRESHOLDS.FIRST_APRON)} y={vbHeight - 4} fill="#94a3b8" fontSize="11" textAnchor="middle">
            1st
          </text>
          <text x={scaleX(THRESHOLDS.SECOND_APRON)} y={vbHeight - 4} fill="#94a3b8" fontSize="11" textAnchor="middle">
            2nd
          </text>
        </>
      )}
    </svg>
  );
}
