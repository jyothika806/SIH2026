# 2. Problem statement

## 2.1 The mobility problem

Indian cities run large private-vehicle and app-cab fleets that are **structurally under-occupied**. A four-seat cab often carries one rider. Bike taxis cannot pool. Autos sit between the two. The result:

- More vehicles on the same corridor than demand requires.
- Higher fare per passenger than a shared trip would need.
- More congestion, fuel, and emissions for the same origin–destination demand.
- Drivers with empty seats and no legal, consented way to fill them mid-trip.

## 2.2 The safety problem

Existing ride-hailing verification is **OTP theatre**:

1. Driver arrives.
2. Passenger reads a PIN from the app (or shares it over the phone).
3. Anyone in the seat of the car can start the trip.

That does not prove the operator is the **enrolled driver**. Photo-on-profile is not liveness. Device fingerprint on the driver’s phone only proves *someone who can unlock that phone* is present.

Meanwhile, harm is concentrated in:

- Night / poorly lit / isolated segments.
- Route deviation and unexpected stops.
- Unvetted co-passengers in informal sharing.
- Slow SOS with no live corridor context.

## 2.3 The matching problem

Naive “people nearby going the same way” is not a product:

- Straight-line distance ignores one-way streets, flyovers, and river crossings.
- Unbounded detours destroy trust.
- Simultaneous joiners race for the last seat.
- Fare split without a published model feels like a scam.
- Showing full name, exact age, gender, and live GPS of a co-passenger is a privacy incident waiting to happen.

## 2.4 Formal problem statement

**Design and operate a ride-hailing system that (a) matches passengers to vehicles and to each other using road-network overlap and capacity constraints, (b) never mutates an in-progress trip without occupant and driver consent, (c) unlocks trip start only after driver identity verification with liveness, and (d) continuously scores journey risk from route, time, telemetry, and verification state — without classifying people as dangerous from demographics.**

## 2.5 Constraints unique to this product (India / SIH)

- Payments: UPI-first, GST invoices, driver TDS — not Stripe-only thinking.
- Law: Digital Personal Data Protection Act, 2023; IT Act; possible state taxi aggregator rules; biometric is sensitive personal data.
- Maps: Google Maps has cost and ToS limits; OSRM + OSM is the default routing brain for matching; a commercial map may still be used for the consumer basemap.
- Connectivity: GPS jitter, 4G drops in underpasses, dual-SIM driver phones.
- Vehicles: Bike (1), Auto (3), Cab (4), Van (7–8) with different pooling legality and helmet / permit rules.

## 2.6 Out of scope for the core problem (still documented later)

- Intercity buses and trains.
- Fully autonomous vehicles.
- Using Aadhaar eKYC facial match without a licensed KYC service.
- Predicting criminality of a person.
