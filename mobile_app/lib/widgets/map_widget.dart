import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

class MapWidget extends StatelessWidget {
  final LatLng pickupLocation;
  final LatLng dropoffLocation;
  final List<LatLng>? routePolyline;
  final List<LatLng>? driverLocations;
  final bool showRoute;
  final bool showDriverMarkers;

  const MapWidget({
    super.key,
    required this.pickupLocation,
    required this.dropoffLocation,
    this.routePolyline,
    this.driverLocations,
    this.showRoute = true,
    this.showDriverMarkers = true,
  });

  @override
  Widget build(BuildContext context) {
    // Calculate bounds to fit all markers
    final bounds = LatLngBounds();
    bounds.extend(pickupLocation);
    bounds.extend(dropoffLocation);
    
    if (driverLocations != null) {
      for (final location in driverLocations!) {
        bounds.extend(location);
      }
    }

    return FlutterMap(
      options: MapOptions(
        initialCenter: LatLng(
          (pickupLocation.latitude + dropoffLocation.latitude) / 2,
          (pickupLocation.longitude + dropoffLocation.longitude) / 2,
        ),
        initialZoom: 13.0,
        bounds: bounds,
        boundsOptions: const FitBoundsOptions(
          padding: EdgeInsets.all(50),
        ),
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.optimalride.app',
        ),
        if (showRoute && routePolyline != null && routePolyline!.isNotEmpty)
          PolylineLayer(
            polylines: [
              Polyline(
                points: routePolyline!,
                strokeWidth: 4.0,
                color: Colors.blue,
              ),
            ],
          ),
        MarkerLayer(
          markers: [
            // Pickup marker (green)
            Marker(
              point: pickupLocation,
              width: 40,
              height: 40,
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.green,
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 2),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 4,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.location_on,
                  color: Colors.white,
                  size: 24,
                ),
              ),
            ),
            // Dropoff marker (red)
            Marker(
              point: dropoffLocation,
              width: 40,
              height: 40,
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.red,
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 2),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 4,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.location_on,
                  color: Colors.white,
                  size: 24,
                ),
              ),
            ),
            // Driver markers (blue)
            if (showDriverMarkers && driverLocations != null)
              ...driverLocations!.map(
                (location) => Marker(
                  point: location,
                  width: 36,
                  height: 36,
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.blue,
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.3),
                          blurRadius: 4,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.directions_car,
                      color: Colors.white,
                      size: 20,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}
