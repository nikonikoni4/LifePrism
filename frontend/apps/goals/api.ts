/**
 * GoalsV2 API Service Layer
 * 
 * This file is now a compatibility layer.
 * Main implementation has been moved to ./apis folder.
 */

export * from './types/backend';
export * from './apis';

import { goalsV2Api } from './apis/goal';
export default goalsV2Api;
