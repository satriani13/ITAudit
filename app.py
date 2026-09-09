# -*- coding: utf-8 -*-
"""
Webapp de auditoria IT para nuevas fabricas / oficinas.

Arranque local:
    PORT=5001 venv/bin/python app.py

Sub-path en el VPS (detras de nginx con auth_request):
    PORT=3020 HOST=127.0.0.1 APP_BASE=/proyectos/it-audit venv/bin/python app.py
"""

import mimetypes
import os
import uuid
from datetime import datetime

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_file,
)
from werkzeug.utils import secure_filename

from models import (
    AUDIT_KIND,
    AUDIT_STATUS,
    ITEM_SEVERITY,
    ITEM_STATUS,
    Attachment,
    Audit,
    Item,
    Section,
    db,
)
from template_data import DEFAULT_LANG, LANGS, build_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# APP_BASE: prefijo de montaje ("" en local, "/proyectos/it-audit" en el VPS).
APP_BASE = os.environ.get("APP_BASE", "").rstrip("/")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
ALLOWED_EXT = {
    "png", "jpg", "jpeg", "gif", "webp", "bmp", "heic", "svg",
    "pdf", "txt", "csv", "log", "md",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods",
    "zip", "vsdx", "dwg", "json", "xml",
}

# Textos del informe imprimible (renderizado en servidor) por idioma.
REPORT_I18N = {
    "es": {
        "report_title": "Informe de auditoría IT", "generated": "Generado",
        "audit": "Auditoría", "type": "Tipo", "client": "Cliente",
        "location": "Ubicación", "auditor": "Auditor", "start_date": "Fecha de inicio",
        "status": "Estado", "progress": "Progreso", "issues": "incidencias",
        "notes": "Notas", "col_item": "Ítem", "col_status": "Estado", "col_sev": "Sev.",
        "col_owner": "Responsable", "col_findings": "Hallazgos / recomendación",
        "no_items": "Sin ítems.", "attachments": "adjunto(s)", "print": "Imprimir / PDF",
        "kind": {"fabrica": "Fábrica", "oficina": "Oficina", "cpd": "CPD", "otro": "Otro"},
        "st": {"pendiente": "Pendiente", "en_progreso": "En progreso", "ok": "OK",
               "incidencia": "Incidencia", "no_aplica": "No aplica"},
        "sev": {"baja": "Baja", "media": "Media", "alta": "Alta", "critica": "Crítica"},
        "audit_status": {"en_progreso": "En progreso", "completada": "Completada",
                         "archivada": "Archivada"},
    },
    "en": {
        "report_title": "IT audit report", "generated": "Generated",
        "audit": "Audit", "type": "Type", "client": "Client",
        "location": "Location", "auditor": "Auditor", "start_date": "Start date",
        "status": "Status", "progress": "Progress", "issues": "issues",
        "notes": "Notes", "col_item": "Item", "col_status": "Status", "col_sev": "Sev.",
        "col_owner": "Owner", "col_findings": "Findings / recommendation",
        "no_items": "No items.", "attachments": "attachment(s)", "print": "Print / PDF",
        "kind": {"fabrica": "Factory", "oficina": "Office", "cpd": "Data center", "otro": "Other"},
        "st": {"pendiente": "Pending", "en_progreso": "In progress", "ok": "OK",
               "incidencia": "Issue", "no_aplica": "N/A"},
        "sev": {"baja": "Low", "media": "Medium", "alta": "High", "critica": "Critical"},
        "audit_status": {"en_progreso": "In progress", "completada": "Completed",
                         "archivada": "Archived"},
    },
    "it": {
        "report_title": "Report di audit IT", "generated": "Generato",
        "audit": "Audit", "type": "Tipo", "client": "Cliente",
        "location": "Sede", "auditor": "Auditor", "start_date": "Data di inizio",
        "status": "Stato", "progress": "Avanzamento", "issues": "problemi",
        "notes": "Note", "col_item": "Voce", "col_status": "Stato", "col_sev": "Grav.",
        "col_owner": "Responsabile", "col_findings": "Riscontri / raccomandazione",
        "no_items": "Nessuna voce.", "attachments": "allegato/i", "print": "Stampa / PDF",
        "kind": {"fabrica": "Stabilimento", "oficina": "Ufficio", "cpd": "Data center", "otro": "Altro"},
        "st": {"pendiente": "In sospeso", "en_progreso": "In corso", "ok": "OK",
               "incidencia": "Problema", "no_aplica": "N/D"},
        "sev": {"baja": "Bassa", "media": "Media", "alta": "Alta", "critica": "Critica"},
        "audit_status": {"en_progreso": "In corso", "completada": "Completato",
                         "archivada": "Archiviato"},
    },
}

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(DATA_DIR, "itaudit.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
db.init_app(app)

with app.app_context():
    db.create_all()


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
@app.context_processor
def inject_base():
    # En las plantillas: <base href="{{ base }}/">  (base == "" en local)
    return {"base": APP_BASE}


def _audit_upload_dir(audit_id):
    path = os.path.join(UPLOAD_DIR, str(audit_id))
    os.makedirs(path, exist_ok=True)
    return path


def _clean(value, maxlen=None):
    if value is None:
        return None
    value = str(value).strip()
    if maxlen:
        value = value[:maxlen]
    return value


def _apply_fields(obj, payload, spec):
    """spec: dict campo -> (maxlen | None, allowed_tuple | None). Devuelve True si cambio algo."""
    changed = False
    for field, (maxlen, allowed) in spec.items():
        if field not in payload:
            continue
        val = _clean(payload.get(field), maxlen)
        if allowed is not None and val not in allowed:
            abort(400, description="Valor no valido para '%s': %s" % (field, val))
        if getattr(obj, field) != val:
            setattr(obj, field, val)
            changed = True
    return changed


def _next_position(model, **filters):
    q = db.session.query(db.func.max(model.position)).filter_by(**filters)
    current = q.scalar()
    return (current or 0) + 1


# --------------------------------------------------------------------------- #
#  Vistas HTML
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/audit/<int:audit_id>")
def audit_view(audit_id):
    audit = db.session.get(Audit, audit_id)
    if audit is None:
        abort(404)
    return render_template("audit.html", audit_id=audit_id)


@app.route("/audit/<int:audit_id>/report")
def audit_report(audit_id):
    audit = db.session.get(Audit, audit_id)
    if audit is None:
        abort(404)
    lang = request.args.get("lang", DEFAULT_LANG)
    if lang not in LANGS:
        lang = DEFAULT_LANG
    return render_template(
        "report.html",
        audit=audit,
        lang=lang,
        t=REPORT_I18N[lang],
        generated=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


@app.route("/health")
def health():
    return jsonify(ok=True)


# --------------------------------------------------------------------------- #
#  API - Auditorias
# --------------------------------------------------------------------------- #
@app.get("/api/audits")
def list_audits():
    audits = Audit.query.order_by(Audit.created_at.desc()).all()
    return jsonify([a.to_dict() for a in audits])


@app.post("/api/audits")
def create_audit():
    payload = request.get_json(force=True, silent=True) or {}
    name = _clean(payload.get("name"), 200)
    if not name:
        abort(400, description="El nombre de la auditoria es obligatorio.")

    audit = Audit(name=name)
    _apply_fields(
        audit,
        payload,
        {
            "location": (200, None),
            "client": (200, None),
            "auditor": (200, None),
            "start_date": (10, None),
            "notes": (None, None),
            "kind": (20, AUDIT_KIND),
            "status": (20, AUDIT_STATUS),
        },
    )
    db.session.add(audit)
    db.session.flush()

    # Materializar la plantilla (en el idioma pedido) salvo que se pida vacia.
    if payload.get("blank") is not True:
        lang = payload.get("lang") if payload.get("lang") in LANGS else DEFAULT_LANG
        for s_pos, sec in enumerate(build_template(lang), start=1):
            section = Section(
                audit_id=audit.id,
                key=sec["key"],
                title=sec["title"],
                description=sec.get("description", ""),
                position=s_pos,
            )
            db.session.add(section)
            db.session.flush()
            for i_pos, title in enumerate(sec.get("items", []), start=1):
                db.session.add(
                    Item(section_id=section.id, title=title, position=i_pos)
                )

    db.session.commit()
    return jsonify(audit.to_dict(deep=True)), 201


@app.get("/api/audits/<int:audit_id>")
def get_audit(audit_id):
    audit = db.session.get(Audit, audit_id)
    if audit is None:
        abort(404)
    return jsonify(audit.to_dict(deep=True))


@app.patch("/api/audits/<int:audit_id>")
def update_audit(audit_id):
    audit = db.session.get(Audit, audit_id)
    if audit is None:
        abort(404)
    payload = request.get_json(force=True, silent=True) or {}
    _apply_fields(
        audit,
        payload,
        {
            "name": (200, None),
            "location": (200, None),
            "client": (200, None),
            "auditor": (200, None),
            "start_date": (10, None),
            "notes": (None, None),
            "kind": (20, AUDIT_KIND),
            "status": (20, AUDIT_STATUS),
        },
    )
    if not audit.name:
        abort(400, description="El nombre no puede quedar vacio.")
    db.session.commit()
    return jsonify(audit.to_dict())


@app.delete("/api/audits/<int:audit_id>")
def delete_audit(audit_id):
    audit = db.session.get(Audit, audit_id)
    if audit is None:
        abort(404)
    db.session.delete(audit)
    db.session.commit()

    # Limpiar adjuntos en disco.
    folder = os.path.join(UPLOAD_DIR, str(audit_id))
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, fname))
            except OSError:
                pass
        try:
            os.rmdir(folder)
        except OSError:
            pass
    return jsonify(ok=True)


