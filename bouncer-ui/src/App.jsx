import { useState, useEffect, useRef, useCallback } from "react";

const TIERS = {
  free:       { label: "free",       limit: 5,   color: "#F4A460", tagColor: "#E8922A" },
  pro:        { label: "pro",        limit: 30,  color: "#DA8FDB", tagColor: "#B85EC0" },
  enterprise: { label: "enterprise", limit: 100, color: "#E8837A", tagColor: "#C9493E" },
};

const PSEUDOCODE = `function checkRateLimit(clientId, tier) {
  const now = Date.now()
  const window = 60_000 // 1 minute

  -- Atomic Lua script on Redis
  local key = "rl:" .. clientId
  local limit = LIMITS[tier]

  -- Remove expired requests outside window
  redis.ZREMRANGEBYSCORE(key, 0, now - window)

  -- Count requests in current window
  local count = redis.ZCARD(key)

  if count >= limit then
    -- 🚫 Too many requests
    local oldest = redis.ZRANGE(key, 0, 0)[1]
    local retryAfter = oldest + window - now
    return { allowed: false, retryAfter }
  end

  -- ✅ Allow request, record timestamp
  redis.ZADD(key, now, now)
  redis.EXPIRE(key, window / 1000)

  return {
    allowed: true,
    remaining: limit - count - 1
  }
}`;

const BUCKET_W = 220;
const BUCKET_H = 260;
const BUCKET_TOP_INSET = 15;

function Bucket({ tier, count, limit, blockRate, blobs, onReset }) {
  const cfg = TIERS[tier];
  const fillPct = Math.min(count / limit, 1.12);
  const isOverflow = blockRate > 0.1;
  const waterH = fillPct * (BUCKET_H - 20);
  const waterY = BUCKET_H - waterH;
  const waterColor = isOverflow ? "#1a6db5" : "#60A5FA";
  const w = BUCKET_W;
  const h = BUCKET_H;

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      gap: 0, width: w,
    }}>
      {/* Fixed-height SVG so all buckets stay aligned regardless of fill */}
      <svg
        width={w}
        height={h + 80}
        viewBox={`0 0 ${w} ${h + 80}`}
        style={{ overflow: "visible", display: "block" }}
      >
        {/* Handle */}
        <path
          d={`M 55 30 Q ${w/2} -28 ${w-55} 30`}
          fill="none" stroke={cfg.color} strokeWidth={7} strokeLinecap="round"
        />
        <circle cx={55}    cy={32} r={7} fill={cfg.color} />
        <circle cx={w-55}  cy={32} r={7} fill={cfg.color} />

        {/* Bucket body outline */}
        <path
          d={`M ${BUCKET_TOP_INSET} 25
              Q 10 ${h} 35 ${h+5}
              L ${w-35} ${h+5}
              Q ${w-10} ${h} ${w-BUCKET_TOP_INSET} 25
              Z`}
          fill={cfg.color} opacity={0.18}
        />
        <path
          d={`M ${BUCKET_TOP_INSET} 25
              Q 10 ${h} 35 ${h+5}
              L ${w-35} ${h+5}
              Q ${w-10} ${h} ${w-BUCKET_TOP_INSET} 25
              Z`}
          fill="none" stroke={cfg.color} strokeWidth={3}
        />

        {/* Water fill — clipped to bucket shape, flat top */}
        <clipPath id={`clip-${tier}`}>
          <path d={`M ${BUCKET_TOP_INSET} 25 Q 10 ${h} 35 ${h+5} L ${w-35} ${h+5} Q ${w-10} ${h} ${w-BUCKET_TOP_INSET} 25 Z`} />
        </clipPath>
        <rect
          x={0} y={waterY} width={w} height={h + 10}
          fill={waterColor}
          opacity={0.82}
          clipPath={`url(#clip-${tier})`}
          style={{ transition: "y 0.25s ease, height 0.25s ease, fill 0.5s ease" }}
        />

        {/* Overflow drips */}
        {isOverflow && [0.25, 0.5, 0.75].map((t, i) => (
          <ellipse key={i}
            cx={20 + t * (w - 40)} cy={h + 10}
            rx={5} ry={3}
            fill="#1a6db5" opacity={0.7}
            style={{ animation: `drip ${0.8 + i * 0.25}s ease-in-out infinite` }}
          />
        ))}

        {/* Falling blobs */}
        {blobs.map(b => (
          <circle key={b.id}
            cx={b.x} cy={0} r={b.size}
            fill={cfg.tagColor} opacity={0.9}
            style={{ animation: "blobFall 0.55s ease-in forwards" }}
          />
        ))}

        {/* Bag tag — tight loop around handle, short drop to tag */}
        <ellipse cx={62} cy={29} rx={6} ry={5}
          fill="none" stroke="#888" strokeWidth={1.5} />
        <line x1={62} y1={34} x2={56} y2={66}
          stroke="#888" strokeWidth={1.5} strokeLinecap="round" />
        <circle cx={56} cy={68} r={2} fill="#666" />
        <rect x={18} y={70} width={72} height={28} rx={6}
          fill={cfg.tagColor} stroke="#333" strokeWidth={1} />
        <text x={54} y={89} textAnchor="middle"
          fontFamily="'Nunito', sans-serif"
          fontSize={12} fontWeight="700" fontStyle="italic" fill="white">
          {cfg.label}
        </text>
      </svg>

      {/* Counter — fixed height so layout never shifts */}
      <div style={{
        height: 28,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "'Nunito', sans-serif",
        fontSize: 15, fontWeight: 700,
        color: isOverflow ? "#1a6db5" : "#444",
        letterSpacing: "0.05em",
        transition: "color 0.4s ease",
      }}>
        {count} <span style={{ color: "#bbb", fontWeight: 400, marginLeft: 4 }}>/ {limit}</span>
      </div>

      {/* Rate limited badge — fixed height slot so layout never shifts */}
      <div style={{ height: 28, display: "flex", alignItems: "center", justifyContent: "center" }}>
        {isOverflow && (
          <div style={{
            fontSize: 11, fontFamily: "'Nunito', sans-serif",
            background: "#DBEAFE", color: "#1a6db5",
            padding: "2px 10px", borderRadius: 20,
            border: "1px solid #93C5FD", fontWeight: 700,
          }}>
            RATE LIMITED
          </div>
        )}
      </div>

      {/* Per-bucket reset */}
      <button
        onClick={onReset}
        style={{
          marginTop: 8,
          background: "white", border: "1.5px solid #ddd",
          color: "#999", padding: "5px 16px", borderRadius: 8,
          cursor: "pointer", fontSize: 11,
          fontFamily: "'Nunito', sans-serif", fontWeight: 700,
          letterSpacing: "0.04em",
          transition: "all 0.15s ease",
        }}
        onMouseEnter={e => { e.target.style.borderColor = "#aaa"; e.target.style.color = "#555"; }}
        onMouseLeave={e => { e.target.style.borderColor = "#ddd"; e.target.style.color = "#999"; }}
      >
        ↺ reset
      </button>
    </div>
  );
}

