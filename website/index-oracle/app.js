// Synaptic AI Capability Index — Interactive Prompt Oracle Client

let capabilityPack = null;

const SFIA_DISCIPLINES = {
  "PROG": "Software Development",
  "TEST": "Testing",
  "REQM": "Requirements & Architecture",
  "DBDS": "Database Design",
  "VISU": "Visual Design & CSS",
  "ANIM": "Animation Development",
  "GRAP": "Graphic Design",
  "COMM": "Communication & Docs",
  "PROD": "Product Management"
};

const SFIA_PATTERNS = [
  { code: "TEST", regex: /\b(test|tests|testing|pytest|unit test|mock|regression|assertion|coverage)\b/i },
  { code: "DBDS", regex: /\b(sql|database|postgres|postgresql|sqlite|migration|query|schema|index|table)\b/i },
  { code: "VISU", regex: /\b(css|styling|theme|glassmorphic|html|layout|template|tailwind|ui|responsive)\b/i },
  { code: "REQM", regex: /\b(spec|architecture|requirements|design doc|rfcs?|epic|governs|tradeoff)\b/i },
  { code: "COMM", regex: /\b(doc|docs|documentation|readme|changelog|blog|guide|tutorial)\b/i },
  { code: "PROD", regex: /\b(roadmap|backlog|feature|release|sprint|prioritize|gtm)\b/i },
  { code: "PROG", regex: /\b(code|function|class|method|refactor|fix|bug|algorithm|api|endpoint|cli|async)\b/i },
];

const PREFERENCE_MODES = ["balanced", "quality", "cost", "quota"];
const PREFERENCE_LABELS = ["Balanced (ROI)", "Max Quality", "Lowest Cost", "Quota Safe"];

function classifyPrompt(prompt) {
  const text = prompt.trim();
  if (!text) {
    return { code: "PROG", name: SFIA_DISCIPLINES["PROG"], complexity: "LOW" };
  }

  let matchedCode = "PROG";
  for (const p of SFIA_PATTERNS) {
    if (p.regex.test(text)) {
      matchedCode = p.code;
      break;
    }
  }

  // Complexity
  let complexity = "MEDIUM";
  const lower = text.toLowerCase();
  const highKw = ["race condition", "deadlock", "architecture", "refactor", "async", "distributed", "protocol", "lock", "concurrency"];
  const lowKw = ["typo", "readme", "comment", "lint", "formatting", "rename", "bump"];

  if (highKw.some(k => lower.includes(k)) || text.length > 250) {
    complexity = "COMPLEX";
  } else if (lowKw.some(k => lower.includes(k)) || text.length < 25) {
    complexity = "LOW";
  }

  return {
    code: matchedCode,
    name: SFIA_DISCIPLINES[matchedCode] || "Software Engineering",
    complexity
  };
}

function selectCandidates(candidates, optimizeFor) {
  if (!candidates || candidates.length === 0) return {};

  const valid = [...candidates];

  // 1. Primary Pick
  let primary;
  if (optimizeFor === "quality") {
    primary = [...valid].sort((a, b) => (!b.unmeasured - !a.unmeasured) || (b.quality_score - a.quality_score))[0];
  } else if (optimizeFor === "cost") {
    primary = [...valid].sort((a, b) => (!b.unmeasured - !a.unmeasured) || (a.cost_per_verified_fix_usd - b.cost_per_verified_fix_usd))[0];
  } else if (optimizeFor === "quota") {
    primary = [...valid].sort((a, b) => ((b.failover_risk !== "high") - (a.failover_risk !== "high")) || (b.quality_score - a.quality_score))[0];
  } else { // balanced
    primary = [...valid].sort((a, b) => {
      const scoreA = (a.quality_score / Math.max(0.01, a.cost_per_verified_fix_usd || 0.5)) * (a.failover_risk === "high" ? 0.8 : 1.0);
      const scoreB = (b.quality_score / Math.max(0.01, b.cost_per_verified_fix_usd || 0.5)) * (b.failover_risk === "high" ? 0.8 : 1.0);
      return (!b.unmeasured - !a.unmeasured) || (scoreB - scoreA);
    })[0];
  }

  // 2. Failover Pick (different harness with low failover risk)
  const failoverPool = valid.filter(c => c.harness !== primary?.harness);
  const failover = failoverPool.sort((a, b) => ((b.failover_risk !== "high") - (a.failover_risk !== "high")) || (b.quality_score - a.quality_score))[0] || valid[1];

  // 3. Budget Pick (lowest cost)
  const budget = [...valid].sort((a, b) => (a.cost_per_verified_fix_usd - b.cost_per_verified_fix_usd) || (b.quality_score - a.quality_score))[0];

  return { primary, failover, budget };
}

