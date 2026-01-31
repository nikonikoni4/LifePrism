/**
 * goalsV2 类型统一导出
 */

// 核心业务实体
export type {
    ThemeKey,
    MilestoneItem,
    EditableMilestone,
    JournalEntry,
    Goal,
    PlanDoc,
} from './entities';

// 视图/组件相关
export type {
    DateCellData,
    CalendarViewProps,
    TaskPoolViewProps,
    DailyTaskStats,
    DailyTaskHeaderProps,
    DailyTaskToolbarProps,
    TaskInputBoxProps,
    PlanDocEditorViewProps,
    SelectOption,
    BaseViewProps,
} from './views';

// 通用类型
export type {
    ViewMode,
    ActiveTab,
    TodoItem,
} from './common';
