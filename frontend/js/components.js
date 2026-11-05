/* Presentation helpers: provider labels, badges, toasts, tag rendering. */

const PROVIDER_LABELS = {
  llm: "LLM aktif",
  mock: "Simulasi AI",
  mock_fallback: "LLM gagal — menggunakan simulasi",
};

const PROVIDER_BADGE_CLASS = {
  llm: "badge badge-ok",
  mock: "badge badge-neutral",
  mock_fallback: "badge badge-warn",
};

const ELIGIBILITY_LABELS = {
  eligible: "Memenuhi persyaratan",
  potentially_eligible: "Berpotensi memenuhi",
  not_eligible: "Belum memenuhi",
};

const ELIGIBILITY_CLASS = {
  eligible: "badge badge-ok",
  potentially_eligible: "badge badge-warn",
  not_eligible: "badge badge-bad",
};

const REQUIREMENT_LABELS = {
  met: "Terpenuhi",
  not_met: "Belum terpenuhi",
  unknown: "Belum diketahui",
  not_applicable: "Tidak berlaku",
};

const REQUIREMENT_CLASS = {
  met: "badge badge-ok",
  not_met: "badge badge-bad",
  unknown: "badge badge-neutral",
  not_applicable: "badge badge-neutral",
};

const VERIFICATION_LABELS = {
  draft: "Draft",
  processing: "Diproses",
  pending_verification: "Menunggu verifikasi",
  verified: "Terverifikasi (demo)",
  rejected: "Ditolak",
};

const VERIFICATION_CLASS = {
  draft: "badge badge-neutral",
  processing: "badge badge-info",
  pending_verification: "badge badge-warn",
  verified: "badge badge-ok",
  rejected: "badge badge-bad",
};

const APPLICATION_LABELS = {
  open: "Pendaftaran dibuka",
  closed: "Pendaftaran ditutup",
  upcoming: "Pendaftaran belum dibuka",
  unknown: "Periode tidak diketahui",
};

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function providerBadge(mode, reason) {
  const label = PROVIDER_LABELS[mode] || "Simulasi AI";
  const cls = PROVIDER_BADGE_CLASS[mode] || "badge badge-neutral";
  const suffix = mode === "mock_fallback" && reason ? ` (${escapeHtml(reason)})` : "";
  return `<span class="${cls}" title="provider_mode=${escapeHtml(mode)}">${label}${suffix}</span>`;
}

function providerCell(job) {
  if (job && job.source_type === "manual") {
    return '<span class="badge badge-info">Input manual</span>';
  }
  return providerBadge(job && job.provider_mode, job && job.fallback_reason);
}

function eligibilityBadge(status) {
  return `<span class="${ELIGIBILITY_CLASS[status] || "badge badge-neutral"}">${
    ELIGIBILITY_LABELS[status] || escapeHtml(status)
  }</span>`;
}

function requirementBadge(status) {
  return `<span class="${REQUIREMENT_CLASS[status] || "badge badge-neutral"}">${
    REQUIREMENT_LABELS[status] || escapeHtml(status)
  }</span>`;
}

function verificationBadge(status) {
  return `<span class="${VERIFICATION_CLASS[status] || "badge badge-neutral"}">${
    VERIFICATION_LABELS[status] || escapeHtml(status)
  }</span>`;
}

function applicationBadge(status) {
  return `<span class="badge badge-info">${APPLICATION_LABELS[status] || "Periode tidak diketahui"}</span>`;
}

function toast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  container.appendChild(item);
  window.setTimeout(() => item.remove(), 6000);
}

function setBusy(button, busy, busyText = "Memproses…") {
  if (!button) return;
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
  } else {
    if (button.dataset.originalText) button.textContent = button.dataset.originalText;
    button.disabled = false;
  }
}

function formatScore(score) {
  return score === null || score === undefined ? "—" : `${score.toFixed(1)}%`;
}

function formatActual(value) {
  if (value === null || value === undefined || value === "") return "Belum diisi";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function renderTagItem(tag, options = {}) {
  const decision = options.decision || "confirm";
  const decisionControl = options.readonly
    ? `<span class="badge badge-neutral">${escapeHtml(tag.review_status || tag.confirmation_status || "")}</span>`
    : `<select class="tag-decision" data-slug="${escapeHtml(tag.slug)}" data-context="${escapeHtml(
        tag.context
      )}">
         <option value="confirm" ${decision === "confirm" ? "selected" : ""}>Setujui</option>
         <option value="reject" ${decision === "reject" ? "selected" : ""}>Tolak</option>
       </select>`;

  const rejectedNote = tag.previously_rejected
    ? '<span class="badge badge-warn">pernah ditolak</span>'
    : "";
  const confidence =
    tag.confidence === null || tag.confidence === undefined
      ? ""
      : `<span class="muted small">confidence ${Number(tag.confidence).toFixed(2)}</span>`;

  return `
    <li>
      <div class="tag-head">
        <div>
          <strong>${escapeHtml(tag.name || tag.slug)}</strong>
          <div class="tag-slug">${escapeHtml(tag.slug)} · ${escapeHtml(tag.context)}</div>
        </div>
        <div class="tag-actions">${rejectedNote}${confidence}${decisionControl}</div>
      </div>
      ${tag.evidence ? `<div class="tag-evidence">“${escapeHtml(tag.evidence)}”</div>` : ""}
    </li>`;
}

function renderEmpty(container, message) {
  container.innerHTML = `<p class="empty">${escapeHtml(message)}</p>`;
}
