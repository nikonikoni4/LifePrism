export const getDaysInMonth = (year: number, month: number) => new Date(year, month + 1, 0).getDate();
export const getFirstDayOfMonth = (year: number, month: number) => new Date(year, month, 1).getDay();

export const isSameDay = (d1: Date | null, d2: Date | null) => {
    if (!d1 || !d2) return false;
    return d1.getFullYear() === d2.getFullYear() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getDate() === d2.getDate();
};

export const isDayInRange = (date: Date | null, start: Date | null, end: Date | null) => {
    if (!start || !end || !date) return false;
    const target = date.getTime();
    const s = start.getTime();
    const e = end.getTime();
    return target > Math.min(s, e) && target < Math.max(s, e);
};

export const isToday = (date: Date) => isSameDay(date, new Date());

export interface DayData {
    date: Date | null;
    isCurrentMonth: boolean;
}

// Generate grid data for a single month
export const getMonthGridData = (year: number, month: number): DayData[] => {
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);

    const days: DayData[] = [];

    // Padding (previous month)
    for (let i = 0; i < firstDay; i++) {
        days.push({ date: null, isCurrentMonth: false });
    }

    // Current month
    for (let i = 1; i <= daysInMonth; i++) {
        const d = new Date(year, month, i);
        days.push({ date: d, isCurrentMonth: true });
    }

    return days;
};
