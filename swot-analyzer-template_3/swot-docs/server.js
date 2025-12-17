#!/usr/bin/env node
/**
 * Запуск Docusaurus с Basic Auth
 * Использование: node server.js
 * 
 * Переменные окружения:
 *   SWOT_USER - логин (по умолчанию: admin)
 *   SWOT_PASSWORD - пароль (по умолчанию: swot2024)
 *   PORT - порт (по умолчанию: 3000)
 */

const { spawn } = require('child_process');
const http = require('http');
const httpProxy = require('http-proxy');

const USER = process.env.SWOT_USER || 'admin';
const PASSWORD = process.env.SWOT_PASSWORD || 'swot2024';
const PORT = parseInt(process.env.PORT || '3000');
const DOCUSAURUS_PORT = 3001;

console.log(`
🔐 SWOT Analyzer с авторизацией
================================
👤 Логин: ${USER}
🔑 Пароль: ${PASSWORD.slice(0, 2)}${'*'.repeat(PASSWORD.length - 2)}
🌐 Порт: ${PORT}
================================
`);

// Запускаем Docusaurus на внутреннем порту
const docusaurus = spawn('npx', ['docusaurus', 'start', '--port', DOCUSAURUS_PORT.toString(), '--no-open'], {
  stdio: ['pipe', 'pipe', 'pipe'],
  shell: true,
});

docusaurus.stdout.on('data', (data) => {
  const msg = data.toString();
  if (msg.includes('Docusaurus website is running')) {
    console.log('✅ Docusaurus запущен');
    console.log(`\n🌐 Откройте: http://localhost:${PORT}\n`);
  }
});

docusaurus.stderr.on('data', (data) => {
  // Фильтруем лишние сообщения
  const msg = data.toString();
  if (!msg.includes('webpack') && !msg.includes('Compiling')) {
    process.stderr.write(data);
  }
});

// Создаём прокси с Basic Auth
const proxy = httpProxy.createProxyServer({
  target: `http://localhost:${DOCUSAURUS_PORT}`,
  ws: true,
});

const server = http.createServer((req, res) => {
  // Проверяем Basic Auth
  const auth = req.headers.authorization;
  
  if (!auth || !auth.startsWith('Basic ')) {
    res.writeHead(401, {
      'WWW-Authenticate': 'Basic realm="SWOT Analyzer"',
      'Content-Type': 'text/html; charset=utf-8',
    });
    res.end('<h1>🔐 Требуется авторизация</h1>');
    return;
  }
  
  const credentials = Buffer.from(auth.slice(6), 'base64').toString();
  const [user, pass] = credentials.split(':');
  
  if (user !== USER || pass !== PASSWORD) {
    res.writeHead(401, {
      'WWW-Authenticate': 'Basic realm="SWOT Analyzer"',
      'Content-Type': 'text/html; charset=utf-8',
    });
    res.end('<h1>❌ Неверный логин или пароль</h1>');
    return;
  }
  
  // Проксируем запрос
  proxy.web(req, res, {}, (err) => {
    if (err) {
      res.writeHead(502);
      res.end('Docusaurus ещё запускается, подождите...');
    }
  });
});

// WebSocket для hot reload
server.on('upgrade', (req, socket, head) => {
  const auth = req.headers.authorization;
  
  if (auth && auth.startsWith('Basic ')) {
    const credentials = Buffer.from(auth.slice(6), 'base64').toString();
    const [user, pass] = credentials.split(':');
    
    if (user === USER && pass === PASSWORD) {
      proxy.ws(req, socket, head);
      return;
    }
  }
  
  socket.destroy();
});

server.listen(PORT, () => {
  console.log(`🔐 Прокси-сервер запущен на порту ${PORT}`);
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n👋 Завершение...');
  docusaurus.kill();
  server.close();
  process.exit(0);
});
