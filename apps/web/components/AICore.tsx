"use client";

export type CoreState =
  | "IDLE"
  | "LISTENING"
  | "THINKING"
  | "PLANNING"
  | "EXECUTING"
  | "VERIFYING"
  | "COMPLETED"
  | "ERROR";

const STATE_COLORS: Record<CoreState, { main: string; soft: string; label: string }> = {
  IDLE: { main: "#22d3ee", soft: "rgba(34,211,238,0.16)", label: "System idle — awaiting command" },
  LISTENING: { main: "#34d399", soft: "rgba(52,211,153,0.16)", label: "Listening…" },
  THINKING: { main: "#a78bfa", soft: "rgba(167,139,250,0.18)", label: "Thinking…" },
  PLANNING: { main: "#a78bfa", soft: "rgba(167,139,250,0.18)", label: "Planning task…" },
  EXECUTING: { main: "#38bdf8", soft: "rgba(56,189,248,0.18)", label: "Executing…" },
  VERIFYING: { main: "#fbbf24", soft: "rgba(251,191,36,0.16)", label: "Verifying result…" },
  COMPLETED: { main: "#34d399", soft: "rgba(52,211,153,0.18)", label: "Completed ✓" },
  ERROR: { main: "#f87171", soft: "rgba(248,113,113,0.18)", label: "Error — check the message" },
};

const SPIN_SPEED: Record<CoreState, string> = {
  IDLE: "26s",
  LISTENING: "7s",
  THINKING: "5s",
  PLANNING: "6s",
  EXECUTING: "3.2s",
  VERIFYING: "8s",
  COMPLETED: "18s",
  ERROR: "30s",
};

export function coreStateLabel(state: CoreState): string {
  return STATE_COLORS[state].label;
}

export default function AICore({
  state = "IDLE",
  size = 250,
  showLabel = true,
}: {
  state?: CoreState;
  size?: number;
  showLabel?: boolean;
}) {
  const c = STATE_COLORS[state];
  const gid = `core-${state.toLowerCase()}`;
  return (
    <div className="flex flex-col items-center" role="img" aria-label={`AI core state: ${state}`}>
      <div className="relative" style={{ width: size, height: size }}>
        <div
          className="absolute inset-0 rounded-full blur-2xl transition-colors duration-700"
          style={{ background: `radial-gradient(circle, ${c.soft} 0%, transparent 65%)` }}
        />
        <svg viewBox="0 0 200 200" className="relative h-full w-full">
          <defs>
            <radialGradient id={gid} cx="50%" cy="42%" r="65%">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
              <stop offset="35%" stopColor={c.main} />
              <stop offset="100%" stopColor={c.main} stopOpacity="0.25" />
            </radialGradient>
          </defs>

          {/* outer dashed ring */}
          <g className="animate-spin-slow" style={{ transformOrigin: "100px 100px", animationDuration: SPIN_SPEED[state] }}>
            <circle cx="100" cy="100" r="94" fill="none" stroke={c.main} strokeOpacity="0.4" strokeWidth="1" strokeDasharray="3 9" />
          </g>
          {/* tick ring */}
          <g className="animate-spin-rev" style={{ transformOrigin: "100px 100px", animationDuration: "26s" }}>
            <circle cx="100" cy="100" r="82" fill="none" stroke={c.main} strokeOpacity="0.55" strokeWidth="5" strokeDasharray="1.5 11.4" />
          </g>
          {/* energy ring */}
          <circle
            cx="100" cy="100" r="70" fill="none" stroke={c.main} strokeOpacity="0.75" strokeWidth="1.6"
            className={state === "EXECUTING" || state === "THINKING" ? "energy-dash" : undefined}
            strokeDasharray={state === "EXECUTING" || state === "THINKING" ? undefined : "2 6"}
          />
          {/* inner counter ring */}
          <g className="animate-spin-slower" style={{ transformOrigin: "100px 100px" }}>
            <circle cx="100" cy="100" r="56" fill="none" stroke="#a78bfa" strokeOpacity="0.5" strokeWidth="1" strokeDasharray="14 7" />
          </g>
          {/* orb */}
          <g className="animate-core-pulse" style={{ transformOrigin: "100px 100px" }}>
            <circle cx="100" cy="100" r="34" fill={`url(#${gid})`} />
            <circle cx="100" cy="100" r="34" fill="none" stroke={c.main} strokeOpacity="0.8" strokeWidth="1" />
          </g>
          <circle cx="88" cy="86" r="7" fill="#ffffff" opacity="0.75" />
        </svg>
        {(state === "EXECUTING" || state === "LISTENING") && (
          <span className="ping-ring absolute inset-3 rounded-full border" style={{ borderColor: c.main }} />
        )}
      </div>
      {showLabel ? (
        <div className="mt-3 text-center">
          <div className="font-display text-sm font-bold tracking-[0.3em] transition-colors duration-500" style={{ color: c.main }}>
            {state}
          </div>
          <div className="mt-0.5 text-xs text-zinc-400">{c.label}</div>
        </div>
      ) : null}
    </div>
  );
}
