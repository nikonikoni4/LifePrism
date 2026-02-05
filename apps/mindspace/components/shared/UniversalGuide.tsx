
import React, { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence, Variants } from 'framer-motion';
import { X, Search, ChevronRight, BookOpen, ChevronDown, CornerDownRight } from 'lucide-react';
import { GUIDE_DATA, GuideSection } from '../../data/guideContent';

interface UniversalGuideProps {
  isOpen: boolean;
  onClose: () => void;
  guideId?: string;
}

const UniversalGuide: React.FC<UniversalGuideProps> = ({ isOpen, onClose, guideId = 'main' }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSection, setActiveSection] = useState<string>('');
  // Expanded sections state for sidebar accordion behavior
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [mounted, setMounted] = useState(false);

  const sections = GUIDE_DATA[guideId] || [];

  // Ensure we only render portal after mount to avoid SSR hydration mismatches (good practice)
  useEffect(() => {
    setMounted(true);
  }, []);

  // Initialize active section
  useEffect(() => {
    if (isOpen && sections.length > 0 && !activeSection) {
      setActiveSection(sections[0].id);
      setExpandedSections(new Set([sections[0].id]));
    }
  }, [isOpen, sections]);

  // --- Helper: Flatten sections for search ---
  const flattenSections = (items: GuideSection[]): GuideSection[] => {
    let flat: GuideSection[] = [];
    items.forEach(item => {
      flat.push(item);
      if (item.subsections) {
        flat = flat.concat(flattenSections(item.subsections));
      }
    });
    return flat;
  };

  const allSectionsFlat = useMemo(() => flattenSections(sections), [sections]);

  const searchResults = useMemo(() => {
    if (!searchQuery) return null;
    return allSectionsFlat.filter(section => 
      section.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (section.content && section.content.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  }, [searchQuery, allSectionsFlat]);

  const toggleExpand = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleNavClick = (section: GuideSection) => {
    setActiveSection(section.id);
    
    // Auto expand parent if needed (simplified: just ensure current is expanded if it has children)
    if (section.subsections) {
        setExpandedSections(prev => new Set(prev).add(section.id));
    }

    const element = document.getElementById(`guide-section-${section.id}`);
    if (element) {
      // Smooth scroll with offset for sticky headers if any
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const modalVariants: Variants = {
    hidden: { opacity: 0, scale: 0.95 },
    visible: { opacity: 1, scale: 1, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
    exit: { opacity: 0, scale: 0.95, transition: { duration: 0.3 } }
  };

  // --- Recursive Sidebar Renderer ---
  const renderSidebarItem = (item: GuideSection, depth: number = 0) => {
    const hasChildren = item.subsections && item.subsections.length > 0;
    const isExpanded = expandedSections.has(item.id);
    const isActive = activeSection === item.id;

    return (
      <div key={item.id} className="w-full">
        <button 
          onClick={() => handleNavClick(item)}
          className={`w-full text-left px-4 py-3 my-0.5 rounded-xl transition-all duration-200 group flex items-center justify-between
            ${isActive 
              ? 'bg-white shadow-sm border border-slate-100 text-slate-800' 
              : 'hover:bg-slate-50/80 text-slate-500 hover:text-slate-700'}
          `}
          style={{ paddingLeft: `${depth * 16 + 16}px` }}
        >
          <div className="flex items-center gap-2 overflow-hidden">
            {depth > 0 && <CornerDownRight size={12} className="opacity-30 flex-shrink-0" />}
            <span className={`font-medium text-sm truncate ${isActive ? 'font-semibold' : ''}`}>
              {item.title}
            </span>
          </div>

          {hasChildren && (
            <div 
              onClick={(e) => toggleExpand(item.id, e)}
              className="p-1 rounded-md hover:bg-slate-200/50 text-slate-400 transition-colors"
            >
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </div>
          )}
        </button>

        <AnimatePresence>
          {hasChildren && isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              {item.subsections!.map(sub => renderSidebarItem(sub, depth + 1))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  };

  // --- Recursive Content Renderer ---
  const renderContentRecursive = (items: GuideSection[], level: number = 1) => {
    return items.map((section) => (
      <div 
        key={section.id} 
        id={`guide-section-${section.id}`} 
        className={`scroll-mt-10 mb-12 ${level > 1 ? 'pl-6 md:pl-8 border-l-2 border-slate-100/50 ml-2' : ''}`}
      >
        {/* Breadcrumb-ish styling for hierarchy */}
        {level === 1 && (
            <div className="flex items-center gap-4 mb-6">
                <span className="w-12 h-[2px] bg-[#c9a063]"></span>
                <span className="text-xs font-bold tracking-[0.2em] uppercase text-[#c9a063]">
                    {section.id.replace(/-/g, ' ')}
                </span>
            </div>
        )}
        
        {/* Title sizing based on depth */}
        <h2 className={`font-serif text-slate-900 mb-6 ${level === 1 ? 'text-4xl' : level === 2 ? 'text-2xl mt-8' : 'text-xl mt-6'}`}>
          {section.title}
        </h2>
        
        {section.content && (
            <div 
              className="text-lg leading-loose text-slate-600 font-light"
              dangerouslySetInnerHTML={{ __html: section.content }} 
            />
        )}

        {/* Recursive children rendering */}
        {section.subsections && section.subsections.length > 0 && (
            <div className="mt-8">
                {renderContentRecursive(section.subsections, level + 1)}
            </div>
        )}

        {level === 1 && <div className="h-px w-full bg-slate-100 mt-16" />}
      </div>
    ));
  };

  // Don't render until client-side hydration is complete
  if (!mounted) return null;

  // 使用 Portal 将组件直接挂载到 body 上，打破原有的层叠上下文
  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          // 这里的 z-index 设置得非常高，确保覆盖所有应用层的内容 (包括 z-100 的页面)
          className="fixed inset-0 z-[9999] bg-[#fcfcf9]/60 backdrop-blur-md flex items-center justify-center p-4 md:p-10 font-sans"
          onClick={onClose}
        >
          <motion.div 
            variants={modalVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={(e) => e.stopPropagation()}
            className="bg-white/90 w-full max-w-6xl h-[90vh] md:h-[85vh] rounded-[30px] shadow-2xl border border-white flex overflow-hidden backdrop-blur-xl relative"
          >
            {/* Left Sidebar */}
            <aside className="w-1/3 min-w-[280px] bg-[#fcfcf9]/95 border-r border-slate-200/60 flex flex-col hidden md:flex">
               {/* Header Area */}
               <div className="p-8 pb-4 border-b border-slate-100/50">
                 <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 rounded-full bg-[#c9a063]/10 flex items-center justify-center text-[#c9a063]">
                        <BookOpen size={20} />
                    </div>
                    <div>
                        <h2 className="font-serif text-2xl text-slate-900 tracking-tight">Mind Space</h2>
                        <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400 font-medium">User Manual</p>
                    </div>
                 </div>

                 {/* Search Box */}
                 <div className="relative group">
                   <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 group-focus-within:text-[#c9a063] transition-colors" />
                   <input 
                      type="text" 
                      placeholder="Search topics..." 
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full bg-white border border-slate-200 rounded-xl py-2.5 pl-10 pr-4 text-sm outline-none focus:border-[#c9a063]/50 focus:ring-2 focus:ring-[#c9a063]/10 transition-all placeholder:text-slate-400 text-slate-700"
                   />
                 </div>
               </div>
               
               {/* Navigation List */}
               <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                 {searchQuery ? (
                   // Flattened Search Results
                   <div className="space-y-1">
                      <p className="px-4 py-2 text-xs font-bold uppercase text-slate-400 tracking-wider">Search Results</p>
                      {searchResults && searchResults.length > 0 ? (
                        searchResults.map(section => (
                            <button 
                                key={section.id}
                                onClick={() => handleNavClick(section)}
                                className="w-full text-left px-4 py-3 rounded-xl hover:bg-slate-50 text-slate-600 hover:text-slate-900 transition-colors text-sm font-medium flex items-center gap-2"
                            >
                                <Search size={14} className="opacity-50" />
                                {section.title}
                            </button>
                        ))
                      ) : (
                        <div className="p-4 text-center text-slate-400 text-sm">No results found.</div>
                      )}
                   </div>
                 ) : (
                   // Recursive Tree
                   <div className="space-y-1">
                      {sections.map(section => renderSidebarItem(section))}
                   </div>
                 )}
               </div>
            </aside>

            {/* Right Content Area */}
            <main className="flex-1 overflow-y-auto p-8 md:p-16 scroll-smooth bg-white/40 custom-scrollbar relative">
                <button 
                    onClick={onClose} 
                    className="absolute top-6 right-6 p-2 rounded-full hover:bg-slate-100 transition-colors z-10"
                >
                    <X size={24} className="text-slate-400 hover:text-slate-800" />
                </button>

                {/* Mobile Search/Header (visible only on small screens) */}
                <div className="md:hidden mb-8 pb-8 border-b border-slate-100">
                    <h2 className="font-serif text-3xl text-slate-900 mb-4">Guide</h2>
                    <div className="relative group">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                        <input 
                            type="text" 
                            placeholder="Search..." 
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full bg-white border border-slate-200 rounded-xl py-2.5 pl-10 pr-4 text-sm outline-none"
                        />
                    </div>
                    {/* Simplified flat mobile nav if searching */}
                    {searchQuery && (
                         <div className="mt-4 space-y-2">
                             {searchResults?.map(s => (
                                 <div key={s.id} onClick={() => handleNavClick(s)} className="p-2 bg-slate-50 rounded-lg text-sm">{s.title}</div>
                             ))}
                         </div>
                    )}
                </div>

               <div className="max-w-3xl mx-auto pb-20">
                 {searchQuery && searchResults ? (
                    // When searching, show flattened content matches
                    searchResults.map(section => (
                        <div key={section.id} id={`guide-section-${section.id}`} className="mb-12">
                             <h2 className="font-serif text-2xl text-slate-900 mb-4">{section.title}</h2>
                             {section.content ? (
                                <div className="text-lg leading-loose text-slate-600 font-light" dangerouslySetInnerHTML={{ __html: section.content }} />
                             ) : (
                                <p className="text-slate-400 italic">Contains subsections...</p>
                             )}
                             <hr className="my-8 border-slate-100" />
                        </div>
                    ))
                 ) : (
                    // Default Recursive Render
                    renderContentRecursive(sections)
                 )}
               </div>
            </main>

          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default UniversalGuide;
