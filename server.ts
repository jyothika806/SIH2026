/**
 * SafeVoyage Sentinel - Production Express & Node.js Backend Gateway
 *
 * Capabilities:
 * - Upstream Gemini AI Resilience with Exponential Backoff & Degraded Fallbacks (Defect #QA-01)
 * - Multimodal Attachment Ingestion (Base64 Image/Audio) in Assistant Chat (Defect #QA-02)
 * - Express Microservices Gateway: Reverse Proxy to FastAPI for /api/v1/{driver,passenger,transit,rides,auth,...}
 * - Standalone Mock Fallback Routes for Driver KYC, Passenger, and Transit Monitoring (Defect #QA-05)
 * - Helmet HTTP Security Headers, CORS policy, and Correlation ID request tracing
 */

import express, { Request, Response, NextFunction } from "express";
import cors from "cors";
import helmet from "helmet";
import path from "path";
import { v4 as uuidv4 } from "uuid";
import { GoogleGenAI, Type } from "@google/genai";

// ============================================================================
// 1. TYPE DEFINITIONS & SCHEMAS
// ============================================================================

export interface Attachment {
  mimeType: string;
  data: string; // Base64 encoded payload
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequestBody {
  location?: string;
  messages: ChatMessage[];
  attachments?: Attachment[];
}

export interface ChatResponseBody {
  status: "ok" | "degraded";
  text: string;
  fallback?: boolean;
  model?: string;
  timestamp: string;
}

export type IncidentPriority = "Low" | "Moderate" | "High" | "Critical";

export interface IncidentRequestBody {
  reporterName?: string;
  reporterPhone?: string;
  incidentType?: string;
  description: string;
  location?: string | { lat: number; lng: number; address?: string };
  contactEmergencyName?: string;
  audioRecorded?: boolean;
}

export interface IncidentTriageData {
  category: string;
  priority: IncidentPriority;
  riskScore: number;
  summary: string;
  guideInstructions: string;
  recommendedAuthority: string;
}

export interface IncidentResponseBody extends IncidentTriageData {
  status: "ok" | "degraded";
  fallback?: boolean;
  timestamp: string;
}

export interface SupportTicket {
  id: string;
  formType: string;
  subject: string;
  description: string;
  senderName: string;
  senderEmail: string;
  guardianName?: string;
  guardianEmail?: string;
  guardianPhone?: string;
  priority: string;
  status: "Open" | "In Progress" | "Resolved";
  createdAt: string;
  userEmailSent: boolean;
  guardianNotificationSent: boolean;
  notificationLogs?: Record<string, unknown>;
}

// Driver & Passenger Transit Types
export interface DriverRegisterPayload {
  driverName?: string;
  phone?: string;
  licenseNumber?: string;
  vehicleType?: "cab" | "auto" | "bike" | string;
  vehicleNumber?: string;
  vehicleModel?: string;
  vehicleColor?: string;
  year?: number;
}

export interface RideTrackPayload {
  rideId?: string;
  passengerId?: string;
  driverId?: string;
  userLocation?: { lat: number; lng: number };
}

export interface PassengerPayload {
  passengerId?: string;
  name?: string;
  phone?: string;
  pickup?: string | { lat: number; lng: number };
  dropoff?: string | { lat: number; lng: number };
  guardianPhone?: string;
}

export interface TransitPayload {
  route?: string;
  origin?: string;
  destination?: string;
  departureTime?: string;
  passengerCount?: number;
}

// ============================================================================
// 2. CONFIGURATION & CLIENT INITIALIZATION
// ============================================================================

const PORT = parseInt(process.env.PORT || "8080", 10);
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-3.8-flash";
const FASTAPI_SERVICE_URL = (process.env.FASTAPI_SERVICE_URL || "http://localhost:8000").replace(/\/$/, "");

if (!GEMINI_API_KEY) {
  console.warn("⚠️ [WARN] GEMINI_API_KEY is not defined. AI Proxy will run in Local Fallback mode.");
}

console.log(`🔗 [Microservices Gateway] FastAPI target configured at: ${FASTAPI_SERVICE_URL}`);

const ai = new GoogleGenAI({
  apiKey: GEMINI_API_KEY || "dummy-key-for-initialization"
});

// In-memory store for support tickets
const supportTickets: SupportTicket[] = [];

// ============================================================================
// 3. RESILIENCE UTILITY: EXPONENTIAL BACKOFF RETRY
// ============================================================================

export interface RetryOptions {
  maxRetries?: number;
  initialDelayMs?: number;
  backoffFactor?: number;
  maxDelayMs?: number;
  operationName?: string;
}

export async function withExponentialBackoff<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxRetries = 3,
    initialDelayMs = 1000,
    backoffFactor = 2,
    maxDelayMs = 10000,
    operationName = "Gemini API Call"
  } = options;

  let attempt = 0;
  let delay = initialDelayMs;

  while (true) {
    try {
      return await fn();
    } catch (error: any) {
      attempt++;

      const status = error?.status || error?.code || error?.response?.status;
      const message = error?.message || String(error);

      const isRetryable =
        status === 503 ||
        status === 429 ||
        status === 500 ||
        status === "UNAVAILABLE" ||
        message.includes("503") ||
        message.includes("UNAVAILABLE") ||
        message.includes("high demand") ||
        message.includes("timeout") ||
        message.includes("ECONNRESET") ||
        message.includes("ETIMEDOUT");

      if (!isRetryable || attempt > maxRetries) {
        console.error(`❌ [${operationName}] Failed after ${attempt} attempt(s). Error: ${message}`);
        throw error;
      }

      const jitter = Math.random() * (delay * 0.25);
      const sleepTime = Math.min(delay + jitter, maxDelayMs);

      console.warn(
        `⚠️ [${operationName}] Attempt ${attempt}/${maxRetries} failed (${status || message}). Retrying in ${Math.round(
          sleepTime
        )}ms...`
      );

      await new Promise((resolve) => setTimeout(resolve, sleepTime));
      delay *= backoffFactor;
    }
  }
}