# --------------------------------------------------------------------------- #
#  API - Secciones
# --------------------------------------------------------------------------- #
@app.post("/api/sections")
def create_section():
    payload = request.get_json(force=True, silent=True) or {}
    audit_id = payload.get("audit_id")
    audit = db.session.get(Audit, audit_id) if audit_id else None
    if audit is None:
        abort(404, description="Auditoria no encontrada.")
    title = _clean(payload.get("title"), 200)
    if not title:
        abort(400, description="El titulo de la seccion es obligatorio.")
    section = Section(
        audit_id=audit.id,
        title=title,
        key=_clean(payload.get("key"), 60) or "",
        description=_clean(payload.get("description"), None) or "",
        position=_next_position(Section, audit_id=audit.id),
    )
    db.session.add(section)
    db.session.commit()
    return jsonify(section.to_dict(deep=True)), 201


@app.patch("/api/sections/<int:section_id>")
def update_section(section_id):
    section = db.session.get(Section, section_id)
    if section is None:
        abort(404)
    payload = request.get_json(force=True, silent=True) or {}
    _apply_fields(
        section,
        payload,
        {"title": (200, None), "description": (None, None), "key": (60, None)},
    )
    if "position" in payload:
        try:
            section.position = int(payload["position"])
        except (TypeError, ValueError):
            abort(400, description="position debe ser un entero.")
    if not section.title:
        abort(400, description="El titulo no puede quedar vacio.")
    db.session.commit()
    return jsonify(section.to_dict())


