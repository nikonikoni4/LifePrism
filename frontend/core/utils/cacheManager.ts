/**
 * LocalStorage Cache Manager
 * 
 * 通用的 LocalStorage 缓存管理工具
 * 支持过期时间、版本控制、自动清理等功能
 */

export interface CacheOptions {
    /** 缓存过期时间（毫秒），默认 1 小时 */
    ttl?: number;
    /** 数据版本号，用于缓存失效 */
    version?: string;
    /** 是否压缩数据（对于大数据量） */
    compress?: boolean;
}

export interface CacheItem<T> {
    /** 缓存的数据 */
    value: T;
    /** 过期时间戳 */
    expiry: number;
    /** 数据版本号 */
    version?: string;
    /** 创建时间戳 */
    createdAt: number;
    /** 最后访问时间戳 */
    lastAccessedAt: number;
}

export class CacheManager {
    private static readonly PREFIX = 'lifewatch_';
    private static readonly DEFAULT_TTL = 60 * 60 * 1000; // 1 小时
    private static readonly MAX_STORAGE_SIZE = 5 * 1024 * 1024; // 5MB 警告阈值

    /**
     * 设置缓存
     */
    static set<T>(key: string, value: T, options: CacheOptions = {}): boolean {
        try {
            const {
                ttl = this.DEFAULT_TTL,
                version,
                compress = false,
            } = options;

            const now = Date.now();
            const cacheItem: CacheItem<T> = {
                value,
                expiry: now + ttl,
                version,
                createdAt: now,
                lastAccessedAt: now,
            };

            const serialized = JSON.stringify(cacheItem);

            // 检查存储大小
            this.checkStorageSize(serialized.length);

            localStorage.setItem(this.PREFIX + key, serialized);
            return true;
        } catch (error) {
            console.error(`[CacheManager] 设置缓存失败 (${key}):`, error);

            // 如果是存储空间不足，尝试清理过期缓存
            if (error instanceof DOMException && error.name === 'QuotaExceededError') {
                console.warn('[CacheManager] 存储空间不足，尝试清理过期缓存...');
                this.clearExpired();

                // 重试一次
                try {
                    localStorage.setItem(this.PREFIX + key, JSON.stringify({
                        value,
                        expiry: Date.now() + (options.ttl || this.DEFAULT_TTL),
                        version: options.version,
                        createdAt: Date.now(),
                        lastAccessedAt: Date.now(),
                    }));
                    return true;
                } catch (retryError) {
                    console.error('[CacheManager] 重试设置缓存仍然失败:', retryError);
                }
            }

            return false;
        }
    }

    /**
     * 获取缓存
     */
    static get<T>(key: string, expectedVersion?: string): T | null {
        try {
            const itemStr = localStorage.getItem(this.PREFIX + key);
            if (!itemStr) {
                return null;
            }

            const item: CacheItem<T> = JSON.parse(itemStr);

            // 检查是否过期
            if (Date.now() > item.expiry) {
                console.log(`[CacheManager] 缓存已过期 (${key})`);
                this.remove(key);
                return null;
            }

            // 检查版本号
            if (expectedVersion && item.version !== expectedVersion) {
                console.log(`[CacheManager] 缓存版本不匹配 (${key}): 期望 ${expectedVersion}, 实际 ${item.version}`);
                this.remove(key);
                return null;
            }

            // 更新最后访问时间
            item.lastAccessedAt = Date.now();
            localStorage.setItem(this.PREFIX + key, JSON.stringify(item));

            return item.value;
        } catch (error) {
            console.error(`[CacheManager] 获取缓存失败 (${key}):`, error);
            return null;
        }
    }

    /**
     * 删除指定缓存
     */
    static remove(key: string): void {
        try {
            localStorage.removeItem(this.PREFIX + key);
        } catch (error) {
            console.error(`[CacheManager] 删除缓存失败 (${key}):`, error);
        }
    }

    /**
     * 清除所有缓存
     */
    static clear(): void {
        try {
            const keys = Object.keys(localStorage);
            keys.forEach(key => {
                if (key.startsWith(this.PREFIX)) {
                    localStorage.removeItem(key);
                }
            });
            console.log('[CacheManager] 已清除所有缓存');
        } catch (error) {
            console.error('[CacheManager] 清除缓存失败:', error);
        }
    }

    /**
     * 清除过期的缓存
     */
    static clearExpired(): number {
        try {
            const keys = Object.keys(localStorage);
            const now = Date.now();
            let clearedCount = 0;

            keys.forEach(key => {
                if (key.startsWith(this.PREFIX)) {
                    try {
                        const itemStr = localStorage.getItem(key);
                        if (itemStr) {
                            const item: CacheItem<any> = JSON.parse(itemStr);
                            if (now > item.expiry) {
                                localStorage.removeItem(key);
                                clearedCount++;
                            }
                        }
                    } catch (error) {
                        // 如果解析失败，删除该项
                        localStorage.removeItem(key);
                        clearedCount++;
                    }
                }
            });

            if (clearedCount > 0) {
                console.log(`[CacheManager] 已清除 ${clearedCount} 个过期缓存`);
            }

            return clearedCount;
        } catch (error) {
            console.error('[CacheManager] 清除过期缓存失败:', error);
            return 0;
        }
    }

