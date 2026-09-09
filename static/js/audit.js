"use strict";

const T = window.I18N.t;

const root = document.getElementById("audit-root");
const AUDIT_ID = root.dataset.auditId;
const API = new URL("api/", document.baseURI).href;
const ACTIVE_KEY = "itaudit_active_" + AUDIT_ID;

const toast = document.getElementById("toast");
const snavList = document.getElementById("snav-list");
const pane = document.getElementById("section-pane");
const dialog = document.getElementById("audit-dialog");
const form = document.getElementById("audit-form");

const nameEl = document.getElementById("audit-name");
const subEl = document.getElementById("audit-sub");
const overallBar = document.getElementById("overall-bar");
const overallText = document.getElementById("overall-text");
const overallIssues = document.getElementById("overall-issues");

const itemSearch = document.getElementById("item-search");
const itemStatusFilter = document.getElementById("item-status-filter");
const itemSevFilter = document.getElementById("item-sev-filter");

let audit = null;
let activeSectionId = null;
try {
  const s = parseInt(localStorage.getItem(ACTIVE_KEY), 10);
  if (!isNaN(s)) activeSectionId = s;
} catch (e) {}

function setActive(id) {
  activeSectionId = id;
  try {
    localStorage.setItem(ACTIVE_KEY, String(id));
  } catch (e) {}
}

function notify(msg, isErr) {
  toast.textContent = msg;
  toast.classList.toggle("err", !!isErr);
  toast.hidden = false;
  clearTimeout(notify._t);
  notify._t = setTimeout(() => (toast.hidden = true), 2600);
}

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new Error((body && body.error) || res.statusText);
  return body;
}

