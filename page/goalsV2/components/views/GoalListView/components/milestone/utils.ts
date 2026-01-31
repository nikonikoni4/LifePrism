import { MilestoneItem, EditableMilestone } from '../../../../../types';

export const convertToEditableMilestones = (milestones: MilestoneItem[]): EditableMilestone[] => {
    return milestones.map(m => ({
        id: m.id,
        content: m.content,
        orderIndex: m.orderIndex
    }));
};