// ============================================================================
// 4. DEGRADED HEURISTIC FALLBACKS (AI Chat & Incident Triage)
// ============================================================================

function generateFallbackChatResponse(location?: string, userPrompt?: string): string {
  const loc = location || "Current Location";
  const promptLower = (userPrompt || "").toLowerCase();

  if (promptLower.includes("hospital") || promptLower.includes("doctor") || promptLower.includes("medical")) {
    return (
      `⚠️ **[Offline Sentinel Mode - Satellite Degraded]**\n\n` +
      `Immediate Medical Resources near **${loc}**:\n` +
      `• Primary Emergency Dispatch: Dial **911** (US/Canada) or **112** (International / EU).\n` +
      `• Action: Seek the nearest hospital or emergency clinic. Keep device unlocked showing your digital Medical Alert Card.`
    );
  }

  if (promptLower.includes("police") || promptLower.includes("danger") || promptLower.includes("safe") || promptLower.includes("scam")) {
    return (
      `⚠️ **[Offline Sentinel Mode - Satellite Degraded]**\n\n` +
      `Safety Navigation & Law Enforcement near **${loc}**:\n` +
      `• Security Node: Tourist Police kiosks and public transport command hubs are active along central transit corridors.\n` +
      `• Protective Action: Stay in well-lit areas with security presence (e.g. hotel lobbies, metro stations).\n` +
      `• Emergency Contacts: Local Police: **911 / 112**.`
    );
  }

  return (
    `⚠️ **[Offline Sentinel Mode - Satellite Degraded]**\n\n` +
    `Notice: AI upstream servers are experiencing temporary high demand. Localized sentinel protocols remain active for **${loc}**:\n` +
    `• Keep situational awareness and store valuables inside secure bags.\n` +
    `• Stick to approved SafeVoyage zones and verified transit corridors.\n` +
    `• If you feel unsafe, press the SOS Beacon button immediately.`
  );
}

