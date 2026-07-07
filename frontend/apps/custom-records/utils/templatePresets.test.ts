/**
 * L3 模板预设测试
 *
 * Seam: templatePresets.ts — 纯函数 getTemplatePreset + TEMPLATE_PRESETS
 * 验证 5 套模板的 CSS 类名映射和配置正确性
 */
import { describe, it, expect } from 'vitest';
import { TEMPLATE_PRESETS, getTemplatePreset, TEMPLATE_IDS } from './templatePresets';

describe('templatePresets', () => {
  // ==================== 模板完整性 ====================

  describe('TEMPLATE_PRESETS', () => {
    it('should have exactly 5 templates', () => {
      expect(TEMPLATE_PRESETS).toHaveLength(5);
    });

    it('should have unique ids for all templates', () => {
      const ids = TEMPLATE_PRESETS.map(t => t.id);
      expect(new Set(ids).size).toBe(5);
    });

    it('should include clean, paper, minimal, bold, metric templates', () => {
      const ids = TEMPLATE_IDS;
      expect(ids).toContain('clean');
      expect(ids).toContain('paper');
      expect(ids).toContain('minimal');
      expect(ids).toContain('bold');
      expect(ids).toContain('metric');
    });

    it('each template should have required properties', () => {
      for (const t of TEMPLATE_PRESETS) {
        expect(t).toHaveProperty('id');
        expect(t).toHaveProperty('name');
        expect(t).toHaveProperty('description');
        expect(t).toHaveProperty('cardClass');
        expect(t).toHaveProperty('titleClass');
        expect(t).toHaveProperty('mainClass');
        expect(t).toHaveProperty('chipClass');
        expect(t).toHaveProperty('accentBarClass');
      }
    });
  });

  // ==================== getTemplatePreset ====================

  describe('getTemplatePreset', () => {
    it('should return clean template by default', () => {
      const t = getTemplatePreset('clean');
      expect(t.id).toBe('clean');
      expect(t.name).toBe('简洁');
    });

    it('should return paper template', () => {
      const t = getTemplatePreset('paper');
      expect(t.id).toBe('paper');
      expect(t.name).toBe('纸张');
    });

    it('should return minimal template', () => {
      const t = getTemplatePreset('minimal');
      expect(t.id).toBe('minimal');
      expect(t.name).toBe('极简');
    });

    it('should return bold template', () => {
      const t = getTemplatePreset('bold');
      expect(t.id).toBe('bold');
      expect(t.name).toBe('粗体');
    });

    it('should return metric template', () => {
      const t = getTemplatePreset('metric');
      expect(t.id).toBe('metric');
      expect(t.name).toBe('数据');
    });

    it('should fallback to clean for unknown template id', () => {
      const t = getTemplatePreset('nonexistent');
      expect(t.id).toBe('clean');
    });

    it('should fallback to clean for undefined input', () => {
      const t = getTemplatePreset(undefined);
      expect(t.id).toBe('clean');
    });
  });

  // ==================== 模板差异化 ====================

  describe('template differentiation', () => {
    it('clean and paper should have different cardClass', () => {
      expect(getTemplatePreset('clean').cardClass).not.toBe(getTemplatePreset('paper').cardClass);
    });

    it('bold should have font-bold in titleClass', () => {
      const bold = getTemplatePreset('bold');
      expect(bold.titleClass).toContain('font-bold');
    });

    it('metric should have mono font somewhere', () => {
      const metric = getTemplatePreset('metric');
      const allClasses = `${metric.cardClass} ${metric.titleClass} ${metric.mainClass} ${metric.chipClass}`;
      expect(allClasses).toMatch(/mono|font-mono/);
    });
  });
});
