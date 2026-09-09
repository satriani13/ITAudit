# -*- coding: utf-8 -*-
"""Modelos SQLAlchemy de la webapp de auditoria IT."""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# --- Vocabularios (se validan en la capa API, aqui solo como referencia) ---
AUDIT_STATUS = ("en_progreso", "completada", "archivada")
AUDIT_KIND = ("fabrica", "oficina", "cpd", "otro")
ITEM_STATUS = ("pendiente", "en_progreso", "ok", "incidencia", "no_aplica")
ITEM_SEVERITY = ("baja", "media", "alta", "critica")

# Estados que cuentan como "resuelto" para el calculo de progreso.
DONE_STATUS = ("ok", "no_aplica")


def _now():
    return datetime.utcnow()


class Audit(db.Model):
    __tablename__ = "audits"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), default="")
    kind = db.Column(db.String(20), default="fabrica")
    client = db.Column(db.String(200), default="")
    auditor = db.Column(db.String(200), default="")
    status = db.Column(db.String(20), default="en_progreso")
    start_date = db.Column(db.String(10), default="")  # ISO yyyy-mm-dd
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    sections = db.relationship(
        "Section",
        backref="audit",
        cascade="all, delete-orphan",
        order_by="Section.position",
    )

    def progress(self):
        total = 0
        done = 0
        for section in self.sections:
            for item in section.items:
                total += 1
                if item.status in DONE_STATUS:
                    done += 1
        pct = round(done * 100 / total) if total else 0
        return {"total": total, "done": done, "pct": pct}

    def issue_count(self):
        return sum(
            1
            for section in self.sections
            for item in section.items
            if item.status == "incidencia"
        )

    def to_dict(self, deep=False):
        data = {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "kind": self.kind,
            "client": self.client,
            "auditor": self.auditor,
            "status": self.status,
            "start_date": self.start_date,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "progress": self.progress(),
            "issues": self.issue_count(),
        }
        if deep:
            data["sections"] = [s.to_dict(deep=True) for s in self.sections]
        return data


class Section(db.Model):
    __tablename__ = "sections"

    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(
        db.Integer, db.ForeignKey("audits.id", ondelete="CASCADE"), nullable=False
    )
    key = db.Column(db.String(60), default="")
    # tkey: clave de plantilla. Si tiene valor, el texto (título/descripción) es el
    # de la plantilla y se muestra traducido al idioma de la UI. Se pone a NULL en
    # cuanto el usuario edita el texto (pasa a ser contenido propio).
    tkey = db.Column(db.String(80))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    position = db.Column(db.Integer, default=0)

    items = db.relationship(
        "Item",
        backref="section",
        cascade="all, delete-orphan",
        order_by="Item.position",
    )

    def progress(self):
        total = len(self.items)
        done = sum(1 for i in self.items if i.status in DONE_STATUS)
        pct = round(done * 100 / total) if total else 0
        return {"total": total, "done": done, "pct": pct}

    def to_dict(self, deep=False):
        data = {
            "id": self.id,
            "audit_id": self.audit_id,
            "key": self.key,
            "tkey": self.tkey,
            "title": self.title,
            "description": self.description,
            "position": self.position,
            "progress": self.progress(),
        }
        if deep:
            data["items"] = [i.to_dict() for i in self.items]
        return data


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(
        db.Integer, db.ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    # tkey: ver Section.tkey. NULL = ítem propio (texto tal cual); con valor = ítem
    # de plantilla, se muestra traducido al idioma de la UI.
    tkey = db.Column(db.String(80))
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pendiente")
    severity = db.Column(db.String(20), default="media")
    assignee = db.Column(db.String(200), default="")
    due_date = db.Column(db.String(10), default="")
    findings = db.Column(db.Text, default="")
    recommendation = db.Column(db.Text, default="")
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    attachments = db.relationship(
        "Attachment",
        backref="item",
        cascade="all, delete-orphan",
        order_by="Attachment.created_at",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "section_id": self.section_id,
            "tkey": self.tkey,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "severity": self.severity,
            "assignee": self.assignee,
            "due_date": self.due_date,
            "findings": self.findings,
            "recommendation": self.recommendation,
            "position": self.position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "attachments": [a.to_dict() for a in self.attachments],
        }


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(
        db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    stored_name = db.Column(db.String(255), nullable=False)  # nombre en disco
    original_name = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(120), default="application/octet-stream")
    size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=_now)

    @property
    def is_image(self):
        return (self.mime or "").startswith("image/")

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "original_name": self.original_name,
            "mime": self.mime,
            "size": self.size,
            "is_image": self.is_image,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
