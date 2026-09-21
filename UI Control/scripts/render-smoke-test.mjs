import { existsSync, mkdirSync, realpathSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';

const studioUrl = process.env.STUDIO_URL || 'http://127.0.0.1:5200/';

function findBrowser() {
  const candidates = process.platform === 'win32'
    ? [
        join(process.env.PROGRAMFILES || '', 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'),
        join(process.env.PROGRAMFILES || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
        join(process.env['PROGRAMFILES(X86)'] || '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      ]
    : ['/usr/bin/brave-browser', '/usr/bin/google-chrome', '/usr/bin/chromium'];

  const browser = candidates.find(candidate => candidate && existsSync(candidate));
  if (!browser) throw new Error('No supported Chromium browser found for the render smoke test.');
  return browser;
}

async function reservePort() {
  const server = createServer();
  await new Promise((resolvePromise, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolvePromise);
  });
  const address = server.address();
  const port = typeof address === 'object' && address ? address.port : 0;
  await new Promise(resolvePromise => server.close(resolvePromise));
  return port;
}

async function waitForDebugPage(port) {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json`);
      const pages = await response.json();
      const page = pages.find(candidate => candidate.type === 'page' && candidate.url.startsWith(studioUrl));
      if (page?.webSocketDebuggerUrl) return page;
    } catch {
      // Browser is still starting.
    }
    await new Promise(resolvePromise => setTimeout(resolvePromise, 100));
  }
  throw new Error('Timed out waiting for the headless browser debug page.');
}

async function inspectRender(debugUrl) {
  const socket = new WebSocket(debugUrl);
  await new Promise((resolvePromise, reject) => {
    socket.addEventListener('open', resolvePromise, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });

  let requestId = 0;
  const pending = new Map();
  const exceptions = [];

  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message);
      pending.delete(message.id);
    }
    if (message.method === 'Runtime.exceptionThrown') {
      exceptions.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
    }
  });

  const send = (method, params = {}) => new Promise(resolvePromise => {
    const id = ++requestId;
    pending.set(id, resolvePromise);
    socket.send(JSON.stringify({ id, method, params }));
  });

  await send('Runtime.enable');
  await send('Page.enable');
  await send('Page.reload', { ignoreCache: true });
  await new Promise(resolvePromise => setTimeout(resolvePromise, 1_500));

  const response = await send('Runtime.evaluate', {
    expression: `({
      rootChildren: document.querySelector('#root')?.childElementCount ?? 0,
      bodyText: document.body.innerText.trim()
    })`,
    returnByValue: true,
  });

  socket.send(JSON.stringify({ id: ++requestId, method: 'Browser.close' }));

  return {
    ...response.result.result.value,
    exceptions,
  };
}

let browserProcess;
let profileDir;

try {
  const response = await fetch(studioUrl);
  if (!response.ok) throw new Error(`Studio returned HTTP ${response.status}.`);

  const port = await reservePort();
  const tempRoot = realpathSync(tmpdir());
  profileDir = resolve(join(tempRoot, `homecartel-render-smoke-${process.pid}`));
  if (!profileDir.startsWith(`${tempRoot}${sep}`)) {
    throw new Error(`Refusing to create browser profile outside temp: ${profileDir}`);
  }
  mkdirSync(profileDir, { recursive: true });

  browserProcess = spawn(findBrowser(), [
    `--user-data-dir=${profileDir}`,
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    `--remote-debugging-port=${port}`,
    studioUrl,
  ], { stdio: 'ignore' });

  const page = await waitForDebugPage(port);
  const result = await inspectRender(page.webSocketDebuggerUrl);

  if (result.exceptions.length) {
    throw new Error(`Frontend runtime exception:\n${result.exceptions.join('\n')}`);
  }
  if (result.rootChildren === 0 || !result.bodyText) {
    throw new Error('Frontend rendered an empty #root element.');
  }

  console.log(`PASS: Studio rendered ${result.rootChildren} root child with visible content.`);
} finally {
  if (browserProcess && !browserProcess.killed) browserProcess.kill();
  await new Promise(resolvePromise => setTimeout(resolvePromise, 2_000));
  if (profileDir && existsSync(profileDir)) {
    const tempRoot = realpathSync(tmpdir());
    const resolvedProfile = resolve(profileDir);
    if (resolvedProfile.startsWith(`${tempRoot}${sep}`)) {
      try {
        rmSync(resolvedProfile, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 });
      } catch (error) {
        if (!['EBUSY', 'ENOTEMPTY', 'EPERM'].includes(error?.code)) throw error;
      }
    }
  }
}