function renderCard(rec, type, badgeClass) {
  if (!rec) return '';
  const isPrimary = type === 'Top Recommended';
  const unmeasBadge = rec.unmeasured ? '<div class="unmeas-flag">⚠ Under 5 samples (Unmeasured)</div>' : '';

  return `
    <div class="rec-card ${isPrimary ? 'primary-card' : ''}">
      <span class="card-role-badge ${badgeClass}">${type}</span>
      <h3 class="card-title">${rec.harness.toUpperCase()}</h3>
      <div class="card-model">${rec.model}</div>
      <div class="metrics-list">
        <div class="metric-item">
          <span class="metric-num">${rec.quality_score.toFixed(1)}</span>
          <span class="metric-label">Quality Score</span>
        </div>
        <div class="metric-item">
          <span class="metric-num">$${rec.cost_per_verified_fix_usd.toFixed(2)}</span>
          <span class="metric-label">Cost / Fix</span>
        </div>
        <div class="metric-item">
          <span class="metric-num">${rec.median_review_cycles.toFixed(1)}</span>
          <span class="metric-label">Review Cycles</span>
        </div>
        <div class="metric-item">
          <span class="metric-num">n=${rec.sample_size}</span>
          <span class="metric-label">Tasks Verified</span>
        </div>
      </div>
      ${unmeasBadge}
    </div>
  `;
}

function updateOracle() {
  const promptInput = document.getElementById('prompt-input');
  const slider = document.getElementById('preference-slider');
  const classBadge = document.getElementById('classification-badge');
  const compBadge = document.getElementById('complexity-badge');
  const sliderLabel = document.getElementById('slider-label');
  const recsContainer = document.getElementById('recommendations-container');
  const quotaStrip = document.getElementById('quota-strip');
  const quotaText = document.getElementById('quota-text');

  const prompt = promptInput.value;
  const optIndex = parseInt(slider.value, 10);
  const optimizeFor = PREFERENCE_MODES[optIndex];
  sliderLabel.textContent = PREFERENCE_LABELS[optIndex];

  const cls = classifyPrompt(prompt);
  classBadge.textContent = `${cls.code} — ${cls.name}`;
  compBadge.textContent = cls.complexity;

  if (!capabilityPack || !capabilityPack.matrix) {
    recsContainer.innerHTML = '<div class="loading-state">Loading capability index matrix...</div>';
    return;
  }

  const matrix = capabilityPack.matrix;
  const candidates = matrix[cls.code] || matrix["PROG"] || [];

  const { primary, failover, budget } = selectCandidates(candidates, optimizeFor);

  let html = '';
  html += renderCard(primary, 'Top Recommended', 'primary-badge');
  html += renderCard(failover, 'Failover Pick', 'failover-badge');
  html += renderCard(budget, 'Budget Pick', 'budget-badge');

  recsContainer.innerHTML = html;

  // Quota alerts
  const advisories = capabilityPack.quota_advisories || {};
  const activeHarnesses = [primary?.harness, failover?.harness, budget?.harness].filter(Boolean);
  const matchedAdvisories = activeHarnesses.filter(h => advisories[h]).map(h => `${h.toUpperCase()}: ${advisories[h]}`);

  if (matchedAdvisories.length > 0) {
    quotaText.textContent = matchedAdvisories.join(' · ');
    quotaStrip.classList.remove('hidden');
  } else {
    quotaStrip.classList.add('hidden');
  }
}

// Initialize Application
async function init() {
  try {
    const res = await fetch('pack-latest.json');
    if (res.ok) {
      capabilityPack = await res.json();
    }
  } catch (err) {
    console.warn("Using offline fallback capability pack:", err);
  }

  // Fallback defaults if fetch is blocked
  if (!capabilityPack) {
    capabilityPack = {
      matrix: {
        PROG: [
          { harness: "codex", model: "gpt-5.6-terra", quality_score: 9.04, cost_per_verified_fix_usd: 0.52, median_review_cycles: 1.1, sample_size: 410, unmeasured: false, failover_risk: "low" },
          { harness: "grok", model: "grok-4.6", quality_score: 8.55, cost_per_verified_fix_usd: 0.48, median_review_cycles: 1.2, sample_size: 176, unmeasured: false, failover_risk: "low" },
          { harness: "claude", model: "claude-3.7-sonnet", quality_score: 9.20, cost_per_verified_fix_usd: 0.65, median_review_cycles: 1.1, sample_size: 150, unmeasured: false, failover_risk: "high" },
          { harness: "agy", model: "gemini-3.8-flash", quality_score: 7.58, cost_per_verified_fix_usd: 0.08, median_review_cycles: 1.6, sample_size: 89, unmeasured: false, failover_risk: "none" }
        ]
      },
      quota_advisories: {
        claude: "Active weekly quota cliff; Codex or Grok recommended"
      },
      snapshot_metadata: {
        snapshot_id: "pack-offline",
        sha256: "local-preview-pack"
      }
    };
  }

  const metaEl = document.getElementById('snapshot-indicator');
  if (metaEl && capabilityPack.snapshot_metadata) {
    const meta = capabilityPack.snapshot_metadata;
    metaEl.textContent = `Snapshot: ${meta.snapshot_id} (SHA-256: ${meta.sha256.substring(0, 16)}...) · ${meta.total_tasks || 2700}+ tasks`;
  }

  const promptInput = document.getElementById('prompt-input');
  promptInput.addEventListener('input', updateOracle);

  const slider = document.getElementById('preference-slider');
  slider.addEventListener('input', updateOracle);

  document.querySelectorAll('.chip').forEach(btn => {
    btn.addEventListener('click', (e) => {
      promptInput.value = e.target.getAttribute('data-prompt');
      updateOracle();
    });
  });

  const copyBtn = document.getElementById('copy-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText('brew install synlynk');
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
    });
  }

  // Initial trigger with default sample prompt
  promptInput.value = "Refactor database connection pool with async retry and circuit breaker";
  updateOracle();
}

document.addEventListener('DOMContentLoaded', init);
