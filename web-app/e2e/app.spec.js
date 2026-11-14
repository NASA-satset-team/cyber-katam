import { expect, test } from '@playwright/test';

test('analyst layers, valid H3 resolutions and cell details respond', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Memahami lahan. Merencanakan ketahanan.' })).toBeVisible();
  await expect(page.locator('.hexagons polygon')).toHaveCount(159);
  await page.getByRole('button', { name: '9', exact: true }).click();
  await expect(page.locator('.hexagons polygon')).toHaveCount(1000);
  await page.getByRole('button', { name: '7', exact: true }).click();
  await expect(page.locator('.hexagons polygon')).toHaveCount(30);
  await page.locator('.hexagons polygon').first().dispatchEvent('click');
  await expect(page.getByText('Tutupan lahan', { exact: true })).toBeVisible();
  await expect(page.locator('.cell-detail')).toContainText('Belum Tersedia');
  await expect(page.locator('.cell-detail')).toContainText('bukan observasi spesifik sel');
  await page.getByRole('button', { name: 'Tutup rincian sel' }).click();
  await page.getByRole('switch', { name: 'Lapisan ECOSTRESS' }).click();
  await expect(page.getByRole('switch', { name: 'Lapisan ECOSTRESS' })).toHaveAttribute('aria-checked', 'false');
  await expect(page.locator('.map-legend')).not.toContainText('Stres akar (PVRS)');
  await page.getByRole('switch', { name: 'Lapisan SMAP L4' }).click();
  await expect(page.locator('.active-context')).not.toContainText('SMAP');
  await page.getByRole('switch', { name: 'Lapisan SRTM' }).click();
  await expect(page.locator('.active-context')).toContainText('SRTM');
  await page.getByRole('button', { name: 'Tampilkan kisi H3' }).click();
  await expect(page.locator('.hexagons')).toHaveCSS('opacity', '0');
  await page.getByRole('button', { name: 'Perbesar peta' }).click();
  await page.getByRole('button', { name: 'Atur ulang peta' }).click();
  expect(errors).toEqual([]);
});

test('mock simulation updates only after running and resets gate approvals', async ({ page }) => {
  await page.goto('/');
  const initial = await page.locator('.risk-metric.red > strong').textContent();
  await page.getByRole('slider', { name: 'Anomali curah hujan' }).fill('-30');
  await page.getByRole('slider', { name: 'Kenaikan suhu' }).fill('3');
  await expect(page.locator('.risk-metric.red > strong')).toHaveText(initial);
  await expect(page.getByText('Perubahan belum dijalankan')).toBeVisible();
  await page.getByRole('button', { name: 'Jalankan Simulasi' }).click();
  await expect(page.locator('.risk-metric.red > strong')).not.toHaveText(initial);
  await expect(page.locator('.simulation-summary')).toContainText('Kondisi lebih kering');
  await page.getByRole('button', { name: 'Lihat Penjelasan Keputusan' }).click();
  await page.getByRole('button', { name: 'Simulasikan Lulus', exact: true }).click();
  await expect(page.locator('.gate-step').first()).toContainText('Lulus · Simulasi');
  await page.getByRole('button', { name: 'Kembali ke dasbor analis' }).click();
  await page.getByRole('button', { name: 'Jalankan Simulasi' }).click();
  await page.getByRole('button', { name: 'Lihat Penjelasan Keputusan' }).click();
  await expect(page.locator('.gate-step').first()).toContainText('Belum Diverifikasi');
});

test('four-gate audit enforces role and always abstains without real evidence', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Lihat Penjelasan Keputusan' }).click();
  await expect(page.locator('.xai-block')).toHaveCount(4);
  await page.locator('.gate-step').nth(3).click();
  await expect(page.getByText('Selesaikan gerbang sebelumnya', { exact: false })).toBeVisible();
  await page.locator('.gate-step').first().click();
  await page.getByRole('button', { name: 'Simulasikan Gagal', exact: true }).click();
  await expect(page.locator('.abstention-banner')).toContainText('gagal');
  for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Simulasikan Lulus', exact: true }).click();
  await page.getByRole('textbox', { name: 'Nama PPL untuk simulasi' }).fill('Siti Rahma');
  await page.getByRole('checkbox', { name: /Saya memahami/ }).check();
  await expect(page.getByRole('button', { name: 'Simulasikan Tanda Tangan PPL' })).toBeDisabled();
  await page.getByRole('combobox', { name: 'Peran verifikasi demo' }).selectOption('PPL');
  await page.getByRole('button', { name: 'Simulasikan Tanda Tangan PPL' }).click();
  await expect(page.locator('.signature-record')).toContainText('Siti Rahma');
  await expect(page.locator('.verification-meter')).toContainText('4/4');
  await expect(page.locator('.verification-meter')).toContainText('0%');
  await expect(page.locator('.abstention-banner')).toContainText('Abstain — Data Belum Memadai');
  await page.getByText('Bukti yang masih diperlukan', { exact: false }).click();
  await expect(page.getByText('Konfirmasi benih, inokulan, biaya, dan pasar', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Atur ulang verifikasi' }).click();
  await expect(page.locator('.verification-meter')).toContainText('0/4');
});

test('farmer mode compares crops, explains terms and exports actual PNG under 150 KB', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Petani / PPL', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Selamat pagi, Pak/Bu!' })).toBeVisible();
  await expect(page.locator('.farmer-scenario')).toHaveCount(3);
  await page.getByRole('button', { name: 'Cadangan air tanah' }).click();
  await expect(page.getByRole('tooltip')).toContainText('dimanfaatkan akar');
  await page.locator('.farmer-scenario').nth(2).getByRole('button').click();
  await expect(page.locator('.recommendation-content > h3')).toHaveText('Padi – Kacang Hijau');
  await page.getByRole('button', { name: 'Bagikan Ringkasan via WhatsApp' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('.share-preview img')).toBeVisible();
  await expect(page.getByText('Di bawah 150 KB', { exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Unduh Kartu PNG' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.png$/);
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  const image = Buffer.concat(chunks);
  expect(image.length).toBeLessThan(150_000);
  expect(image.subarray(1, 4).toString()).toBe('PNG');
  await page.getByRole('button', { name: 'Simulasikan Berbagi', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('status')).toBeVisible();
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('Tidak ada pesan WhatsApp yang dikirim');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: 'Lihat Alasan Rekomendasi' }).click();
  await expect(page.locator('.certificate-meta')).toContainText('Padi – Kacang Hijau');
});

test('mobile starts with farmer view and all three experiences fit the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Selamat pagi, Pak/Bu!' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.getByRole('button', { name: 'Lihat Alasan Rekomendasi' }).click();
  await expect(page.getByRole('heading', { name: 'Sertifikat Penjelasan Keputusan' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.getByRole('button', { name: /^Analis/ }).click();
  await expect(page.locator('.geospatial-svg')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
});

test('period and scenario choices propagate to the audit, with Indonesian UI', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Periode analisis' }).selectOption('11–20 November 2026');
  await page.getByRole('button', { name: /A Padi – Bera/ }).click();
  await page.getByRole('button', { name: 'Lihat Penjelasan Keputusan' }).click();
  await expect(page.locator('.certificate-meta')).toContainText('11–20 November 2026');
  await expect(page.locator('.certificate-meta')).toContainText('Padi – Bera');
  await expect(page.locator('html')).toHaveAttribute('lang', 'id');
});
