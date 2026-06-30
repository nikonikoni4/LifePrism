/**
 * 日历滚动管理 Hook
 * 职责：仅在初始化时滚动到当前日期，用户点击日历时不触发滚动
 */
import { useEffect, useRef } from 'react';
import { debugLog } from './diaryDebug';

export function useCalendarScroll(activeDate: Date, enabled: boolean) {
  // 标记是否已经完成初始滚动
  const hasScrolledRef = useRef(false);
  // 追踪上次的 enabled 状态，用于检测从禁用到启用的切换
  const prevEnabledRef = useRef(enabled);

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
        containerFound: !!calendarContainer
      });

      if (el && calendarContainer) {
        // 计算元素相对于容器的位置
        const containerRect = calendarContainer.getBoundingClientRect();
        const elementRect = el.getBoundingClientRect();
        const offsetTop = elementRect.top - containerRect.top + calendarContainer.scrollTop;

        // 滚动到目标位置（居中）
        const scrollTo = offsetTop - containerRect.height / 2 + elementRect.height / 2;

        debugLog('scroll', '[useCalendarScroll] Scrolling calendar container', {
          containerScrollTop: calendarContainer.scrollTop,
          targetScrollTop: scrollTo,
          elementOffsetTop: offsetTop
        });

        calendarContainer.scrollTo({
          top: scrollTo,
          behavior: 'smooth'
        });

        hasScrolledRef.current = true;
        debugLog('scroll', '[useCalendarScroll] Scrolled successfully, marking as scrolled');
      } else {
        console.error('[useCalendarScroll] Missing required elements:', {
          element: !!el,
          container: !!calendarContainer
        });
        // 即使失败也标记为已滚动，避免重复尝试
        hasScrolledRef.current = true;
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [activeDate, enabled]);

  // 提供重置方法，用于"回到今天"按钮
  const resetScroll = () => {
    debugLog('scroll', '[useCalendarScroll] resetScroll called, clearing hasScrolled flag');
    hasScrolledRef.current = false;
  };

  return { resetScroll };
}
