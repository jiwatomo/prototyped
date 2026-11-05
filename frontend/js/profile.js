/* Dedicated profile input page: analyze the description, review it, submit once. */
const ProfilePage = {
  els: {},
  analysis: null,

  async start() {
    this.els = {
      description: document.getElementById("description"),
      btnAnalyze: document.getElementById("btn-analyze"),
      btnConfirm: document.getElementById("btn-confirm"),
      status: document.getElementById("profile-status"),
      analysisCard: document.getElementById("analysis-card"),
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

    this.els.btnAnalyze.addEventListener("click", () => this.analyze());
    this.els.btnConfirm.addEventListener("click", () => this.confirm());
    this.els.description.addEventListener("input", () => {
      this.els.status.textContent = "Deskripsi berubah — jalankan analisis ulang sebelum dikirim.";
    });

    await Shell.init({ role: "student", onReady: () => this.loadProfile() });
  },

  async loadProfile() {
    try {
      const profile = State.setProfile(await API.getProfile());
      if (profile.submitted) {
        // One submission per user: already done, go straight to the results.
        window.location.replace("app.html");
        return;
      }
      this.els.description.value = profile.description || "";
      this.els.status.textContent =
        profile.profile_status === "analyzed"
          ? "Ada hasil analisis tersimpan. Periksa lalu kirim sekali."
          : "Belum ada hasil analisis terbaru.";

      const analysis = profile.last_analysis;
      if (
        profile.profile_status === "analyzed" &&
        analysis &&
        analysis.analysis_id === profile.latest_analysis_id
      ) {
        this.renderAnalysis({
          analysis_id: analysis.analysis_id,
          facts: analysis.facts || [],
          suggested_tags: analysis.suggested_tags || [],
          provider_mode: analysis.provider && analysis.provider.provider_mode,
          fallback_reason: analysis.provider && analysis.provider.fallback_reason,
        });
      }
    } catch (error) {
      toast(error.message, "error");
    }
  },

  async analyze() {
    const description = this.els.description.value.trim();
    if (!description) {
      toast("Deskripsi tidak boleh kosong.", "error");
      return;
    }
    setBusy(this.els.btnAnalyze, true, "Menganalisis…");
    try {
      const analysis = State.setAnalysis(await API.analyze(description));
      this.analysis = analysis;
      this.renderAnalysis(analysis);
      toast(
        `Analisis selesai (${PROVIDER_LABELS[analysis.provider_mode] || "Simulasi AI"}). Periksa sebelum mengirim.`,
        "success"
      );
    } catch (error) {
      if (error.status === 409 && error.code === "already_submitted") {
        window.location.replace("app.html");
        return;
      }
      toast(error.message, "error");
    } finally {
      setBusy(this.els.btnAnalyze, false);
    }
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

  renderAnalysis(analysis) {
    this.analysis = analysis;
    const facts = {};
    (analysis.facts || []).forEach((fact) => {
      facts[fact.field_key] = fact.value;
    });
    this.fillFacts(facts);

    this.els.analysisCard.hidden = false;
    const providerSlot = document.getElementById("analysis-provider");
    if (providerSlot) {
      providerSlot.innerHTML = analysis.provider_mode
        ? ` ${providerBadge(analysis.provider_mode, analysis.fallback_reason)}`
        : "";
    }
    this.els.analysisCard.scrollIntoView({ behavior: "smooth", block: "start" });
  },

  collectFacts() {
    const fields = this.els.factFields;
    const numeric = (value) => (value === "" || value === null ? null : Number(value));
    const achievements = fields.achievements.value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    return {
      education_level: fields.education_level.value || null,
      major: fields.major.value.trim() || null,
      institution: fields.institution.value.trim() || null,
      gpa: numeric(fields.gpa.value),
      domicile: fields.domicile.value.trim() || null,
      toefl_type: fields.toefl_type.value || null,
      toefl_score: numeric(fields.toefl_score.value),
      achievements: achievements,
    };
  },

  async confirm() {
    if (!this.analysis) {
      toast("Jalankan analisis profil terlebih dahulu.", "error");
      return;
    }
    const facts = this.collectFacts();
    if (facts.gpa !== null && (facts.gpa < 0 || facts.gpa > 4)) {
      toast("IPK harus berada di antara 0 dan 4.", "error");
      return;
    }
    const confirmed = window.confirm(
      "Kirim profil sekarang? Pengiriman hanya bisa dilakukan satu kali."
    );
    if (!confirmed) return;

    setBusy(this.els.btnConfirm, true, "Mengirim…");
    try {
      const profile = State.setProfile(
        await API.confirm({
          analysis_id: this.analysis.analysis_id,
          facts,
          tags: [],
        })
      );
      if (!profile.submitted) {
        throw new Error("Pengiriman tidak tercatat di server.");
      }
      toast("Profil terkirim. Membuka rekomendasi…", "success");
      window.setTimeout(() => window.location.replace("app.html"), 500);
    } catch (error) {
      if (error.status === 409 && error.code === "already_submitted") {
        window.location.replace("app.html");
        return;
      }
      toast(error.message, "error");
      setBusy(this.els.btnConfirm, false);
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  ProfilePage.start().catch((error) => {
    if (error && error.message === "wrong-role") return;
    toast(error.message || "Gagal memuat halaman profil.", "error");
  });
});
