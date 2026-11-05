/* Add a scholarship: AI extraction from URL/text/PDF. Manual form lives in admin-manual.js. */
const AdminNew = {
  els: {},

  async start() {
    this.els = {
      url: document.getElementById("admin-url"),
      text: document.getElementById("admin-text"),
      file: document.getElementById("admin-file"),
      extract: document.getElementById("btn-extract"),
      status: document.getElementById("extract-status"),
    };

    this.els.extract.addEventListener("click", () => this.createExtraction());
    this.els.file.addEventListener("change", () => {
      const hasFile = this.els.file.files.length > 0;
      this.els.status.textContent = hasFile ? `PDF dipilih: ${this.els.file.files[0].name}` : "";
    });

    await Shell.init({ role: "admin" });
    await AdminManual.init();
  },

  async createExtraction() {
    const url = this.els.url.value.trim();
    const text = this.els.text.value.trim();
    const file = this.els.file.files[0];
    if (!url && !text && !file) {
      toast("Isi URL, teks sumber, atau pilih file PDF terlebih dahulu.", "error");
      return;
    }

    const formData = new FormData();
    if (url) formData.append("source_url", url);
    else if (text) formData.append("source_text", text);
    if (!url && !text && file) formData.append("file", file);

    setBusy(this.els.extract, true, "Mengekstrak…");
    this.els.status.textContent = "Memproses sumber…";
    try {
      const job = await API.createExtraction(formData);
      this.els.status.textContent = "Ekstraksi selesai. Membuka halaman kelola…";
      toast(
        `Ekstraksi selesai (${PROVIDER_LABELS[job.provider_mode] || "Simulasi AI"}). Hasil wajib diperiksa.`,
        "success"
      );
      window.location.assign(
        `admin-scholarships.html?id=${encodeURIComponent(job.scholarship.id)}`
      );
    } catch (error) {
      this.els.status.textContent = "Ekstraksi gagal.";
      toast(error.message, "error");
      setBusy(this.els.extract, false);
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  AdminNew.start().catch((error) => {
    if (error && error.message === "wrong-role") return;
    toast(error.message || "Gagal memuat halaman tambah beasiswa.", "error");
  });
});
