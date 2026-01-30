/**
 * 统一背景样式配置
 * 为 goalsV2 视图提供一致的浅灰色背景，以突出白色系内容卡片
 */

/**
 * 主背景样式 - 浅灰色渐变
 * 使用微妙的渐变创造层次感，让白色内容更加突出
 */
export const viewBackground = {
    /** 基础背景类名 */
    className: 'bg-gradient-to-br from-slate-100 to-slate-200/60',

    /** 内联样式 - 用于需要更精细控制的场景 */
    style: {
        background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%)',
    } as React.CSSProperties,
};

/**
 * 带有微妙纹理的背景 - 更高级的视觉效果
 * 包含细微的网格纹理，增加设计深度
 */
export const viewBackgroundTextured = {
    /** 基础背景类名 */
    className: 'bg-slate-100/95',

    /** 带纹理的内联样式 */
    style: {
        background: `
            linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%),
            radial-gradient(circle at 25% 25%, rgba(0, 0, 0, 0.02) 1px, transparent 1px)
        `,
        backgroundSize: '100% 100%, 20px 20px',
    } as React.CSSProperties,
};

/**
 * 柔和的灰色背景 - 简洁版本
 * 适用于不需要渐变效果的场景
 */
export const viewBackgroundSimple = {
    /** Tailwind 类名 */
    className: 'bg-[#ecf1f6]',

    /** 内联样式 */
    style: {
        backgroundColor: '#ecf1f6',
    } as React.CSSProperties,
};

/**
 * 组合使用示例：
 * 
 * import { viewBackground } from '../shared/background';
 * 
 * // 使用 className
 * <div className={`h-full ${viewBackground.className}`}>
 * 
 * // 使用 style
 * <div className="h-full" style={viewBackground.style}>
 * 
 * // 组合使用
 * <div className={viewBackground.className} style={viewBackground.style}>
 */

export default viewBackground;
