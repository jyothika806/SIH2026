/**
 * SafeVoyage Sentinel - AIAssistant.tsx
 * 
 * Features:
 * - Conversational AI Tourist Safety Companion
 * - Voice Dictation Input: Web Speech API (SpeechRecognition / webkitSpeechRecognition)
 *   with live transcript streaming directly into the message input field
 * - Multimodal Attachment Ingestion: File picker with Base64 payload encoding
 *   forwarded to POST /api/assistant/chat
 * - Quick Diagnostic Presets (Zone Safety, Crime Index, Emergency Hospital, Local Laws)
 * - Emergency Distress Panic Mode Preset
 * - Dark Tactical Glassmorphic Aesthetic
 */

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Paperclip,
  Mic,
  MicOff,
  Bot,
  User,
  Shield,
  ShieldAlert,
  MapPin,
  Sparkles,
  AlertTriangle,
  FileText,
  X,
  Volume2
} from "lucide-react";

export interface Attachment {
  name: string;
  type: string;
  size: number;
  data: string; // Base64 representation
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  attachment?: {
    name: string;
    type: string;
    size: number;
  };
}

interface AIAssistantProps {
  currentLocation?: string;
  setCurrentLocation?: (loc: string) => void;
}

export const AIAssistant: React.FC<AIAssistantProps> = ({
  currentLocation = "Times Square, New York",
  setCurrentLocation
}) => {
  // --------------------------------------------------------------------------
  // STATE MANAGEMENT
  // --------------------------------------------------------------------------
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "init-1",
      role: "assistant",
      content:
        `Hello Alexis! I am **SafeVoyage Copilot**, your autonomous security and response guardian. ` +
        `I am continuously monitoring localized crime forecasts, threat matrices, and emergency hospital nodes around **${currentLocation}**.\n\n` +
        `How can I assist your transit path or safety evaluations right now?`,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    }
  ]);

  const [inputText, setInputText] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [activeAttachment, setActiveAttachment] = useState<Attachment | null>(null);

  // Speech Recognition / Voice Dictation State
  const [isListening, setIsListening] = useState<boolean>(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);

  // Distress Pulse Timer
  const [isDistressActive, setIsDistressActive] = useState<boolean>(false);
  const [distressTimer, setDistressTimer] = useState<number>(0);
  const distressIntervalRef = useRef<any>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSubmitting]);

  // Distress timer loop
  useEffect(() => {
    if (isDistressActive) {
      distressIntervalRef.current = setInterval(() => {
        setDistressTimer((prev) => prev + 1);
      }, 1000);
    } else {
      if (distressIntervalRef.current) clearInterval(distressIntervalRef.current);
      setDistressTimer(0);
    }
    return () => {
      if (distressIntervalRef.current) clearInterval(distressIntervalRef.current);
    };
  }, [isDistressActive]);

  // --------------------------------------------------------------------------
  // VOICE DICTATION HANDLER (WEB SPEECH API)
  // --------------------------------------------------------------------------
  const toggleVoiceDictation = () => {
    setSpeechError(null);

    // If already listening, stop
    if (isListening) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
      }
      setIsListening(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setSpeechError("Speech recognition is not supported in this browser.");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        setIsListening(true);
        setSpeechError(null);
      };

      recognition.onerror = (event: any) => {
        console.error("Speech Recognition Error:", event.error);
        if (event.error === "not-allowed") {
          setSpeechError("Microphone permission was denied.");
        } else {
          setSpeechError(`Voice input error: ${event.error}`);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      // Live transcript streaming into the textarea input box
      recognition.onresult = (event: any) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }

        setInputText((prev) => {
          // If interim, cleanly append or replace current stream
          const trimmed = prev.trim();
          return trimmed ? `${trimmed} ${transcript.trim()}` : transcript;
        });
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      console.error("Voice dictation init failed:", err);
      setSpeechError("Could not initialize voice recognition.");
      setIsListening(false);
    }
  };

  // --------------------------------------------------------------------------
  // FILE ATTACHMENT HANDLER (BASE64 CONVERSION)
  // --------------------------------------------------------------------------
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();

      reader.onload = () => {
        const base64String = reader.result as string;
        setActiveAttachment({
          name: file.name,
          type: file.type,
          size: file.size,
          data: base64String
        });
      };

      reader.readAsDataURL(file);
    }
  };

  // --------------------------------------------------------------------------
  // MESSAGE SUBMISSION & LLM CHAT PROXY CALL
  // --------------------------------------------------------------------------
  const sendMessage = async (overridePrompt?: string) => {
    const textToSend = overridePrompt !== undefined ? overridePrompt : inputText;

    if (!textToSend.trim() && !activeAttachment) return;

    // Stop voice dictation if active
    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      setIsListening(false);
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: textToSend || "Transmitted attachment for automated security review...",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      attachment: activeAttachment
        ? {
            name: activeAttachment.name,
            type: activeAttachment.type,
            size: activeAttachment.size
          }
        : undefined
    };

    setMessages((prev) => [...prev, userMessage]);
    if (overridePrompt === undefined) setInputText("");
    const attachmentToUpload = activeAttachment;
    setActiveAttachment(null);
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          location: currentLocation,
          messages: [...messages, userMessage].map((m) => ({
            role: m.role,
            content: m.content
          })),
          attachments: attachmentToUpload
            ? [
                {
                  mimeType: attachmentToUpload.type,
                  data: attachmentToUpload.data
                }
              ]
            : undefined
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Failed to reach assistant proxy.`);
      }

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: data.text || "No response received from safety agent.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } catch (err: any) {
      console.warn("API proxy failure. Displaying satellite fallback guidance:", err);

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content:
            `⚠️ **Satellite connection lag detected.** Re-establishing redundant secure channel...\n\n` +
            `In the meantime: Keep situational awareness, ensure you remain in public lit areas, or dial local emergency services (**911** / **112**) if an immediate threat exists.`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTimer = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  // Diagnostic Presets
  const PRESETS = [
    {
      title: "Zone Safety Lookup",
      prompt: "Is my current zone safe right now?",
      desc: "Live risk & threat index check"
    },
    {
      title: "Crime & Theft Index",
      prompt: "What local crime or tourist scam risks should I know in this city?",
      desc: "Historical forecasting logs"
    },
    {
      title: "Emergency Hospitals",
      prompt: "Locate the nearest official emergency hospital or trauma clinic near me.",
      desc: "Medical dispatch directions"
    },
    {
      title: "Local Laws Advice",
      prompt: "What are the local tourist rights, curfew laws, and consulate protocols here?",
      desc: "Legal protection guidelines"
    }
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 py-2 text-left font-sans h-[calc(100vh-140px)] min-h-[580px] text-gray-100">
      {/* -------------------------------------------------------------------- */}
      {/* LEFT COLUMN: DIAGNOSTICS & POSITIONING HUB */}
      {/* -------------------------------------------------------------------- */}
      <div className="lg:col-span-4 flex flex-col gap-5 h-full">
        {/* Positioning Box */}
        <div className="bg-[#120E22]/80 backdrop-blur-md p-5 rounded-3xl border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse" />
            <h3 className="text-xs font-black font-mono uppercase tracking-widest text-gray-400">
              POSITIONING HUB
            </h3>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold text-gray-300 block font-sans">
              Current Evaluated Landmark / Node
            </label>
            <div className="relative">
              <MapPin className="absolute left-3.5 top-1/2 transform -translate-y-1/2 text-blue-500 h-4 w-4" />
              <input
                type="text"
                value={currentLocation}
                onChange={(e) => setCurrentLocation && setCurrentLocation(e.target.value)}
                placeholder="e.g. Times Square, New York"
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-800 bg-slate-900/60 text-white font-medium text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <p className="text-[10px] text-gray-400 font-mono">
              AI adapts context, threat indexes, emergency dispatch numbers, and local hospitals
              automatically to this node.
            </p>
          </div>

          <div className="pt-3 border-t border-slate-800/80 space-y-2 text-xs font-mono">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Sentinel Network:</span>
              <span className="text-emerald-400 font-bold flex items-center gap-1">🟢 Linked</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Protection Tier:</span>
              <span className="text-blue-400 font-bold uppercase bg-blue-500/10 px-2 py-0.5 rounded text-[10px] border border-blue-500/20">
                Guardian Elite
              </span>
            </div>
          </div>
        </div>

        {/* Interactive Diagnostics Presets */}
        <div className="bg-[#120E22]/80 backdrop-blur-md p-5 rounded-3xl border border-slate-800 shadow-xl flex-1 flex flex-col gap-3 overflow-hidden">
          <div className="flex items-center gap-1.5">
            <Sparkles className="h-4 w-4 text-blue-400" />
            <h4 className="text-xs font-black uppercase font-mono tracking-wider text-gray-400">
              Interactive Diagnostics
            </h4>
          </div>

          <div className="grid grid-cols-1 gap-2.5 overflow-y-auto pr-1 flex-1">
            {PRESETS.map((preset, idx) => (
              <button
                key={idx}
                onClick={() => sendMessage(preset.prompt)}
                className="p-3 text-left rounded-xl bg-slate-900/50 hover:bg-blue-600/10 hover:border-blue-500/30 border border-slate-800/80 transition-all cursor-pointer group space-y-1 block"
              >
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-gray-200 group-hover:text-blue-400 font-display transition-colors">
                    {preset.title}
                  </span>
                </div>
                <p className="text-[10px] text-gray-400 line-clamp-1">{preset.prompt}</p>
                <div className="text-[9px] font-mono font-semibold tracking-widest uppercase text-blue-400/80">
                  {preset.desc}
                </div>
              </button>
            ))}
          </div>

          <div className="mt-auto pt-3 border-t border-slate-800/80 flex items-center gap-2 bg-amber-500/5 p-2 rounded-xl border border-amber-500/20">
            <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0" />
            <p className="text-[10px] text-amber-400 leading-normal font-mono">
              <strong>Need Immediate Authority Response?</strong> Switch to the SOS Incident tab for
              satellite police dispatch.
            </p>
          </div>
        </div>
      </div>

      {/* -------------------------------------------------------------------- */}
      {/* RIGHT COLUMN: CHAT WINDOW & MULTIMODAL / VOICE INPUT ENGINE */}
      {/* -------------------------------------------------------------------- */}
      <div className="lg:col-span-8 flex flex-col bg-[#120E22]/80 backdrop-blur-md h-full rounded-3xl border border-slate-800 shadow-2xl overflow-hidden">
        {/* Chat Header */}
        <div className="px-5 py-4 border-b border-slate-800/80 flex justify-between items-center bg-slate-900/40">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-lg">
                <Bot className="h-5 w-5 animate-pulse text-white" />
              </div>
              <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-emerald-500 border-2 border-slate-950 animate-pulse" />
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-white font-display">
                  SafeVoyage Safety Companion
                </span>
                <span className="px-1.5 py-0.5 rounded text-[8px] font-mono font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  Gemini 3.8 Flash
                </span>
              </div>
              <p className="text-[10px] text-gray-400 font-mono">Targeting Node: {currentLocation}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-gray-400">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping" />
            <span>Active Link</span>
          </div>
        </div>

        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-sm">
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 max-w-[85%] ${
                msg.role === "user" ? "ml-auto flex-row-reverse text-right" : "mr-auto text-left"
              }`}
            >
              <div
                className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-slate-900 text-blue-400 border border-slate-800"
                }`}
              >
                {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>

              <div className="space-y-1">
                <div
                  className={`px-4 py-3 rounded-2xl leading-relaxed text-sm ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white rounded-tr-none text-left shadow-sm"
                      : "bg-slate-900/90 border border-slate-800 text-gray-200 rounded-tl-none font-sans"
                  }`}
                >
                  {msg.content.split("\n\n").map((para, pIdx) => (
                    <p key={pIdx} className={pIdx > 0 ? "mt-2" : ""}>
                      {para.split("**").map((chunk, cIdx) =>
                        cIdx % 2 === 1 ? (
                          <strong key={cIdx} className="font-extrabold text-blue-400">
                            {chunk}
                          </strong>
                        ) : (
                          chunk
                        )
                      )}
                    </p>
                  ))}

                  {/* Attachment Preview in Message Bubble */}
                  {msg.attachment && (
                    <div className="mt-2.5 p-2 bg-black/40 rounded-xl flex items-center gap-2 border border-white/10 max-w-sm text-xs">
                      <FileText className="h-4 w-4 text-emerald-400 shrink-0" />
                      <div className="truncate flex-1">
                        <p className="font-semibold truncate">{msg.attachment.name}</p>
                        <p className="text-[10px] opacity-70 font-mono">
                          {(msg.attachment.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                    </div>
                  )}
                </div>
                <div className="text-[9px] text-gray-500 font-mono px-1">{msg.timestamp}</div>
              </div>
            </motion.div>
          ))}

          {/* Typing Indicator */}
          {isSubmitting && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3 mr-auto items-center">
              <div className="h-8 w-8 rounded-lg bg-slate-900 flex items-center justify-center text-blue-400 border border-slate-800">
                <Bot className="h-4 w-4 text-blue-400 animate-pulse" />
              </div>
              <div className="bg-slate-900 px-4 py-2.5 rounded-2xl border border-slate-800 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" />
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Active Attachment Chip */}
        {activeAttachment && (
          <div className="px-5 py-2 bg-blue-950/40 border-t border-slate-800 flex justify-between items-center text-xs">
            <div className="flex items-center gap-2 text-blue-400">
              <Paperclip className="h-4 w-4 animate-pulse" />
              <span className="font-semibold truncate max-w-xs">{activeAttachment.name}</span>
              <span className="font-mono text-[10px] text-gray-400">
                ({(activeAttachment.size / 1024).toFixed(1)} KB)
              </span>
            </div>
            <button
              onClick={() => setActiveAttachment(null)}
              className="text-gray-400 hover:text-red-400 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Speech Dictation Error Notification */}
        {speechError && (
          <div className="px-5 py-1.5 bg-red-950/60 border-t border-red-800/60 flex items-center justify-between text-xs text-red-300 font-mono">
            <span>⚠️ {speechError}</span>
            <button onClick={() => setSpeechError(null)} className="hover:text-white">
              ✕
            </button>
          </div>
        )}

        {/* Message Input Cockpit */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex gap-2.5 items-center">
            {/* Hidden File Picker Input */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="image/*,video/*,audio/*"
              className="hidden"
            />

            {/* Paperclip Button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-3 bg-slate-900 hover:bg-slate-800 text-gray-400 hover:text-white rounded-xl border border-slate-800 transition-colors"
              title="Attach photo or audio recording"
            >
              <Paperclip className="h-5 w-5" />
            </button>

            {/* Emergency Distress Preset Toggle */}
            <button
              onClick={() => {
                if (isDistressActive) {
                  setIsDistressActive(false);
                  setInputText("I need help locating the nearest police unit or hospital, I feel unsafe here");
                } else {
                  setIsDistressActive(true);
                }
              }}
              className={`p-3 rounded-xl border transition-all cursor-pointer relative ${
                isDistressActive
                  ? "bg-red-650 hover:bg-red-700 text-white border-red-500 animate-pulse shadow-lg shadow-red-500/30"
                  : "bg-slate-900 hover:bg-slate-800 text-gray-400 border-slate-800"
              }`}
              title="Toggle emergency distress preset prompt"
            >
              <ShieldAlert className="h-5 w-5" />
              {isDistressActive && (
                <span className="absolute -top-7 left-1/2 transform -translate-x-1/2 bg-red-600 text-white font-mono font-bold text-[9px] px-1.5 py-0.5 rounded shadow">
                  {formatTimer(distressTimer)}
                </span>
              )}
            </button>

            {/* Textarea Input */}
            <div className="flex-1 relative">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about safe transit pathways, medical services or city crime..."
                rows={1}
                className="w-full pr-12 pl-4 py-3 rounded-xl border border-slate-800 bg-slate-900 text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none min-h-[46px] max-h-[80px]"
              />
            </div>

            {/* ============================================================ */}
            {/* ASSISTANT VOICE DICTATION INPUT BUTTON */}
            {/* ============================================================ */}
            <button
              onClick={toggleVoiceDictation}
              className={`p-3 rounded-xl border transition-all cursor-pointer relative ${
                isListening
                  ? "bg-red-600 text-white border-red-400 animate-pulse shadow-lg shadow-red-500/40"
                  : "bg-slate-900 hover:bg-slate-800 text-gray-400 hover:text-white border-slate-800"
              }`}
              title={isListening ? "Listening... Click to stop voice dictation" : "Dictate message via microphone"}
              id="assistant-voice-dictation-btn"
            >
              {isListening ? (
                <>
                  <MicOff className="h-5 w-5 text-white" />
                  <span className="absolute -top-7 left-1/2 transform -translate-x-1/2 bg-red-600 text-white text-[9px] font-mono font-black uppercase px-1.5 py-0.5 rounded whitespace-nowrap shadow">
                    REC
                  </span>
                </>
              ) : (
                <Mic className="h-5 w-5" />
              )}
            </button>

            {/* Send Button */}
            <button
              onClick={() => sendMessage()}
              disabled={isSubmitting || (!inputText.trim() && !activeAttachment)}
              className="p-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-xl shadow-md transition-all active:scale-95 cursor-pointer border border-transparent"
              id="ai-assistant-send-btn"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
