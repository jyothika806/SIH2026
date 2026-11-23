# Driving licence verification and vehicle-class policy

## Verification state and evidence

Licence state is explicitly `pending`, `approved`, `rejected`, or `unavailable`. Only an approved, unexpired record with complete evidence may contribute to dispatch eligibility. A manual Parivahan review records source (`parivahan`), verification reference, timestamp, reviewer, outcome, vehicle classes, transport-endorsement declaration, and expiry. Retain the review under the applicable privacy policy. A screenshot hash may support chain-of-custody, but it does not establish that a licence is valid.

DigiLocker remains disabled until authorized integration credentials and permissions are available. No identity or licence verification may be simulated when external access is unavailable.

## Legal basis and unresolved class mappings

The Motor Vehicles Act, 1988 provides the statutory framework for requiring an effective driving licence and authorizing classes of motor vehicles. The Central Motor Vehicles Rules, 1989 and applicable amendments/regional rules govern implementation and endorsements. Consult the current official text and the relevant transport authority before enabling a category. The official sources are [India Code](https://www.indiacode.nic.in/) and [MoRTH](https://morth.nic.in/). Their legal text could not be independently retrieved in this implementation environment, so this document does not claim that any code mapping below is legally approved.

| App category | Configured candidate licence classes | Commercial transport endorsement policy | Release status |
|---|---|---|---|
| Bike | `MCWG` | Required by current application policy; applicability to the particular commercial service and vehicle must be legally reviewed | Blocked: mapping unreviewed |
| Auto | `3W-T`, `LMV-3W`, `e-rickshaw` | Required by current application policy; confirm vehicle subtype, permit, class, and endorsement with the relevant authority | Blocked: mapping unreviewed |
| Cab | `LMV-TR`, `LMV` | Required by current application policy; confirm vehicle weight/use, class, transport authorization, and any endorsement with the relevant authority | Blocked: mapping unreviewed |

The codes above are configuration candidates, not an assertion that the classes are equivalent or sufficient for a commercial passenger service. Confirm the exact vehicle registration category, gross vehicle weight, licence class, transport endorsement, permit, and state-specific rules for each product category. Where the source or interpretation is uncertain, do not approve the mapping.

Approved records must be re-reviewed through the authorized source at least every `LICENCE_REVALIDATION_DAYS` days (default 180); older evidence blocks dispatch until a new timestamped review is recorded. Revalidation does not infer a licence's current validity from a saved screenshot or hash.

`LICENCE_CLASS_MAP_REVIEWED` defaults to false. Keep it false until a qualified legal/compliance reviewer records the official sources, jurisdiction, category-specific rule, mapping, reviewer, and review date. The configurable mapping and endorsement policy must then be updated together. Any missing or unreviewed mapping blocks dispatch.
