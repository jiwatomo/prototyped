/* Recommendations page: guarded by session + one-time submission state. */
const Home = {
  els: {},

  async start() {
    this.els = {
      recompute: document.getElementById("btn-recompute"),
      recList: document.getElementById("rec-list"),
      recRejected: document.getElementById("rec-rejected"),
      recWarnings: document.getElementById("rec-warnings"),
      recCounts: document.getElementById("rec-counts"),
      hotList: document.getElementById("hot-list"),
      hotSection: document.getElementById("hot-section"),
      recentList: document.getElementById("recent-list"),
      recentSection: document.getElementById("recent-section"),
    };

    this.els.recompute.addEventListener("click", () => this.loadRecommendations(true));
    await Shell.init({ role: "student", onReady: () => this.load() });
  },

  async load() {
    try {
      const profile = State.setProfile(await API.getProfile());
      if (!profile.submitted) {
        window.location.replace("profile.html");
        return;
      }
      await this.loadRecommendations();
    } catch (error) {
      toast(error.message, "error");
    }
  },

  async loadRecommendations(showToast = false) {
    if (showToast) setBusy(this.els.recompute, true, "Menghitung…");
    try {
      const payload = State.setRecommendations(await API.recommendations());
      this.renderRecommendations(payload);
      if (showToast) toast("Rekomendasi diperbarui.", "success");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      if (showToast) setBusy(this.els.recompute, false);
    }
  },

  renderRecommendations(payload) {
    const counts = payload.counts || {};
    this.els.recCounts.innerHTML = `${providerBadge(payload.provider_mode)} ${counts.total || 0} beasiswa demo · ${
      counts.eligible || 0
    } memenuhi · ${counts.potentially_eligible || 0} berpotensi · ${counts.not_eligible || 0} belum memenuhi`;

    this.els.recWarnings.innerHTML = (payload.warnings || [])
      .map((text) => `<div class="warning">${escapeHtml(text)}</div>`)
      .join("");

    const results = payload.results || [];
    const matched = results.filter((item) => item.eligibility_status !== "not_eligible");
    const excluded = results.filter((item) => item.eligibility_status === "not_eligible");

    this.els.recList.innerHTML = matched.length
      ? matched.map((item) => this.card(item)).join("")
      : '<p class="empty">Belum ada beasiswa yang cocok pada bagian utama.</p>';
    this.els.recRejected.innerHTML = excluded.length
      ? excluded.map((item) => this.card(item)).join("")
      : '<p class="empty">Tidak ada beasiswa yang tersisih.</p>';

    this.renderHighlights(payload.hot || [], payload.recent || []);
  },

  renderHighlights(hot, recent) {
    const fill = (section, list, container) => {
      if (!section || !container) return;
      if (!list.length) {
        section.hidden = true;
        return;
      }
      section.hidden = false;
      container.innerHTML = list.map((item) => this.miniCard(item)).join("");
    };
    fill(this.els.hotSection, hot, this.els.hotList);
    fill(this.els.recentSection, recent, this.els.recentList);
  },

  miniCard(item) {
    const score = item.relevance_score === null ? "—" : `${item.relevance_score.toFixed(1)}%`;
    return `
      <article class="card mini-card">
        <div class="card-meta">
          <span class="badge badge-info">DEMO</span>
          ${verificationBadge(item.verification_status)}
          ${applicationBadge(item.application_status)}
        </div>
        <h3>${escapeHtml(item.name)}</h3>
        <p class="muted small">${escapeHtml(item.organizer || "Penyelenggara tidak diketahui")}</p>
        <div class="row space-between" style="margin-top:.3rem">
          <span class="muted small">Batas akhir: ${escapeHtml(item.application_deadline || "tidak diketahui")}</span>
          ${eligibilityBadge(item.eligibility_status)}
        </div>
        <p class="muted small">Skor relevansi ${score}</p>
      </article>`;
  },

  card(item) {
    const requirements = (item.requirements || [])
      .map(
        (req) => `
        <li>
          <span class="req-name">${escapeHtml(req.description || req.field_key || "Persyaratan")}
            <span class="muted small">${
              req.field_key
                ? `(${escapeHtml(formatActual(req.required_value))}${
                    req.unit ? " " + escapeHtml(req.unit) : ""
                  } · aktual: ${escapeHtml(formatActual(req.actual))})`
                : "(berdasarkan profil)"
            }</span>
          </span>
          ${requirementBadge(req.status)}
        </li>`
      )
      .join("");

    const scoreBlock =
      item.relevance_score === null
        ? `<div><div class="score">—</div><div class="score-label">${escapeHtml(
            item.score_status === "insufficient_preferences" ? "Belum cukup preferensi" : "Tanpa skor"
          )}</div></div>`
        : `<div><div class="score">${formatScore(item.relevance_score)}</div><div class="score-label">Skor relevansi</div></div>`;

    return `
      <article class="card">
        <div class="card-meta">
          <span class="badge badge-info">DATA DEMO</span>
          ${verificationBadge(item.verification_status)}
          ${applicationBadge(item.application_status)}
        </div>
        <h3>${escapeHtml(item.name)}</h3>
        <p class="muted small">${escapeHtml(item.organizer || "Penyelenggara tidak diketahui")}</p>
        <div class="row space-between">
          ${scoreBlock}
          <div>${eligibilityBadge(item.eligibility_status)}</div>
        </div>
        <ul class="req-list">${requirements || '<li class="empty">Belum ada persyaratan tercatat.</li>'}</ul>
        <p class="explanation">${escapeHtml(item.explanation || "")}</p>
      </article>`;
  },
};

document.addEventListener("DOMContentLoaded", () => {
  Home.start().catch((error) => {
    if (error && error.message === "wrong-role") return;
    toast(error.message || "Gagal memuat halaman rekomendasi.", "error");
  });
});