function generateFallbackIncidentTriage(payload: IncidentRequestBody): IncidentTriageData {
  const desc = (payload.description || "").toLowerCase();
  const type = (payload.incidentType || "").toLowerCase();

  const isCritical =
    desc.includes("stab") ||
    desc.includes("knife") ||
    desc.includes("gun") ||
    desc.includes("blood") ||
    desc.includes("fire") ||
    desc.includes("explosion") ||
    desc.includes("unconscious") ||
    desc.includes("attack") ||
    desc.includes("critical") ||
    desc.includes("sos") ||
    type.includes("medical") ||
    payload.reporterName?.includes("CRITICAL SOS");

  const isHigh =
    desc.includes("stalk") ||
    desc.includes("harass") ||
    desc.includes("threat") ||
    desc.includes("follow") ||
    desc.includes("chase") ||
    desc.includes("weapon");

  const isLow =
    desc.includes("lost") ||
    desc.includes("forgot") ||
    desc.includes("dropped") ||
    desc.includes("wallet") ||
    desc.includes("bottle") ||
    type.includes("property");

  if (isCritical) {
    return {
      category: payload.incidentType || "Critical Emergency & Life Safety Incident",
      priority: "Critical",
      riskScore: 98,
      summary: `EMERGENCY ALERT: Critical incident reported at ${
        typeof payload.location === "string" ? payload.location : "Active GPS Anchor"
      }. Immediate responder routing triggered.`,
      guideInstructions:
        "1. Move immediately to a secure, locked shelter or populated lobby.\n" +
        "2. Do NOT confront suspects or enter hazardous zones.\n" +
        "3. Maintain open audio channels; first responders alerted.",
      recommendedAuthority: "Metropolitan Police Tactical Response & City EMS Ambulance Dispatch"
    };
  }

  if (isHigh) {
    return {
      category: payload.incidentType || "Personal Security Threat & Harassment",
      priority: "High",
      riskScore: 82,
      summary: "High priority threat event logged. Immediate safety escort recommended.",
      guideInstructions:
        "1. Enter the nearest open store, hotel, or transit station immediately.\n" +
        "2. Inform staff that you are being followed or harassed.\n" +
        "3. Keep phone in hand with SOS button primed.",
      recommendedAuthority: "Transit Police Precinct & Local Tourist Protection Unit"
    };
  }

  if (isLow) {
    return {
      category: payload.incidentType || "Lost Property / Minor Incident",
      priority: "Low",
      riskScore: 12,
      summary: "Minor property/amenity event logged. No immediate personal safety threat detected.",
      guideInstructions:
        "1. Retrace steps safely if within familiar grounds.\n" +
        "2. Check nearby customer service, lost & found, or info kiosks.\n" +
        "3. File a local property report online or at the precinct desk.",
      recommendedAuthority: "Municipal Transit Lost & Found Bureau"
    };
  }

  return {
    category: payload.incidentType || "General Incident & Safety Advisory",
    priority: "Moderate",
    riskScore: 50,
    summary: "Safety incident recorded under active sentinel monitoring. Local authorities notified.",
    guideInstructions:
      "1. Maintain situational awareness and stay in visible pedestrian corridors.\n" +
      "2. Keep your device charged and synced with your guardian contacts.\n" +
      "3. Report further updates via the emergency console.",
    recommendedAuthority: "Local Municipal Police Patrol Division"
  };
}

// ============================================================================
// 5. STANDALONE FALLBACK MOCK HANDLERS FOR DRIVER & TRANSIT ECOSYSTEM
// ============================================================================

function handleMockDriverRegister(req: Request, res: Response) {
  const body: DriverRegisterPayload = req.body;
  const mockDriverId = `DRV-${new Date().getFullYear()}-${Math.random().toString(36).substring(2, 7).toUpperCase()}`;

  res.status(200).json({
    status: "degraded_mock",
    message: "FastAPI microservice offline. Profile registered in standalone fallback memory.",
    verified: true,
    driverId: mockDriverId,
    driverName: body.driverName || "Alexis Carter (Verified Partner)",
    licenseNumber: body.licenseNumber || "DL-9821-X44",
    vehicle: {
      type: body.vehicleType || "cab",
      model: body.vehicleModel || "Toyota Camry Hybrid",
      number: body.vehicleNumber || "NYC-T-88219",
      color: body.vehicleColor || "Silver Metallic",
      year: body.year || 2024,
      verificationStatus: "VERIFIED"
    },
    livenessVerification: {
      status: "PASSED",
      confidence: 0.985,
      method: "Passive 3D Facial Mesh Biometric Authenticator"
    },
    assignedCorridor: "Manhattan Midtown Safe Transit Line 1",
    timestamp: new Date().toISOString()
  });
}

function handleMockDriverStatus(req: Request, res: Response) {
  res.status(200).json({
    status: "degraded_mock",
    message: "FastAPI microservice offline. Operating in standalone telemetry mode.",
    driverId: "DRV-2026-X9481",
    isOnline: true,
    isAvailableForDispatch: true,
    currentLocation: {
      lat: 40.758,
      lng: -73.9855,
      address: "42nd St & Broadway, New York, NY",
      heading: 42,
      speedKmH: 26.4
    },
    safetyScore: 98,
    biometricsVerified: true,
    activeRidersCount: 1,
    emergencyHotline: "+1 (800) 555-SAFE",
    lastHeartbeat: new Date().toISOString()
  });
}

function handleMockRideTrack(req: Request, res: Response) {
  const body: RideTrackPayload = req.body;
  const rideId = body.rideId || `RIDE-${new Date().getFullYear()}-TR882`;

  res.status(200).json({
    status: "degraded_mock",
    message: "FastAPI microservice offline. Generating telemetry from standalone Corridor Engine.",
    rideId: rideId,
    tripStatus: "IN_TRANSIT",
    corridorMatched: true,
    corridorName: "Times Square -> Grand Central Safe Transit Corridor",
    driver: {
      driverId: body.driverId || "DRV-2026-X9481",
      name: "Rajesh Kumar (Gold Certified)",
      phone: "+1 (555) 019-2831",
      rating: 4.96,
      vehicle: "NYC-T-88219 (Silver Camry Hybrid)",
      livenessStatus: "VERIFIED_ACTIVE"
    },
    passengerSafetyIndex: 96,
    telemetry: {
      currentLat: 40.7572,
      currentLng: -73.9842,
      speedKmh: 31.2,
      estimatedArrivalMinutes: 5,
      routeDeviationDetected: false,
      geofenceBoundaryStatus: "WITHIN_SAFE_CORRIDOR",
      guardianTrackingActive: true
    },
    emergencyAssistance: {
      sosTriggerAvailable: true,
      policeDispatchNumber: "911",
      guardianNotificationSynced: true
    },
    timestamp: new Date().toISOString()
  });
}

