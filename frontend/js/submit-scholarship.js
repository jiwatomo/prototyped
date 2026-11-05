/* Student: submit a scholarship screenshot for admin review. */
const SubmitScholarship = {
  els: {},
  previewUrl: null,
  MAX_BYTES: 5 * 1024 * 1024,
  ALLOWED: ["image/png", "image/jpeg", "image/webp"],

  async start() {
    this.els = {
      file: document.getElementById("submission-file"),
      previewWrap: document.getElementById("submission-preview-wrap"),
      preview: document.getElementById("submission-preview"),
      note: document.getElementById("submission-note"),
      submit: document.getElementById("btn-submit-scholarship"),
      status: document.getElementById("submission-status"),
      list: document.getElementById("my-submissions"),
      reload: document.getElementById("btn-reload-submissions"),
    };

    this.els.file.addEventListener("change", () => this.showPreview());
    this.els.submit.addEventListener("click", () => this.submit());
    this.els.reload.addEventListener("click", () => this.loadMine());

    await Shell.init({ role: "student" });
    await this.loadMine();
  },

  showPreview() {
    const file = this.els.file.files[0];
    if (this.previewUrl) {
      URL.revokeObjectURL(this.previewUrl);
      this.previewUrl = null;
    }
    if (!file) {
      this.els.previewWrap.hidden = true;
      return;
    }
    if (!this.ALLOWED.includes(file.type)) {
      toast("Format gambar harus PNG, JPEG, atau WEBP.", "error");
      this.els.file.value = "";
      this.els.previewWrap.hidden = true;
      return;
    }
    if (file.size > this.MAX_BYTES) {
      toast("Ukuran gambar melebihi 5 MB.", "error");
      this.els.file.value = "";
      this.els.previewWrap.hidden = true;
      return;
    }
    this.previewUrl = URL.createObjectURL(file);
    this.els.preview.src = this.previewUrl;
    this.els.previewWrap.hidden = false;
  },

  async submit() {
    const file = this.els.file.files[0];
    if (!file) {
      toast("Pilih screenshot terlebih dahulu.", "error");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    const note = this.els.note.value.trim();
    if (note) formData.append("note", note);

    setBusy(this.els.submit, true, "Mengirim…");
    this.els.status.textContent = "Mengunggah screenshot…";
    try {
      const result = await API.submitScholarship(formData);
      this.els.status.textContent = `Terkirim (${result.status}). Menunggu konfirmasi admin.`;
      toast("Screenshot terkirim ke antrean admin.", "success");
      this.els.file.value = "";
      this.els.note.value = "";
      this.els.previewWrap.hidden = true;
      if (this.previewUrl) {
        URL.revokeObjectURL(this.previewUrl);
        this.previewUrl = null;
      }
      await this.loadMine();
    } catch (error) {
      this.els.status.textContent = "Gagal mengirim.";
      toast(error.message, "error");
    } finally {
      setBusy(this.els.submit, false);
    }
  },

  async loadMine() {
    try {
      const data = await API.mySubmissions();
      if (!data.submissions.length) {
        renderEmpty(this.els.list, "Belum ada kiriman.");
        return;
      }
      const labels = { pending: "Menunggu admin", processed: "Diproses", rejected: "Ditolak" };
      const badgeClass = { pending: "badge-warn", processed: "badge-ok", rejected: "badge-bad" };
      this.els.list.innerHTML = data.submissions
        .map(
          (item) => `
          <li>
            <div class="tag-head">
              <div>
                <strong>${escapeHtml(labels[item.status] || item.status)}</strong>
                <div class="tag-slug">${item.created_at ? new Date(item.created_at).toLocaleString("id-ID") : ""}</div>
              </div>
              <span class="badge ${badgeClass[item.status] || "badge-neutral"}">${escapeHtml(
                item.status
              )}</span>
            </div>
            ${item.note ? `<div class="tag-evidence">${escapeHtml(item.note)}</div>` : ""}
            ${item.reason ? `<div class="warning">Alasan: ${escapeHtml(item.reason)}</div>` : ""}
          </li>`
        )
        .join("");
    } catch (error) {
      toast(error.message, "error");
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  SubmitScholarship.start().catch((error) => {
    if (error && error.message === "wrong-role") return;
    toast(error.message || "Gagal memuat halaman kirim beasiswa.", "error");
  });
});
