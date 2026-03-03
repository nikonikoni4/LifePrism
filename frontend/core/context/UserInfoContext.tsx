import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
} from 'react';
import { SettingsAPI } from '../../apps/settings/api';

const DEFAULT_USER_NAME = 'User';

interface UserInfoContextType {
    userName: string;
    setUserName: (name: string) => void;
    refreshUserName: () => Promise<void>;
}

const UserInfoContext = createContext<UserInfoContextType | undefined>(undefined);

export const UserInfoProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [userName, setUserNameState] = useState<string>(DEFAULT_USER_NAME);

    const setUserName = useCallback((name: string) => {
        const trimmed = name.trim();
        setUserNameState(trimmed || DEFAULT_USER_NAME);
    }, []);

    const refreshUserName = useCallback(async () => {
        try {
            const settings = await SettingsAPI.getSettings();
            setUserName(settings.user_name || '');
        } catch {
            // Keep previous name if settings request fails.
        }
    }, [setUserName]);

    useEffect(() => {
        void refreshUserName();
    }, [refreshUserName]);

    const value = useMemo(
        () => ({ userName, setUserName, refreshUserName }),
        [userName, setUserName, refreshUserName]
    );

    return (
        <UserInfoContext.Provider value={value}>
            {children}
        </UserInfoContext.Provider>
    );
};

export const useUserInfo = (): UserInfoContextType => {
    const context = useContext(UserInfoContext);
    if (!context) {
        throw new Error('useUserInfo must be used within a UserInfoProvider');
    }
    return context;
};
