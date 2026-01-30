export type ViewMode = 'single' | 'dual';

export type ActiveTab = 'goals' | 'plans' | 'pool' | 'assign' | 'daily';

export interface BaseViewProps {
  className?: string;
}

export * from './entities';