/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, ReactNode } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Camera, 
  Activity, 
  Users, 
  Layers, 
  Settings, 
  Bell, 
  Cpu, 
  Search,
  ChevronRight,
  Maximize2,
  MoreVertical,
  Shield,
  Clock
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar
} from 'recharts';
import { cn } from '@/src/lib/utils.ts';
import type { CameraConfig, ReidLog, SystemStats } from '@/src/types/index.ts';

// Mock Data
const MOCK_CAMERAS: CameraConfig[] = [
  { id: 'cam-1', name: 'Main Entrance', status: 'online', fps: 30, resolution: '1920x1080', bitrate: '4.2 Mbps' },
  { id: 'cam-2', name: 'Lobby South', status: 'online', fps: 28, resolution: '1920x1080', bitrate: '3.8 Mbps' },
  { id: 'cam-3', name: 'Restricted Area', status: 'online', fps: 30, resolution: '1920x1080', bitrate: '4.5 Mbps' },
  { id: 'cam-4', name: 'Parking Lot', status: 'online', fps: 25, resolution: '1920x1080', bitrate: '3.1 Mbps' },
];

const MOCK_STATS_DATA = [
  { time: '09:00', count: 12 },
  { time: '10:00', count: 18 },
  { time: '11:00', count: 25 },
  { time: '12:00', count: 42 },
  { time: '13:00', count: 38 },
  { time: '14:00', count: 31 },
  { time: '15:00', count: 45 },
  { time: '16:00', count: 52 },
];

