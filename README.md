# Auditoría IT

Webapp para registrar y hacer seguimiento de **auditorías IT** al poner en marcha
una nueva fábrica u oficina: infraestructura/CPD, red, cableado estructurado,
puestos, servidores, backup, software y licencias, seguridad, servicios,
proveedores, continuidad y documentación.

- **Plantilla fija + ítems dinámicos**: al crear una auditoría se generan 12
  secciones con sus checklists; luego se añaden/editan/borran secciones e ítems.
  La vista de auditoría muestra una **barra lateral con los apartados** y, a la
  derecha, solo los ítems del apartado seleccionado.
- Cada ítem tiene estado (`pendiente` / `en_progreso` / `ok` / `incidencia` /
  `no_aplica`), severidad, responsable, fecha límite, hallazgos, recomendación y
  **adjuntos** (fotos y documentos).
- Barras de progreso por sección y por auditoría, filtros e informe imprimible
  (`/audit/<id>/report?lang=es|en|it`).
- **Multi-idioma** ES / EN / IT: la interfaz se traduce al vuelo y la preferencia
  se guarda en el navegador (localStorage, por defecto ES). La plantilla de
  secciones/ítems se genera en el idioma activo al **crear** la auditoría; el
  texto que edites después se conserva tal cual y cambiar de idioma no reescribe
  auditorías ya creadas.

## Stack

Flask + Flask-SQLAlchemy + SQLite. Frontend sin build (Jinja + JS vanilla).
Base de datos en `data/itaudit.db` y adjuntos en `uploads/<audit_id>/`
(ambos se crean solos y están fuera de git).

## Desarrollo local

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
PORT=5001 venv/bin/python app.py
# http://localhost:5001/
```

Para probar el montaje en sub-path (como en el VPS):

```bash
PORT=5001 APP_BASE=/proyectos/it-audit venv/bin/python app.py
```

## Despliegue en el VPS (portal jpchost)

Sigue el patrón de `network-monitor` (Flask + PM2 + nginx `auth_request`).

1. **Clonar** y arrancar:

   ```bash
   git clone https://github.com/satriani13/ITAudit.git /var/www/proyectos-src/it-audit
   cd /var/www/proyectos-src/it-audit
   ./deploy.sh
   ```

   PM2 levanta `it-audit` escuchando en `127.0.0.1:3020`
   (`APP_BASE=/proyectos/it-audit`). Comprobar puerto libre antes:
   `ss -tlnp | grep 3020`.

2. **nginx** — en `/etc/nginx/sites-enabled/portal`, dentro del `server` 443:

   ```nginx
   location /proyectos/it-audit/ {
       auth_request /auth/verify;
       error_page 401 = @portal_login;
       proxy_pass http://127.0.0.1:3020/;
       proxy_set_header Host              $host;
       proxy_set_header X-Real-IP         $remote_addr;
       proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       client_max_body_size 30m;
   }
   ```

   Recargar: `nginx -t && nginx -s reload`.

3. **Registrar en el portal** (`/var/www/admin/data/portal.db`):

   ```sql
   INSERT INTO projects (slug, title, description, type, hosting, public, sort_order)
   VALUES ('it-audit', 'Auditoría IT',
           'Registro y seguimiento de auditorías IT para nuevas fábricas/oficinas',
           'app', 'vps', 0, 30);
   ```

   Asignar permisos al usuario correspondiente en la tabla `permissions`
   (o marcar el proyecto como visible desde el panel admin).

4. Acceso: `https://jpchost.ddns.net/proyectos/it-audit/` (requiere login del portal).

### Actualizaciones posteriores

```bash
cd /var/www/proyectos-src/it-audit && ./deploy.sh
```

## API

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/audits` | lista de auditorías |
| POST | `/api/audits` | crear (materializa la plantilla en `lang` = `es`/`en`/`it`; `{"blank": true}` la omite) |
| GET | `/api/audits/<id>` | auditoría con secciones e ítems |
| PATCH / DELETE | `/api/audits/<id>` | editar / borrar |
| POST | `/api/sections` | crear sección (`{audit_id, title}`) |
| PATCH / DELETE | `/api/sections/<id>` | editar / borrar |
| POST | `/api/items` | crear ítem (`{section_id, title}`) |
| PATCH / DELETE | `/api/items/<id>` | editar / borrar |
| POST | `/api/items/<id>/attachments` | subir adjunto (multipart, campo `file`) |
| GET | `/api/attachments/<id>` | descargar (`?dl=1` fuerza descarga) |
| DELETE | `/api/attachments/<id>` | borrar adjunto |
