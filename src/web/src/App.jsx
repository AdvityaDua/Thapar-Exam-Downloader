import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, Search, CheckCircle2, AlertCircle, FileArchive } from 'lucide-react';
import { downloadExams } from './lib/downloader';
import axios from 'axios';

// Debounce hook
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

function App() {
  const [searchMode, setSearchMode] = useState('code'); // 'code' or 'name'
  const [query, setQuery] = useState('');
  
  // Autocomplete state
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debouncedQuery = useDebounce(query, 300);
  
  const [isDownloading, setIsDownloading] = useState(false);
  const [progressData, setProgressData] = useState(null);
  const [error, setError] = useState('');
  
  const wrapperRef = useRef(null);

  // Close suggestions if clicked outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Clear suggestions when mode changes
  useEffect(() => {
    setQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
  }, [searchMode]);

  // Fetch suggestions
  useEffect(() => {
    async function fetchSuggestions() {
      if (!debouncedQuery.trim() || debouncedQuery.length < 1) {
        setSuggestions([]);
        return;
      }
      try {
        // User explicitly stated: searchn is for code, searchs is for name
        const endpoint = searchMode === 'code' ? 'searchn.php' : 'searchs.php';
        const res = await axios.get(`/api/${endpoint}?term=${encodeURIComponent(debouncedQuery)}`);
        
        // Sometimes PHP returns JSON with text/html content type
        let data = res.data;
        if (typeof data === 'string') {
          try {
            data = JSON.parse(data);
          } catch (e) {
            console.error('Failed to parse suggestions JSON');
          }
        }
        
        // Ensure it's an array
        if (Array.isArray(data)) {
          setSuggestions(data);
          setShowSuggestions(true);
        } else {
          setSuggestions([]);
        }
      } catch (err) {
        console.error('Failed to fetch suggestions:', err);
      }
    }
    fetchSuggestions();
  }, [debouncedQuery, searchMode]);

  const handleDownload = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) {
      setError('Please enter a search query.');
      return;
    }
    
    setShowSuggestions(false);
    setError('');
    setIsDownloading(true);
    setProgressData({ status: 'Starting...', progress: 0 });
    
    try {
      await downloadExams({
        subjectCode: searchMode === 'code' ? query.trim() : null,
        subjectName: searchMode === 'name' ? query.trim() : null,
        onProgress: setProgressData
      });
    } catch (err) {
      setError(err.message || 'An error occurred during the download.');
      setProgressData(null);
    } finally {
      setIsDownloading(false);
    }
  };

  const selectSuggestion = (suggestion) => {
    // If suggestion is an object (e.g., { label: "...", value: "..." }), handle it. 
    // Otherwise assume it's a string.
    const value = typeof suggestion === 'string' ? suggestion : suggestion.value || suggestion.label;
    setQuery(value || '');
    setShowSuggestions(false);
  };

  return (
    <div className="bg-mesh min-h-screen flex items-center justify-center p-6 font-sans text-slate-100">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="glass-panel w-full max-w-lg rounded-3xl p-8 relative overflow-visible"
      >
        {/* Header */}
        <div className="text-center mb-10">
          <motion.div 
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
            className="w-16 h-16 bg-gradient-to-tr from-indigo-500 to-purple-500 rounded-2xl mx-auto mb-6 flex items-center justify-center shadow-lg shadow-indigo-500/30"
          >
            <FileArchive className="w-8 h-8 text-white" />
          </motion.div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Thapar Exam DL</h1>
          <p className="text-slate-400">Download past year papers instantly.</p>
        </div>

        {/* Form */}
        <form onSubmit={handleDownload} className="space-y-6">
          <div className="flex bg-white/5 rounded-xl p-1 backdrop-blur-sm border border-white/10">
            <button
              type="button"
              onClick={() => setSearchMode('code')}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${searchMode === 'code' ? 'bg-white/10 text-white shadow' : 'text-slate-400 hover:text-white'}`}
            >
              By Code
            </button>
            <button
              type="button"
              onClick={() => setSearchMode('name')}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${searchMode === 'name' ? 'bg-white/10 text-white shadow' : 'text-slate-400 hover:text-white'}`}
            >
              By Name
            </button>
          </div>

          {/* Autocomplete Input Container */}
          <div className="relative" ref={wrapperRef}>
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 z-10" />
            <input
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => {
                if (suggestions.length > 0) setShowSuggestions(true);
              }}
              placeholder={searchMode === 'code' ? 'e.g. UCP101' : 'e.g. UBIQUITOUS AND PERVASIVE COMPUTING'}
              className="glass-input w-full pl-12 relative z-0"
              disabled={isDownloading}
              autoComplete="off"
            />
            
            {/* Dropdown */}
            <AnimatePresence>
              {showSuggestions && suggestions.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="absolute left-0 right-0 top-full mt-2 bg-zinc-900 border border-white/10 rounded-xl shadow-2xl z-50 max-h-60 overflow-y-auto"
                >
                  <ul className="py-2">
                    {suggestions.map((item, idx) => (
                      <li 
                        key={idx}
                        onClick={() => selectSuggestion(item)}
                        className="px-4 py-3 hover:bg-indigo-500/20 cursor-pointer text-sm text-slate-200 transition-colors"
                      >
                        {typeof item === 'string' ? item : item.label || item.value}
                      </li>
                    ))}
                  </ul>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Error Message */}
          <AnimatePresence>
            {error && (
              <motion.div 
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl flex items-center gap-3 text-sm mt-4">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <p>{error}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Progress Section */}
          <AnimatePresence>
            {progressData && !error && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-3 bg-white/5 p-4 rounded-xl border border-white/10 mt-4"
              >
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-300 font-medium truncate pr-4">
                    {progressData.status}
                  </span>
                  <span className="text-indigo-400 font-bold whitespace-nowrap">
                    {progressData.progress}%
                  </span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${progressData.progress}%` }}
                    transition={{ ease: "easeInOut" }}
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isDownloading || (progressData && progressData.done)}
            className="primary-btn w-full flex items-center justify-center gap-2 group mt-2"
          >
            {isDownloading ? (
              <motion.div 
                animate={{ rotate: 360 }} 
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full"
              />
            ) : (progressData && progressData.done) ? (
              <>
                <CheckCircle2 className="w-5 h-5 text-white" />
                Done!
              </>
            ) : (
              <>
                <Download className="w-5 h-5 group-hover:-translate-y-1 transition-transform" />
                Download Zip
              </>
            )}
          </button>
        </form>
      </motion.div>
    </div>
  );
}

export default App;