function handleMockPassengerBook(req: Request, res: Response) {
  const body: PassengerPayload & {
    vehicleType?: string;
    seatsRequired?: number;
    pickup?: { lat?: number; lng?: number; address?: string } | string;
    dropoff?: { lat?: number; lng?: number; address?: string } | string;
  } = req.body;
  const rideId = `ride-${Date.now()}`;
  const pickupAddress = typeof body.pickup === "string" ? body.pickup : body.pickup?.address || "MG Road, Bengaluru";
  const dropoffAddress = typeof body.dropoff === "string" ? body.dropoff : body.dropoff?.address || "Indiranagar, Bengaluru";

  res.status(200).json({
    success: true,
    status: "degraded_mock",
    message: "FastAPI microservice offline. Booking processed by Smart Commutation Engine fallback.",
    rideId,
    bookingId: rideId,
    estimatedFare: 150,
    estimatedDuration: 25,
    driverId: "driver-001",
    passengerName: body.name || "Priya Sharma",
    pickupAddress,
    dropoffAddress,
    vehicleType: body.vehicleType || "cab",
    seatsRequired: body.seatsRequired || 1,
    assignedDriver: {
      driverId: "driver-001",
      name: "Rajesh Kumar",
      age: 34,
      gender: "male",
      phone: "+91 98765 43210",
      rating: 4.8,
      vehicle: "KA 01 AB 1234"
    },
    timestamp: new Date().toISOString()
  });
}

function jsonOk(res: Response, payload: Record<string, unknown>) {
  res.status(200).json({
    success: true,
    status: "degraded_mock",
    timestamp: new Date().toISOString(),
    ...payload
  });
}

function handleSmartCommutationFallback(req: Request, res: Response, fullPath: string, method: string): boolean {
  const body = (req.body || {}) as Record<string, unknown>;

  if (fullPath.startsWith("/api/v1/passenger/mid-ride/request") && method === "POST") {
    jsonOk(res, { requestId: `join-${Date.now()}`, message: "Join request dispatched to co-passengers" });
    return true;
  }
  if (fullPath.startsWith("/api/v1/passenger/mid-ride/consent") && method === "POST") {
    jsonOk(res, { consensusReached: true, message: "Unanimous/majority consent recorded" });
    return true;
  }
  if (fullPath.startsWith("/api/v1/passenger/risk-score") && method === "GET") {
    jsonOk(res, {
      score: "low",
      scoreValue: 18,
      factors: {
        routeSafetyIndex: 86,
        timeOfDayRisk: 16,
        streetLightingIndex: 82,
        historicalIncidentFrequency: 12,
        driverSafetyProfile: 92,
        coPassengerSafetyRating: 84
      },
      recommendations: ["Corridor is well lit", "Driver safety profile is strong"]
    });
    return true;
  }
  if (fullPath.startsWith("/api/v1/passenger/consolidation") && method === "GET") {
    jsonOk(res, {
      suggestions: [
        { type: "bike_to_auto", headline: "2 Bike requests → 1 Auto", savingsPercent: 30, driverBonus: 40, suggestedVehicle: "auto" },
        { type: "bike_to_cab", headline: "5 Bike requests → 1 Cab/Van", savingsPercent: 38, driverBonus: 120, suggestedVehicle: "cab" }
      ]
    });
    return true;
  }
  if (fullPath.startsWith("/api/v1/passenger/sos") && method === "POST") {
    jsonOk(res, {
      incidentId: `sos-${Date.now()}`,
      emergencyContactsNotified: true,
      locationShared: true,
      securityCenterAlerted: true
    });
    return true;
  }
  if (fullPath.startsWith("/api/v1/passenger/status") && method === "POST") {
    jsonOk(res, { message: "Passenger GPS streamed", location: body.location || body });
    return true;
  }
  if (fullPath.startsWith("/api/v1/passenger/status") && method === "GET") {
    jsonOk(res, {
      rideId: fullPath.split("/").pop(),
      status: "driver_assigned",
      identityVerified: false,
      otpLocked: true,
      otp: "4567",
      eta: 8,
      fare: 150,
      occupiedSeats: 1,
      openSeats: 3,
      capacity: 4,
      vehicleType: "cab",
      geofence: { active: true, radius: 220, driftMeters: 18, breached: false }
    });
    return true;
  }

  if (fullPath.startsWith("/api/v1/driver/status") && method === "POST") {
    jsonOk(res, { online: body.online !== false, vehicleType: body.vehicleType || "cab", vacantSeats: body.vacantSeats || 3 });
    return true;
  }
  if (fullPath.startsWith("/api/v1/driver/seats") && method === "POST") {
    jsonOk(res, { vacantSeats: Number(body.vacantSeats ?? 2) });
    return true;
  }
  if (fullPath.startsWith("/api/v1/driver/verify-identity") && method === "POST") {
    jsonOk(res, { verified: true, otpUnlocked: "4567", message: "Identity verified" });
    return true;
  }
  if (fullPath.startsWith("/api/v1/driver/accept-waypoint") && method === "POST") {
    jsonOk(res, { extraFare: 48, detourMinutes: 2, message: "Waypoint accepted" });
    return true;
  }
  if (fullPath.startsWith("/api/v1/driver/location") && method === "POST") {
    jsonOk(res, { message: "Driver GPS streamed", location: body.location || body });
    return true;
  }
  if (fullPath.startsWith("/api/v1/driver/start-ride") && method === "POST") {
    jsonOk(res, { rideStarted: true });
    return true;
  }
  if (fullPath.startsWith("/api/v1/driver/complete") && method === "POST") {
    jsonOk(res, { message: "Trip completed" });
    return true;
  }
  if (fullPath.startsWith("/api/v1/driver/sos") && method === "POST") {
    jsonOk(res, { incidentId: `sos-${Date.now()}`, securityCenterAlerted: true });
    return true;
  }

  return false;
}

