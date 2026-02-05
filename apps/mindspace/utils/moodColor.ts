
interface ColorPoint {
  p: number;
  label: string;
  color: string; // Hex
  bg: string;    // Hex
}

export const MOOD_COLOR_POINTS: ColorPoint[] = [
  { p: 0, label: "非常不愉快", color: "#4B49AC", bg: "#EBEBFF" },
  { p: 17, label: "不愉快", color: "#3F51B5", bg: "#E8EAF6" },
  { p: 33, label: "有点不愉快", color: "#63B3ED", bg: "#EBF8FF" },
  { p: 50, label: "不悲不喜", color: "#94A3B8", bg: "#F1F5F9" },
  { p: 67, label: "有点愉快", color: "#4ADE80", bg: "#F0FDF4" },
  { p: 83, label: "愉快", color: "#FACC15", bg: "#FEFCE8" },
  { p: 100, label: "非常愉快", color: "#F97316", bg: "#FFF7ED" }
];

/**
 * 将两种十六进制颜色按照比例混合
 */
export const interpolateHexColor = (color1: string, color2: string, factor: number): string => {
  const r1 = parseInt(color1.substring(1, 3), 16);
  const g1 = parseInt(color1.substring(3, 5), 16);
  const b1 = parseInt(color1.substring(5, 7), 16);

  const r2 = parseInt(color2.substring(1, 3), 16);
  const g2 = parseInt(color2.substring(3, 5), 16);
  const b2 = parseInt(color2.substring(5, 7), 16);

  const r = Math.round(r1 + factor * (r2 - r1));
  const g = Math.round(g1 + factor * (g2 - g1));
  const b = Math.round(b1 + factor * (b2 - b1));

  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase()}`;
};

/**
 * 根据分数获取心情颜色样式
 * @param {number} score - 0-100 的分数
 * @returns {object} - 返回包含 { bg, color } 的对象
 */
export const getMoodStyleByScore = (score: number): { bg: string; color: string } => {
  let lower = MOOD_COLOR_POINTS[0];
  let upper = MOOD_COLOR_POINTS[MOOD_COLOR_POINTS.length - 1];

  for (let i = 0; i < MOOD_COLOR_POINTS.length - 1; i++) {
    if (score >= MOOD_COLOR_POINTS[i].p && score <= MOOD_COLOR_POINTS[i + 1].p) {
      lower = MOOD_COLOR_POINTS[i];
      upper = MOOD_COLOR_POINTS[i + 1];
      break;
    }
  }

  const range = upper.p - lower.p;
  const factor = range === 0 ? 0 : (score - lower.p) / range;

  return {
    bg: interpolateHexColor(lower.bg, upper.bg, factor),
    color: interpolateHexColor(lower.color, upper.color, factor)
  };
};
