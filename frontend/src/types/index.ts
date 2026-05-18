export interface Person {
  id: string;
  thumbnail: string;
  lastSeen: string;
  location: string;
  score: number;
}

export interface ReidLog {
  id: string;
  timestamp: string;
  personId: string;
  fromCamera: string;
  toCamera: string;
  confidence: number;
  thumbnail: string;
}

export interface CameraConfig {
  id: string;
  name: string;
  status: 'online' | 'offline';
  fps: number;
  resolution: string;
  bitrate: string;
}

export interface SystemStats {
  cpuUsage: number;
  gpuUsage: number;
  ramUsage: number;
  gpuTemp: number;
}