function CodePanel({ visible, activeLine, onClose }) {
  const lines = PSEUDOCODE.split("\n");
  return (
    <div style={{
      position: "fixed", top: 0, right: 0, bottom: 0, width: 420,
      background: "#0F1117",
      transform: visible ? "translateX(0)" : "translateX(100%)",
      transition: "transform 0.35s cubic-bezier(0.4,0,0.2,1)",
      zIndex: 100,
      display: "flex", flexDirection: "column",
      boxShadow: "-8px 0 32px rgba(0,0,0,0.3)",
      fontFamily: "'Nunito', sans-serif",
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "16px 20px", borderBottom: "1px solid #2a2d3a",
      }}>
        <span style={{ color: "#60A5FA", fontSize: 13, fontWeight: 700, letterSpacing: "0.1em" }}>
          SLIDING WINDOW ALGORITHM
        </span>
        <button onClick={onClose} style={{
          background: "none", border: "none", color: "#666",
          cursor: "pointer", fontSize: 18, padding: "0 4px",
        }}>✕</button>
      </div>
      <div style={{ padding: "16px 0", overflowY: "auto", flex: 1 }}>
        {lines.map((line, i) => (
          <div key={i} style={{
            padding: "2px 20px",
            background: i === activeLine ? "rgba(96,165,250,0.12)" : "transparent",
            borderLeft: i === activeLine ? "3px solid #60A5FA" : "3px solid transparent",
            transition: "background 0.2s ease",
          }}>
            <span style={{ color: "#555", fontSize: 11, marginRight: 12, userSelect: "none", display: "inline-block", width: 20, textAlign: "right" }}>{i + 1}</span>
            <span style={{
              color: line.includes("--") ? "#6B7280" :
                     line.includes("return") ? "#F59E0B" :
                     line.includes("function") ? "#818CF8" :
                     line.includes("if") || line.includes("const") || line.includes("local") ? "#60A5FA" :
                     "#D1D5DB",
              fontSize: 13, lineHeight: 1.7, whiteSpace: "pre",
            }}>{line}</span>
          </div>
        ))}
      </div>
      <div style={{
        padding: "12px 20px", borderTop: "1px solid #2a2d3a",
        fontSize: 11, color: "#555",
      }}>
        Redis sorted sets · Lua atomicity · O(log N) per request
      </div>
    </div>
  );
}

