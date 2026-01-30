/**
 * TodoItem 工具函数
 * 用于处理层级结构转换等操作
 */

import { TodoItem } from './types';

/**
 * 将扁平的 TodoItem 列表转换为树形结构
 * @param items - 扁平的 TodoItem 数组（包含 parentId 字段）
 * @returns 构建好的树形结构（根节点的 parentId 为 null）
 */
export function flatListToTree(items: TodoItem[]): TodoItem[] {
    const itemMap = new Map<number, TodoItem>();
    const roots: TodoItem[] = [];

    // 第一遍：创建所有项的映射，并初始化 children
    items.forEach(item => {
        itemMap.set(item.id, { ...item, children: [] });
    });

    // 第二遍：构建父子关系
    items.forEach(item => {
        const current = itemMap.get(item.id)!;
        if (item.parentId === null) {
            // 根节点
            roots.push(current);
        } else {
            // 子节点，找到父节点并添加
            const parent = itemMap.get(item.parentId);
            if (parent) {
                parent.children = parent.children || [];
                parent.children.push(current);
            } else {
                // 父节点不存在，作为根节点处理（数据异常容错）
                roots.push(current);
            }
        }
    });

    // 对每个层级按 orderIndex 排序
    const sortChildren = (items: TodoItem[]): TodoItem[] => {
        return items
            .sort((a, b) => a.orderIndex - b.orderIndex)
            .map(item => ({
                ...item,
                children: item.children ? sortChildren(item.children) : undefined
            }));
    };

    return sortChildren(roots);
}

/**
 * 将树形结构扁平化为列表
 * @param tree - 树形结构的 TodoItem 数组
 * @returns 扁平化的 TodoItem 数组
 */
export function treeToFlatList(tree: TodoItem[]): TodoItem[] {
    const result: TodoItem[] = [];

    const traverse = (items: TodoItem[]) => {
        items.forEach(item => {
            const { children, ...itemWithoutChildren } = item;
            result.push(itemWithoutChildren as TodoItem);
            if (children && children.length > 0) {
                traverse(children);
            }
        });
    };

    traverse(tree);
    return result;
}

/**
 * 获取指定节点的所有后代 ID
 * @param item - 目标节点
 * @returns 包含该节点及其所有后代的 ID 数组
 */
export function getDescendantIds(item: TodoItem): number[] {
    const ids: number[] = [item.id];

    if (item.children && item.children.length > 0) {
        item.children.forEach(child => {
            ids.push(...getDescendantIds(child));
        });
    }

    return ids;
}

/**
 * 在树中查找指定 ID 的节点
 * @param tree - 树形结构
 * @param id - 目标节点 ID
 * @returns 找到的节点，或 undefined
 */
export function findItemById(tree: TodoItem[], id: number): TodoItem | undefined {
    for (const item of tree) {
        if (item.id === id) return item;
        if (item.children && item.children.length > 0) {
            const found = findItemById(item.children, id);
            if (found) return found;
        }
    }
    return undefined;
}

/**
 * 计算节点的深度（层级）
 * @param items - 扁平列表
 * @param id - 目标节点 ID
 * @returns 深度（根节点为 0）
 */
export function getItemDepth(items: TodoItem[], id: number): number {
    const itemMap = new Map<number, TodoItem>();
    items.forEach(item => itemMap.set(item.id, item));

    let depth = 0;
    let current = itemMap.get(id);

    while (current && current.parentId !== null) {
        depth++;
        current = itemMap.get(current.parentId);
    }

    return depth;
}
