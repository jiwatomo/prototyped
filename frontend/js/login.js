/* Login page: demo credentials, role tabs and redirect into the app. */
const ROLES = {
  user: {
    username: "demo-student",
    password: "student123",
    title: "Masuk sebagai Pengguna",
    subtitle: "Mode pengguna dipakai untuk mengisi profil dan melihat rekomendasi.",
  },
  admin: {
    username: "demo-admin",
    password: "admin123",
    title: "Masuk sebagai Admin",
    subtitle: "Mode admin dipakai untuk ekstraksi, verifikasi, dan keputusan katalog.",
  },
};

const LoginPage = {
  els: {},
  role: "user",
  redirecting: false,

  init() {
    this.els = {
      form: document.getElementById("login-form"),
      username: document.getElementById("username"),
      password: document.getElementById("password"),
      submit: document.getElementById("btn-login"),
      error: document.getElementById("login-error"),
      title: document.getElementById("login-title"),
      subtitle: document.getElementById("login-subtitle"),
      roleUser: document.getElementById("role-user"),
      roleAdmin: document.getElementById("role-admin"),
      navUser: document.getElementById("nav-user"),
      navAdmin: document.getElementById("nav-admin"),
      fill: document.getElementById("btn-fill"),
    };

    this.els.roleUser.addEventListener("click", () => this.setRole("user"));
    this.els.roleAdmin.addEventListener("click", () => this.setRole("admin"));
    this.els.fill.addEventListener("click", () => this.fillCredentials());
    this.els.form.addEventListener("submit", (event) => this.submit(event));

    const session = Auth.get();
    if (session && session.token && !Auth.isExpired(session)) {
      this.redirecting = true;
      window.location.replace("app.html");
      return;
    }
    if (session && Auth.isExpired(session)) Auth.clear();

    const requested = new URLSearchParams(window.location.search).get("role");
    this.setRole(requested === "admin" ? "admin" : "user", { updateUrl: false });
  },

  setRole(role, { updateUrl = true } = {}) {
    this.role = role === "admin" ? "admin" : "user";
    const config = ROLES[this.role];
    this.els.title.textContent = config.title;
    this.els.subtitle.textContent = config.subtitle;
    this.els.roleUser.classList.toggle("is-active", this.role === "user");
    this.els.roleAdmin.classList.toggle("is-active", this.role === "admin");
    this.els.navUser.classList.toggle("primary", this.role === "user");
    this.els.navAdmin.classList.toggle("primary", this.role === "admin");
    this.els.username.value = config.username;
    this.fillCredentials();
    this.hideError();
    if (updateUrl) {
      const url = new URL(window.location.href);
      url.searchParams.set("role", this.role);
      window.history.replaceState({}, "", url);
    }
  },

  fillCredentials() {
    const config = ROLES[this.role];
    this.els.username.value = config.username;
    this.els.password.value = config.password;
  },

  showError(message) {
    this.els.error.textContent = message;
    this.els.error.hidden = false;
  },

  hideError() {
    this.els.error.hidden = true;
    this.els.error.textContent = "";
  },

  async redirectAfterLogin(session) {
    if (session.role === "admin") {
      window.location.replace("admin.html");
      return;
    }
    try {
      const profile = await API.getProfile();
      window.location.replace(profile.submitted ? "app.html" : "profile.html");
    } catch (error) {
      window.location.replace("app.html");
    }
  },

  async submit(event) {
    event.preventDefault();
    if (this.redirecting) return;
    this.hideError();

    const username = this.els.username.value.trim();
    const password = this.els.password.value;
    if (!username || !password) {
      this.showError("Username dan kata sandi wajib diisi.");
      return;
    }

    this.els.submit.disabled = true;
    this.els.submit.textContent = "Memeriksa…";
    try {
      const session = await Auth.login(username, password);
      await this.redirectAfterLogin(session);
    } catch (error) {
      const message =
        error.status === 401
          ? "Username atau kata sandi tidak sesuai."
          : error.message || "Gagal masuk. Coba lagi.";
      this.showError(message);
      this.els.submit.disabled = false;
      this.els.submit.textContent = "Masuk";
    }
  },
};

document.addEventListener("DOMContentLoaded", () => LoginPage.init());