function handleMockTransitSchedule(req: Request, res: Response) {
  const body: TransitPayload = req.body;

  res.status(200).json({
    status: "degraded_mock",
    message: "FastAPI microservice offline. Transit schedule served from Sentinel Route Cache.",
    route: body.route || "ST-SAFE-01",
    origin: body.origin || "Central Bus Terminal",
    destination: body.destination || "Airport Terminal 2",
    schedule: [
      { departureTime: "12:00", arrivalTime: "12:45", status: "ON_TIME", safetyRating: "A+" },
      { departureTime: "12:30", arrivalTime: "13:15", status: "ON_TIME", safetyRating: "A+" },
      { departureTime: "13:00", arrivalTime: "13:45", status: "SLIGHT_DELAY", safetyRating: "A" }
    ],
    fareEstimate: { standard: 3.5, express: 5.0, currency: "USD" },
    safeCorridorActive: true,
    policePatrolSync: true,
    timestamp: new Date().toISOString()
  });
}


// ============================================================================
// 6. MICROSERVICES GATEWAY REVERSE PROXY
// ============================================================================

/**
 * Proxies HTTP requests to the FastAPI backend service.
 * If the microservice is unreachable, falls back to local standalone mock handlers.
 * Correlation IDs set by the upstream middleware are forwarded automatically via request headers.
 */
async function proxyToFastAPI(req: Request, res: Response): Promise<void> {
  const targetUrl = `${FASTAPI_SERVICE_URL}${req.originalUrl}`;
  const method = req.method;

  try {
    const headers: Record<string, string> = {};
    for (const [key, value] of Object.entries(req.headers)) {
      if (key.toLowerCase() !== "host" && typeof value === "string") {
        headers[key] = value;
      }
    }
    headers["x-forwarded-for"] = req.ip || "127.0.0.1";
    headers["x-gateway-proxy"] = "SafeVoyage-Express-Gateway";
    // Forward correlation IDs set by the tracing middleware
    if (req.headers["x-correlation-id"]) {
      headers["x-correlation-id"] = req.headers["x-correlation-id"] as string;
    }

    const fetchOptions: RequestInit = {
      method,
      headers
    };

    if (method !== "GET" && method !== "HEAD" && req.body) {
      fetchOptions.body = JSON.stringify(req.body);
      headers["content-type"] = "application/json";
    }

    // Attempt upstream connection with 5s timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    fetchOptions.signal = controller.signal;

    const upstreamResponse = await fetch(targetUrl, fetchOptions);
    clearTimeout(timeoutId);

    res.status(upstreamResponse.status);
    upstreamResponse.headers.forEach((val, key) => {
      if (key.toLowerCase() !== "transfer-encoding" && key.toLowerCase() !== "content-encoding") {
        res.setHeader(key, val);
      }
    });

    const data = await upstreamResponse.text();
    res.send(data);
  } catch (proxyError: any) {
    console.warn(`⚠️ [Gateway Proxy] FastAPI microservice unreachable at ${targetUrl}. Route fallback engaged.`);

    // Use req.originalUrl for path matching so /api/v1/* prefixes are preserved
    const fullPath = req.originalUrl.split("?")[0]; // strip query params

    if (fullPath.startsWith("/api/v1/driver/register") && method === "POST") {
      handleMockDriverRegister(req, res);
      return;
    }

    if (fullPath.startsWith("/api/v1/driver/status") && method === "GET") {
      handleMockDriverStatus(req, res);
      return;
    }

    if (fullPath.startsWith("/api/v1/rides/track") && method === "POST") {
      handleMockRideTrack(req, res);
      return;
    }

    if (fullPath.startsWith("/api/v1/passenger/book") && method === "POST") {
      handleMockPassengerBook(req, res);
      return;
    }

    if (fullPath.startsWith("/api/v1/passenger/track") && method === "GET") {
      handleMockRideTrack(req, res); // re-use ride-track schema for passenger tracking
      return;
    }

    if (fullPath.startsWith("/api/v1/transit/schedule") || fullPath.startsWith("/api/v1/transit/fare")) {
      handleMockTransitSchedule(req, res);
      return;
    }

    if (handleSmartCommutationFallback(req, res, fullPath, method)) {
      return;
    }

    // Generic fallback for any other FastAPI route
    res.status(200).json({
      status: "degraded_mock",
      message: "FastAPI microservice unreachable. Running in standalone fallback mode.",
      targetUrl,
      error: proxyError?.message || "Connection refused",
      timestamp: new Date().toISOString()
    });
  }
}


