/* Landing page: resume an existing demo session or route to login. */
document.addEventListener("DOMContentLoaded", () => {
  const banner = document.getElementById("resume-banner");
  const text = document.getElementById("resume-text");
  const logout = document.getElementById("resume-logout");
  const session = Auth.get();

  if (!session || !session.token) return;

  if (Auth.isExpired(session)) {
    Auth.clear();
    return;
  }

  banner.hidden = false;
  const resumeLink = document.getElementById("resume-link");
  if (resumeLink) {
    resumeLink.href = session.role === "admin" ? "admin.html" : "app.html";
  }
  const roleLabel = session.role === "admin" ? "Admin" : "Pengguna";
  text.textContent = `Masuk sebagai ${session.user ? session.user.display_name : "pengguna"} (${roleLabel}).`;

  logout.addEventListener("click", async () => {
    await Auth.logout({ redirect: false });
    banner.hidden = true;
    window.location.reload();
  });
});
