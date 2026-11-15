import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test.use({ channel: 'chrome', timezoneId: 'Asia/Jakarta', viewport: { width: 1365, height: 900 } });

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-11-15T05:00:00Z'));
  const { levels } = JSON.parse(await readFile('public/demo-grid-levels.json', 'utf8'));
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname !== '/api/forecast/map') {
      await route.fulfill({ status: 503, json: { detail: 'Unavailable in UI test' } });
      return;
    }
    const date = url.searchParams.get('date');
    const offset = Number(date.slice(-2)) - 15;
    const resolution = Number(url.searchParams.get('resolution'));
    await route.fulfill({ json: {
      date, resolution, horizon_code: `H+${offset}`,
      cells: Object.fromEntries(levels[String(resolution)].map(cell => [cell.id, {
        fc_precip_total_mm: offset * 10, fc_precip_max_1h_mm: offset,
        fc_tmean_c: 26, fc_tmax_c: 30, fc_wind_max_ms: 3, n_children: 1,
      }])),
    } });
  });
  await page.goto('/id/dark/policymaker');
  await expect(page.locator('.leaflet-overlay-pane path[fill="#059669"]')).toHaveCount(552);
});

test('forecast days, resolutions and details replace only the weather overlay', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const next = page.getByRole('button', { name: 'Hari berikutnya', exact: false });
  const grid = page.locator('.leaflet-overlay-pane path[fill^="rgb("]');
  await next.click();
  await expect(page.locator('.forecast-map-legend')).toContainText('H+1');
  await expect(grid).toHaveCount(1500);
  const firstColor = await grid.first().getAttribute('fill');
  const index = await grid.evaluateAll(paths => paths.findIndex(path => {
    const r = path.getBoundingClientRect();
    return r.x > 400 && r.x < 900 && r.y > 200 && r.y < 600;
  }));
  expect(index).toBeGreaterThanOrEqual(0);
  await grid.nth(index).click();
  await expect(page.locator('.cell-detail')).toContainText('2026-11-16');
  await expect(page.locator('.cell-detail')).toContainText('10,0 mm');
  await expect(page.locator('.cell-detail')).toContainText('Prediksi turunan data API Meteomatics');
  await page.getByRole('button', { name: '9', exact: true }).dispatchEvent('click');
  await expect(grid).toHaveCount(4143);
  await expect(page.locator('.cell-detail')).toHaveCount(0);
  await next.click();
  await expect(page.locator('.forecast-map-legend')).toContainText('H+2');
  await expect(grid.first()).not.toHaveAttribute('fill', firstColor);
  await next.click();
  await expect(page.locator('.forecast-map-legend')).toContainText('H+3');
  await expect(next).toBeDisabled();
  await page.getByRole('button', { name: '7', exact: true }).dispatchEvent('click');
  await expect(grid).toHaveCount(425);
  await page.getByRole('button', { name: 'Tampilkan kisi H3', exact: true }).click();
  await expect(grid).toHaveCount(0);
  await expect(page.locator('.leaflet-overlay-pane path[fill="#059669"]')).toHaveCount(552);
  await page.getByRole('button', { name: 'Tampilkan kisi H3', exact: true }).click();
  await expect(grid).toHaveCount(425);
  for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Hari sebelumnya', exact: true }).click();
  await expect(page.locator('.period-date-display')).toHaveText('15 November 2026');
  await expect(page.locator('.forecast-map-legend')).toHaveCount(0);
  await expect(grid).toHaveCount(0);
  await expect(page.locator('.leaflet-overlay-pane path[fill="#64748b"]').first()).toBeAttached();
  expect(errors).toEqual([]);
});

test('forecast API failure never leaves historical scores on a future date', async ({ page }) => {
  await page.route('**/api/forecast/map?**', route => route.fulfill({
    status: 404, json: { detail: 'Tidak ada forecast untuk tanggal ini.' },
  }));
  await page.getByRole('button', { name: 'Hari berikutnya', exact: false }).click();
  await expect(page.getByRole('alert')).toContainText('Prediksi tidak tersedia');
  await expect(page.locator('.leaflet-overlay-pane path[fill^="rgb("]')).toHaveCount(0);
  await expect(page.locator('.leaflet-overlay-pane path[fill="#64748b"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Hari sebelumnya', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('.leaflet-overlay-pane path[fill="#64748b"]').first()).toBeAttached();
});

test('forecast legend fits on mobile without overlapping source notes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Hari berikutnya', exact: false }).click();
  await expect(page.locator('.forecast-map-legend')).toContainText('H+1');
  const legend = await page.locator('.forecast-map-legend').boundingBox();
  const source = await page.locator('.map-source-note').boundingBox();
  expect(legend.y + legend.height).toBeLessThan(source.y);
  expect(legend.x).toBeGreaterThanOrEqual(0);
  expect(legend.x + legend.width).toBeLessThanOrEqual(390);
  const path = test.info().outputPath('forecast-mobile.png');
  await page.screenshot({ path });
  console.log('Mobile screenshot:', path);
});
