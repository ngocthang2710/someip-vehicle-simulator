#pragma once

#include <vsomeip/vsomeip.hpp>
#include <thread>
#include <atomic>
#include <mutex>
#include <memory>
#include <functional>
#include <cstdint>

// ─── Service / Instance IDs ───────────────────────────────────────────────────
static constexpr vsomeip::service_t VEHICLE_SERVICE_ID   = 0x1234;
static constexpr vsomeip::service_t ENGINE_SERVICE_ID    = 0x1235;
static constexpr vsomeip::service_t THROTTLE_SERVICE_ID  = 0x1236;
static constexpr vsomeip::instance_t INSTANCE_ID         = 0x0001;

// ─── Event IDs ────────────────────────────────────────────────────────────────
static constexpr vsomeip::event_t EVENT_SPEED        = 0x8001;
static constexpr vsomeip::event_t EVENT_RPM          = 0x8002;
static constexpr vsomeip::event_t EVENT_FUEL         = 0x8003;
static constexpr vsomeip::event_t EVENT_GEAR         = 0x8004;
static constexpr vsomeip::event_t EVENT_BRAKE        = 0x8005;

// ─── Method IDs ───────────────────────────────────────────────────────────────
static constexpr vsomeip::method_t METHOD_SET_THROTTLE  = 0x0001;
static constexpr vsomeip::method_t METHOD_SET_BRAKE     = 0x0002;
static constexpr vsomeip::method_t METHOD_GET_INFO      = 0x0003;
static constexpr vsomeip::method_t METHOD_EMERG_STOP    = 0x0004;

// ─── Eventgroup IDs ──────────────────────────────────────────────────────────
static constexpr vsomeip::eventgroup_t EG_SPEED_RPM  = 0x0001;
static constexpr vsomeip::eventgroup_t EG_FUEL_GEAR  = 0x0002;
static constexpr vsomeip::eventgroup_t EG_BRAKE      = 0x0003;

// ─── Vehicle State ────────────────────────────────────────────────────────────
struct VehicleState {
    float    speed_kmh       = 0.0f;
    uint16_t engine_rpm      = 800;
    uint8_t  gear            = 0;       // 0=P, 1=R, 2=N, 3-8=D1-D5
    float    fuel_percent    = 100.0f;
    float    throttle_pos    = 0.0f;    // 0.0 ~ 1.0
    bool     brake_active    = false;
    float    coolant_temp    = 25.0f;   // Celsius
};

// ─── Callback type ────────────────────────────────────────────────────────────
using ThrottleCallback = std::function<void(float)>;
using BrakeCallback    = std::function<void(float)>;

// ─────────────────────────────────────────────────────────────────────────────
class VehicleService {
public:
    VehicleService();
    ~VehicleService();

    bool init();
    void start();
    void stop();

    // Cập nhật state từ bên ngoài (simulation loop hoặc HAL)
    void updateSpeed(float kmh);
    void updateRPM(uint16_t rpm);
    void updateGear(uint8_t gear);
    void updateFuel(float percent);
    void updateBrakeStatus(bool active);

    // Register callbacks khi nhận command từ client
    void setThrottleCallback(ThrottleCallback cb) { throttle_cb_ = std::move(cb); }
    void setBrakeCallback(BrakeCallback cb)        { brake_cb_    = std::move(cb); }

    VehicleState getState() const;

private:
    // vsomeip runtime
    std::shared_ptr<vsomeip::application> app_;

    // Vehicle state (thread-safe)
    mutable std::mutex state_mutex_;
    VehicleState state_;

    // Callbacks
    ThrottleCallback throttle_cb_;
    BrakeCallback    brake_cb_;

    // Simulation thread
    std::thread sim_thread_;
    std::atomic<bool> running_{false};

    // Internal helpers
    void onState(vsomeip::state_type_e state);
    void onThrottleRequest(const std::shared_ptr<vsomeip::message>& msg);
    void onBrakeRequest(const std::shared_ptr<vsomeip::message>& msg);
    void onGetInfoRequest(const std::shared_ptr<vsomeip::message>& msg);
    void onEmergencyStop(const std::shared_ptr<vsomeip::message>& msg);

    void registerServices();
    void simulationLoop();

    // Serializers
    std::vector<uint8_t> serializeFloat(float value);
    std::vector<uint8_t> serializeUInt16(uint16_t value);
    std::vector<uint8_t> serializeVehicleInfo();
    float deserializeFloat(const std::shared_ptr<vsomeip::message>& msg);
};
