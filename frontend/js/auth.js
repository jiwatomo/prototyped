/* Demo session storage and guards. The token is opaque; roles are enforced by the backend. */
const SESSION_KEY = "scholar.session";
const LANDING_PAGE = "index.html";
const APP_PAGE = "app.html";

const Auth = {
  get() {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  },

  set(data) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
  },

  clear() {
    sessionStorage.removeItem(SESSION_KEY);
  },

  token() {
    const session = this.get();
    return session && session.token ? session.token : null;
  },

  isExpired(session) {
    if (!session || !session.expires_at) return true;
    const expires = new Date(session.expires_at).getTime();
    return Number.isFinite(expires) ? expires <= Date.now() : false;
  },

  async login(username, password) {
    const data = await API.login(username, password);
    this.set(data);
    return data;
  },

  async logout({ redirect = true, callApi = true } = {}) {
    if (callApi && this.token()) {
      try {
        await API.logout();
      } catch (error) {
        /* the local session is cleared regardless */
      }
    }
    this.clear();
    if (redirect) window.location.replace(LANDING_PAGE);
  },

  /** Used by app.html: redirects to the landing page when there is no usable session. */
  async requireSession() {
    let session = this.get();
    if (!session || !session.token || this.isExpired(session)) {
      this.clear();
      window.location.replace(LANDING_PAGE);
      throw new Error("Sesi tidak tersedia.");
    }
    try {
      const fresh = await API.session();
      session = { ...session, ...fresh, token: session.token };
      this.set(session);
      return session;
    } catch (error) {
      this.clear();
      window.location.replace(LANDING_PAGE);
      throw error;
    }
  },
};
