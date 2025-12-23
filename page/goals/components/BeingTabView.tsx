
import React from 'react';
import { User, Plus } from 'lucide-react';
import { MOCK_BEING } from '../api';

const BeingTabView: React.FC = () => {
  return (
    <div className="max-w-3xl mx-auto py-12 space-y-16 text-center animate-fade-in pb-40">
      <div className="relative">
        <div className="absolute -top-20 left-1/2 -translate-x-1/2 text-blue-50 opacity-40 -z-10">
          <User size={260} />
        </div>
        <h3 className="text-6xl font-black text-slate-900 relative z-10 tracking-tighter">Identity Design</h3>
        <p className="text-2xl text-slate-400 mt-8 font-bold italic">"Consistency defines excellence."</p>
      </div>

      <div className="space-y-8">
        {MOCK_BEING.map(being => (
          <div key={being.id} className="group p-14 bg-white rounded-[4rem] shadow-[0_4px_6px_-1px_rgba(0,0,0,0.05)] border border-slate-200/40 hover:shadow-xl transition-all cursor-default">
            <p className="text-3xl font-bold text-slate-800 leading-tight italic tracking-tight">
              "{being.content}"
            </p>
          </div>
        ))}
        <button className="mt-12 flex items-center justify-center gap-5 w-full py-14 border-4 border-dashed border-slate-200 rounded-[4rem] text-slate-400 hover:border-blue-400/50 hover:text-blue-600 hover:bg-white transition-all font-bold uppercase tracking-[0.25em] group text-sm">
          <Plus size={40} className="group-hover:rotate-90 transition-transform" />
          Add Core Belief
        </button>
      </div>
    </div>
  );
};

export default BeingTabView;
