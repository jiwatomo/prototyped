/* Admin: list users, create demo accounts, reset passwords. */
const AdminUsers = {
  els: {},
  selectedUserId: null,

  async start() {
    this.els = {
      username: document.getElementById("new-username"),
      displayName: document.getElementById("new-display-name"),
      role: document.getElementById("new-role"),
      password: document.getElementById("new-password"),
      create: document.getElementById("btn-create-user"),
      createStatus: document.getElementById("create-status"),
      tbody: document.getElementById("users-tbody"),
      reload: document.getElementById("btn-reload-users"),
      resetCard: document.getElementById("reset-card"),
      resetTarget: document.getElementById("reset-target"),
      resetPassword: document.getElementById("reset-password"),
      resetButton: document.getElementById("btn-reset-password"),
      resetCancel: document.getElementById("btn-cancel-reset"),
      resetResult: document.getElementById("reset-result"),
    };

    this.els.create.addEventListener("click", () => this.createUser());
    this.els.reload.addEventListener("click", () => this.loadUsers());
    this.els.resetButton.addEventListener("click", () => this.resetPassword());
    this.els.resetCancel.addEventListener("click", () => this.closeReset());

    await Shell.init({ role: "admin" });
    await this.loadUsers();
  },

  async loadUsers() {
    try {
      const data = await API.adminUsers();
      this.els.tbody.innerHTML = data.users
        .map(
          (user) => `
          <tr>
            <td>${escapeHtml(user.username)}</td>
            <td>${escapeHtml(user.display_name)}</td>
            <td><span class="badge ${user.role === "admin" ? "badge-warn" : "badge-info"}">${
              user.role === "admin" ? "Admin" : "Pengguna"
            }</span></td>
            <td>${
              user.role === "student"
                ? user.profile_submitted
                  ? '<span class="badge badge-ok">terkirim</span>'
                  : `<span class="badge badge-neutral">${escapeHtml(
                      user.profile_status || "draft"
                    )}</span>`
                : '<span class="muted small">—</span>'
            }</td>
            <td><button class="btn tiny" type="button" data-reset="${escapeHtml(
              user.id
            )}" data-username="${escapeHtml(user.username)}">Reset kata sandi</button></td>
          </tr>`
        )
        .join("");

      this.els.tbody.querySelectorAll("[data-reset]").forEach((button) => {
        button.addEventListener("click", () =>
          this.openReset(button.dataset.reset, button.dataset.username)
        );
      });
    } catch (error) {
      toast(error.message, "error");
    }
  },

  async createUser() {
    const username = this.els.username.value.trim();
    const password = this.els.password.value;
    const role = this.els.role.value;
    if (!username) {
      toast("Username wajib diisi.", "error");
      return;
    }
    if (password.length < 8) {
      toast("Kata sandi minimal 8 karakter.", "error");
      return;
    }

    setBusy(this.els.create, true, "Menyimpan…");
    try {
      const user = await API.createAdminUser({
        username,
        display_name: this.els.displayName.value.trim(),
        role,
        password,
      });
      this.els.createStatus.textContent = `Akun ${user.username} dibuat.`;
      toast(
        `Akun ${user.username} (${role === "admin" ? "admin" : "pengguna"}) dibuat.`,
        "success"
      );
      this.els.username.value = "";
      this.els.displayName.value = "";
      this.els.password.value = "";
      await this.loadUsers();
    } catch (error) {
      this.els.createStatus.textContent = "Gagal membuat akun.";
      toast(error.message, "error");
    } finally {
      setBusy(this.els.create, false);
    }
  },

  openReset(userId, username) {
    this.selectedUserId = userId;
    this.els.resetCard.hidden = false;
    this.els.resetTarget.textContent = `Akun: ${username}`;
    this.els.resetPassword.value = "";
    this.els.resetResult.innerHTML = "";
    this.els.resetCard.scrollIntoView({ behavior: "smooth", block: "start" });
  },

  closeReset() {
    this.selectedUserId = null;
    this.els.resetCard.hidden = true;
    this.els.resetResult.innerHTML = "";
  },

  async resetPassword() {
    if (!this.selectedUserId) return;
    const password = this.els.resetPassword.value.trim();
    if (password && password.length < 8) {
      toast("Kata sandi minimal 8 karakter.", "error");
      return;
    }
    const confirmed = window.confirm(
      "Reset kata sandi akun ini? Semua sesi aktif akun tersebut akan dicabut."
    );
    if (!confirmed) return;

    setBusy(this.els.resetButton, true, "Menyimpan…");
    try {
      const result = await API.resetUserPassword(this.selectedUserId, password || null);
      if (result.generated && result.temporary_password) {
        this.els.resetResult.innerHTML = `<div class="warning">Kata sandi sementara untuk <strong>${escapeHtml(
          result.username
        )}</strong>: <code>${escapeHtml(result.temporary_password)}</code> — catat sekarang, tidak ditampilkan lagi.</div>`;
      } else {
        this.els.resetResult.innerHTML =
          '<div class="warning">Kata sandi diperbarui dan sesi lama dicabut.</div>';
      }
      toast("Kata sandi diperbarui.", "success");
      this.els.resetPassword.value = "";
    } catch (error) {
      toast(error.message, "error");
    } finally {
      setBusy(this.els.resetButton, false);
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  AdminUsers.start().catch((error) => {
    if (error && error.message === "wrong-role") return;
    toast(error.message || "Gagal memuat halaman pengguna.", "error");
  });
});