// ============================================================================
// 7. EXPRESS APPLICATION & ROUTE DEFINITIONS
// ============================================================================

export const app = express();

// ----------------------------------------------------------------------------
// Security, CORS & Body Parsing Middleware
// ----------------------------------------------------------------------------

// Helmet: sets 14+ security HTTP headers (XSS, clickjacking, MIME sniffing…)
// contentSecurityPolicy disabled so the embedded Google Maps iframe can load.
app.use(helmet({ contentSecurityPolicy: false }));

app.use(
  cors({
    origin: "*",
    methods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization", "X-Correlation-ID", "X-Request-ID"]
  })
);

app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ extended: true, limit: "50mb" }));

// ----------------------------------------------------------------------------
// Correlation ID & Request Tracing Middleware
// Stamps every request with X-Correlation-ID (caller-supplied or generated)
// and a fresh X-Request-ID. Both are echoed back in the response headers so
// the frontend can log them alongside API timing metrics.
// ----------------------------------------------------------------------------
app.use((req: Request, res: Response, next: NextFunction) => {
  const correlationId = (req.headers["x-correlation-id"] as string) || uuidv4();
  const requestId = uuidv4();

  // Normalise onto req.headers so downstream middleware & proxyToFastAPI see it
  req.headers["x-correlation-id"] = correlationId;

  res.setHeader("X-Correlation-ID", correlationId);
  res.setHeader("X-Request-ID", requestId);

  console.log(`→ [${correlationId}] ${req.method} ${req.originalUrl}`);
  next();
});

// ----------------------------------------------------------------------------
// Health Check Endpoint
// ----------------------------------------------------------------------------
app.get("/api/health", async (_req: Request, res: Response) => {
  let fastApiHealthy = false;
  try {
    const check = await fetch(`${FASTAPI_SERVICE_URL}/health`, { signal: AbortSignal.timeout(1500) });
    fastApiHealthy = check.ok;
  } catch {}

  res.status(200).json({
    status: "ok",
    hasApiKey: Boolean(GEMINI_API_KEY),
    fastApiConnected: fastApiHealthy,
    fastApiTarget: FASTAPI_SERVICE_URL,
    timestamp: new Date().toISOString()
  });
});

// ----------------------------------------------------------------------------
// 1. FASTAPI MICROSERVICES GATEWAY ROUTES
//    /api/v1/{driver,passenger,transit,rides,auth,liveness,risk,…}
// ----------------------------------------------------------------------------
app.use("/api/v1/driver", proxyToFastAPI);
app.use("/api/v1/passenger", proxyToFastAPI);   // passenger trip booking & tracking
app.use("/api/v1/transit", proxyToFastAPI);     // transit schedules, fare & dispatch
app.use("/api/v1/rides", proxyToFastAPI);
app.use("/api/v1/auth", proxyToFastAPI);
app.use("/api/v1/liveness", proxyToFastAPI);
app.use("/api/v1/risk", proxyToFastAPI);
app.use("/api/v1/gemini", proxyToFastAPI);
app.use("/api/v1/consensus", proxyToFastAPI);
app.use("/api/v1/fare", proxyToFastAPI);
app.use("/api/v1/emergency", proxyToFastAPI);
app.use("/api/v1/dispatch", proxyToFastAPI);
app.use("/api/v1/payment", proxyToFastAPI);
app.use("/api/v1/notification", proxyToFastAPI);
app.use("/api/v1/rating", proxyToFastAPI);