// PATCH con "debounce" por elemento+campo para el guardado en línea.
const pending = new Map();
function savePatch(kind, id, field, value, redraw) {
  const key = `${kind}:${id}:${field}`;
  clearTimeout(pending.get(key));
  pending.set(
    key,
    setTimeout(async () => {
      pending.delete(key);
      try {
        await api(`${kind}/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [field]: value }),
        });
        if (redraw) await load();
        else notify(T("toast.saved"));
      } catch (e) {
        notify(e.message, true);
      }
    }, 450)
  );
}

async function load() {
  try {
    audit = await api("audits/" + AUDIT_ID + "?lang=" + window.I18N.currentLang());
  } catch (e) {
    notify(T("err.load_audit") + ": " + e.message, true);
    return;
  }
  if (!audit.sections.some((s) => s.id === activeSectionId)) {
    setActive(audit.sections.length ? audit.sections[0].id : null);
  }
  renderHead();
  renderSectionNav();
  renderActivePane();
}

function renderHead() {
  document.title = "Auditoría · " + audit.name;
  nameEl.textContent = audit.name;
  subEl.textContent = [
    T("kind." + audit.kind),
    T("status." + audit.status),
    audit.client,
    audit.location,
    audit.auditor && T("field.auditor") + ": " + audit.auditor,
    audit.start_date && T("field.start_date") + ": " + audit.start_date,
  ]
    .filter(Boolean)
    .join("  ·  ");
  const p = audit.progress;
  overallBar.style.width = p.pct + "%";
  overallBar.dataset.full = p.pct === 100 ? "1" : "";
  overallText.textContent = T("audit.completed_items", { done: p.done, total: p.total, pct: p.pct });
  overallIssues.textContent = audit.issues
    ? `${audit.issues} ${audit.issues > 1 ? T("card.issue_many") : T("card.issue_one")}`
    : "";
  document.getElementById("report-link").href = new URL(
    "audit/" + AUDIT_ID + "/report?lang=" + window.I18N.currentLang(),
    document.baseURI
  ).href;
}

function itemVisible(item) {
  const q = itemSearch.value.trim().toLowerCase();
  if (itemStatusFilter.value && item.status !== itemStatusFilter.value) return false;
  if (itemSevFilter.value && item.severity !== itemSevFilter.value) return false;
  if (q && !(item.title + " " + item.findings + " " + item.description).toLowerCase().includes(q)) return false;
  return true;
}

function renderSectionNav() {
  const tpl = document.getElementById("snav-item-tpl");
  snavList.innerHTML = "";
  audit.sections.forEach((section, idx) => {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.dataset.sectionId = section.id;
    if (section.id === activeSectionId) node.classList.add("active");
    node.querySelector("[data-title]").textContent = `${idx + 1}. ${section.title}`;
    const bar = node.querySelector("[data-bar]");
    bar.style.width = section.progress.pct + "%";
    bar.dataset.full = section.progress.pct === 100 ? "1" : "";
    node.querySelector("[data-count]").textContent =
      `${section.progress.done}/${section.progress.total}`;
    node.addEventListener("click", () => {
      if (section.id === activeSectionId) return;
      setActive(section.id);
      renderSectionNav();
      renderActivePane();
    });
    snavList.appendChild(node);
  });
}

function renderActivePane() {
  pane.innerHTML = "";
  const section = audit.sections.find((s) => s.id === activeSectionId);
  if (!section) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = T("section.pick");
    pane.appendChild(p);
    return;
  }

  const tpl = document.getElementById("section-pane-tpl");
  const node = tpl.content.firstElementChild.cloneNode(true);
  window.I18N.apply(node);

  const idx = audit.sections.indexOf(section);
  node.querySelector("[data-title]").textContent = `${idx + 1}. ${section.title}`;
  const desc = node.querySelector("[data-desc]");
  desc.textContent = section.description || "";
  desc.hidden = !section.description;

  node.querySelector('[data-act="add-item"]').addEventListener("click", () => addItem(section.id));
  node.querySelector('[data-act="edit-section"]').addEventListener("click", () => editSection(section));
  node.querySelector('[data-act="del-section"]').addEventListener("click", () => delSection(section));

  const itemsBox = node.querySelector("[data-items]");
  const itemTpl = document.getElementById("item-tpl");
  const visibleItems = section.items.filter(itemVisible);
  if (!visibleItems.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = section.items.length ? T("section.no_items_filter") : T("section.no_items");
    itemsBox.appendChild(p);
  }
  visibleItems.forEach((item) => itemsBox.appendChild(buildItem(itemTpl, item)));

  pane.appendChild(node);
}

function buildItem(itemTpl, item) {
  const node = itemTpl.content.firstElementChild.cloneNode(true);
  window.I18N.apply(node);
  node.dataset.itemId = item.id;
  node.dataset.status = item.status;

  node.querySelectorAll("[data-field]").forEach((input) => {
    const f = input.dataset.field;
    input.value = item[f] == null ? "" : item[f];
    const evt = input.tagName === "SELECT" ? "change" : "input";
    input.addEventListener(evt, () => {
      const redraw = f === "status"; // el progreso y el color dependen del estado
      if (f === "status") node.dataset.status = input.value;
      savePatch("items", item.id, f, input.value, redraw);
    });
  });

  node.querySelector('[data-act="expand"]').addEventListener("click", () => {
    const d = node.querySelector(".item-detail");
    d.hidden = !d.hidden;
  });
  node.querySelector('[data-act="del-item"]').addEventListener("click", async () => {
    if (!confirm(T("confirm.del_item"))) return;
    try {
      await api("items/" + item.id, { method: "DELETE" });
      await load();
    } catch (e) {
      notify(e.message, true);
    }
  });

  // --- Adjuntos ---
  const listBox = node.querySelector("[data-attach-list]");
  renderAttachments(listBox, item.attachments);

  const fileInput = node.querySelector(".attach-input");
  fileInput.addEventListener("change", () => uploadFiles(item.id, fileInput.files, listBox));

  const drop = node.querySelector("[data-drop]");
  ["dragenter", "dragover"].forEach((e) =>
    drop.addEventListener(e, (ev) => {
      ev.preventDefault();
      drop.classList.add("drag");
    })
  );
  ["dragleave", "drop"].forEach((e) =>
    drop.addEventListener(e, (ev) => {
      ev.preventDefault();
      drop.classList.remove("drag");
    })
  );
  drop.addEventListener("drop", (ev) => uploadFiles(item.id, ev.dataTransfer.files, listBox));

  return node;
}

function renderAttachments(box, attachments) {
  box.innerHTML = "";
  attachments.forEach((att) => {
    const wrap = document.createElement("div");
    wrap.className = "attach-item";
    const url = new URL("api/attachments/" + att.id, document.baseURI).href;
    if (att.is_image) {
      const img = document.createElement("img");
      img.src = url;
      img.alt = att.original_name;
      wrap.appendChild(img);
    } else {
      const ico = document.createElement("div");
      ico.className = "file-ico";
      ico.textContent = "📄";
      wrap.appendChild(ico);
    }
    const link = document.createElement("a");
    link.className = "fname";
    link.href = url + "?dl=1";
    link.textContent = att.original_name;
    link.title = att.original_name + ` (${Math.round(att.size / 1024)} KB)`;
    wrap.appendChild(link);

    const del = document.createElement("button");
    del.className = "att-del";
    del.textContent = "×";
    del.addEventListener("click", async () => {
      try {
        await api("attachments/" + att.id, { method: "DELETE" });
        wrap.remove();
      } catch (e) {
        notify(e.message, true);
      }
    });
    wrap.appendChild(del);
    box.appendChild(wrap);
  });
}

async function uploadFiles(itemId, fileList, listBox) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  for (const file of files) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const att = await api(`items/${itemId}/attachments`, { method: "POST", body: fd });
      const item = findItem(itemId);
      if (item) {
        item.attachments.push(att);
        renderAttachments(listBox, item.attachments);
      }
    } catch (e) {
      notify(`"${file.name}": ${e.message}`, true);
    }
  }
  notify(T("attach.uploaded"));
}

function findItem(id) {
  for (const s of audit.sections) {
    const it = s.items.find((i) => i.id === id);
    if (it) return it;
  }
  return null;
}

async function addItem(sectionId) {
  const title = prompt(T("prompt.new_item"));
  if (!title || !title.trim()) return;
  try {
    await api("items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ section_id: sectionId, title: title.trim() }),
    });
    await load();
  } catch (e) {
    notify(e.message, true);
  }
}

async function editSection(section) {
  const title = prompt(T("prompt.section_title"), section.title);
  if (title === null) return;
  const description = prompt(T("prompt.section_desc"), section.description || "");
  try {
    await api("sections/" + section.id, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim(), description: (description || "").trim() }),
    });
    await load();
  } catch (e) {
    notify(e.message, true);
  }
}

async function delSection(section) {
  if (!confirm(T("confirm.del_section", { title: section.title }))) return;
  try {
    await api("sections/" + section.id, { method: "DELETE" });
    if (section.id === activeSectionId) activeSectionId = null;
    await load();
  } catch (e) {
    notify(e.message, true);
  }
}

document.getElementById("add-section-btn").addEventListener("click", async () => {
  const title = prompt(T("prompt.new_section"));
  if (!title || !title.trim()) return;
  try {
    const sec = await api("sections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audit_id: Number(AUDIT_ID), title: title.trim() }),
    });
    if (sec && sec.id) setActive(sec.id);
    await load();
  } catch (e) {
    notify(e.message, true);
  }
});

[itemSearch, itemStatusFilter, itemSevFilter].forEach((el) =>
  el.addEventListener("input", renderActivePane)
);

// --- Editar datos de la auditoría ---
document.getElementById("edit-audit-btn").addEventListener("click", () => {
  form.reset();
  ["name", "kind", "status", "client", "location", "auditor", "start_date", "notes"].forEach((f) => {
    if (form[f]) form[f].value = audit[f] || "";
  });
  dialog.showModal();
});

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    await api("audits/" + AUDIT_ID, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    dialog.close();
    notify(T("toast.audit_updated"));
    await load();
  } catch (e) {
    notify(e.message, true);
  }
});

dialog.addEventListener("click", (ev) => {
  if (ev.target.matches("[data-close]")) dialog.close();
});

document.getElementById("delete-audit-btn").addEventListener("click", async () => {
  if (!confirm(T("confirm.del_audit"))) return;
  try {
    await api("audits/" + AUDIT_ID, { method: "DELETE" });
    location.href = document.baseURI;
  } catch (e) {
    notify(e.message, true);
  }
});

load();
