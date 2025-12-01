
import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import TimelinePage from './components/TimelinePage';
import AIChatPanel from './components/AIChatPanel';

function App() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState('home');

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-slate-800 font-sans relative">
      
      {/* Navigation (Left Sidebar) */}
      <Sidebar 
        currentPage={currentPage} 
        onNavigate={setCurrentPage}
        onChatToggle={() => setIsChatOpen(!isChatOpen)} 
      />

      {/* Main Content Area (Center) */}
      <main 
        className={`lg:ml-64 p-6 lg:p-10 min-h-screen transition-all duration-300 ease-in-out ${
          isChatOpen ? 'lg:mr-[400px]' : ''
        }`}
      >
        {currentPage === 'home' && <Dashboard />}
        {currentPage === 'timeline' && <TimelinePage />}
        
        {/* Fallback for pages not yet implemented */}
        {!['home', 'timeline'].includes(currentPage) && (
             <div className="flex flex-col items-center justify-center h-[60vh] text-center animate-fade-in">
                <h2 className="text-2xl font-bold text-slate-300 mb-2">Coming Soon</h2>
                <p className="text-slate-400">The {currentPage} module is currently under development.</p>
                <button 
                    onClick={() => setCurrentPage('home')}
                    className="mt-6 px-6 py-2 bg-white border border-gray-200 rounded-xl text-slate-600 font-medium hover:bg-gray-50 transition-colors"
                >
                    Return Home
                </button>
             </div>
        )}
      </main>

      {/* AI Chat (Right Sidebar) */}
      <AIChatPanel isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} />
      
    </div>
  );
}

export default App;