const MOCK_REID_LOGS: ReidLog[] = [
  { id: '1', timestamp: '14:22:05', personId: 'PID-1024', fromCamera: 'Main Entrance', toCamera: 'Lobby South', confidence: 0.98, thumbnail: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop' },
  { id: '2', timestamp: '14:22:12', personId: 'PID-0982', fromCamera: 'Lobby South', toCamera: 'Main Entrance', confidence: 0.94, thumbnail: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop' },
  { id: '3', timestamp: '14:22:15', personId: 'PID-1105', fromCamera: 'Restricted Area', toCamera: 'Lobby South', confidence: 0.96, thumbnail: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop' },
  { id: '4', timestamp: '14:22:20', personId: 'PID-0871', fromCamera: 'Main Entrance', toCamera: 'Lobby South', confidence: 0.92, thumbnail: 'https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=100&h=100&fit=crop' },
];

export default function App() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'history'>('dashboard');
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null);
  const [selectedCamera, setSelectedCamera] = useState<CameraConfig | null>(MOCK_CAMERAS[0]);
  const [systemStats, setSystemStats] = useState<SystemStats>({
    cpuUsage: 45,
    gpuUsage: 78,
    ramUsage: 62,
    gpuTemp: 54
  });
  const [currentTime, setCurrentTime] = useState(new Date());
  const [logs, setLogs] = useState<ReidLog[]>(MOCK_REID_LOGS);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    const statsTimer = setInterval(() => {
      setSystemStats(prev => ({
        ...prev,
        cpuUsage: Math.floor(40 + Math.random() * 15),
        gpuUsage: Math.floor(70 + Math.random() * 20),
        ramUsage: Math.floor(60 + Math.random() * 5),
        gpuTemp: Math.floor(52 + Math.random() * 6)
      }));
    }, 3000);

    const logTimer = setInterval(() => {
      const newLog: ReidLog = {
        id: Math.random().toString(),
        timestamp: new Date().toLocaleTimeString([], { hour12: false }),
        personId: `PID-${Math.floor(800 + Math.random() * 400)}`,
        fromCamera: MOCK_CAMERAS[Math.floor(Math.random() * 4)].name,
        toCamera: MOCK_CAMERAS[Math.floor(Math.random() * 4)].name,
        confidence: 0.85 + Math.random() * 0.14,
        thumbnail: `https://images.unsplash.com/photo-${Math.random() > 0.5 ? '1507003211169-0a1dd7228f2d' : '1494790108377-be9c29b29330'}?w=100&h=100&fit=crop`
      };
      setLogs(prev => [newLog, ...prev.slice(0, 9)]);
    }, 5000);

    return () => {
      clearInterval(timer);
      clearInterval(statsTimer);
      clearInterval(logTimer);
    };
  }, []);

  const handleShowHistory = (personId: string, imageSrc: string | null = null) => {
    setSelectedPersonId(personId);
    setUploadedImage(imageSrc);
    setCurrentView('history');
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          // Simulate finding a matched ID from the uploaded image
          const fakeMatchedId = `PID-${Math.floor(1000 + Math.random() * 9000)}`;
          handleShowHistory(fakeMatchedId, event.target.result as string);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  return (
    <div className="flex h-screen w-screen bg-[#0a0a0c] text-white font-sans overflow-hidden">
      {/* Vertical Sidebar Nav */}
      <nav className="w-16 border-r border-[#1f1f23] flex flex-col items-center py-6 space-y-8 bg-[#0d0d0f]">
        <div 
          className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center mb-4 cursor-pointer hover:bg-blue-500 transition-colors"
          onClick={() => setCurrentView('dashboard')}
        >
          <Shield className="w-6 h-6 text-white" />
        </div>
        <NavItem icon={<Activity size={22} />} active={currentView === 'dashboard'} onClick={() => setCurrentView('dashboard')} />
        <NavItem icon={<Users size={22} />} active={currentView === 'history'} onClick={() => currentView === 'history' ? null : null} />
        <NavItem icon={<Layers size={22} />} />
        <NavItem icon={<Search size={22} />} />
        <div className="mt-auto space-y-6">
          <NavItem icon={<Settings size={22} />} />
          <NavItem icon={<Bell size={22} />} />
        </div>
      </nav>

      {/* Main Container */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Header */}
        <header className="h-16 border-b border-[#1f1f23] flex items-center justify-between px-8 bg-[#0d0d0f]">
          <div className="flex items-center space-x-4">
            <h1 
              className="text-xl font-bold tracking-tight bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent cursor-pointer"
              onClick={() => setCurrentView('dashboard')}
            >
              EYE-D CONTROL CENTER
            </h1>
            <div className="px-2 py-0.5 rounded bg-blue-600/10 border border-blue-600/20 text-[10px] text-blue-400 font-bold uppercase tracking-widest">
              Jetson Orin Nano
            </div>
            {currentView === 'history' && (
              <div className="flex items-center space-x-2 text-gray-500">
                <ChevronRight size={14} />
                <span className="text-xs font-bold uppercase tracking-widest text-blue-400">History Explorer</span>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-8">
            <SystemMetric label="GPU" value={`${systemStats.gpuUsage}%`} color="text-emerald-400" />
            <SystemMetric label="CPU" value={`${systemStats.cpuUsage}%`} color="text-blue-400" />
            <SystemMetric label="TEMP" value={`${systemStats.gpuTemp}°C`} color="text-orange-400" />
            <div className="flex items-center space-x-2 text-gray-400 border-l border-[#1f1f23] pl-8">
              <Clock size={16} />
              <span className="text-sm font-mono">{currentTime.toLocaleTimeString([], { hour12: false })}</span>
            </div>
          </div>
        </header>

        <AnimatePresence mode="wait">
          {currentView === 'dashboard' ? (
            <motion.div 
              key="dashboard"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex-1 flex flex-row overflow-hidden"
            >
              {/* Central Area: Video Grid + Logs */}
              <div className="flex-1 flex flex-col p-4 space-y-4 overflow-hidden">
                {/* 4-Split Grid */}
                <div className="grid grid-cols-2 grid-rows-2 gap-4 flex-[2]">
                  {MOCK_CAMERAS.map((cam, idx) => (
                    <div 
                      key={cam.id} 
                      className={cn(
                        "relative rounded-xl overflow-hidden border border-[#1f1f23] bg-black group transition-all duration-300",
                        selectedCamera?.id === cam.id ? "ring-2 ring-blue-500/50 scale-[0.99] border-blue-500/30" : "hover:border-gray-700"
                      )}
                      onClick={() => setSelectedCamera(cam)}
                    >
                      <VideoFeed camera={cam} isActive={selectedCamera?.id === cam.id} />
                      <div className="absolute top-4 left-4 flex items-center space-x-2 z-20">
                        <div className={cn(
                          "w-2 h-2 rounded-full",
                          idx === 2 ? "bg-emerald-500 animate-pulse" : "bg-red-500 animate-pulse"
                        )} />
                        <span className="text-xs font-medium text-white shadow-sm drop-shadow-md">{cam.name}</span>
                      </div>
                      <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity z-20">
                        <button className="p-2 rounded-lg bg-black/50 backdrop-blur-sm text-white hover:bg-black/70">
                          <Maximize2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Bottom: Re-ID Log Feed */}
                <div className="flex-1 min-h-[200px] border border-[#1f1f23] rounded-xl bg-[#0d0d0f] flex flex-col overflow-hidden">
                  <div className="px-4 py-3 border-b border-[#1f1f23] flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Activity size={16} className="text-blue-400" />
                      <h3 className="text-sm font-bold tracking-tight">REAL-TIME RE-ID LOG</h3>
                    </div>
                    <span className="text-[10px] text-gray-500 font-mono italic">STREAMING DATA...</span>
                  </div>
                  <div className="flex-1 p-2 overflow-y-auto space-y-2 scrollbar-thin scrollbar-thumb-[#1f1f23]">
                    <AnimatePresence initial={false}>
                      {logs.map((log) => (
                        <ReidLogRow key={log.id} log={log} onClick={() => handleShowHistory(log.personId)} />
                      ))}
                    </AnimatePresence>
                  </div>
                </div>
              </div>

              {/* Right Sidebar: Stats + Camera Controls */}
              <aside className="w-80 border-l border-[#1f1f23] bg-[#0d0d0f] flex flex-col overflow-y-auto">
                <div className="p-6 space-y-6">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Crowd Density</h3>
                      <Users size={18} className="text-blue-500" />
                    </div>
                    <div className="h-48 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={MOCK_STATS_DATA}>
                          <defs>
                            <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <XAxis dataKey="time" hide />
                          <YAxis hide />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#1a1a1e', borderColor: '#1f1f23', fontSize: '12px' }}
                            itemStyle={{ color: '#60a5fa' }}
                          />
                          <Area type="monotone" dataKey="count" stroke="#3b82f6" fillOpacity={1} fill="url(#colorCount)" strokeWidth={2} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <StatCard label="Total Visitors" value="2,482" delta="+12%" />
                      <StatCard label="Occupancy" value="84%" delta="-3%" inverse={true} />
                    </div>
                  </div>

                  <hr className="border-[#1f1f23]" />

                  <div className="space-y-6">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Feed Controls</h3>
                      <Settings size={18} className="text-gray-500" />
                    </div>
                    
                    <div className="space-y-4">
                      <div className="p-4 rounded-xl bg-[#141416] border border-[#1f1f23]">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-bold text-blue-400">{selectedCamera?.name || 'No Camera Selected'}</span>
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 text-[8px] font-bold tracking-tighter uppercase">Live</span>
                        </div>
                        <div className="space-y-2">
                           <ControlToggle label="Object Detection" active />
                           <ControlToggle label="Person Tracking" active />
                           <ControlToggle label="Mask Check" />
                           <ControlToggle label="Anonymization" />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[10px] text-gray-500 font-medium font-mono uppercase">
                        <div className="p-2 rounded bg-[#141416]">FPS: <span className="text-gray-300">{selectedCamera?.fps || 0}</span></div>
                        <div className="p-2 rounded bg-[#141416]">RES: <span className="text-gray-300">1080P</span></div>
                        <div className="p-2 rounded bg-[#141416]">BW: <span className="text-gray-300">{selectedCamera?.bitrate || '0 Mbps'}</span></div>
                        <div className="p-2 rounded bg-[#141416]">LAT: <span className="text-gray-300">12ms</span></div>
                      </div>

                      <div className="relative w-full">
                        <input 
                          type="file" 
                          accept="image/*" 
                          id="reid-upload" 
                          className="hidden" 
                          onChange={handleImageUpload}
                        />
                        <label 
                          htmlFor="reid-upload" 
                          className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-sm font-bold transition-all active:scale-[0.98] cursor-pointer flex items-center justify-center space-x-2"
                        >
                          <Search size={16} />
                          <span>SEARCH BY IMAGE</span>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              </aside>
            </motion.div>
          ) : (
            <PersonHistory key="history" personId={selectedPersonId || 'PID-UNKNOWN'} targetImage={uploadedImage} onBack={() => setCurrentView('dashboard')} />
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

const PersonHistory: React.FC<{ personId: string; targetImage: string | null; onBack: () => void }> = ({ personId, targetImage, onBack }) => {
  const historyEvents = [
    { id: 'ev-1', time: '14:22:05', camera: 'Lobby South', confidence: 0.98, img: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&h=600&fit=crop', videoColor: 'emerald' },
    { id: 'ev-2', time: '14:15:30', camera: 'Main Entrance', confidence: 0.95, img: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&h=600&fit=crop', videoColor: 'blue' },
    { id: 'ev-3', time: '14:05:12', camera: 'Parking Lot', confidence: 0.88, img: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&h=600&fit=crop', videoColor: 'yellow' },
  ];

  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="flex-1 flex flex-col overflow-hidden bg-[#0a0a0c]"
    >
      <div className="p-8 flex flex-row gap-8 h-full overflow-hidden">
        {/* Left: Summary Profile */}
        <div className="w-80 flex flex-col space-y-6">
          <div className="relative rounded-2xl overflow-hidden border border-blue-500/30 bg-[#0d0d0f]">
            <img src={targetImage || historyEvents[0].img} alt="Profile" className="w-full h-80 object-cover" />
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black to-transparent p-6">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[10px] font-black text-blue-400 uppercase tracking-[0.2em] mb-1">Target Profile</div>
                  <div className="text-3xl font-black">{personId}</div>
                </div>
                <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-600/20">
                  <Shield size={24} />
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
             <div className="p-4 rounded-xl bg-[#0d0d0f] border border-[#1f1f23]">
                <div className="text-[10px] font-bold text-gray-500 uppercase mb-1">Status</div>
                <div className="text-emerald-400 font-bold uppercase tracking-tighter">Normal</div>
             </div>
             <div className="p-4 rounded-xl bg-[#0d0d0f] border border-[#1f1f23]">
                <div className="text-[10px] font-bold text-gray-500 uppercase mb-1">Matches</div>
                <div className="text-white font-bold">12 Count</div>
             </div>
          </div>

          <div className="space-y-3">
            <button className="w-full py-4 rounded-xl bg-white text-black font-bold hover:bg-gray-200 transition-colors shadow-lg active:scale-[0.98]">
              SAVE TO EVIDENCE
            </button>
            <button 
              onClick={onBack}
              className="w-full py-4 rounded-xl bg-transparent border border-[#1f1f23] text-gray-400 font-bold hover:bg-[#141416] transition-colors active:scale-[0.98]"
            >
              RETURN TO MONITORING
            </button>
          </div>
        </div>
        {/* Right: Timeline */}
        <div className="flex-1 flex flex-col overflow-hidden bg-[#0d0d0f] rounded-3xl border border-[#1f1f23]">
          <div className="px-8 py-6 border-b border-[#1f1f23] flex items-center justify-between">
            <h2 className="text-lg font-bold tracking-tight">Movement Trajectory</h2>
            <div className="flex space-x-2">
              <span className="px-3 py-1 rounded-full bg-[#141416] border border-[#1f1f23] text-xs font-medium text-gray-400">History Log</span>
              <span className="px-3 py-1 rounded-full bg-blue-600/10 border border-blue-600/20 text-xs font-medium text-blue-400">May 15, 2026</span>
            </div>
          </div>
          
          <div className="flex-1 p-8 overflow-y-auto scrollbar-thin scrollbar-thumb-[#1f1f23]">
            <div className="relative pl-12 space-y-12">
              {/* Timeline Line */}
              <div className="absolute left-[23px] top-4 bottom-4 w-0.5 bg-[#1f1f23]" />
              
              {historyEvents.map((event, idx) => (
                <div key={idx} className="relative">
                  {/* Node */}
                  <div className={cn(
                    "absolute -left-[35px] top-1 w-6 h-6 rounded-full border-4 border-[#0d0d0f] transform transition-all duration-500 z-10",
                    idx === 0 ? "bg-blue-600 scale-125" : "bg-gray-700"
                  )} />
                  
                  <div className="flex flex-row gap-8 items-start group">
                    <div className="w-32 flex-shrink-0 pt-1">
                      <div className="text-xl font-mono font-bold text-white mb-1">{event.time}</div>
                      <div className="text-xs font-bold text-gray-500 uppercase tracking-widest">{event.camera}</div>
                    </div>
                    
                    <div className="flex-1 p-6 rounded-2xl bg-[#141416] border border-[#1f1f23] group-hover:border-blue-500/30 transition-all">
                      <div className="flex flex-row gap-8">
                        {/* Inline Video Feed */}
                        <div className="w-64 h-36 rounded-xl overflow-hidden border border-white/5 relative bg-black shrink-0">
                           <div className="absolute inset-0 grayscale opacity-40" style={{ backgroundImage: `url(${event.img})`, backgroundSize: 'cover' }} />
                           <div className="scanline" />
                           <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-black to-transparent" />
                           
                           {/* Simulation Overlay */}
                           <motion.div 
                             animate={{ x: [10, 40, 20, 10], y: [10, 30, 10, 10] }}
                             transition={{ duration: 5 + idx, repeat: Infinity, ease: 'linear' }}
                             className={cn(
                               "absolute border-2 w-16 h-28 z-10",
                               event.videoColor === 'emerald' ? 'border-emerald-500/50' : 
                               event.videoColor === 'blue' ? 'border-blue-500/50' : 'border-yellow-400/50'
                             )}
                           >
                             <div className={cn(
                               "text-[6px] font-black px-1 py-0.5 text-black",
                               event.videoColor === 'emerald' ? 'bg-emerald-500' : 
                               event.videoColor === 'blue' ? 'bg-blue-500' : 'bg-yellow-400'
                             )}>
                               {personId}
                             </div>
                           </motion.div>

                           <div className="absolute top-2 left-2 z-20 flex items-center space-x-1">
                              <div className="w-1.5 h-1.5 rounded-full bg-red-600 animate-pulse" />
                              <span className="text-[7px] font-black text-white uppercase tracking-tighter">Event Feed</span>
                           </div>
                        </div>

                        <div className="flex-1 flex flex-col justify-center">
                          <div className="flex items-center justify-between mb-4">
                            <span className="px-2 py-0.5 rounded bg-blue-600/10 text-blue-400 text-[10px] font-black uppercase">Detection Captured</span>
                            <span className="text-xs font-bold text-emerald-400">{(event.confidence * 100).toFixed(1)}% Re-ID Match</span>
                          </div>
                          <div className="text-sm text-gray-400 font-medium leading-relaxed">
                            Verified detection in {event.camera} zone. Edge processing confirmed identity with high-confidence Re-ID biometric data.
                          </div>
                          <div className="mt-4 flex items-center space-x-4">
                             <div className="flex flex-col">
                                <span className="text-[9px] text-gray-600 font-bold uppercase tracking-widest">FPS</span>
                                <span className="text-xs font-mono font-bold">29.9</span>
                             </div>
                             <div className="flex flex-col">
                                <span className="text-[9px] text-gray-600 font-bold uppercase tracking-widest">Metadata</span>
                                <span className="text-xs font-mono font-bold">JSON Encoded</span>
                             </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

const NavItem: React.FC<{ icon: ReactNode; active?: boolean; onClick?: () => void }> = ({ icon, active = false, onClick }) => {
  return (
    <div 
      className={cn(
        "w-10 h-10 rounded-xl flex items-center justify-center cursor-pointer transition-all hover:scale-110",
        active ? "bg-white/10 text-white" : "text-gray-500 hover:text-gray-300"
      )}
      onClick={onClick}
    >
      {icon}
    </div>
  );
}

const SystemMetric: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => {
  return (
    <div className="flex flex-col items-end">
      <span className="text-[9px] font-bold text-gray-500 uppercase tracking-widest">{label}</span>
      <span className={cn("text-xs font-mono font-bold", color)}>{value}</span>
    </div>
  );
}

const VideoFeed: React.FC<{ camera: CameraConfig; isActive?: boolean }> = ({ camera, isActive = false }) => {
  return (
    <div className="w-full h-full bg-[#0a0a0c] flex items-center justify-center overflow-hidden relative">
      <div className="absolute inset-0 bg-[#0a0a0c]">
        <div className="w-full h-full opacity-30 bg-[radial-gradient(circle_at_center,_transparent_0%,_black_100%)]" 
             style={{ backgroundImage: `url('https://www.transparenttextures.com/patterns/carbon-fibre.png')` }} />
      </div>
      
      <div className="scanline" />

      {/* Simulation Overlay */}
      <div className="relative w-full h-full p-4 overflow-hidden z-10">
        {/* Grid pattern overlay */}
        <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        
        {/* Bounding boxes simulation */}
        <motion.div 
          animate={{ x: [0, 50, -20, 0], y: [0, 20, 40, 0] }}
          transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
          className="absolute border border-emerald-500/50 w-24 h-48 flex flex-col justify-start"
        >
          <div className="bg-emerald-500/80 text-black text-[8px] font-black px-1 leading-tight self-start uppercase">
            PERSON [98%]
          </div>
          <div className="mt-auto h-1 w-full bg-emerald-500/20" />
        </motion.div>

        <motion.div 
          animate={{ x: [200, 150, 180, 200], y: [100, 80, 120, 100] }}
          transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
          className="absolute border border-blue-500/50 w-20 h-40 flex flex-col justify-start"
        >
          <div className="bg-blue-500/80 text-white text-[8px] font-black px-1 leading-tight self-start uppercase">
            {camera.id === 'cam-3' ? 'RESTRICTED' : 'VISITOR'}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

const ReidLogRow: React.FC<{ log: ReidLog; onClick?: () => void }> = ({ log, onClick }) => {
  return (
    <motion.div 
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ scale: 1.01 }}
      className="flex items-center space-x-4 p-3 rounded-lg bg-[#141416] border border-[#1f1f23] hover:border-blue-500/50 transition-colors group cursor-pointer"
      onClick={onClick}
    >
      <div className="flex-shrink-0 relative">
        <img src={log.thumbnail} alt="Person" className="w-12 h-12 rounded-lg object-cover grayscale group-hover:grayscale-0 transition-all border border-[#1f1f23]" />
        <div className="absolute -top-1 -left-1 bg-blue-600 text-[8px] font-bold px-1 rounded shadow-sm">MATCH</div>
      </div>
      <div className="flex-1 grid grid-cols-4 gap-4 items-center">
        <div className="flex flex-col">
          <span className="text-[9px] text-gray-500 uppercase font-black tracking-widest leading-none mb-1">Entity ID</span>
          <span className="text-sm font-mono text-white font-bold">{log.personId}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] text-gray-500 uppercase font-black tracking-widest leading-none mb-1">Movement</span>
          <span className="text-xs text-blue-400 font-bold whitespace-nowrap overflow-hidden text-ellipsis flex items-center">
            {log.fromCamera} <ChevronRight size={10} className="mx-1 text-gray-600" /> {log.toCamera}
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[9px] text-gray-500 uppercase font-black tracking-widest leading-none mb-1">Confidence</span>
          <div className="flex items-center space-x-1">
             <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
             <span className={cn(
              "text-xs font-bold",
              log.confidence > 0.95 ? "text-emerald-400" : "text-yellow-400"
            )}>{(log.confidence * 100).toFixed(1)}%</span>
          </div>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[9px] text-gray-500 uppercase font-black tracking-widest leading-none mb-1">Event Time</span>
          <span className="text-xs font-mono text-gray-300">{log.timestamp}</span>
        </div>
      </div>
      <ChevronRight size={16} className="text-gray-700 group-hover:text-blue-400 transition-transform group-hover:translate-x-1" />
    </motion.div>
  );
}

const StatCard: React.FC<{ label: string; value: string; delta: string; inverse?: boolean }> = ({ label, value, delta, inverse = false }) => {
  const isPositive = delta.startsWith('+');
  const isGood = inverse ? !isPositive : isPositive;
  return (
    <div className="p-3 rounded-xl bg-[#141416] border border-[#1f1f23]">
      <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest mb-1">{label}</div>
      <div className="flex items-baseline justify-between">
        <div className="text-lg font-bold">{value}</div>
        <div className={cn("text-[10px] font-bold", isGood ? "text-emerald-500" : "text-red-500")}>
          {delta}
        </div>
      </div>
    </div>
  );
}

const ControlToggle: React.FC<{ label: string; active?: boolean }> = ({ label, active = false }) => {
  const [isOn, setIsOn] = useState(active);
  return (
    <div className="flex items-center justify-between group cursor-pointer" onClick={() => setIsOn(!isOn)}>
      <span className="text-xs text-gray-400 group-hover:text-white transition-colors">{label}</span>
      <div className={cn(
        "w-8 h-4 rounded-full transition-all relative flex items-center px-0.5",
        isOn ? "bg-blue-600" : "bg-[#1f1f23]"
      )}>
        <div className={cn(
          "w-3 h-3 rounded-full bg-white transition-all transform",
          isOn ? "translate-x-4" : "translate-x-0"
        )} />
      </div>
    </div>
  );
}
