
import React from 'react';
import {
  Home,
  Clock,
  Target,
  FileBarChart,
  Settings,
  Sparkles,
  User,
  Tag
} from 'lucide-react';

interface SidebarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
  onChatToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentPage, onNavigate, onChatToggle }) => {
  const navItems = [
    { id: 'home', icon: Home, label: 'Home' },
    { id: 'timeline', icon: Clock, label: 'Timeline' },
    { id: 'categorization', icon: Tag, label: 'Categorization' },
    { id: 'goals', icon: Target, label: 'Goals' },
    { id: 'reports', icon: FileBarChart, label: 'Reports' },
    { id: 'settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div className="fixed left-0 top-0 h-full w-20 lg:w-64 bg-white border-r border-gray-100 flex flex-col justify-between py-6 z-40 transition-all duration-300">
      {/* Logo Area */}
      <div className="px-4 lg:px-8 mb-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-morandi-blue rounded-2xl flex items-center justify-center text-white font-bold text-xl shadow-morandi-blue/20 shadow-lg">
            L
          </div>
          <span className="hidden lg:block font-bold text-xl tracking-tight text-slate-800">LifeWatchAI</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 lg:px-6 space-y-1.5">
        {navItems.map((item) => {
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-2xl transition-all duration-200 group ${isActive
                ? 'bg-blue-50 text-blue-600 shadow-sm ring-1 ring-blue-100'
                : 'text-slate-500 hover:bg-gray-50 hover:text-slate-800'
                }`}
            >
              <item.icon
                size={20}
                strokeWidth={isActive ? 2.5 : 2}
                className={`transition-colors ${isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'}`}
              />
              <span className={`hidden lg:block font-medium ${isActive ? 'font-semibold' : ''}`}>{item.label}</span>
            </button>
          );
        })}

        {/* AI Chat Entry */}
        <div className="pt-6 mt-6 border-t border-dashed border-gray-100">
          <p className="hidden lg:block px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Assistant</p>
          <button
            onClick={onChatToggle}
            className="w-full flex items-center gap-3 px-4 py-3.5 rounded-2xl bg-gradient-to-br from-indigo-50 to-purple-50 text-indigo-700 hover:shadow-md hover:scale-[1.02] transition-all duration-200 border border-indigo-100/50 group"
          >
            <div className="bg-white p-1.5 rounded-lg shadow-sm group-hover:rotate-12 transition-transform duration-300">
              <Sparkles size={16} className="text-indigo-500 fill-indigo-100" />
            </div>
            <span className="hidden lg:block font-semibold">Ask AI Assistant</span>
          </button>
        </div>
      </nav>

      {/* User Profile */}
      <div className="px-4 lg:px-6 mt-auto">
        <div className="flex items-center gap-3 p-3 rounded-2xl border border-transparent hover:border-gray-100 hover:bg-gray-50 cursor-pointer transition-all duration-200">
          <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden border-2 border-white shadow-md">
            <img src="https://picsum.photos/seed/alex/100/100" alt="User" className="w-full h-full object-cover" />
          </div>
          <div className="hidden lg:block">
            <p className="text-sm font-bold text-slate-800">Alex Chen</p>
            <p className="text-xs text-slate-400 font-medium">Pro Account</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
