/* Shared page shell: session guard, header chip, logout and provider badge. */
const PAGE_HOME = { student: "app.html", admin: "admin.html" };

const Shell = {
  session: null,

  async init({ role, onReady } = {}) {
    this.session = await Auth.requireSession();

    const chip = document.getElementById("session-user");
    const logout = document.getElementById("btn-logout");
    const user = this.session.user || {};
    chip.textContent = `${user.display_name || user.username} · ${
      this.session.role === "admin" ? "Admin" : "Pengguna"
    }`;
    chip.className = `session-chip ${this.session.role === "admin" ? "is-admin" : ""}`;
    chip.hidden = false;
    logout.hidden = false;
    logout.addEventListener("click", () => Auth.logout());

    await this.loadHealth();

    if (role && this.session.role !== role) {
      window.location.replace(PAGE_HOME[this.session.role] || "index.html");
      throw new Error("wrong-role");
    }
    if (onReady) await onReady(this.session);
    return this.session;
  },

  async loadHealth() {
    const badge = document.getElementById("provider-badge");
    if (!badge) return;
    try {
      const health = await API.health();
      const ai = health.ai || {};
      const mode = ai.provider_mode || "mock";
      badge.className = PROVIDER_BADGE_CLASS[mode] || "badge badge-neutral";
      badge.textContent =
        (PROVIDER_LABELS[mode] || "Simulasi AI") +
        (mode === "mock_fallback" && ai.fallback_reason ? ` (${ai.fallback_reason})` : "");
      badge.title = `provider=${ai.provider_name || "-"} · llm_configured=${ai.llm_configured}`;
      if (mode === "unavailable") {
        toast("Konfigurasi AI tidak lengkap dan fallback dimatikan.", "error");
      }
    } catch (error) {
      badge.textContent = "Status AI tidak tersedia";
    }
  },
};
