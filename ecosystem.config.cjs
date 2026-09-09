// PM2 — webapp de auditoria IT. Debe ser .cjs (evita choques con ESM del entorno).
// Arranque en el VPS: pm2 start ecosystem.config.cjs
module.exports = {
  apps: [
    {
      name: "it-audit",
      script: "app.py",
      interpreter: "venv/bin/python",
      cwd: __dirname,
      env: {
        HOST: "127.0.0.1",
        PORT: "3020",
        APP_BASE: "/proyectos/it-audit",
        MAX_UPLOAD_MB: "25",
      },
      autorestart: true,
      max_restarts: 10,
      watch: false,
    },
  ],
};
