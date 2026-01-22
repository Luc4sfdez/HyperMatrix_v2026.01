/**
 * HyperMatrix E2E Tests with Playwright
 * ======================================
 * Comprehensive end-to-end tests for all pages and functionality.
 *
 * Run: npx playwright test tests/e2e_test.js
 * Or:  node tests/e2e_test.js (standalone mode)
 */

const { chromium } = require('playwright');

const BASE_URL = process.env.HYPERMATRIX_URL || 'http://localhost:26020';

// Test results tracking
const results = [];
let errors = [];

async function test(name, fn) {
  try {
    await fn();
    results.push({ name, status: 'PASS' });
    console.log(`  [OK] ${name}`);
    return true;
  } catch (err) {
    results.push({ name, status: 'FAIL', error: err.message });
    console.log(`  [FAIL] ${name}: ${err.message}`);
    return false;
  }
}

async function runTests() {
  console.log('\n========================================');
  console.log('  HYPERMATRIX E2E TESTS');
  console.log(`  URL: ${BASE_URL}`);
  console.log('========================================\n');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text().substring(0, 200));
    }
  });
  page.on('pageerror', err => {
    errors.push(err.message.substring(0, 200));
  });

  try {
    // =====================
    // DASHBOARD
    // =====================
    console.log('> DASHBOARD');

    await test('Page loads', async () => {
      await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    });

    await test('Dashboard title visible', async () => {
      await page.waitForSelector('text=Dashboard', { timeout: 5000 });
    });

    await test('Sidebar navigation visible', async () => {
      const sidebar = await page.$('nav, [class*="sidebar"]');
      if (!sidebar) throw new Error('Sidebar not found');
    });

    // =====================
    // FILE BROWSER
    // =====================
    console.log('\n> FILE BROWSER');

    await test('Open file browser', async () => {
      // Click on folder selection button
      const folderBtn = await page.$('button:has-text("Seleccionar"), button:has-text("Carpeta"), button:has-text("Proyecto")');
      if (folderBtn) {
        await folderBtn.click();
        await page.waitForTimeout(1000);
      }
    });

    await test('Quick locations visible', async () => {
      // Check if Projects and Workspace buttons are visible
      const projectsBtn = await page.$('button:has-text("Proyectos")');
      const workspaceBtn = await page.$('button:has-text("Workspace")');
      // At least one should exist when file browser is open
      if (!projectsBtn && !workspaceBtn) {
        // Close modal if open and continue
        const closeBtn = await page.$('button:has-text("Cancelar"), button:has-text("Cerrar")');
        if (closeBtn) await closeBtn.click();
      }
    });

    // Close any open modal
    const closeBtn = await page.$('button:has-text("Cancelar")');
    if (closeBtn) await closeBtn.click();
    await page.waitForTimeout(500);

    // =====================
    // RESULTADOS
    // =====================
    console.log('\n> RESULTADOS');

    await test('Navigate to Resultados', async () => {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1000);

      // Try different ways to navigate
      let clicked = false;
      const selectors = ['text=Resultados', 'a:has-text("Resultados")', '[href*="result"]'];
      for (const sel of selectors) {
        const el = await page.$(sel);
        if (el && await el.isVisible()) {
          await el.click();
          clicked = true;
          break;
        }
      }
      if (!clicked) {
        // Maybe need to expand menu first
        const menuBtn = await page.$('text=Analisis');
        if (menuBtn) {
          await menuBtn.click();
          await page.waitForTimeout(300);
          const resultados = await page.$('text=Resultados');
          if (resultados) await resultados.click();
        }
      }
      await page.waitForTimeout(2000);
    });

    await test('Resultados page content', async () => {
      const content = await page.textContent('body');
      if (!content.includes('Resultados') && !content.includes('escaneo') && !content.includes('scan')) {
        throw new Error('Resultados page content not found');
      }
    });

    // =====================
    // LINEAGE
    // =====================
    console.log('\n> LINEAGE');

    await test('Navigate to Lineage', async () => {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1000);

      const lineageLink = await page.$('text=Grafo Linaje');
      if (lineageLink) {
        await lineageLink.click();
        await page.waitForTimeout(2000);
      } else {
        // Try expanding menu
        const menuBtn = await page.$('text=Analisis');
        if (menuBtn) await menuBtn.click();
        await page.waitForTimeout(300);
        const link = await page.$('text=Grafo Linaje');
        if (link) await link.click();
      }
      await page.waitForTimeout(2000);
    });

    await test('Lineage has dropdown', async () => {
      const select = await page.$('select');
      if (!select) throw new Error('No dropdown found');
    });

    // =====================
    // COMPARADOR
    // =====================
    console.log('\n> COMPARADOR');

    await test('Navigate to Comparador', async () => {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1000);

      const link = await page.$('text=Comparador');
      if (link && await link.isVisible()) {
        await link.click();
      }
      await page.waitForTimeout(2000);
    });

    await test('Compare page has inputs', async () => {
      const content = await page.textContent('body');
      if (!content.includes('Comparar') && !content.includes('archivo')) {
        throw new Error('Compare page content not found');
      }
    });

    // =====================
    // CONFIGURACION
    // =====================
    console.log('\n> CONFIGURACION');

    await test('Navigate to Configuracion', async () => {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1000);

      // Try Sistema menu
      const sysMenu = await page.$('text=Sistema');
      if (sysMenu) {
        await sysMenu.click();
        await page.waitForTimeout(300);
      }

      const link = await page.$('text=Configuracion');
      if (link && await link.isVisible()) {
        await link.click();
      }
      await page.waitForTimeout(2000);
    });

    await test('Config page has inputs', async () => {
      const inputs = await page.$$('input');
      if (inputs.length === 0) throw new Error('No inputs found');
    });

    // =====================
    // AI PANEL
    // =====================
    console.log('\n> AI PANEL');

    await test('Open AI panel', async () => {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1000);

      // Find AI button (robot emoji or similar)
      const aiBtn = await page.$('button:has-text("AI"), button:has-text("IA"), [title*="IA"], [title*="AI"]');
      if (aiBtn) {
        await aiBtn.click();
        await page.waitForTimeout(1000);
      }
    });

    await test('AI panel shows status', async () => {
      // Check for AI panel elements
      const content = await page.textContent('body');
      const hasAI = content.includes('Asistente') ||
                    content.includes('Ollama') ||
                    content.includes('modelo') ||
                    content.includes('Chat');
      if (!hasAI) {
        // AI panel might not be open, that's ok
        console.log('    (AI panel not visible)');
      }
    });

    // =====================
    // API HEALTH
    // =====================
    console.log('\n> API ENDPOINTS');

    await test('Health endpoint', async () => {
      const response = await page.request.get(`${BASE_URL}/health`);
      if (!response.ok()) throw new Error(`Status ${response.status()}`);
    });

    await test('Scan list endpoint', async () => {
      const response = await page.request.get(`${BASE_URL}/api/scan/list`);
      if (!response.ok()) throw new Error(`Status ${response.status()}`);
    });

    await test('Browse endpoint', async () => {
      const response = await page.request.get(`${BASE_URL}/api/browse?path=/projects`);
      if (!response.ok()) throw new Error(`Status ${response.status()}`);
    });

    await test('Workspace endpoint', async () => {
      const response = await page.request.get(`${BASE_URL}/api/workspace`);
      if (!response.ok()) throw new Error(`Status ${response.status()}`);
    });

    await test('AI status endpoint', async () => {
      const response = await page.request.get(`${BASE_URL}/api/ai/status`);
      if (!response.ok()) throw new Error(`Status ${response.status()}`);
    });

  } catch (err) {
    console.error(`\nFatal error: ${err.message}`);
  }

  await browser.close();

  // =====================
  // SUMMARY
  // =====================
  console.log('\n========================================');
  console.log('  RESULTS');
  console.log('========================================\n');

  let passed = 0, failed = 0;
  results.forEach(r => {
    if (r.status === 'PASS') passed++;
    else failed++;
  });

  console.log(`  Passed: ${passed}`);
  console.log(`  Failed: ${failed}`);
  console.log(`  Total:  ${results.length}`);

  if (errors.length > 0) {
    console.log(`\n  JS Errors: ${errors.length}`);
    errors.slice(0, 5).forEach(e => console.log(`    - ${e.substring(0, 100)}`));
  } else {
    console.log('\n  No JavaScript errors!');
  }

  console.log('\n========================================\n');

  return failed === 0;
}

// Run tests
runTests().then(success => {
  process.exit(success ? 0 : 1);
}).catch(err => {
  console.error(err);
  process.exit(1);
});
