/**
 * SafeVoyage Sentinel - SafetyDashboard.tsx
 * 
 * Features:
 * - Live Google Maps Embed + Tactical Radar HUD
 * - Defect #QA-03 Resolved: Interactive Geofence Radius Slider (50m - 1000m) with live map circle scaling
 * - Defect #QA-04 Resolved: Automated Web Audio Dual-Oscillator Siren on Geofence Boundary Breach
 * - Simulate GPS Drift & Realtime Telemetry calculations
 * - 5-Second SOS Panic Trigger with Abort / Cancel
 * - Voice Copilot Command System
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  ShieldAlert,
  AlertTriangle,
  Radio,
  Compass,
  Navigation,
  Crosshair,
  Volume2,
  VolumeX,
  Play,
  Pause,
  RotateCcw,
  Search,
  Sliders,
  CheckCircle,
  PhoneCall,
  MapPin,
  Mic,
  Maximize2
} from "lucide-react";

// ============================================================================
// HELPER: HAVERSINE DISTANCE CALCULATION (METERS)
// ============================================================================
export function calculateDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371e3; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

// ============================================================================
// PRESET ZONES (HAZARDS & SAFE HAVENS)
// ============================================================================
export interface HazardZone {
  id: string;
  name: string;
  lat: number;
  lng: number;
  threatScore: number;
  riskType: string;
}

export interface SafeHaven {
  id: string;
  name: string;
  lat: number;
  lng: number;
  status: string;
  type: "police" | "hospitality";
  phone: string;
  address: string;
  note: string;
  leftOffset: number;
  topOffset: number;
}

const HAZARD_ZONES: HazardZone[] = [
  {
    id: "haz-1",
    name: "Red Zone: Port District Corridor",
    lat: 40.7562,
    lng: -73.989,
    threatScore: 83,
    riskType: "Active Crime & Pedestrian Hazard"
  },
  {
    id: "haz-2",
    name: "Orange Zone: Central Market Jam",
    lat: 40.7595,
    lng: -73.982,
    threatScore: 55,
    riskType: "Severe Pickpocket Frequency"
  }
];

const SAFE_HAVENS: SafeHaven[] = [
  {
    id: "safe-1",
    name: "Tourist Police Substation",
    lat: 40.757,
    lng: -73.986,
    status: "Active Guard Presence",
    type: "police",
    phone: "212-555-0199",
    address: "42nd St & Broadway Kiosk",
    note: "Central visitor security desk. Dedicated armed tourist patrol division with multi-language translators.",
    leftOffset: 45,
    topOffset: 68
  },
  {
    id: "safe-2",
    name: "Approved Hospitality Plaza",
    lat: 40.7588,
    lng: -73.984,
    status: "Secure Haven Synced",
    type: "hospitality",
    phone: "212-555-0125",
    address: "405 W 45th St, NY",
    note: "Gold hotel partnership under safe-corridor agreement. 24h monitored vestibule.",
    leftOffset: 58,
    topOffset: 35
  },
  {
    id: "safe-3",
    name: "Metropolitan Police Precinct 14",
    lat: 40.7554,
    lng: -73.9812,
    status: "Tactical Desk Active",
    type: "police",
    phone: "212-555-0144",
    address: "357 W 35th St, NY",
    note: "Primary regional law enforcement precinct. Armed tactical units and medical holding bays.",
    leftOffset: 32,
    topOffset: 50
  },
  {
    id: "safe-4",
    name: "Times Square Police Command Kiosk",
    lat: 40.758,
    lng: -73.9855,
    status: "Rapid Dispatch Unit",
    type: "police",
    phone: "212-555-0155",
    address: "43rd St & Broadway, NY",
    note: "High-visibility kiosk with direct surveillance tie-ins and motorcycle escorts.",
    leftOffset: 52,
    topOffset: 48
  }
];

interface SafetyDashboardProps {
  currentLocation?: string;
}

export const SafetyDashboard: React.FC<SafetyDashboardProps> = ({
  currentLocation = "Times Square, New York"
}) => {
  // --------------------------------------------------------------------------
  // USER TELEMETRY & PROFILE STATE
  // --------------------------------------------------------------------------
  const [travelerName] = useState<string>(
    () => localStorage.getItem("traveler_name") || "Alexis Carter"
  );
  const [userPlan] = useState<string>(
    () => localStorage.getItem("userPlan") || "Voyager Solo"
  );
  const [bloodType] = useState<string>(
    () => localStorage.getItem("traveler_bloodType") || "O Positive"
  );

  // --------------------------------------------------------------------------
  // GEOSPATIAL & POSITIONING STATE
  // --------------------------------------------------------------------------
  const ANCHOR_LAT = 40.758;
  const ANCHOR_LNG = -73.9855;

  const [lat, setLat] = useState<number>(ANCHOR_LAT);
  const [lng, setLng] = useState<number>(ANCHOR_LNG);
  const [heading, setHeading] = useState<number>(42);
  const [speed, setSpeed] = useState<number>(9);
  const [zoom, setZoom] = useState<number>(15);
  const [mapType, setMapType] = useState<"roadmap" | "satellite" | "terrain" | "hybrid">("roadmap");
  const [displayMode, setDisplayMode] = useState<"live" | "tactical">("live");

  // DEFECT #QA-03: Interactive Geofence Radius Slider state (defaults to 150m)
  const [geofenceRadius, setGeofenceRadius] = useState<number>(150);
  const [isGeofenceBreached, setIsGeofenceBreached] = useState<boolean>(false);
  const [isDrifting, setIsDrifting] = useState<boolean>(false);

  // --------------------------------------------------------------------------
  // DYNAMIC RISK & SCORE STATE
  // --------------------------------------------------------------------------
  const [safetyScore, setSafetyScore] = useState<number>(94);
  const [threatLevel, setThreatLevel] = useState<"Low" | "Moderate" | "High">("Low");
  const [selectedPoi, setSelectedPoi] = useState<any>(null);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showSearchDropdown, setShowSearchDropdown] = useState<boolean>(false);
  const [poiFilter, setPoiFilter] = useState<"all" | "police" | "close">("all");

  // --------------------------------------------------------------------------
  // SOS & AUDIO OSCILLATOR SIREN ENGINE
  // --------------------------------------------------------------------------
  const [isSOSActive, setIsSOSActive] = useState<boolean>(false);
  const [sosCountdown, setSosCountdown] = useState<number | null>(null);
  const [isSirenPlaying, setIsSirenPlaying] = useState<boolean>(false);
  const [auditLogs, setAuditLogs] = useState<string[]>([]);

  // Web Audio Context & Oscillators
  const audioCtxRef = useRef<AudioContext | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);
  const oscSineRef = useRef<OscillatorNode | null>(null);
  const oscSawRef = useRef<OscillatorNode | null>(null);
  const sirenIntervalRef = useRef<any>(null);
  const sosIntervalRef = useRef<any>(null);

  // Voice Command System
  const [isListeningVoice, setIsListeningVoice] = useState<boolean>(false);
  const [capturedVoicePhrase, setCapturedVoicePhrase] = useState<string>("");

  // Distance from Anchor & Hazard Proximity
  const distanceFromAnchor = calculateDistance(lat, lng, ANCHOR_LAT, ANCHOR_LNG);
  const nearestHazard = HAZARD_ZONES.map((z) => ({
    ...z,
    distance: calculateDistance(lat, lng, z.lat, z.lng)
  })).reduce((prev, curr) => (curr.distance < prev.distance ? curr : prev));

  // --------------------------------------------------------------------------
  // AUDIO SYNTHESIS ENGINE (DEFECT #QA-04: SIREN OSCILLATOR)
  // --------------------------------------------------------------------------
  const startSirenSynth = useCallback(() => {
    try {
      if (audioCtxRef.current) return; // Already active

      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) {
        console.warn("Web Audio API not supported in this browser.");
        return;
      }

      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;

      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.35, ctx.currentTime + 0.15);
      gain.connect(ctx.destination);
      gainNodeRef.current = gain;

      // Dual Oscillators (Sine 580Hz -> 1100Hz + Sawtooth 440Hz -> 800Hz)
      const sineOsc = ctx.createOscillator();
      sineOsc.type = "sine";
      sineOsc.frequency.setValueAtTime(580, ctx.currentTime);
      sineOsc.connect(gain);
      sineOsc.start();
      oscSineRef.current = sineOsc;

      const sawOsc = ctx.createOscillator();
      sawOsc.type = "sawtooth";
      sawOsc.frequency.setValueAtTime(440, ctx.currentTime);
      sawOsc.connect(gain);
      sawOsc.start();
      oscSawRef.current = sawOsc;

      let cycle = 0;
      sirenIntervalRef.current = setInterval(() => {
        if (!ctx || !sineOsc || !sawOsc) return;
        const now = ctx.currentTime;
        if (cycle === 0) {
          sineOsc.frequency.exponentialRampToValueAtTime(1100, now + 0.38);
          sawOsc.frequency.exponentialRampToValueAtTime(800, now + 0.38);
          cycle = 1;
        } else {
          sineOsc.frequency.exponentialRampToValueAtTime(550, now + 0.38);
          sawOsc.frequency.exponentialRampToValueAtTime(380, now + 0.38);
          cycle = 0;
        }
      }, 400);

      setIsSirenPlaying(true);
    } catch (e) {
      console.error("Failed to start Web Audio Siren Oscillator:", e);
    }
  }, []);

  const stopSirenSynth = useCallback(() => {
    if (sirenIntervalRef.current) {
      clearInterval(sirenIntervalRef.current);
      sirenIntervalRef.current = null;
    }

    if (gainNodeRef.current && audioCtxRef.current) {
      try {
        gainNodeRef.current.gain.linearRampToValueAtTime(
          0,
          audioCtxRef.current.currentTime + 0.1
        );
      } catch {}
    }

    setTimeout(() => {
      try {
        oscSineRef.current?.stop();
        oscSawRef.current?.stop();
        audioCtxRef.current?.close();
      } catch {}
      oscSineRef.current = null;
      oscSawRef.current = null;
      audioCtxRef.current = null;
      gainNodeRef.current = null;
    }, 120);

    setIsSirenPlaying(false);
  }, []);

  const speakAlert = useCallback((text: string) => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      utterance.pitch = 1.05;
      window.speechSynthesis.speak(utterance);
    }
  }, []);

  // --------------------------------------------------------------------------
  // DEFECT #QA-04 RESOLUTION: AUTOMATED SIREN ON GEOFENCE BREACH
  // --------------------------------------------------------------------------
  useEffect(() => {
    const isBreached = distanceFromAnchor > geofenceRadius;

    if (isBreached !== isGeofenceBreached) {
      setIsGeofenceBreached(isBreached);

      if (isBreached) {
        // Automatically start the Web Audio Siren Oscillator
        startSirenSynth();
        speakAlert(
          `Warning: Safe geofence breached by ${
            distanceFromAnchor - geofenceRadius
          } meters. Turn back immediately!`
        );
        setAuditLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] GEOFENCE BREACH: ${distanceFromAnchor}m > ${geofenceRadius}m threshold. SIREN ACTIVATED.`,
          ...prev
        ]);
      } else {
        // Automatically stop the Web Audio Siren Oscillator when back within perimeter
        stopSirenSynth();
        speakAlert("Geofence perimeter re-secured. Safe coverage active.");
        setAuditLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] Geofence re-entered (${distanceFromAnchor}m <= ${geofenceRadius}m). Siren silenced.`,
          ...prev
        ]);
      }
    }
  }, [
    distanceFromAnchor,
    geofenceRadius,
    isGeofenceBreached,
    startSirenSynth,
    stopSirenSynth,
    speakAlert
  ]);

  // Cleanup Web Audio & intervals on unmount
  useEffect(() => {
    return () => {
      stopSirenSynth();
      if (sosIntervalRef.current) clearInterval(sosIntervalRef.current);
    };
  }, [stopSirenSynth]);

  // --------------------------------------------------------------------------
  // DYNAMIC SAFETY SCORE CALCULATION
  // --------------------------------------------------------------------------
  useEffect(() => {
    let score = 98;
    if (distanceFromAnchor > geofenceRadius) {
      score -= Math.min(30, Math.round((distanceFromAnchor - geofenceRadius) / 5));
    }
    if (nearestHazard.distance < 120) {
      score -= Math.max(10, Math.round((120 - nearestHazard.distance) * 0.6));
    }

    const finalScore = Math.max(10, Math.min(100, score));
    setSafetyScore(finalScore);
    setThreatLevel(finalScore > 80 ? "Low" : finalScore > 55 ? "Moderate" : "High");
  }, [distanceFromAnchor, geofenceRadius, nearestHazard.distance]);

  // --------------------------------------------------------------------------
  // SIMULATE GPS DRIFT ENGINE
  // --------------------------------------------------------------------------
  useEffect(() => {
    let driftTimer: any = null;
    if (isDrifting) {
      driftTimer = setInterval(() => {
        setLat((prev) => prev - 0.00015);
        setLng((prev) => prev - 0.00022);
        setHeading((prev) => (prev + 12) % 360);
        setSpeed((prev) => Math.min(14, Math.max(5, prev + (Math.random() > 0.5 ? 1 : -1))));
      }, 1500);
    }
    return () => {
      if (driftTimer) clearInterval(driftTimer);
    };
  }, [isDrifting]);

  const recenterCoordinates = () => {
    setLat(ANCHOR_LAT);
    setLng(ANCHOR_LNG);
    setHeading(42);
    setSpeed(9);
    stopSirenSynth();
    speakAlert("GPS coordinates centered on Times Square anchor.");
    setAuditLogs((prev) => [
      `[${new Date().toLocaleTimeString()}] Coordinates recentered to anchor.`,
      ...prev
    ]);
  };

  // --------------------------------------------------------------------------
  // 5-SECOND SOS PANIC COUNTDOWN & CANCELLATION
  // --------------------------------------------------------------------------
  const toggleSOSCountdown = () => {
    if (sosCountdown !== null || isSOSActive) {
      // Cancel active SOS
      if (sosIntervalRef.current) clearInterval(sosIntervalRef.current);
      setSosCountdown(null);
      setIsSOSActive(false);
      stopSirenSynth();
      speakAlert("Emergency SOS cancelled. Alarms deactivated.");
      setAuditLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] SOS dispatch manually aborted.`,
        ...prev
      ]);
    } else {
      // Trigger 5s Countdown
      setSosCountdown(5);
      speakAlert("Warning: SOS countdown initiated. 5 seconds to abort.");
      setAuditLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] 5-second emergency SOS countdown armed.`,
        ...prev
      ]);

      sosIntervalRef.current = setInterval(() => {
        setSosCountdown((prev) => {
          if (prev === null) return null;
          if (prev <= 1) {
            clearInterval(sosIntervalRef.current);
            dispatchSOSAlert();
            return null;
          }
          return prev - 1;
        });
      }, 1000);
    }
  };

  const dispatchSOSAlert = async () => {
    setIsSOSActive(true);
    startSirenSynth();
    speakAlert(
      `Emergency SOS Active! Transmitting coordinates ${lat.toFixed(4)}, ${lng.toFixed(
        4
      )} to First Responders!`
    );

    setAuditLogs((prev) => [
      `[${new Date().toLocaleTimeString()}] CRITICAL SOS DISPATCHED to emergency services.`,
      `[${new Date().toLocaleTimeString()}] Audio siren synth locked active.`,
      ...prev
    ]);

    try {
      await fetch("/api/incidents/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reporterName: "CRITICAL SOS ACTIVATED",
          reporterPhone: "Immediate GPS Stream Channel",
          incidentType: "Emergency SOS Button Push",
          description: "EMERGENCY: User activated immediate SOS button countdown. GPS Coordinates and audio broadcast channels locked active.",
          location: `${lat.toFixed(6)}, ${lng.toFixed(6)}`,
          contactEmergencyName: "Family Beacon Direct Alert",
          audioRecorded: true
        })
      });
    } catch (e) {
      console.warn("Backend link offline, local emergency triage fallback active.", e);
    }
  };

  // --------------------------------------------------------------------------
  // VOICE COMMAND COPILOT SYSTEM
  // --------------------------------------------------------------------------
  const triggerVoiceCommand = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Web Speech API is not supported in this browser.");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.lang = "en-US";
      recognition.interimResults = false;

      recognition.onstart = () => {
        setIsListeningVoice(true);
      };

      recognition.onerror = () => {
        setIsListeningVoice(false);
      };

      recognition.onend = () => {
        setIsListeningVoice(false);
      };

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setCapturedVoicePhrase(transcript);

        const lower = transcript.toLowerCase();
        if (lower.includes("sos") || lower.includes("help") || lower.includes("panic")) {
          toggleSOSCountdown();
        } else if (lower.includes("radius") || lower.includes("geofence") || lower.includes("fence")) {
          // Adjust geofence radius via voice
          const match = lower.match(/\d+/);
          const newRad = match ? Math.min(1000, Math.max(50, parseInt(match[0], 10))) : 250;
          setGeofenceRadius(newRad);
          speakAlert(`Adjusted geofence boundary radius to ${newRad} meters.`);
        } else if (lower.includes("silence") || lower.includes("clear") || lower.includes("stop")) {
          stopSirenSynth();
          setIsSOSActive(false);
          if (sosIntervalRef.current) clearInterval(sosIntervalRef.current);
          setSosCountdown(null);
          speakAlert("Alarms silenced.");
        }
      };

      recognition.start();
    } catch (e) {
      setIsListeningVoice(false);
    }
  };

  return (
    <div className="space-y-6 py-2 text-left font-sans text-gray-100">
      {/* ==================================================================== */}
      {/* 1. GEOFENCE BREACH & SOS ALARM BANNER */}
      {/* ==================================================================== */}
      <AnimatePresence>
        {(isGeofenceBreached || isSOSActive) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className={`p-4 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border text-white shadow-xl ${
              isSOSActive
                ? "bg-gradient-to-r from-red-650 to-rose-600 border-red-500 animate-pulse"
                : "bg-gradient-to-r from-amber-600 to-orange-500 border-amber-400"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-white/20 rounded-xl shrink-0">
                <ShieldAlert className="h-6 w-6 text-white animate-spin" />
              </div>
              <div className="space-y-0.5">
                <h4 className="text-sm font-black font-mono tracking-widest uppercase">
                  {isSOSActive
                    ? "CRITICAL SOS BEACON BROADCASTING"
                    : "GEOFENCE BOUNDARY CONTAINMENT BREACH"}
                </h4>
                <p className="text-xs text-white/90 font-medium">
                  {isSOSActive
                    ? `Transmitting Coordinates (${lat.toFixed(4)}, ${lng.toFixed(4)}) to Metropolitan First Responders.`
                    : `Current anchor offset: ${distanceFromAnchor}m. Maximum permitted perimeter: ${geofenceRadius}m.`}
                </p>
              </div>
            </div>

            <button
              onClick={() => {
                stopSirenSynth();
                setIsSOSActive(false);
              }}
              className="px-4 py-2 bg-white text-gray-900 hover:bg-gray-100 rounded-xl text-xs font-black uppercase tracking-wider shadow cursor-pointer transition-transform hover:scale-105 shrink-0"
            >
              SILENCE WARNING
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ==================================================================== */}
      {/* 2. MAIN COCKPIT: RADAR / MAP & TELEMETRY */}
      {/* ==================================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        <div className="lg:col-span-8 flex flex-col space-y-6">
          {/* Tactical Monitor Box */}
          <div className="bg-[#120E22]/80 backdrop-blur-md p-6 rounded-3xl border border-slate-800 shadow-2xl relative overflow-hidden flex flex-col justify-between">
            {/* Top Bar: Live Map vs Tactical HUD & Action Controls */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-slate-800/80 z-20">
              <div className="space-y-1">
                <span className="text-[10px] font-black font-mono tracking-widest text-blue-400 uppercase flex items-center gap-1.5">
                  <Radio className="h-3.5 w-3.5 animate-pulse text-blue-400" />
                  PRECISION TARGET MONITOR
                </span>
                <h3 className="text-xl font-extrabold text-white">Active Precision Map</h3>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* View Mode Toggle */}
                <div className="flex bg-slate-900 p-1 rounded-xl border border-slate-800">
                  <button
                    onClick={() => setDisplayMode("live")}
                    className={`px-3 py-1.5 text-[10px] font-mono font-black uppercase rounded-lg transition-all ${
                      displayMode === "live"
                        ? "bg-blue-600 text-white shadow-md"
                        : "text-gray-400 hover:text-white"
                    }`}
                  >
                    🗺️ Live Map
                  </button>
                  <button
                    onClick={() => setDisplayMode("tactical")}
                    className={`px-3 py-1.5 text-[10px] font-mono font-black uppercase rounded-lg transition-all ${
                      displayMode === "tactical"
                        ? "bg-blue-600 text-white shadow-md"
                        : "text-gray-400 hover:text-white"
                    }`}
                  >
                    🚀 Tactical HUD
                  </button>
                </div>

                {/* Simulate GPS Drift Button */}
                <button
                  onClick={() => setIsDrifting(!isDrifting)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-black uppercase tracking-wider flex items-center gap-1.5 transition-all ${
                    isDrifting
                      ? "bg-amber-500 text-slate-950 font-black animate-pulse shadow-md"
                      : "bg-slate-900 hover:bg-slate-800 text-gray-200 border border-slate-800"
                  }`}
                  title="Simulate continuous drift towards the Port District danger block"
                >
                  {isDrifting ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                  <span>{isDrifting ? "Pause Drift" : "Simulate Drift"}</span>
                </button>

                {/* Recenter Button */}
                <button
                  onClick={recenterCoordinates}
                  className="p-2 bg-slate-900 hover:bg-slate-800 text-gray-300 rounded-xl border border-slate-800"
                  title="Recenter position to Times Square Anchor"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Interactive Map Visual Area */}
            <div className="my-6 min-h-[380px] rounded-3xl border border-slate-800 relative overflow-hidden flex flex-col justify-end bg-slate-950 shadow-inner">
              {displayMode === "live" ? (
                <iframe
                  title="Live Google Map"
                  src={`https://maps.google.com/maps?q=${lat},${lng}&t=${
                    mapType === "satellite" || mapType === "hybrid"
                      ? "k"
                      : mapType === "terrain"
                      ? "p"
                      : "m"
                  }&z=${zoom}&ie=UTF8&iwloc=&output=embed`}
                  className="w-full h-full border-0 absolute inset-0"
                  loading="lazy"
                  referrerPolicy="no-referrer"
                />
              ) : (
                /* Tactical Radar HUD Simulation */
                <div className="absolute inset-0 bg-[#070512] bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] flex items-center justify-center">
                  {/* Dynamic Geofence Visual Perimeter (Scales smoothly with geofenceRadius state) */}
                  <div
                    className={`absolute rounded-full border-2 border-dashed transition-all duration-300 pointer-events-none flex items-center justify-center ${
                      isGeofenceBreached
                        ? "border-red-500/70 bg-red-500/10 animate-pulse"
                        : "border-blue-500/50 bg-blue-500/5"
                    }`}
                    style={{
                      width: `${geofenceRadius * 0.9}px`,
                      height: `${geofenceRadius * 0.9}px`
                    }}
                  >
                    <span className="text-[9px] font-mono font-bold px-2 py-0.5 bg-slate-900/90 text-blue-400 border border-blue-500/30 rounded -top-3 absolute">
                      PERIMETER: {geofenceRadius}M
                    </span>
                  </div>

                  {/* Anchor Point */}
                  <div className="h-3 w-3 rounded-full bg-emerald-500 shadow-[0_0_15px_#10b981]" />

                  {/* User Marker */}
                  <motion.div
                    className="absolute flex flex-col items-center cursor-pointer select-none"
                    animate={{
                      x: `${(lng - ANCHOR_LNG) * 22000}px`,
                      y: `${(ANCHOR_LAT - lat) * 22000}px`
                    }}
                    transition={{ type: "spring", stiffness: 80 }}
                  >
                    <div
                      className={`h-7 w-7 rounded-full flex items-center justify-center text-white border-2 shadow-lg ${
                        isGeofenceBreached
                          ? "bg-red-650 border-red-300 animate-ping"
                          : "bg-blue-600 border-blue-300"
                      }`}
                    >
                      <Crosshair className="h-4 w-4" />
                    </div>
                    <span className="text-[8px] font-mono font-bold bg-slate-900 px-1 rounded mt-1 border border-slate-800">
                      Alexis (You)
                    </span>
                  </motion.div>
                </div>
              )}

              {/* Map Layers Selector (Roadmap / Satellite / Terrain / Hybrid) */}
              <div className="absolute top-4 right-4 z-30">
                <div className="bg-slate-900/95 backdrop-blur-md shadow-2xl border border-slate-800 rounded-xl p-1 flex gap-1">
                  {(["roadmap", "satellite", "terrain", "hybrid"] as const).map((type) => (
                    <button
                      key={type}
                      onClick={() => setMapType(type)}
                      className={`px-2.5 py-1 text-[9.5px] font-mono font-black uppercase tracking-wider rounded-lg transition-all ${
                        mapType === type
                          ? "bg-blue-600 text-white shadow-md"
                          : "text-gray-400 hover:bg-slate-800 hover:text-white"
                      }`}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </div>

              {/* Landmark Search Overlay */}
              <div className="absolute top-4 left-4 z-30 max-w-[260px] w-full">
                <div className="bg-slate-900/95 backdrop-blur-md border border-slate-800 rounded-2xl p-1.5 px-3 flex items-center gap-2 shadow-xl">
                  <Search className="h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onFocus={() => setShowSearchDropdown(true)}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search Google Maps..."
                    className="w-full text-xs bg-transparent border-none text-white focus:outline-none"
                  />
                </div>

                {showSearchDropdown && (
                  <div className="mt-1 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden text-xs">
                    <button
                      onClick={() => {
                        setLat(40.757);
                        setLng(-73.986);
                        setShowSearchDropdown(false);
                      }}
                      className="w-full p-2.5 text-left hover:bg-slate-800 flex items-center gap-2 border-b border-slate-800/80"
                    >
                      <MapPin className="h-3.5 w-3.5 text-emerald-400" />
                      <div>
                        <p className="font-bold text-gray-200">Tourist Police Substation</p>
                        <p className="text-[10px] text-gray-400">40.7570° N, -73.9860° W</p>
                      </div>
                    </button>
                    <button
                      onClick={() => {
                        setLat(40.7562);
                        setLng(-73.989);
                        setShowSearchDropdown(false);
                      }}
                      className="w-full p-2.5 text-left hover:bg-slate-800 flex items-center gap-2"
                    >
                      <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                      <div>
                        <p className="font-bold text-red-400">🔴 Red Zone: Port District</p>
                        <p className="text-[10px] text-gray-400">Hazard Danger Territory</p>
                      </div>
                    </button>
                  </div>
                )}
              </div>

              {/* ============================================================ */}
              {/* DEFECT #QA-03 RESOLUTION: INTERACTIVE GEOFENCE SLIDER OVERLAY */}
              {/* ============================================================ */}
              <div className="absolute bottom-4 right-4 z-30 max-w-[280px] w-full bg-slate-900/95 backdrop-blur-md p-3.5 rounded-2xl border border-slate-800 shadow-2xl space-y-2">
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className="font-black text-blue-400 flex items-center gap-1.5 text-[11px] uppercase tracking-wider">
                    <Sliders className="h-3.5 w-3.5 text-blue-400" />
                    Geofence Radius
                  </span>
                  <span className="bg-blue-600/20 text-blue-400 font-extrabold px-2 py-0.5 rounded text-[10px] border border-blue-500/30">
                    {geofenceRadius} METERS
                  </span>
                </div>

                {/* Range Input Slider */}
                <div className="space-y-1">
                  <input
                    type="range"
                    min="50"
                    max="1000"
                    step="25"
                    value={geofenceRadius}
                    onChange={(e) => setGeofenceRadius(Number(e.target.value))}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                  />
                  <div className="flex justify-between text-[9px] font-mono text-gray-400">
                    <span>50m</span>
                    <span>500m</span>
                    <span>1000m</span>
                  </div>
                </div>

                {/* Quick Presets */}
                <div className="flex gap-1.5 pt-1">
                  {[100, 250, 500].map((preset) => (
                    <button
                      key={preset}
                      onClick={() => setGeofenceRadius(preset)}
                      className={`flex-1 py-1 rounded text-[9.5px] font-mono font-bold transition-all border ${
                        geofenceRadius === preset
                          ? "bg-blue-600 text-white border-blue-400"
                          : "bg-slate-800 hover:bg-slate-750 text-gray-300 border-slate-700"
                      }`}
                    >
                      {preset}m
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Bottom Bar: Live Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 border-t border-slate-800/80 text-xs font-mono text-gray-400">
              <div className="flex justify-between items-center">
                <span>GPS Coordinates:</span>
                <span className="font-bold text-white">
                  {lat.toFixed(5)}° N, {lng.toFixed(5)}° W
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span>Anchor Distance:</span>
                <span
                  className={`font-bold ${
                    isGeofenceBreached ? "text-red-400 animate-pulse" : "text-emerald-400"
                  }`}
                >
                  {distanceFromAnchor}m {isGeofenceBreached ? "(BREACH)" : "(SAFE)"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span>Nearest Threat:</span>
                <span className="font-bold text-amber-400">
                  {nearestHazard.name.split(":")[0]} ({nearestHazard.distance}m)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------------ */}
        {/* RIGHT COLUMN: TACTICAL EMERGENCY COCKPIT & VOICE SYSTEM */}
        {/* ------------------------------------------------------------------ */}
        <div className="lg:col-span-4 flex flex-col space-y-6">
          {/* Tactical SOS Panel */}
          <div className="bg-[#120E22]/80 backdrop-blur-md p-6 rounded-3xl border border-slate-800 shadow-2xl flex flex-col items-center text-center space-y-5">
            <span className="text-[10px] font-black font-mono tracking-widest text-red-400 uppercase">
              AUTONOMOUS SOS PANIC DISPATCHER
            </span>

            {/* Circular SOS Panic Trigger Button */}
            <div className="relative py-2">
              {sosCountdown !== null && (
                <div className="absolute inset-0 m-auto h-36 w-36 rounded-full bg-red-650/40 blur-xl animate-ping" />
              )}
              <button
                onClick={toggleSOSCountdown}
                className={`h-32 w-32 rounded-full flex flex-col items-center justify-center font-extrabold tracking-widest uppercase transition-all shadow-2xl border-4 ${
                  sosCountdown !== null
                    ? "bg-red-600 border-white text-white animate-pulse"
                    : isSOSActive
                    ? "bg-red-700 border-red-400 text-white"
                    : "bg-gradient-to-tr from-red-650 to-rose-600 border-red-500 hover:scale-105 active:scale-95 text-white"
                }`}
              >
                {sosCountdown !== null ? (
                  <>
                    <span className="text-3xl font-black font-mono">{sosCountdown}</span>
                    <span className="text-[9px] uppercase tracking-wider mt-0.5">Cancel SOS</span>
                  </>
                ) : isSOSActive ? (
                  <>
                    <VolumeX className="h-6 w-6 mb-1" />
                    <span className="text-[10px]">Silence SOS</span>
                  </>
                ) : (
                  <>
                    <ShieldAlert className="h-8 w-8 mb-1" />
                    <span className="text-sm font-black">SOS PANIC</span>
                  </>
                )}
              </button>
            </div>

            <p className="text-[11px] text-gray-400 font-mono leading-relaxed">
              Press to trigger immediate 5-second countdown. Dispatches satellite beacons, activates
              dual Web Audio siren oscillators, and streams GPS telemetry.
            </p>

            {/* Manual Siren Synth Test Toggle */}
            <div className="w-full pt-3 border-t border-slate-800 flex justify-between items-center text-xs font-mono">
              <span className="text-gray-400">Web Audio Siren Synth:</span>
              <button
                onClick={() => (isSirenPlaying ? stopSirenSynth() : startSirenSynth())}
                className={`px-3 py-1 rounded-lg font-bold text-[10px] uppercase transition-all ${
                  isSirenPlaying
                    ? "bg-red-600 text-white animate-pulse"
                    : "bg-slate-800 text-gray-300 hover:bg-slate-700"
                }`}
              >
                {isSirenPlaying ? "Stop Siren" : "Test Siren"}
              </button>
            </div>
          </div>

          {/* Voice Command Bar */}
          <div className="bg-[#120E22]/80 backdrop-blur-md p-5 rounded-3xl border border-slate-800 shadow-xl space-y-3">
            <div className="flex justify-between items-center">
              <div>
                <h4 className="text-xs font-black font-mono uppercase text-gray-300 flex items-center gap-1.5">
                  <Mic className="h-4 w-4 text-blue-400" />
                  Voice Copilot Commands
                </h4>
                <p className="text-[10px] text-gray-400">Hands-free tracking & alarm override</p>
              </div>

              <button
                onClick={triggerVoiceCommand}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold uppercase transition-all ${
                  isListeningVoice
                    ? "bg-red-500 text-white animate-pulse"
                    : "bg-blue-600 hover:bg-blue-700 text-white"
                }`}
              >
                {isListeningVoice ? "Listening..." : "Speak"}
              </button>
            </div>

            {capturedVoicePhrase && (
              <p className="p-2 bg-slate-900/90 rounded-xl text-[10px] font-mono text-gray-300 border border-slate-800">
                Captured: &ldquo;{capturedVoicePhrase}&rdquo;
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
