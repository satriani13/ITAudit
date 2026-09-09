"use strict";

// Ruta base del documento (respeta el <base href> inyectado por Flask).
const API = new URL("api/", document.baseURI).href;

const grid = document.getElementById("audit-grid");
const emptyBox = document.getElementById("empty");
const search = document.getElementById("search");
const statusFilter = document.getElementById("status-filter");
const dialog = document.getElementById("audit-dialog");
const form = document.getElementById("audit-form");
const dialogTitle = document.getElementById("dialog-title");
const toast = document.getElementById("toast");

let audits = [];

const KIND_LABEL = { fabrica: "Fábrica", oficina: "Oficina", cpd: "CPD", otro: "Otro" };
const STATUS_LABEL = { en_progreso: "En progreso", completada: "Completada", archivada: "Archivada" };

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

async function load() {
  try {
    audits = await api("audits");
    render();
  } catch (e) {
    notify("No se pudieron cargar las auditorías: " + e.message, true);
  }
}

function render() {
  const q = search.value.trim().toLowerCase();
  const st = statusFilter.value;
  const tpl = document.getElementById("card-tpl");
  grid.innerHTML = "";

  const list = audits.filter((a) => {
    if (st && a.status !== st) return false;
    if (!q) return true;
    return [a.name, a.client, a.location, a.auditor].join(" ").toLowerCase().includes(q);
  });

  emptyBox.hidden = audits.length !== 0;
  if (audits.length && !list.length) {
    grid.innerHTML = '<p class="muted">Sin resultados para el filtro.</p>';
    return;
  }

  for (const a of list) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.href = new URL("audit/" + a.id, document.baseURI).href;
    const kind = node.querySelector("[data-kind]");
    kind.textContent = KIND_LABEL[a.kind] || a.kind;
    const status = node.querySelector("[data-status]");
    status.textContent = STATUS_LABEL[a.status] || a.status;
    status.dataset.v = a.status;
    node.querySelector("[data-name]").textContent = a.name;
    node.querySelector("[data-sub]").textContent =
      [a.client, a.location].filter(Boolean).join(" · ") || "Sin datos de cliente";
    const bar = node.querySelector("[data-bar]");
    bar.style.width = a.progress.pct + "%";
    if (a.progress.pct === 100) bar.dataset.full = "1";
    node.querySelector("[data-progress-text]").textContent =
      `${a.progress.done}/${a.progress.total} ítems (${a.progress.pct}%)`;
    node.querySelector("[data-issues]").textContent = a.issues
      ? `${a.issues} incidencia${a.issues > 1 ? "s" : ""}`
      : "";
    grid.appendChild(node);
  }
}

function openDialog() {
  form.reset();
  form.id.value = "";
  dialogTitle.textContent = "Nueva auditoría";
  document.getElementById("blank-wrap").hidden = false;
  dialog.showModal();
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const fd = new FormData(form);
  const payload = Object.fromEntries(fd.entries());
  payload.blank = fd.get("blank") === "on";
  try {
    const created = await api("audits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    dialog.close();
    notify("Auditoría creada");
    location.href = new URL("audit/" + created.id, document.baseURI).href;
  } catch (e) {
    notify(e.message, true);
  }
});

dialog.addEventListener("click", (ev) => {
  if (ev.target.matches("[data-close]")) dialog.close();
});

document.getElementById("new-audit-btn").addEventListener("click", openDialog);
document.getElementById("empty-new-btn").addEventListener("click", openDialog);
search.addEventListener("input", render);
statusFilter.addEventListener("change", render);

load();
