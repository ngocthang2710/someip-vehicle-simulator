# 📡 SOME/IP Service Specification

## Service Registry

| Service Name        | Service ID | Instance ID | Protocol |
|---------------------|-----------|-------------|----------|
| VehicleSpeedService | 0x1234    | 0x0001      | UDP      |
| EngineRPMService    | 0x1235    | 0x0001      | UDP      |
| ThrottleService     | 0x1236    | 0x0001      | TCP      |

## Events (Server → Client)

| Event Name     | Event ID | Service ID | Payload          | Interval |
|----------------|----------|-----------|------------------|----------|
| VehicleSpeed   | 0x8001   | 0x1234    | float32 (km/h)   | 100ms    |
| EngineRPM      | 0x8002   | 0x1235    | uint16 (rpm)     | 100ms    |
| FuelLevel      | 0x8003   | 0x1234    | float32 (%)      | 1000ms   |
| GearPosition   | 0x8004   | 0x1234    | uint8 (0-8)      | 200ms    |
| BrakeStatus    | 0x8005   | 0x1234    | bool             | 50ms     |

## Methods (Client → Server)

| Method Name      | Method ID | Service ID | Request Payload     | Response Payload |
|------------------|-----------|-----------|---------------------|------------------|
| SetThrottle      | 0x0001    | 0x1236    | float32 (0.0-1.0)  | bool (success)   |
| SetBrake         | 0x0002    | 0x1236    | float32 (0.0-1.0)  | bool (success)   |
| GetVehicleInfo   | 0x0003    | 0x1234    | -                   | VehicleInfoStruct|
| EmergencyStop    | 0x0004    | 0x1236    | -                   | bool             |

## Payload Formats

### VehicleInfoStruct (GetVehicleInfo response)
```
Offset  Size  Type     Field
0       4     float32  speed_kmh
4       2     uint16   engine_rpm
6       1     uint8    gear
7       4     float32  fuel_percent
11      4     float32  throttle_position
15      1     uint8    brake_active
16      4     float32  coolant_temp_celsius
```

## Ports
- SOME/IP SD (Service Discovery): UDP 30490
- SOME/IP Unicast: UDP 30501 (server), UDP 30500 (client)
- SOME/IP TCP: TCP 30502 (ThrottleService)

## vsomeip Event Group

| Eventgroup ID | Events included              |
|---------------|------------------------------|
| 0x0001        | VehicleSpeed, EngineRPM      |
| 0x0002        | FuelLevel, GearPosition      |
| 0x0003        | BrakeStatus                  |
