export interface DateRange {
    start: Date | null;
    end: Date | null;
}

export interface GlassCalendarProps {
    /** Additional CSS classes for the container */
    className?: string;
    /** Whether to allow selecting a date range */
    enableRangeSelection?: boolean;
    /** Callback fired when the selected range changes */
    onRangeSelect?: (range: DateRange) => void;
    /** Number of months to display */
    monthsToShow?: number;
}