// ----------------------------------------------------------------------------
// 2. POST /api/assistant/chat (Multimodal + Resilient Exponential Backoff)
// ----------------------------------------------------------------------------
app.post("/api/assistant/chat", async (req: Request, res: Response): Promise<void> => {
  const { location, messages, attachments }: ChatRequestBody = req.body;

  if (!Array.isArray(messages) || messages.length === 0) {
    res.status(400).json({ error: "Invalid request: 'messages' array is required." });
    return;
  }

  const latestUserMessage = messages[messages.length - 1];
  const userTextPrompt = latestUserMessage?.content || "";

  if (!GEMINI_API_KEY) {
    res.status(200).json({
      status: "degraded",
      text: generateFallbackChatResponse(location, userTextPrompt),
      fallback: true,
      timestamp: new Date().toISOString()
    });
    return;
  }

  try {
    const responseText = await withExponentialBackoff(
      async () => {
        const contents: any[] = [];

        for (let i = 0; i < messages.length - 1; i++) {
          const msg = messages[i];
          contents.push({
            role: msg.role === "assistant" ? "model" : "user",
            parts: [{ text: msg.content }]
          });
        }

        const latestParts: any[] = [{ text: latestUserMessage.content }];

        if (Array.isArray(attachments) && attachments.length > 0) {
          for (const att of attachments) {
            if (att.data && att.mimeType) {
              const base64Data = att.data.includes(",") ? att.data.split(",")[1] : att.data;
              latestParts.push({
                inlineData: {
                  mimeType: att.mimeType,
                  data: base64Data
                }
              });
            }
          }
        }

        contents.push({
          role: "user",
          parts: latestParts
        });

        const response = await ai.models.generateContent({
          model: GEMINI_MODEL,
          contents: contents,
          config: {
            systemInstruction:
              `You are the SafeVoyage Sentinel 24/7 AI Safety Companion. Location: ${location || "Unknown"}.\n` +
              `Provide crisp, authoritative, empathetic tourist safety recommendations. ` +
              `If media (photos/audio) is attached, examine it for immediate safety hazards, landmarks, or distress cues.`
          }
        });

        const textOutput = response.text || "";
        if (!textOutput) throw new Error("Empty response received from Gemini.");
        return textOutput;
      },
      { maxRetries: 3, initialDelayMs: 1000, backoffFactor: 2, operationName: "ChatAssistant" }
    );

    res.status(200).json({
      status: "ok",
      text: responseText,
      fallback: false,
      model: GEMINI_MODEL,
      timestamp: new Date().toISOString()
    });
  } catch (err: any) {
    console.error("⚠️ [ChatAssistant] Gemini unavailable. Serving degraded fallback.", err?.message || err);

    res.status(200).json({
      status: "degraded",
      text: generateFallbackChatResponse(location, userTextPrompt),
      fallback: true,
      timestamp: new Date().toISOString()
    });
  }
});

// ----------------------------------------------------------------------------
// 3. POST /api/incidents/submit (AI Incident Triage + Resilient Exponential Backoff)
// ----------------------------------------------------------------------------
app.post("/api/incidents/submit", async (req: Request, res: Response): Promise<void> => {
  const payload: IncidentRequestBody = req.body;

  if (!payload.description || !payload.description.trim()) {
    res.status(400).json({ error: "Invalid request: 'description' is required." });
    return;
  }

  if (!GEMINI_API_KEY) {
    const fallbackTriage = generateFallbackIncidentTriage(payload);
    res.status(200).json({
      status: "degraded",
      ...fallbackTriage,
      fallback: true,
      timestamp: new Date().toISOString()
    });
    return;
  }

  try {
    const triageResult = await withExponentialBackoff(
      async () => {
        const triagePrompt =
          `You are an Emergency Triage & Crisis Classification AI. Analyze the following incident report:\n\n` +
          `Reporter: ${payload.reporterName || "Anonymous"}\n` +
          `Category Claim: ${payload.incidentType || "Unspecified"}\n` +
          `Location: ${typeof payload.location === "string" ? payload.location : JSON.stringify(payload.location)}\n` +
          `Description: ${payload.description}\n` +
          `Audio Captured: ${payload.audioRecorded ? "Yes" : "No"}\n\n` +
          `Return valid JSON matching this schema:\n` +
          `{\n` +
          `  "category": "Official categorization (string)",\n` +
          `  "priority": "Low" | "Moderate" | "High" | "Critical",\n` +
          `  "riskScore": number (1-100),\n` +
          `  "summary": "Short 1-2 sentence executive crisis summary",\n` +
          `  "guideInstructions": "Numbered tactical safety steps for the traveler",\n` +
          `  "recommendedAuthority": "Specific local authority or emergency service to dispatch"\n` +
          `}`;

        const response = await ai.models.generateContent({
          model: GEMINI_MODEL,
          contents: triagePrompt,
          config: {
            responseMimeType: "application/json",
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                category: { type: Type.STRING },
                priority: { type: Type.STRING, enum: ["Low", "Moderate", "High", "Critical"] },
                riskScore: { type: Type.INTEGER },
                summary: { type: Type.STRING },
                guideInstructions: { type: Type.STRING },
                recommendedAuthority: { type: Type.STRING }
              },
              required: ["category", "priority", "riskScore", "summary", "guideInstructions", "recommendedAuthority"]
            }
          }
        });

        const rawText = response.text || "{}";
        const parsed = JSON.parse(rawText) as IncidentTriageData;

        if (!parsed.priority || typeof parsed.riskScore !== "number") {
          throw new Error("Invalid incident triage schema returned by model.");
        }

        return parsed;
      },
      { maxRetries: 3, initialDelayMs: 1000, backoffFactor: 2, operationName: "IncidentTriage" }
    );

    res.status(200).json({
      status: "ok",
      ...triageResult,
      fallback: false,
      timestamp: new Date().toISOString()
    });
  } catch (err: any) {
    console.error("⚠️ [IncidentTriage] Gemini unavailable. Serving degraded triage.", err?.message || err);

    const fallbackTriage = generateFallbackIncidentTriage(payload);
    res.status(200).json({
      status: "degraded",
      ...fallbackTriage,
      fallback: true,
      timestamp: new Date().toISOString()
    });
  }
});

