/* Admin dashboard: live counts and the verification queue. */
const AdminDashboard = {
  async start() {
    await Shell.init({ role: "admin" });
    await Promise.all([this.loadStats(), this.loadPending()]);
  },

  async loadStats() {
    try {
      const stats = await API.adminStats();
      const users = stats.users || {};
      const scholarships = stats.scholarships || {};
      const extractions = stats.extractions || {};

      document.getElementById("stat-users").textContent = users.total ?? 0;
      document.getElementById("stat-users-hint").textContent =
        `${users.students || 0} pengguna · ${users.admins || 0} admin · ${users.submitted_profiles || 0} profil terkirim`;

      document.getElementById("stat-verified").textContent = scholarships.verified ?? 0;
      document.getElementById("stat-verified-hint").textContent =
        `${scholarships.total || 0} total · ${scholarships.rejected || 0} ditolak`;

      document.getElementById("stat-pending").textContent = scholarships.pending ?? 0;
      document.getElementById("stat-pending-hint").textContent = `${scholarships.draft || 0} draft`;

      document.getElementById("stat-extractions").textContent = extractions.total ?? 0;
      document.getElementById("stat-extractions-hint").textContent =
        `${extractions.completed || 0} selesai · ${extractions.failed || 0} gagal`;
    } catch (error) {
      toast(error.message, "error");
    }
  },

  async loadPending() {
    const list = document.getElementById("pending-list");
    try {
      const data = await API.pendingScholarships();
      if (!data.scholarships.length) {
        renderEmpty(list, "Tidak ada beasiswa menunggu verifikasi.");
        return;
      }
      list.innerHTML = data.scholarships
        .map(
          (item) => `
          <li>
            <div class="tag-head">
              <div>
                <strong>${escapeHtml(item.name)}</strong>
                <div class="tag-slug">${escapeHtml(item.organizer || "-")}</div>
              </div>
              <div class="tag-actions">
                ${verificationBadge(item.verification_status)}
                <a class="btn tiny" href="admin-scholarships.html?id=${encodeURIComponent(
                  item.scholarship_id
                )}">Kelola</a>
              </div>
            </div>
          </li>`
        )
        .join("");
    } catch (error) {
      toast(error.message, "error");
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  AdminDashboard.start().catch((error) => {
    if (error && error.message === "wrong-role") return;
    toast(error.message || "Gagal memuat dashboard.", "error");
  });
});