const API = "http://localhost:8000";

export default function Bouncer() {
  const [counts, setCounts]         = useState({ free: 0, pro: 0, enterprise: 0 });
  const [blobs, setBlobs]           = useState({ free: [], pro: [], enterprise: [] });
  const [limits, setLimits]         = useState({ free: TIERS.free.limit, pro: TIERS.pro.limit, enterprise: TIERS.enterprise.limit });
  const [blockRates, setBlockRates] = useState({ free: 0, pro: 0, enterprise: 0 });
  const [codeVisible, setCodeVisible] = useState(false);
  const [activeLine, setActiveLine]   = useState(0);
  const [running, setRunning] = useState(false);
  const holdRef    = useRef({});
  const simRef     = useRef(null);
  const blobIdRef  = useRef(0);

  useEffect(() => {
    const sync = () =>
      fetch(`${API}/stats`)
        .then(r => r.json())
        .then(data => {
          setLimits(data.tier_limits);
          if (data.tier_stats) {
            const newCounts = {}, newRates = {};
            for (const tier of Object.keys(TIERS)) {
              const ts = data.tier_stats[tier];
              const lim = data.tier_limits[tier];
              newCounts[tier] = ts.total % Math.max(lim, 1);
              newRates[tier]  = ts.block_rate;
            }
            setCounts(newCounts);
            setBlockRates(newRates);
          }
        })
        .catch(console.error);
    sync();
    const id = setInterval(sync, 2000);
    return () => clearInterval(id);
  }, []);

  const spawnBlob = (tier) => {
    const id = blobIdRef.current++;
    const x  = 40 + Math.random() * 140;
    setBlobs(prev => ({ ...prev, [tier]: [...prev[tier], { id, x, size: 6 + Math.random() * 8 }] }));
    setTimeout(() => {
      setBlobs(prev => ({ ...prev, [tier]: prev[tier].filter(b => b.id !== id) }));
    }, 650);
  };

  const fireRequest = useCallback(async (tier) => {
    spawnBlob(tier);
    try {
      const res = await fetch(`${API}/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: "demo-user", tier }),
      });
      if (codeVisible) {
        const allowed = res.status !== 429;
        setActiveLine(allowed ? 20 : 14);
        setTimeout(() => setActiveLine(allowed ? 23 : 16), 400);
      }
    } catch { /* backend unreachable — blob still plays */ }
  }, [codeVisible]);

  // Hold-to-fill: fire repeatedly while mouse/touch held
  const startHold = (tier) => {
    fireRequest(tier);
    holdRef.current[tier] = setInterval(() => fireRequest(tier), 200);
  };
  const stopHold = (tier) => {
    clearInterval(holdRef.current[tier]);
    delete holdRef.current[tier];
  };

  const resetTier = (tier) => {
    setCounts(prev => ({ ...prev, [tier]: 0 }));
    setBlobs(prev => ({ ...prev, [tier]: [] }));
  };

  const resetAll = () => {
    setCounts({ free: 0, pro: 0, enterprise: 0 });
    setBlobs({ free: [], pro: [], enterprise: [] });
    setRunning(false);
  };

  useEffect(() => {
    if (running) {
      simRef.current = setInterval(() => {
        const tiers = ["free", "pro", "enterprise"];
        fireRequest(tiers[Math.floor(Math.random() * tiers.length)]);
      }, 280);
    } else {
      clearInterval(simRef.current);
    }
    return () => clearInterval(simRef.current);
  }, [running, fireRequest]);

  // Clean up hold intervals on unmount
  useEffect(() => () => Object.values(holdRef.current).forEach(clearInterval), []);

  const starPositions = [
    [6,6,14],[8,6,58],[5,7,82],[7,8,72],[9,7,28],[6,8,45],
    [7,9,88],[5,6,35],[8,7,65],[6,8,20],[7,6,50],[9,7,75],
  ];

  return (
    <div style={{ minHeight: "100vh", background: "#FAFAF8", fontFamily: "'Nunito', sans-serif", position: "relative" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700;800&display=swap');
        @keyframes blobFall {
          0%   { transform: translateY(-20px); opacity: 1; }
          75%  { transform: translateY(180px); opacity: 1; }
          100% { transform: translateY(220px); opacity: 0; }
        }
        @keyframes drip {
          0%,100% { transform: translateY(0);   opacity: 0.7; }
          50%     { transform: translateY(6px);  opacity: 0.4; }
        }
      `}</style>

      {/* Background stars */}
      {starPositions.map(([size, row, left], i) => (
        <div key={i} style={{
          position: "fixed",
          left: left < 50 ? `${left}%` : `${100 - left + 40}%`,
          top: `${10 + row * 8}%`,
          fontSize: size * 3.5,
          color: "#ECEAE3",
          pointerEvents: "none", userSelect: "none",
          zIndex: 0,
        }}>☆</div>
      ))}

      {/* Header */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "20px 32px",
        borderBottom: "1px solid #E5E2DA",
        background: "#FAFAF8",
        position: "sticky", top: 0, zIndex: 10,
      }}>
        <button
          onClick={() => window.history.back()}
          style={{
            background: "none", border: "1.5px solid #ccc",
            borderRadius: "50%", width: 36, height: 36,
            cursor: "pointer", fontSize: 16,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>←</button>

        <div style={{ textAlign: "center" }}>
          <h1 style={{
            margin: 0, fontSize: 22, fontWeight: 800,
            fontStyle: "italic", color: "#1a1a1a", letterSpacing: "-0.02em",
          }}>rate limiter visualization</h1>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "#888", fontStyle: "normal" }}>
            visualization showing rate limiter quotas.
          </p>
        </div>

        <button
          onClick={() => setCodeVisible(v => !v)}
          style={{
            background: "#1a1a1a", color: "white", border: "none",
            padding: "8px 18px", borderRadius: 8,
            cursor: "pointer", fontSize: 13, fontWeight: 700,
            fontFamily: "'Nunito', sans-serif", letterSpacing: "0.03em",
          }}>
          {codeVisible ? "Hide Code" : "View Code"}
        </button>
      </div>

      {/* Buckets */}
      <div style={{
        display: "flex", justifyContent: "center", alignItems: "flex-start",
        gap: 48, padding: "40px 32px 16px",
        flexWrap: "wrap",
        marginRight: codeVisible ? 420 : 0,
        transition: "margin-right 0.35s ease",
        position: "relative", zIndex: 1,
      }}>
        {Object.keys(TIERS).map(tier => (
          <div key={tier} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <Bucket
              tier={tier}
              count={counts[tier]}
              limit={limits[tier]}
              blockRate={blockRates[tier]}
              blobs={blobs[tier]}
              onReset={() => resetTier(tier)}
            />
            {/* Hold-to-fill request button */}
            <button
              onMouseDown={() => startHold(tier)}
              onMouseUp={() => stopHold(tier)}
              onMouseLeave={() => stopHold(tier)}
              onTouchStart={e => { e.preventDefault(); startHold(tier); }}
              onTouchEnd={() => stopHold(tier)}
              style={{
                background: "white",
                border: `2px solid ${TIERS[tier].tagColor}`,
                color: TIERS[tier].tagColor,
                padding: "7px 20px", borderRadius: 8,
                cursor: "pointer", fontSize: 12, fontWeight: 700,
                fontFamily: "'Nunito', sans-serif", letterSpacing: "0.05em",
                userSelect: "none", WebkitUserSelect: "none",
                transition: "all 0.12s ease",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = TIERS[tier].tagColor; e.currentTarget.style.color = "white"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "white"; e.currentTarget.style.color = TIERS[tier].tagColor; stopHold(tier); }}
            >
              hold to fill
            </button>
          </div>
        ))}
      </div>

      {/* Global controls */}
      <div style={{
        display: "flex", justifyContent: "center", gap: 12, paddingBottom: 48,
        marginRight: codeVisible ? 420 : 0,
        transition: "margin-right 0.35s ease",
        position: "relative", zIndex: 1,
      }}>
        <button
          onClick={() => setRunning(v => !v)}
          style={{
            background: running ? "#FEF3C7" : "#DCFCE7",
            border: `1.5px solid ${running ? "#F59E0B" : "#4ADE80"}`,
            color: running ? "#92400E" : "#166534",
            padding: "8px 24px", borderRadius: 8,
            cursor: "pointer", fontSize: 13, fontWeight: 700,
            fontFamily: "'Nunito', sans-serif",
          }}>
          {running ? "⏸ pause simulation" : "▶ simulate traffic"}
        </button>
        <button
          onClick={resetAll}
          style={{
            background: "white", border: "1.5px solid #ccc", color: "#666",
            padding: "8px 24px", borderRadius: 8,
            cursor: "pointer", fontSize: 13, fontWeight: 700,
            fontFamily: "'Nunito', sans-serif",
          }}>
          ↺ reset all
        </button>
      </div>

      <CodePanel visible={codeVisible} activeLine={activeLine} onClose={() => setCodeVisible(false)} />
    </div>
  );
}
