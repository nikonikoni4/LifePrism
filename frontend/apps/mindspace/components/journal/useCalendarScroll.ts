/**
 * 日历滚动管理 Hook
 * 职责：
 * 1. 仅在初始化时滚动到当前日期（用户点击日历不触发滚动）
 * 2. 向上无限滚动：滚到顶部时按需 prepend 更早的月份（时间长廊）
 *
 * 防死循环设计（多层防护）：
 * - 防重入闸门 isLoadingOlderRef：加载期间忽略所有 scroll 事件
 * - rAF 节流：每帧最多检查一次，避免高频抖动
 * - 滚动位置补偿：prepend 后把 scrollTop 加上新增内容高度，视觉位置不变，
 *   补偿后 scrollTop 远离顶部，物理上不会再次触发
 * - 补偿后校验 + 无进展检测：异常情况下永久停止（hasReachedOldestRef）
 * - 最早年份下限 minYear：到达后永久停止
 */
import { useEffect, useLayoutEffect, useRef } from 'react';
import { debugLog } from './diaryDebug';

interface CalendarScrollOptions {
  /** 向上滚动到顶部时，加载更早月份的回调 */
  onLoadOlder?: (count: number) => void;
  /** 当前月份列表（用于判断是否已到达最早年份下限） */
  monthList?: Date[];
  /** 距顶部多少 px 内触发加载，默认 100 */
  loadThreshold?: number;
  /** 每次加载多少个月，默认 3 */
  loadBatchSize?: number;
  /** 最早年份下限，默认 2000，到达后停止加载 */
  minYear?: number;
}