    /**
     * 检查缓存是否存在且未过期
     */
    static has(key: string): boolean {
        try {
            const itemStr = localStorage.getItem(this.PREFIX + key);
            if (!itemStr) {
                return false;
            }

            const item: CacheItem<any> = JSON.parse(itemStr);
            return Date.now() <= item.expiry;
        } catch (error) {
            return false;
        }
    }

    /**
     * 获取缓存信息（不返回数据）
     */
    static getInfo(key: string): Omit<CacheItem<any>, 'value'> | null {
        try {
            const itemStr = localStorage.getItem(this.PREFIX + key);
            if (!itemStr) {
                return null;
            }

            const item: CacheItem<any> = JSON.parse(itemStr);
            const { value, ...info } = item;
            return info;
        } catch (error) {
            return null;
        }
    }

    /**
     * 获取所有缓存的键
     */
    static keys(): string[] {
        try {
            const keys = Object.keys(localStorage);
            return keys
                .filter(key => key.startsWith(this.PREFIX))
                .map(key => key.substring(this.PREFIX.length));
        } catch (error) {
            console.error('[CacheManager] 获取缓存键列表失败:', error);
            return [];
        }
    }

    /**
     * 获取缓存统计信息
     */
    static getStats(): {
        totalItems: number;
        totalSize: number;
        expiredItems: number;
        oldestItem: string | null;
        newestItem: string | null;
    } {
        const keys = Object.keys(localStorage);
        const now = Date.now();
        let totalSize = 0;
        let expiredItems = 0;
        let oldestTime = Infinity;
        let newestTime = 0;
        let oldestKey: string | null = null;
        let newestKey: string | null = null;

        keys.forEach(key => {
            if (key.startsWith(this.PREFIX)) {
                try {
                    const itemStr = localStorage.getItem(key);
                    if (itemStr) {
                        totalSize += itemStr.length;
                        const item: CacheItem<any> = JSON.parse(itemStr);

                        if (now > item.expiry) {
                            expiredItems++;
                        }

                        if (item.createdAt < oldestTime) {
                            oldestTime = item.createdAt;
                            oldestKey = key.substring(this.PREFIX.length);
                        }

                        if (item.createdAt > newestTime) {
                            newestTime = item.createdAt;
                            newestKey = key.substring(this.PREFIX.length);
                        }
                    }
                } catch (error) {
                    // 忽略解析错误
                }
            }
        });

        return {
            totalItems: keys.filter(k => k.startsWith(this.PREFIX)).length,
            totalSize,
            expiredItems,
            oldestItem: oldestKey,
            newestItem: newestKey,
        };
    }

    /**
     * 检查存储大小并在必要时发出警告
     */
    private static checkStorageSize(newItemSize: number): void {
        const stats = this.getStats();
        const estimatedSize = stats.totalSize + newItemSize;

        if (estimatedSize > this.MAX_STORAGE_SIZE) {
            console.warn(
                `[CacheManager] 存储空间使用接近上限: ${(estimatedSize / 1024 / 1024).toFixed(2)}MB / 5MB`
            );
        }
    }

    /**
     * 批量设置缓存
     */
    static setMultiple<T>(items: Array<{ key: string; value: T; options?: CacheOptions }>): void {
        items.forEach(({ key, value, options }) => {
            this.set(key, value, options);
        });
    }

    /**
     * 批量获取缓存
     */
    static getMultiple<T>(keys: string[]): Map<string, T | null> {
        const result = new Map<string, T | null>();
        keys.forEach(key => {
            result.set(key, this.get<T>(key));
        });
        return result;
    }

    /**
     * 更新缓存的过期时间
     */
    static touch(key: string, ttl?: number): boolean {
        try {
            const itemStr = localStorage.getItem(this.PREFIX + key);
            if (!itemStr) {
                return false;
            }

            const item: CacheItem<any> = JSON.parse(itemStr);
            item.expiry = Date.now() + (ttl || this.DEFAULT_TTL);
            item.lastAccessedAt = Date.now();

            localStorage.setItem(this.PREFIX + key, JSON.stringify(item));
            return true;
        } catch (error) {
            console.error(`[CacheManager] 更新缓存过期时间失败 (${key}):`, error);
            return false;
        }
    }
}

/**
 * 自动清理过期缓存（在应用启动时调用）
 */
export function initCacheCleanup(): void {
    // 立即清理一次
    CacheManager.clearExpired();

    // 每小时清理一次过期缓存
    setInterval(() => {
        CacheManager.clearExpired();
    }, 60 * 60 * 1000);

    // 打印缓存统计信息
    const stats = CacheManager.getStats();
    console.log('[CacheManager] 缓存统计:', {
        总缓存项: stats.totalItems,
        总大小: `${(stats.totalSize / 1024).toFixed(2)}KB`,
        过期项: stats.expiredItems,
    });
}