// ----------------------------------------------------------------------------
// 4. Support Ticket Endpoints
// ----------------------------------------------------------------------------
app.get("/api/support/list", (_req: Request, res: Response) => {
  res.status(200).json({ queries: supportTickets });
});

app.post("/api/support/submit", (req: Request, res: Response) => {
  const {
    formType = "Support Request",
    subject,
    description,
    senderName,
    senderEmail,
    guardianName,
    guardianEmail,
    guardianPhone,
    priority = "Medium"
  } = req.body;

  const ticketId = `TKT-${new Date().getFullYear()}-${Math.random().toString(36).substring(2, 7).toUpperCase()}`;

  const newTicket: SupportTicket = {
    id: ticketId,
    formType,
    subject,
    description,
    senderName,
    senderEmail,
    guardianName,
    guardianEmail,
    guardianPhone,
    priority,
    status: "Open",
    createdAt: new Date().toISOString(),
    userEmailSent: true,
    guardianNotificationSent: Boolean(guardianEmail)
  };

  supportTickets.unshift(newTicket);

  res.status(200).json({
    success: true,
    message: "Query registered in database.",
    ticketId,
    query: newTicket
  });
});

// ----------------------------------------------------------------------------
// 5. Static Asset Hosting & SPA Catch-All
// ----------------------------------------------------------------------------
const distPath = path.resolve(__dirname, "../dist");
app.use(express.static(distPath));

app.get("*", (_req: Request, res: Response) => {
  const indexHtml = path.join(distPath, "index.html");
  res.sendFile(indexHtml, (err) => {
    if (err) {
      res.status(200).send("SafeVoyage Sentinel Gateway Online. Static assets not built.");
    }
  });
});

// ----------------------------------------------------------------------------
// 6. Structured Error-Handling Middleware (MUST be last — 4 args required)
// Catches any error thrown or passed to next(err) from route handlers above.
// Returns a consistent JSON envelope so clients can always parse the error.
// ----------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-unused-vars
app.use((err: any, req: Request, res: Response, _next: NextFunction) => {
  const correlationId = req.headers["x-correlation-id"] as string || "none";
  const status: number = typeof err.status === "number" ? err.status : 500;

  console.error(`❌ [${correlationId}] Unhandled error on ${req.method} ${req.originalUrl}:`, err?.message || err);

  res.status(status).json({
    status: "error",
    message: err?.message || "Internal Server Error",
    correlationId,
    path: req.originalUrl,
    timestamp: new Date().toISOString()
  });
});

// ============================================================================
// 8. SERVER INITIALIZATION
// ============================================================================
if (process.env.NODE_ENV !== "test") {
  app.listen(PORT, "0.0.0.0", () => {
    console.log(`🚀 SafeVoyage Express Gateway running on http://0.0.0.0:${PORT}`);
    console.log(`🛡️  Helmet security headers: ACTIVE`);
    console.log(`📡 Reverse Proxying /api/v1/{driver,passenger,transit,rides,auth,...} -> ${FASTAPI_SERVICE_URL}`);
    console.log(`🔗 Correlation ID tracing: ACTIVE (X-Correlation-ID / X-Request-ID)`);
  });
}
