import React, { useState } from 'react';
import { FileText, Plus, ChevronRight, Sun, Moon, Coffee, Zap, Clock } from 'lucide-react';
import { JournalEntry } from '../../../../types';
import { formatDateForDisplay } from '../../../../api';
import JournalEntryModal from './JournalEntryModal';

interface JournalPreviewProps {
  goalId: string;
  journals: JournalEntry[];
  onAddJournal: (journal: Omit<JournalEntry, 'id'>) => Promise<void>;
  maxDisplay?: number;
  themeTag?: string;
}

const MoodIcon = ({ mood }: { mood: string }) => {
  switch (mood) {
    case 'joy':
      return <div className="w-5 h-5 rounded-full bg-amber-100 text-amber-500 flex items-center justify-center"><Sun size={10} /></div>;
    case 'calm':
      return <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-500 flex items-center justify-center"><Coffee size={10} /></div>;
    case 'frustrated':
      return <div className="w-5 h-5 rounded-full bg-rose-100 text-rose-500 flex items-center justify-center"><Zap size={10} /></div>;
    default:
      return <div className="w-5 h-5 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center"><Moon size={10} /></div>;
  }
};

const JournalPreview: React.FC<JournalPreviewProps> = ({
  goalId,
  journals,
  onAddJournal,
  maxDisplay = 3,
  themeTag = 'bg-indigo-50 text-indigo-600',
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const sortedJournals = [...(journals || [])].sort((a, b) => {
    const dateA = new Date(`${a.date} ${a.time}`);
    const dateB = new Date(`${b.date} ${b.time}`);
    return dateB.getTime() - dateA.getTime();
  });

  const displayJournals = sortedJournals.slice(0, maxDisplay);
  const hasMore = sortedJournals.length > maxDisplay;

  const handleSave = async (journal: Omit<JournalEntry, 'id'>) => {
    await onAddJournal(journal);
    setIsModalOpen(false);
  };

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
          最近日志
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsModalOpen(true);
          }}
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-indigo-500 hover:bg-indigo-50 transition-colors"
        >
          <Plus size={12} />
          添加
        </button>
      </div>

      {/* Journal List */}
      {displayJournals.length > 0 ? (
        <div className="space-y-2">
          {displayJournals.map((entry) => (
            <div
              key={entry.id}
              className="flex items-start gap-3 p-3 bg-white border border-slate-100 rounded-xl hover:border-slate-200 transition-colors"
              onClick={(e) => e.stopPropagation()}
            >
              <MoodIcon mood={entry.mood} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-700 line-clamp-2 leading-relaxed">
                  {entry.content}
                </p>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="text-[10px] text-slate-400 font-medium">
                    {formatDateForDisplay(entry.date)}
                  </span>
                  {entry.duration > 0 && (
                    <span className="text-[10px] text-slate-400 font-medium flex items-center gap-0.5">
                      <Clock size={8} />
                      +{entry.duration}h
                    </span>
                  )}
                  {entry.tags && entry.tags.length > 0 && (
                    <div className="flex gap-1">
                      {entry.tags.slice(0, 2).map((tag) => (
                        <span
                          key={tag}
                          className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${themeTag}`}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {hasMore && (
            <button
              onClick={(e) => e.stopPropagation()}
              className="w-full flex items-center justify-center gap-1 py-2 text-xs font-medium text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-lg transition-colors"
            >
              查看全部 ({sortedJournals.length}条)
              <ChevronRight size={12} />
            </button>
          )}
        </div>
      ) : (
        <div className="text-center py-6 bg-slate-50 rounded-xl border border-dashed border-slate-200">
          <FileText size={20} className="mx-auto text-slate-300 mb-2" />
          <p className="text-sm text-slate-400 mb-2">暂无日志记录</p>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsModalOpen(true);
            }}
            className="text-xs font-medium text-indigo-500 hover:text-indigo-600 transition-colors"
          >
            记录第一条日志
          </button>
        </div>
      )}

      {/* Journal Entry Modal */}
      {isModalOpen && (
        <JournalEntryModal
          goalId={goalId}
          onClose={() => setIsModalOpen(false)}
          onSave={handleSave}
        />
      )}
    </div>
  );
};

export default JournalPreview;
