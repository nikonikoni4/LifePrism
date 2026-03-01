import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { mindspaceApi, ValueOption, CommitmentOption } from '../apis/mindspace';

interface MindspaceStoreContextType {
    values: ValueOption[];
    commitments: CommitmentOption[];
}

const MindspaceStoreContext = createContext<MindspaceStoreContextType | undefined>(undefined);

export const MindspaceProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [values, setValues] = useState<ValueOption[]>([]);
    const [commitments, setCommitments] = useState<CommitmentOption[]>([]);

    useEffect(() => {
        mindspaceApi.getValues().then(setValues).catch(console.error);
        mindspaceApi.getCommitments().then(setCommitments).catch(console.error);
    }, []);

    return React.createElement(MindspaceStoreContext.Provider, { value: { values, commitments } }, children);
};

export const useMindspaceStore = () => {
    const context = useContext(MindspaceStoreContext);
    if (!context) {
        throw new Error("useMindspaceStore must be used within a MindspaceProvider");
    }
    return context;
};