export function useCalendarScroll(
  activeDate: Date,
  enabled: boolean,
  options?: CalendarScrollOptions,
) {
  // ---------- 初始滚动定位 ----------
  const hasScrolledRef = useRef(false);
  // 追踪上次的 enabled 状态，用于检测从禁用到启用的切换
  const prevEnabledRef = useRef(enabled);

  // ---------- 向上无限滚动 ----------
  const isLoadingOlderRef = useRef(false); // 防重入闸门
  const hasReachedOldestRef = useRef(false); // 已到最早/异常，永久停止
  const pendingCompensationRef = useRef<{ prevScrollHeight: number; prevScrollTop: number } | null>(null);
  const rafIdRef = useRef<number | null>(null);

  // 用 ref 持有最新值，避免 scroll 监听 effect 频繁重注册
  const monthListRef = useRef(options?.monthList);
  monthListRef.current = options?.monthList;
  const onLoadOlderRef = useRef(options?.onLoadOlder);
  onLoadOlderRef.current = options?.onLoadOlder;

  const threshold = options?.loadThreshold ?? 100;
  const batchSize = options?.loadBatchSize ?? 3;
  const minYear = options?.minYear ?? 2000;

  // ========== 初始滚动定位（保持原逻辑） ==========
  useEffect(() => {
    // 如果从禁用切换到启用（比如从设置视图返回），重置滚动标志
    if (!prevEnabledRef.current && enabled) {
      debugLog('scroll', '[useCalendarScroll] enabled changed from false to true, resetting hasScrolled');
      hasScrolledRef.current = false;
    }
    prevEnabledRef.current = enabled;

    debugLog('scroll', '[useCalendarScroll] useEffect triggered', {
      enabled,
      hasScrolled: hasScrolledRef.current,
      activeDate: activeDate.toISOString(),
    });

    // 只在启用且未滚动过的情况下执行初始滚动
    if (!enabled || hasScrolledRef.current) {
      debugLog('scroll', '[useCalendarScroll] Skip scroll:', !enabled ? 'disabled' : 'already scrolled');
      return;
    }

    const timer = setTimeout(() => {
      const scrollId = `diary-date-${activeDate.getFullYear()}-${activeDate.getMonth()}-${activeDate.getDate()}`;
      const el = document.getElementById(scrollId);
      const calendarContainer = document.getElementById('diary-calendar-container');

      debugLog('scroll', '[useCalendarScroll] Attempting to scroll to:', scrollId, {
        elementFound: !!el,
        containerFound: !!calendarContainer,
      });

      if (el && calendarContainer) {
        const containerRect = calendarContainer.getBoundingClientRect();
        const elementRect = el.getBoundingClientRect();
        const offsetTop = elementRect.top - containerRect.top + calendarContainer.scrollTop;
        const scrollTo = offsetTop - containerRect.height / 2 + elementRect.height / 2;

        debugLog('scroll', '[useCalendarScroll] Scrolling calendar container', {
          containerScrollTop: calendarContainer.scrollTop,
          targetScrollTop: scrollTo,
          elementOffsetTop: offsetTop,
        });

        calendarContainer.scrollTo({
          top: scrollTo,
          behavior: 'smooth',
        });

        // 延后标记为已滚动：等 smooth 滚动真正结束后才置 true，
        // 避免平滑滚动经过顶部区域时误触发向上无限加载
        const markScrolled = () => {
          hasScrolledRef.current = true;
          calendarContainer.removeEventListener('scrollend', markScrolled);
          debugLog('scroll', '[useCalendarScroll] Smooth scroll ended, marking as scrolled');
        };
        calendarContainer.addEventListener('scrollend', markScrolled);
        // 兜底：scrollend 未触发时（旧环境/被中断）强制解除屏蔽，避免永久卡死
        setTimeout(markScrolled, 800);
      } else {
        console.error('[useCalendarScroll] Missing required elements:', {
          element: !!el,
          container: !!calendarContainer,
        });
        // 即使失败也标记为已滚动，避免重复尝试
        hasScrolledRef.current = true;
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [activeDate, enabled]);

  // ========== 向上无限滚动监听 ==========
  useEffect(() => {
    if (!enabled) return;
    const calendarContainer = document.getElementById('diary-calendar-container');
    if (!calendarContainer) return;

    const onScroll = () => {
      // rAF 节流：每帧最多检查一次
      if (rafIdRef.current !== null) return;
      rafIdRef.current = requestAnimationFrame(() => {
        rafIdRef.current = null;

        // 初始定位滚动未完成前不响应（避免 smooth 经过顶部误触发加载）
        if (!hasScrolledRef.current) return;
        // 防重入 / 已到最早：直接忽略
        if (isLoadingOlderRef.current || hasReachedOldestRef.current) return;

        const { scrollTop, scrollHeight, clientHeight } = calendarContainer;
        // 未接近顶部：不触发
        if (scrollTop > threshold) return;
        // 内容不足以滚动时也不触发（避免无意义加载）
        if (scrollHeight - clientHeight <= threshold) return;

        // 最早年份下限兜底：到达后永久停止
        const list = monthListRef.current;
        if (list && list.length > 0 && list[0].getFullYear() <= minYear) {
          hasReachedOldestRef.current = true;
          debugLog('scroll', '[useCalendarScroll] 已到达最早年份下限，停止向上加载', { minYear });
          return;
        }

        // 没有加载回调则不触发（避免 pending 卡死）
        if (!onLoadOlderRef.current) return;

        // 触发加载：立即置闸门，记录补偿所需快照
        isLoadingOlderRef.current = true;
        pendingCompensationRef.current = {
          prevScrollHeight: scrollHeight,
          prevScrollTop: scrollTop,
        };
        debugLog('scroll', '[useCalendarScroll] 触发向上加载更早月份', {
          scrollTop,
          threshold,
          batchSize,
        });
        onLoadOlderRef.current(batchSize);
      });
    };

    calendarContainer.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      calendarContainer.removeEventListener('scroll', onScroll);
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
    // 依赖仅稳定标量；monthList/onLoadOlder 通过 ref 读取，避免频繁重注册
  }, [enabled, threshold, batchSize, minYear]);

  // ========== 滚动位置补偿（DOM 更新后、paint 前执行，避免闪烁与跳变） ==========
  useLayoutEffect(() => {
    if (!pendingCompensationRef.current) return;

    const calendarContainer = document.getElementById('diary-calendar-container');
    const { prevScrollHeight, prevScrollTop } = pendingCompensationRef.current;
    pendingCompensationRef.current = null;

    if (!calendarContainer) {
      isLoadingOlderRef.current = false;
      return;
    }

    const delta = calendarContainer.scrollHeight - prevScrollHeight;
    const targetScrollTop = prevScrollTop + delta;
    if (delta > 0) {
      // 补偿：保持用户视觉位置不变。
      // 容器带 CSS scroll-smooth，必须临时强制 instant，否则：
      // 1) scrollTop 赋值会变成平滑动画，动画过程触发 scroll 事件再次进入加载判定；
      // 2) 赋值后立即读取 scrollTop 返回的是动画起点（≈0），会被误判为"仍在顶部"
      //    而永久停止加载（表现为只能加载一次，如停在 2026-01）。
      const prevBehavior = calendarContainer.style.scrollBehavior;
      calendarContainer.style.scrollBehavior = 'auto';
      calendarContainer.scrollTop = targetScrollTop;
      calendarContainer.style.scrollBehavior = prevBehavior;
      debugLog('scroll', '[useCalendarScroll] 补偿滚动位置', {
        delta,
        targetScrollTop,
        actualScrollTop: calendarContainer.scrollTop,
      });
      // 用计算值判断（instant 后实际值即目标值）
      if (targetScrollTop < threshold) {
        hasReachedOldestRef.current = true;
        debugLog('scroll', '[useCalendarScroll] 补偿后仍在顶部，永久停止向上加载');
      }
    } else {
      // 无进展（未真正追加内容）：永久停止，防止死循环
      hasReachedOldestRef.current = true;
      debugLog('scroll', '[useCalendarScroll] 无进展，永久停止向上加载');
    }
    isLoadingOlderRef.current = false;
  }, [options?.monthList, threshold]);

  // 提供重置方法，用于"回到今天"按钮
  const resetScroll = () => {
    debugLog('scroll', '[useCalendarScroll] resetScroll called, clearing hasScrolled flag');
    hasScrolledRef.current = false;
  };

  return { resetScroll };
}
