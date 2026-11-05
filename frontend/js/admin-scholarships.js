/* Admin: manage the scholarship catalogue (list, edit, verify, reject). */
const AdminScholarships = {
  els: {},
  current: null,

  async start() {
    this.els = {
      status: document.getElementById("filter-status"),
      search: document.getElementById("filter-search"),
      apply: document.getElementById("btn-apply-filter"),
      count: document.getElementById("list-count"),
      tbody: document.getElementById("scholarship-tbody"),
      card: document.getElementById("detail-card"),
      title: document.getElementById("detail-title"),
      meta: document.getElementById("detail-meta"),
      warning: document.getElementById("detail-warning"),
      name: document.getElementById("sch-name"),
      organizer: document.getElementById("sch-organizer"),
      levels: document.getElementById("sch-levels"),
      benefits: document.getElementById("sch-benefits"),
      startDate: document.getElementById("sch-start"),
      deadline: document.getElementById("sch-deadline"),
      description: document.getElementById("sch-description"),
      tags: document.getElementById("sch-tags"),
      requirements: document.getElementById("sch-requirements"),
      history: document.getElementById("sch-history"),
      rejectReason: document.getElementById("sch-reject-reason"),
      submissionList: document.getElementById("submission-list"),
      submissionCount: document.getElementById("submission-count"),
      save: document.getElementById("btn-save-scholarship"),
      approve: document.getElementById("btn-approve-scholarship"),
      reject: document.getElementById("btn-reject-scholarship"),
    };

    this.els.apply.addEventListener("click", () => this.loadList());
    this.els.search.addEventListener("keydown", (event) => {
      if (event.key === "Enter") this.loadList();
    });
    this.els.save.addEventListener("click", () => this.save());
    this.els.approve.addEventListener("click", () => this.approve());
    this.els.reject.addEventListener("click", () => this.reject());

    await Shell.init({ role: "admin" });

    const params = new URLSearchParams(window.location.search);
    const status = params.get("status");
    if (status) this.els.status.value = status;
    await this.loadList();
    await this.loadSubmissions();
    const id = params.get("id");
    if (id) await this.open(id);
  },

  async loadList() {
    const params = {};
    if (this.els.status.value) params.status = this.els.status.value;
    if (this.els.search.value.trim()) params.search = this.els.search.value.trim();

    try {
      const data = await API.adminScholarships(params);
      this.els.count.textContent = `${data.count} beasiswa`;
      if (!data.scholarships.length) {
        this.els.tbody.innerHTML =
          '<tr><td colspan="6" class="empty">Tidak ada beasiswa untuk filter ini.</td></tr>';
        return;
      }
      this.els.tbody.innerHTML = data.scholarships
        .map(
          (row) => `
          <tr>
            <td>${escapeHtml(row.name)}<div class="tag-slug">${escapeHtml(row.organizer || "-")}</div></td>
            <td>${verificationBadge(row.verification_status)}</td>
            <td>${row.approved_tags}/${row.tag_count}</td>
            <td>${row.requirement_count}</td>
            <td>${escapeHtml(row.application_deadline || "—")}</td>
            <td><button class="btn tiny" type="button" data-open="${escapeHtml(row.id)}">Kelola</button></td>
          </tr>`
        )
        .join("");

      this.els.tbody.querySelectorAll("[data-open]").forEach((button) => {
        button.addEventListener("click", () => this.open(button.dataset.open));
      });
    } catch (error) {
      toast(error.message, "error");
    }
  },

  async open(id) {
    try {
      const detail = await API.adminScholarship(id);
      this.current = detail;
      this.render(detail);
      const url = new URL(window.location.href);
      url.searchParams.set("id", id);
      window.history.replaceState({}, "", url);
    } catch (error) {
      toast(error.message, "error");
    }
  },

  render(scholarship) {
    this.els.card.hidden = false;
    this.els.title.textContent = scholarship.name;
    this.els.meta.innerHTML = [
      verificationBadge(scholarship.verification_status),
      scholarship.source_type
        ? `<span class="badge badge-info">${escapeHtml(scholarship.source_type)}</span>`
        : "",
      scholarship.updated_at
        ? `<span class="muted small">diperbarui ${new Date(scholarship.updated_at).toLocaleString("id-ID")}</span>`
        : "",
    ]
      .filter(Boolean)
      .join(" ");

    const warnings = [];
    if (scholarship.verification_status === "rejected" && scholarship.rejection_reason) {
      warnings.push(`Ditolak: ${scholarship.rejection_reason}`);
    }
    this.els.warning.innerHTML = warnings
      .map((text) => `<div class="warning">${escapeHtml(text)}</div>`)
      .join("");

    this.els.name.value = scholarship.name || "";
    this.els.organizer.value = scholarship.organizer || "";
    this.els.levels.value = (scholarship.education_levels || []).join(", ");
    this.els.benefits.value = (scholarship.benefits || []).join(", ");
    this.els.startDate.value = scholarship.application_start || "";
    this.els.deadline.value = scholarship.application_deadline || "";
    this.els.description.value = scholarship.description || "";
    this.els.rejectReason.value = scholarship.rejection_reason || "";

    this.els.tags.innerHTML = (scholarship.tags || [])
      .map(
        (tag) => `
        <li>
          <div class="tag-head">
            <div>
              <strong>${escapeHtml(tag.name)}</strong>
              <div class="tag-slug">${escapeHtml(tag.slug)} · ${escapeHtml(tag.context)}</div>
            </div>
            <div class="tag-actions">
              <span class="badge badge-neutral">${escapeHtml(tag.review_status)}</span>
              <select class="tag-review" data-slug="${escapeHtml(tag.slug)}">
                <option value="approve" ${
                  tag.review_status === "approved" ? "selected" : ""
                }>Setujui</option>
                <option value="pending" ${
                  tag.review_status === "pending" ? "selected" : ""
                }>Pending</option>
                <option value="reject" ${
                  tag.review_status === "rejected" ? "selected" : ""
                }>Tolak</option>
              </select>
            </div>
          </div>
        </li>`
      )
      .join("") || "";

    this.els.requirements.innerHTML = (scholarship.requirements || []).length
      ? scholarship.requirements
          .map(
            (req) => `
            <tr>
              <td>${escapeHtml(req.description || "-")}</td>
              <td>${escapeHtml(req.field_key || req.tag_slug || "-")}</td>
              <td>${escapeHtml(req.operator)}</td>
              <td>${escapeHtml(formatActual(req.value))}${req.unit ? " " + escapeHtml(req.unit) : ""}</td>
              <td>${req.is_mandatory ? "Wajib" : "Opsional"}</td>
              <td>${escapeHtml(req.group)} (${escapeHtml(req.group_operator)})</td>
            </tr>`
          )
          .join("")
      : '<tr><td colspan="6" class="empty">Belum ada persyaratan.</td></tr>';

    this.els.history.innerHTML = (scholarship.history || []).length
      ? scholarship.history
          .map(
            (entry) => `
            <li>
              <div class="tag-head">
                <div><strong>${escapeHtml(entry.decision)}</strong>
                  <div class="tag-slug">${escapeHtml(entry.reason || "-")}</div>
                </div>
                <span class="muted small">${entry.created_at ? new Date(entry.created_at).toLocaleString("id-ID") : ""}</span>
              </div>
            </li>`
          )
          .join("")
      : '<li><p class="empty">Belum ada keputusan tercatat.</p></li>';

    const locked = scholarship.verification_status === "verified";
    this.els.approve.disabled = locked;
    this.els.card.scrollIntoView({ behavior: "smooth", block: "start" });
  },

  async loadSubmissions() {
    if (!this.els.submissionList) return;
    try {
      const data = await API.adminSubmissions("pending");
      this.els.submissionCount.textContent = `${data.count} menunggu`;
      if (!data.submissions.length) {
        renderEmpty(this.els.submissionList, "Tidak ada kiriman menunggu.");
        return;
      }
      const labels = { pending: "Menunggu", processed: "Diproses", rejected: "Ditolak" };
      this.els.submissionList.innerHTML = data.submissions
        .map(
          (item) => `
          <li>
            <div class="tag-head">
              <div>
                <strong>${escapeHtml(item.username || "pengguna")}</strong>
                <div class="tag-slug">${item.created_at ? new Date(item.created_at).toLocaleString("id-ID") : ""}</div>
              </div>
              <span class="badge badge-warn">${escapeHtml(labels[item.status] || item.status)}</span>
            </div>
            ${item.note ? `<div class="tag-evidence">${escapeHtml(item.note)}</div>` : ""}
            <div class="submission-thumb" data-image="${escapeHtml(item.image_url)}">
              <span class="muted small">Memuat gambar…</span>
            </div>
            <div class="row" style="margin-top:.3rem">
              <button class="btn tiny primary" type="button" data-process="${escapeHtml(
                item.id
              )}">Tandai diproses</button>
              <input class="submission-reason" data-reason="${escapeHtml(
                item.id
              )}" type="text" placeholder="alasan penolakan (opsional)" />
              <button class="btn tiny danger" type="button" data-reject="${escapeHtml(
                item.id
              )}">Tolak</button>
            </div>
          </li>`
        )
        .join("");

      this.els.submissionList.querySelectorAll("[data-image]").forEach(async (holder) => {
        try {
          const blob = await API.submissionImage(holder.dataset.image);
          const url = URL.createObjectURL(blob);
          holder.innerHTML = `<img src="${url}" alt="Screenshot kiriman pengguna" />`;
        } catch (error) {
          holder.innerHTML = '<span class="muted small">Gambar tidak dapat dimuat.</span>';
        }
      });

      this.els.submissionList.querySelectorAll("[data-process]").forEach((button) => {
        button.addEventListener("click", () => this.processSubmission(button.dataset.process, "processed"));
      });
      this.els.submissionList.querySelectorAll("[data-reject]").forEach((button) => {
        button.addEventListener("click", () => {
          const input = this.els.submissionList.querySelector(
            `[data-reason="${button.dataset.reject}"]`
          );
          this.processSubmission(
            button.dataset.reject,
            "rejected",
            input ? input.value.trim() : ""
          );
        });
      });
    } catch (error) {
      toast(error.message, "error");
    }
  },

  async processSubmission(id, status, reason = "") {
    if (status === "rejected" && !reason) {
      toast("Isi alasan penolakan terlebih dahulu.", "error");
      return;
    }
    if (!window.confirm(status === "processed" ? "Tandai kiriman ini sudah diproses?" : "Tolak kiriman ini?")) {
      return;
    }
    try {
      await API.processSubmission(id, { status, reason: reason || null });
      toast(status === "processed" ? "Kiriman ditandai diproses." : "Kiriman ditolak.", "success");
      await this.loadSubmissions();
    } catch (error) {
      toast(error.message, "error");
    }
  },

  collectPatch() {
    const splitList = (value) =>
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);

    return {
      name: this.els.name.value.trim(),
      organizer: this.els.organizer.value.trim(),
      description: this.els.description.value.trim(),
      education_levels: splitList(this.els.levels.value),
      benefits: splitList(this.els.benefits.value),
      application_start: this.els.startDate.value.trim() || null,
      application_deadline: this.els.deadline.value.trim() || null,
      tags: Array.from(this.els.tags.querySelectorAll(".tag-review")).map((select) => ({
        slug: select.dataset.slug,
        decision: select.value,
      })),
    };
  },

  async save() {
    if (!this.current) return;
    const payload = this.collectPatch();
    if (!payload.name) {
      toast("Nama beasiswa wajib diisi.", "error");
      return;
    }
    setBusy(this.els.save, true, "Menyimpan…");
    try {
      const detail = await API.patchAdminScholarship(this.current.id, payload);
      this.current = detail;
      this.render(detail);
      toast("Perubahan tersimpan.", "success");
      await this.loadList();
    } catch (error) {
      toast(error.message, "error");
    } finally {
      setBusy(this.els.save, false);
    }
  },

  async approve() {
    if (!this.current) return;
    if (!window.confirm(`Setujui “${this.els.name.value.trim()}” dan tampilkan di katalog?`)) return;

    setBusy(this.els.approve, true, "Menyetujui…");
    try {
      const detail = await API.approveAdminScholarship(this.current.id);
      this.current = detail;
      this.render(detail);
      toast("Beasiswa diverifikasi dan masuk katalog pengguna.", "success");
      await this.loadList();
    } catch (error) {
      toast(error.message, "error");
    } finally {
      setBusy(this.els.approve, false);
    }
  },

  async reject() {
    if (!this.current) return;
    const reason = this.els.rejectReason.value.trim();
    if (!reason) {
      toast("Alasan penolakan wajib diisi.", "error");
      this.els.rejectReason.focus();
      return;
    }
    if (!window.confirm("Tolak beasiswa ini? Status menjadi rejected.")) return;

    setBusy(this.els.reject, true, "Menolak…");
    try {
      const detail = await API.rejectAdminScholarship(this.current.id, reason);
      this.current = detail;
      this.render(detail);
      toast("Beasiswa ditolak dengan alasan tersimpan.", "success");
      await this.loadList();
    } catch (error) {
      toast(error.message, "error");
    } finally {
      setBusy(this.els.reject, false);
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  AdminScholarships.start().catch((error) => {
    if (error && error.message === "wrong-role") return;
    toast(error.message || "Gagal memuat halaman beasiswa.", "error");
  });
});
