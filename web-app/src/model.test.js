import { describe, expect, it } from 'vitest';
import { cellCondition, decisionState, gateDefinitions, layers, number, simulate, strategies, updateGate } from './model';

describe('prototype-only scenario logic', () => {
  it('includes the three requested rotations with qualitative trade-offs', () => {
    expect(strategies.map(s => s.name)).toEqual(['Padi – Bera', 'Padi – Kedelai Anjasmoro', 'Padi – Kacang Hijau']);
    for (const strategy of strategies) {
      for (const field of ['water', 'nitrogen', 'pests', 'why', 'benefit', 'risk']) {
        expect(strategy[field].length).toBeGreaterThan(10);
      }
    }
  });
  it('responds deterministically without pretending to be a physics model', () => {
    expect(simulate(-30, 3)).toEqual(simulate(-30, 3));
    expect(simulate(-30, 3).moisture).toBeLessThan(simulate().moisture);
    expect(simulate(-30, 3).pvrs).toBeGreaterThan(simulate().pvrs);
    expect(simulate(30, 0).erosion).toBeGreaterThan(simulate().erosion);
    expect(simulate(30, 0).water).toBeGreaterThan(simulate().water);
    expect(simulate().savings).toBe(16.58);
  });
  it('constrains illustrative indicators to display ranges', () => {
    for (const rain of [-30, 0, 30]) for (const heat of [0, 1.5, 3]) {
      const result = simulate(rain, heat);
      expect(result.pvrs).toBeGreaterThan(0);
      expect(result.pvrs).toBeLessThan(1);
      expect(result.erosion).toBeGreaterThan(0);
      expect(result.erosion).toBeLessThan(1);
      expect(result.moisture).toBeGreaterThan(0);
      expect(result.moisture).toBeLessThan(100);
    }
  });
  it('keeps official advice withheld even after four simulated approvals', () => {
    for (const gates of [[], ['belum'], ['gagal'], ['lulus', 'lulus', 'lulus', 'lulus']]) {
      expect(decisionState(gates).status).toBe('ABSTAIN_FIELD_AUDIT_REQUIRED');
      expect(decisionState(gates).completeness).toBe(0);
    }
    expect(decisionState(['lulus', 'lulus', 'lulus', 'lulus']).passed).toBe(4);
    expect(decisionState(['gagal']).reason).toContain('gagal');
  });
  it('enforces sequential gates and invalidates later approvals on changes', () => {
    const fresh = ['belum', 'belum', 'belum', 'belum'];
    expect(updateGate(fresh, 2, 'lulus')).toEqual(fresh);
    const first = updateGate(fresh, 0, 'lulus');
    expect(updateGate(first, 1, 'lulus')).toEqual(['lulus', 'lulus', 'belum', 'belum']);
    expect(updateGate(['lulus', 'lulus', 'lulus', 'lulus'], 1, 'gagal')).toEqual(['lulus', 'gagal', 'belum', 'belum']);
    expect(updateGate(fresh, 0, 'not-valid')).toEqual(fresh);
  });
  it('respects native source scales and handles missing SRTM', () => {
    expect(layers).toHaveLength(5);
    expect(layers.find(layer => layer.id === 'smap').resolution).toBe('~9 km');
    expect(layers.find(layer => layer.id === 'gpm').resolution).toBe('0,1°');
    expect(layers.find(layer => layer.id === 'srtm').value).toBe('Belum Tersedia');
    expect(layers.find(layer => layer.id === 'eco').description).toContain('ESI terpisah');
    expect(gateDefinitions).toHaveLength(4);
  });
  it('makes visual layer states deterministic and hides indicators when disabled', () => {
    const cell = '898d8d654cbffff';
    expect(cellCondition(cell, [], simulate())).toBe('unknown');
    expect(cellCondition(cell, ['srtm'], simulate())).toBe('unknown');
    expect(cellCondition(cell, ['hls'], simulate())).toBe('safe');
    expect(cellCondition(cell, ['eco', 'gpm'], simulate())).toBe(cellCondition(cell, ['eco', 'gpm'], simulate()));
  });
  it('formats numbers in Indonesian', () => {
    expect(number(.78)).toBe('0,78');
    expect(number(16.58)).toBe('16,58');
  });
});
