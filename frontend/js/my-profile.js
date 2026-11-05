/* Dedicated profile page: submitted facts and deterministic corrections. */
const MyProfile = {
  els: {},

  async start() {
    this.els = {
      submittedAt: document.getElementById("submitted-at"),
      description: document.getElementById("profile-description"),
      factsSummary: document.getElementById("facts-summary"),
      saveFacts: document.getElementById("btn-save-facts"),
      factFields: {
        education_level: document.getElementById("fact-education_level"),
        major: document.getElementById("fact-major"),
        institution: document.getElementById("fact-institution"),
        gpa: document.getElementById("fact-gpa"),
        domicile: document.getElementById("fact-domicile"),
        toefl_type: document.getElementById("fact-toefl_type"),
        toefl_score: document.getElementById("fact-toefl_score"),
        achievements: document.getElementById("fact-achievements"),
      },
    };

    this.els.saveFacts.addEventListener("click", () => this.saveFacts());
    await Shell.init({ role: "student", onReady: () => this.load() });
  },

  async load() {
    try {
      const profile = State.setProfile(await API.getProfile());
      if (!profile.submitted) {
        window.location.replace("profile.html");
        return;
      }
      this.render(profile);
      this.fillFacts(profile.facts || {});
    } catch (error) {
      toast(error.message, "error");
    }
  },

  render(profile) {
    this.els.submittedAt.textContent = profile.profile_submitted_at
      ? `Dikirim ${new Date(profile.profile_submitted_at).toLocaleString("id-ID")}`
      : "";
    this.els.description.textContent = profile.description || "(tidak ada deskripsi tersimpan)";

    const facts = profile.facts || {};
    const rows = [
      ["Jenjang", facts.education_level],
      ["Jurusan", facts.major],
      ["Institusi", facts.institution],
      ["IPK", facts.gpa],
      ["Domisili", facts.domicile],
      ["TOEFL", facts.toefl_score == null ? null : `${facts.toefl_type || ""} ${facts.toefl_score}`.trim()],
      ["Prestasi", (facts.achievements || []).join("; ")],
    ];
    this.els.factsSummary.innerHTML = rows
      .map(
        ([label, value]) => `
        <div class="fact-row${label === "Prestasi" ? " span-all" : ""}">
          <span class="fact-label">${escapeHtml(label)}</span>
          <span class="fact-value">${value ? escapeHtml(formatActual(value)) : "Belum diisi"}</span>
        </div>`
      )
      .join("");

  },

  fillFacts(facts) {
    const fields = this.els.factFields;
    fields.education_level.value = facts.education_level || "";
    fields.major.value = facts.major || "";
    fields.institution.value = facts.institution || "";
    fields.gpa.value = facts.gpa == null ? "" : facts.gpa;
    fields.domicile.value = facts.domicile || "";
    fields.toefl_type.value = facts.toefl_type || "";
    fields.toefl_score.value = facts.toefl_score == null ? "" : facts.toefl_score;
    fields.achievements.value = Array.isArray(facts.achievements)
      ? facts.achievements.join("\n")
      : facts.achievements || "";
  },

  collectFacts() {
    const fields = this.els.factFields;
    const numeric = (value) => (value === "" || value === null ? null : Number(value));
    return {
      education_level: fields.education_level.value || null,
      major: fields.major.value.trim() || null,
      institution: fields.institution.value.trim() || null,
      gpa: numeric(fields.gpa.value),
      domicile: fields.domicile.value.trim() || null,
      toefl_type: fields.toefl_type.value || null,
      toefl_score: numeric(fields.toefl_score.value),
      achievements: fields.achievements.value
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    };
  },

  async saveFacts() {
    const facts = this.collectFacts();
    if (facts.gpa !== null && (facts.gpa < 0 || facts.gpa > 4)) {
      toast("IPK harus berada di antara 0 dan 4.", "error");
      return;
    }
    setBusy(this.els.saveFacts, true, "Menyimpan…");
    try {
      const profile = State.setProfile(await API.updateProfile({ facts }));
      this.render(profile);
      this.fillFacts(profile.facts || {});
      toast("Fakta tersimpan. Rekomendasi dihitung ulang tanpa memanggil AI.", "success");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      setBusy(this.els.saveFacts, false);
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  MyProfile.start().catch((error) => {
    if (error && error.message === "wrong-role") return;
    toast(error.message || "Gagal memuat halaman profil.", "error");
  });
});