@app.delete("/api/sections/<int:section_id>")
def delete_section(section_id):
    section = db.session.get(Section, section_id)
    if section is None:
        abort(404)
    db.session.delete(section)
    db.session.commit()
    return jsonify(ok=True)


# --------------------------------------------------------------------------- #
#  API - Items
# --------------------------------------------------------------------------- #
@app.post("/api/items")
def create_item():
    payload = request.get_json(force=True, silent=True) or {}
    section_id = payload.get("section_id")
    section = db.session.get(Section, section_id) if section_id else None
    if section is None:
        abort(404, description="Seccion no encontrada.")
    title = _clean(payload.get("title"), 300)
    if not title:
        abort(400, description="El titulo del item es obligatorio.")
    item = Item(
        section_id=section.id,
        title=title,
        position=_next_position(Item, section_id=section.id),
    )
    _apply_fields(
        item,
        payload,
        {
            "description": (None, None),
            "assignee": (200, None),
            "due_date": (10, None),
            "findings": (None, None),
            "recommendation": (None, None),
            "status": (20, ITEM_STATUS),
            "severity": (20, ITEM_SEVERITY),
        },
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.patch("/api/items/<int:item_id>")
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    payload = request.get_json(force=True, silent=True) or {}
    _apply_fields(
        item,
        payload,
        {
            "title": (300, None),
            "description": (None, None),
            "assignee": (200, None),
            "due_date": (10, None),
            "findings": (None, None),
            "recommendation": (None, None),
            "status": (20, ITEM_STATUS),
            "severity": (20, ITEM_SEVERITY),
        },
    )
    if "section_id" in payload:
        target = db.session.get(Section, payload["section_id"])
        if target is None:
            abort(400, description="Seccion destino no valida.")
        item.section_id = target.id
    if "position" in payload:
        try:
            item.position = int(payload["position"])
        except (TypeError, ValueError):
            abort(400, description="position debe ser un entero.")
    if not item.title:
        abort(400, description="El titulo no puede quedar vacio.")
    db.session.commit()
    return jsonify(item.to_dict())


@app.delete("/api/items/<int:item_id>")
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    return jsonify(ok=True)


# --------------------------------------------------------------------------- #
#  API - Adjuntos
# --------------------------------------------------------------------------- #
def _ext_ok(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


@app.post("/api/items/<int:item_id>/attachments")
def upload_attachment(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    if "file" not in request.files:
        abort(400, description="No se ha enviado ningun fichero (campo 'file').")
    file = request.files["file"]
    if not file or not file.filename:
        abort(400, description="Fichero vacio.")
    if not _ext_ok(file.filename):
        abort(400, description="Tipo de fichero no permitido.")

    audit_id = item.section.audit_id
    folder = _audit_upload_dir(audit_id)
    safe = secure_filename(file.filename) or "fichero"
    stored = "%d_%s_%s" % (item_id, uuid.uuid4().hex[:8], safe)
    file.save(os.path.join(folder, stored))
    size = os.path.getsize(os.path.join(folder, stored))
    mime = file.mimetype or mimetypes.guess_type(safe)[0] or "application/octet-stream"

    att = Attachment(
        item_id=item_id,
        stored_name=stored,
        original_name=file.filename[:255],
        mime=mime,
        size=size,
    )
    db.session.add(att)
    db.session.commit()
    return jsonify(att.to_dict()), 201


def _attachment_path(att):
    audit_id = att.item.section.audit_id
    return os.path.join(UPLOAD_DIR, str(audit_id), att.stored_name)


@app.get("/api/attachments/<int:att_id>")
def download_attachment(att_id):
    att = db.session.get(Attachment, att_id)
    if att is None:
        abort(404)
    path = _attachment_path(att)
    if not os.path.isfile(path):
        abort(404)
    as_download = request.args.get("dl") == "1"
    return send_file(
        path,
        mimetype=att.mime,
        as_attachment=as_download,
        download_name=att.original_name,
    )


@app.delete("/api/attachments/<int:att_id>")
def delete_attachment(att_id):
    att = db.session.get(Attachment, att_id)
    if att is None:
        abort(404)
    path = _attachment_path(att)
    db.session.delete(att)
    db.session.commit()
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
    return jsonify(ok=True)


# --------------------------------------------------------------------------- #
#  Errores JSON coherentes para /api/*
# --------------------------------------------------------------------------- #
@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(413)
def _json_errors(err):
    if request.path.startswith("/api/"):
        return jsonify(error=getattr(err, "description", str(err)), code=err.code), err.code
    return err


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5001"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
