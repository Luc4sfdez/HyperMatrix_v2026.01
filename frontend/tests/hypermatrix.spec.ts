import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://127.0.0.1:26020';

test.describe('HyperMatrix Frontend Tests', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test.describe('Dashboard Page', () => {

    test('should load the dashboard', async ({ page }) => {
      await expect(page.getByRole('heading', { name: 'HyperMatrix' }).first()).toBeVisible();
      await page.screenshot({ path: 'test-results/dashboard-loaded.png' });
    });

    test('should show connection status indicator', async ({ page }) => {
      const statusIndicator = page.locator('.rounded-full').first();
      await expect(statusIndicator).toBeVisible();
    });

    test('should display project path input field', async ({ page }) => {
      // Use the specific placeholder for the path input
      const input = page.getByPlaceholder(/selecciona o ingresa/i);
      await expect(input).toBeVisible();
    });

    test('should show project history dropdown when clicking input', async ({ page }) => {
      const input = page.getByPlaceholder(/selecciona o ingresa/i);
      await input.click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: 'test-results/project-dropdown.png' });

      const dropdown = page.locator('.absolute.z-50');
      if (await dropdown.count() > 0) {
        console.log('Dropdown visible with history');
      }
    });

    test('should have Explorar button', async ({ page }) => {
      await expect(page.getByRole('button', { name: /explorar/i })).toBeVisible();
    });

    test('should have Iniciar Analisis button', async ({ page }) => {
      await expect(page.getByRole('button', { name: /iniciar/i })).toBeVisible();
    });

  });

  test.describe('Sidebar Navigation', () => {

    test('should have sidebar with navigation', async ({ page }) => {
      // Use exact match for Dashboard
      const dashboardLink = page.getByRole('link', { name: /^.*Dashboard$/i }).first();
      await expect(dashboardLink).toBeVisible();
    });

    test('should navigate to Resultados page', async ({ page }) => {
      await page.getByRole('link', { name: /resultados/i }).click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/resultados-page.png' });
    });

    test('should navigate to Explorador BD page', async ({ page }) => {
      await page.getByRole('link', { name: /explorador/i }).click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/explorer-page.png' });
    });

    test('should navigate to Comparador page', async ({ page }) => {
      await page.getByRole('link', { name: /comparador/i }).click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/compare-page.png' });
    });

    test('should navigate to Reglas page', async ({ page }) => {
      // Reglas is inside the collapsible "SISTEMA" section - expand it first
      const sistemaSection = page.getByText('SISTEMA');
      await sistemaSection.click();
      await page.waitForTimeout(300);

      // Click Reglas - use force because bottom status bar may overlap
      await page.getByRole('link', { name: /reglas/i }).click({ force: true });
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/rules-page.png' });
    });

  });

  test.describe('Scan Results Page', () => {

    test('should display scan results page', async ({ page }) => {
      await page.getByRole('link', { name: /resultados/i }).click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'test-results/scan-results.png' });
    });

    test('should show scan information', async ({ page }) => {
      await page.getByRole('link', { name: /resultados/i }).click();
      await page.waitForTimeout(1500);

      const scanCards = page.locator('[class*="border-l-4"]');
      const count = await scanCards.count();
      console.log(`Found ${count} scan cards`);
      await page.screenshot({ path: 'test-results/scan-cards.png' });
    });

  });

  test.describe('API Integration', () => {

    test('backend health check', async ({ request }) => {
      const response = await request.get(`${BACKEND_URL}/health`);
      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      expect(data.status).toBe('healthy');
      console.log('Backend:', data);
    });

    test('history API returns data', async ({ request }) => {
      const response = await request.get(`${BACKEND_URL}/api/history/projects`);
      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      expect(data).toHaveProperty('recent');
      expect(data).toHaveProperty('favorites');
      console.log(`History: ${data.recent.length} recent, ${data.favorites.length} favorites`);
      if (data.favorites.length > 0) {
        console.log('Favorites:', data.favorites.map((f: any) => f.name));
      }
    });

    test('scan list API returns data', async ({ request }) => {
      const response = await request.get(`${BACKEND_URL}/api/scan/list`);
      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      expect(data).toHaveProperty('scans');
      console.log(`Scans: ${data.scans.length} available`);
    });

    test('browse API works', async ({ request }) => {
      const response = await request.get(`${BACKEND_URL}/api/browse?path=C:/`);
      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      expect(data).toHaveProperty('items');
      console.log(`Browse C:/: ${data.items.length} items`);
    });

  });

  test.describe('File Browser', () => {

    test('should open file browser modal', async ({ page }) => {
      await page.getByRole('button', { name: /explorar/i }).click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: 'test-results/file-browser.png' });

      const modal = page.locator('.fixed.inset-0');
      const isOpen = await modal.count() > 0;
      console.log(`File browser modal open: ${isOpen}`);
      expect(isOpen).toBeTruthy();
    });

  });

});

test.describe('Integration Flow', () => {

  test('complete navigation flow', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    console.log('Step 1: Dashboard');
    await page.screenshot({ path: 'test-results/flow-1.png' });

    await page.getByRole('link', { name: /resultados/i }).click();
    await page.waitForTimeout(1000);
    console.log('Step 2: Results');
    await page.screenshot({ path: 'test-results/flow-2.png' });

    await page.getByRole('link', { name: /comparador/i }).click();
    await page.waitForTimeout(500);
    console.log('Step 3: Comparador');
    await page.screenshot({ path: 'test-results/flow-3.png' });

    // Click first Dashboard link (not Dashboard ML)
    await page.getByRole('link', { name: /dashboard/i }).first().click();
    await page.waitForTimeout(500);
    console.log('Step 4: Back to dashboard');
    await page.screenshot({ path: 'test-results/flow-4.png' });

    await expect(page.getByRole('button', { name: /iniciar/i })).toBeVisible();
  });

  test('project selector interaction', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const input = page.getByPlaceholder(/selecciona o ingresa/i);
    await input.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: 'test-results/selector-open.png' });

    await input.fill('E:/Test');
    await page.waitForTimeout(300);
    await page.screenshot({ path: 'test-results/selector-typed.png' });

    await input.clear();
    await input.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'test-results/selector-cleared.png' });
  });

});
