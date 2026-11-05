/* Admin: type a scholarship by hand. Same tables and review path as AI extraction. */
const MANUAL_CONTEXTS = [
  "eligibility",
  "target_audience",
  "field",
  "achievement",
  "benefit",
  "program",
  "location",
  "obligation",
];

const MANUAL_FIELDS = [
  ["gpa", "IPK (gpa)", true],
  ["toefl_score", "Skor TOEFL", true],
  ["education_level", "Jenjang", false],
  ["major", "Jurusan", false],
  ["domicile", "Domisili", false],
  ["semester", "Semester", true],
  ["age", "Usia", true],
  ["achievements", "Prestasi", false],
];

const MANUAL_OPERATORS = ["gte", "lte", "gt", "lt", "eq", "neq", "in", "not_in", "between", "contains"];
const NUMERIC_FIELDS = new Set(["gpa", "toefl_score", "semester", "age"]);

const AdminManual = {
  tags: [],
  els: {},

  async init() {
    this.els = {
      name: document.getElementById("manual-name"),
      organizer: document.getElementById("manual-organizer"),
      levels: document.getElementById("manual-levels"),
      benefits: document.getElementById("manual-benefits"),
      start: document.getElementById("manual-start"),
      deadline: document.getElementById("manual-deadline"),
      description: document.getElementById("manual-description"),
      tags: document.getElementById("manual-tags"),
      requirements: document.getElementById("manual-requirements"),
      addTag: document.getElementById("btn-add-manual-tag"),
      addRequirement: document.getElementById("btn-add-manual-requirement"),
      save: document.getElementById("btn-save-manual"),
      status: document.getElementById("manual-status"),
    };
    if (!this.els.name) return;

    this.els.addTag.addEventListener("click", () => this.addTagRow());
    this.els.addRequirement.addEventListener("click", () => this.addRequirementRow());
    this.els.save.addEventListener("click", () => this.save());

    try {
      const data = await API.tags();
      this.tags = data.tags || [];
    } catch (error) {
      toast("Gagal memuat daftar Master Tag: " + error.message, "error");
    }
    this.addTagRow("edu.level.s1", "target_audience");
  },

  tagOptions(selected) {
    return this.tags
      .map(
        (tag) =>
          `<option value="${escapeHtml(tag.slug)}" ${tag.slug === selected ? "selected" : ""}>${
            escapeHtml(tag.slug)
          } — ${escapeHtml(tag.name)}</option>`
      )
      .join("");
  },

  contextOptions(selected) {
    return MANUAL_CONTEXTS.map(
      (ctx) =>
        `<option value="${ctx}" ${ctx === selected ? "selected" : ""}>${ctx}</option>`
    ).join("");
  },

  fieldOptions(selected) {
    return MANUAL_FIELDS.map(
      ([key, label, numeric]) =>
        `<option value="${key}" data-numeric="${numeric}" ${key === selected ? "selected" : ""}>${label}</option>`
    ).join("");
  },

  operatorOptions(selected = "gte") {
    return MANUAL_OPERATORS.map(
      (op) => `<option value="${op}" ${op === selected ? "selected" : ""}>${op}</option>`
    ).join("");
  },

  addTagRow(slug, context = "target_audience") {
    const row = document.createElement("div");
    row.className = "builder-row";
    row.dataset.tagRow = "1";
    row.innerHTML = `
      <select class="manual-tag-slug">${this.tagOptions(slug)}</select>
      <select class="manual-tag-context">${this.contextOptions(context)}</select>
      <button class="btn tiny" type="button" data-remove>Hapus</button>`;
    row.querySelector("[data-remove]").addEventListener("click", () => row.remove());
    this.els.tags.appendChild(row);
  },

  addRequirementRow() {
    const row = document.createElement("div");
    row.className = "builder-row req";
    row.dataset.reqRow = "1";
    row.innerHTML = `
      <select class="req-source">
        <option value="field">Field</option>
        <option value="tag">Tag</option>
      </select>
      <select class="req-field">${this.fieldOptions("gpa")}</select>
      <select class="req-tag" hidden>${this.tagOptions("")}</select>
      <select class="req-operator">${this.operatorOptions()}</select>
      <input class="req-value" type="text" placeholder="nilai, mis. 3.0" />
      <input class="req-desc" type="text" placeholder="deskripsi persyaratan" />
      <label class="req-mandatory"><input type="checkbox" checked /> Wajib</label>
      <button class="btn tiny" type="button" data-remove>Hapus</button>`;

    const source = row.querySelector(".req-source");
    const field = row.querySelector(".req-field");
    const tag = row.querySelector(".req-tag");
    source.addEventListener("change", () => {
      const isTag = source.value === "tag";
      field.hidden = isTag;
      tag.hidden = !isTag;
      row.querySelector(".req-value").disabled = isTag;
    });
    row.querySelector("[data-remove]").addEventListener("click", () => row.remove());
    this.els.requirements.appendChild(row);
  },

  parseValue(fieldKey, operator, raw) {
    const text = String(raw || "").trim();
    if (operator === "in" || operator === "not_in") {
      return text
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    }
    if (operator === "between") {
      return text
        .split(",")
        .slice(0, 2)
        .map((item) => Number(item.trim()));
    }
    if (NUMERIC_FIELDS.has(fieldKey)) return Number(text);
    return text;
  },

  collect() {
    const splitList = (value) =>
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);

    const tags = Array.from(this.els.tags.querySelectorAll("[data-tag-row]")).map((row) => ({
      slug: row.querySelector(".manual-tag-slug").value,
      context: row.querySelector(".manual-tag-context").value,
    }));

    const requirements = Array.from(this.els.requirements.querySelectorAll("[data-req-row]")).map(
      (row) => {
        const isTag = row.querySelector(".req-source").value === "tag";
        const fieldKey = isTag ? null : row.querySelector(".req-field").value;
        const operator = row.querySelector(".req-operator").value;
        const rawValue = row.querySelector(".req-value").value;
        return {
          field_key: fieldKey,
          tag_slug: isTag ? row.querySelector(".req-tag").value : null,
          operator,
          value: isTag ? true : this.parseValue(fieldKey, operator, rawValue),
          description: row.querySelector(".req-desc").value.trim() || null,
          is_mandatory: row.querySelector(".req-mandatory input").checked,
        };
      }
    );

    return {
      name: this.els.name.value.trim(),
      organizer: this.els.organizer.value.trim(),
      description: this.els.description.value.trim(),
      education_levels: splitList(this.els.levels.value),
      benefits: splitList(this.els.benefits.value),
      application_start: this.els.start.value.trim() || null,
      application_deadline: this.els.deadline.value.trim() || null,
      tags,
      requirements,
    };
  },

  async save() {
    const payload = this.collect();
    if (!payload.name) {
      toast("Nama beasiswa wajib diisi.", "error");
      this.els.name.focus();
      return;
    }
    if (!payload.tags.length) {
      toast("Tambahkan minimal satu tag.", "error");
      return;
    }
    const missing = payload.requirements.find(
      (req) => !req.tag_slug && (req.value === "" || req.value === null || Number.isNaN(req.value))
    );
    if (missing) {
      toast("Setiap persyaratan butuh nilai yang valid.", "error");
      return;
    }

    setBusy(this.els.save, true, "Menyimpan…");
    this.els.status.textContent = "Menyimpan ke antrean verifikasi…";
    try {
      const job = await API.createManualScholarship(payload);
      this.els.status.textContent = `Tersimpan sebagai ${job.scholarship.verification_status}.`;
      toast("Beasiswa manual tersimpan dan menunggu verifikasi.", "success");
      window.location.assign(
        `admin-scholarships.html?id=${encodeURIComponent(job.scholarship.id)}`
      );
    } catch (error) {
      this.els.status.textContent = "Gagal menyimpan.";
      toast(error.message, "error");
    } finally {
      setBusy(this.els.save, false);
    }
  },
};
