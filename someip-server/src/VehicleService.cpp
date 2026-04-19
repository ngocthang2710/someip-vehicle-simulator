#include "VehicleService.h"

#include <vsomeip/vsomeip.hpp>
#include <android/log.h>
#include <chrono>
#include <cstring>
#include <sstream>
#include <cmath>

#define LOG_TAG "VehicleService"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)

// ─────────────────────────────────────────────────────────────────────────────
VehicleService::VehicleService() {
    app_ = vsomeip::runtime::get()->create_application("vehicle-server");
}

VehicleService::~VehicleService() {
    stop();
}

// ─── Init ─────────────────────────────────────────────────────────────────────
bool VehicleService::init() {
    if (!app_->init()) {
        LOGE("Failed to initialize vsomeip application");
        return false;
    }

    // State change handler
    app_->register_state_handler(
        [this](vsomeip::state_type_e state) { onState(state); });

    // Method handlers
    app_->register_message_handler(
        VEHICLE_SERVICE_ID, INSTANCE_ID, METHOD_GET_INFO,
        [this](const std::shared_ptr<vsomeip::message>& msg) { onGetInfoRequest(msg); });

    app_->register_message_handler(
        THROTTLE_SERVICE_ID, INSTANCE_ID, METHOD_SET_THROTTLE,
        [this](const std::shared_ptr<vsomeip::message>& msg) { onThrottleRequest(msg); });

    app_->register_message_handler(
        THROTTLE_SERVICE_ID, INSTANCE_ID, METHOD_SET_BRAKE,
        [this](const std::shared_ptr<vsomeip::message>& msg) { onBrakeRequest(msg); });

    app_->register_message_handler(
        THROTTLE_SERVICE_ID, INSTANCE_ID, METHOD_EMERG_STOP,
        [this](const std::shared_ptr<vsomeip::message>& msg) { onEmergencyStop(msg); });

    LOGI("VehicleService initialized");
    return true;
}

// ─── Start / Stop ─────────────────────────────────────────────────────────────
void VehicleService::start() {
    running_ = true;
    sim_thread_ = std::thread([this]() { simulationLoop(); });
    app_->start();
}

void VehicleService::stop() {
    running_ = false;
    if (sim_thread_.joinable()) sim_thread_.join();
    app_->stop();
}

// ─── State Handler ────────────────────────────────────────────────────────────
void VehicleService::onState(vsomeip::state_type_e state) {
    if (state == vsomeip::state_type_e::ST_REGISTERED) {
        LOGI("Application registered — offering services");
        registerServices();
    }
}

// ─── Register Services & Events ───────────────────────────────────────────────
void VehicleService::registerServices() {
    // VehicleService (0x1234)
    app_->offer_service(VEHICLE_SERVICE_ID, INSTANCE_ID);
    app_->offer_event(
        VEHICLE_SERVICE_ID, INSTANCE_ID, EVENT_SPEED,
        {EG_SPEED_RPM}, vsomeip::event_type_e::ET_EVENT,
        std::chrono::milliseconds(100), false,
        true, nullptr, vsomeip::reliability_type_e::RT_UNRELIABLE);

    app_->offer_event(
        VEHICLE_SERVICE_ID, INSTANCE_ID, EVENT_FUEL,
        {EG_FUEL_GEAR}, vsomeip::event_type_e::ET_FIELD,
        std::chrono::milliseconds(1000), false,
        true, nullptr, vsomeip::reliability_type_e::RT_RELIABLE);

    app_->offer_event(
        VEHICLE_SERVICE_ID, INSTANCE_ID, EVENT_GEAR,
        {EG_FUEL_GEAR}, vsomeip::event_type_e::ET_FIELD,
        std::chrono::milliseconds(200), false,
        true, nullptr, vsomeip::reliability_type_e::RT_RELIABLE);

    app_->offer_event(
        VEHICLE_SERVICE_ID, INSTANCE_ID, EVENT_BRAKE,
        {EG_BRAKE}, vsomeip::event_type_e::ET_EVENT,
        std::chrono::milliseconds(50), false,
        true, nullptr, vsomeip::reliability_type_e::RT_UNRELIABLE);

    // EngineService (0x1235)
    app_->offer_service(ENGINE_SERVICE_ID, INSTANCE_ID);
    app_->offer_event(
        ENGINE_SERVICE_ID, INSTANCE_ID, EVENT_RPM,
        {EG_SPEED_RPM}, vsomeip::event_type_e::ET_EVENT,
        std::chrono::milliseconds(100), false,
        true, nullptr, vsomeip::reliability_type_e::RT_UNRELIABLE);

    // ThrottleService (0x1236)
    app_->offer_service(THROTTLE_SERVICE_ID, INSTANCE_ID);

    LOGI("Services offered: 0x1234, 0x1235, 0x1236");
}

// ─── Simulation Loop ──────────────────────────────────────────────────────────
// Giả lập ECU: tự tăng/giảm tốc độ, RPM theo throttle
void VehicleService::simulationLoop() {
    LOGI("Simulation loop started");
    double t = 0.0;

    while (running_) {
        {
            std::lock_guard<std::mutex> lock(state_mutex_);

            // Giả lập động cơ đơn giản
            float target_speed = state_.throttle_pos * 180.0f;  // max 180 km/h
            float accel = (target_speed - state_.speed_kmh) * 0.05f;

            if (state_.brake_active) {
                state_.speed_kmh = std::max(0.0f, state_.speed_kmh - 5.0f);
            } else {
                state_.speed_kmh = std::max(0.0f, state_.speed_kmh + accel);
            }

            // RPM phụ thuộc speed và gear
            if (state_.speed_kmh < 1.0f) {
                state_.engine_rpm = 800;
            } else {
                float gear_ratio = (state_.gear == 0) ? 3.5f
                                 : (state_.gear == 1) ? 3.0f
                                 : (state_.gear == 2) ? 2.0f
                                 : (state_.gear == 3) ? 1.5f
                                 : 1.0f;
                state_.engine_rpm = (uint16_t)(state_.speed_kmh * gear_ratio * 30.0f + 800.0f);
                state_.engine_rpm = std::min((uint16_t)7000, state_.engine_rpm);
            }

            // Auto-shift logic
            if (state_.engine_rpm > 4500 && state_.gear < 5) state_.gear++;
            if (state_.engine_rpm < 1200 && state_.gear > 1) state_.gear--;

            // Tiêu thụ nhiên liệu
            float consumption = state_.throttle_pos * 0.001f;
            state_.fuel_percent = std::max(0.0f, state_.fuel_percent - consumption);

            // Nhiệt độ làm mát
            float target_temp = 85.0f + state_.engine_rpm / 500.0f;
            state_.coolant_temp += (target_temp - state_.coolant_temp) * 0.01f;
        }

        // Publish events
        {
            std::lock_guard<std::mutex> lock(state_mutex_);

            auto speed_payload = vsomeip::runtime::get()->create_payload();
            speed_payload->set_data(serializeFloat(state_.speed_kmh));
            app_->notify(VEHICLE_SERVICE_ID, INSTANCE_ID, EVENT_SPEED, speed_payload);

            auto rpm_payload = vsomeip::runtime::get()->create_payload();
            rpm_payload->set_data(serializeUInt16(state_.engine_rpm));
            app_->notify(ENGINE_SERVICE_ID, INSTANCE_ID, EVENT_RPM, rpm_payload);

            auto fuel_payload = vsomeip::runtime::get()->create_payload();
            fuel_payload->set_data(serializeFloat(state_.fuel_percent));
            app_->notify(VEHICLE_SERVICE_ID, INSTANCE_ID, EVENT_FUEL, fuel_payload);

            auto gear_payload = vsomeip::runtime::get()->create_payload();
            gear_payload->set_data({state_.gear});
            app_->notify(VEHICLE_SERVICE_ID, INSTANCE_ID, EVENT_GEAR, gear_payload);

            auto brake_payload = vsomeip::runtime::get()->create_payload();
            brake_payload->set_data({static_cast<uint8_t>(state_.brake_active ? 1 : 0)});
            app_->notify(VEHICLE_SERVICE_ID, INSTANCE_ID, EVENT_BRAKE, brake_payload);
        }

        t += 0.1;
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    LOGI("Simulation loop stopped");
}

// ─── Method Handlers ──────────────────────────────────────────────────────────
void VehicleService::onThrottleRequest(const std::shared_ptr<vsomeip::message>& msg) {
    float throttle = deserializeFloat(msg);
    throttle = std::max(0.0f, std::min(1.0f, throttle));  // clamp [0, 1]

    LOGI("SetThrottle: %.2f", throttle);
    {
        std::lock_guard<std::mutex> lock(state_mutex_);
        state_.throttle_pos = throttle;
    }
    if (throttle_cb_) throttle_cb_(throttle);

    // Send response
    auto response = vsomeip::runtime::get()->create_response(msg);
    auto payload = vsomeip::runtime::get()->create_payload();
    payload->set_data({0x01});  // success = true
    response->set_payload(payload);
    app_->send(response);
}

void VehicleService::onBrakeRequest(const std::shared_ptr<vsomeip::message>& msg) {
    float brake = deserializeFloat(msg);
    LOGI("SetBrake: %.2f", brake);
    {
        std::lock_guard<std::mutex> lock(state_mutex_);
        state_.brake_active = (brake > 0.1f);
    }
    if (brake_cb_) brake_cb_(brake);

    auto response = vsomeip::runtime::get()->create_response(msg);
    auto payload = vsomeip::runtime::get()->create_payload();
    payload->set_data({0x01});
    response->set_payload(payload);
    app_->send(response);
}

void VehicleService::onGetInfoRequest(const std::shared_ptr<vsomeip::message>& msg) {
    LOGD("GetVehicleInfo request received");
    auto response = vsomeip::runtime::get()->create_response(msg);
    auto payload = vsomeip::runtime::get()->create_payload();
    payload->set_data(serializeVehicleInfo());
    response->set_payload(payload);
    app_->send(response);
}

void VehicleService::onEmergencyStop(const std::shared_ptr<vsomeip::message>& msg) {
    LOGI("EMERGENCY STOP requested!");
    {
        std::lock_guard<std::mutex> lock(state_mutex_);
        state_.throttle_pos = 0.0f;
        state_.brake_active = true;
    }
    auto response = vsomeip::runtime::get()->create_response(msg);
    auto payload = vsomeip::runtime::get()->create_payload();
    payload->set_data({0x01});
    response->set_payload(payload);
    app_->send(response);
}

// ─── Public State Updaters ────────────────────────────────────────────────────
void VehicleService::updateSpeed(float kmh) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    state_.speed_kmh = kmh;
}

void VehicleService::updateRPM(uint16_t rpm) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    state_.engine_rpm = rpm;
}

void VehicleService::updateGear(uint8_t gear) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    state_.gear = gear;
}

void VehicleService::updateFuel(float percent) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    state_.fuel_percent = percent;
}

void VehicleService::updateBrakeStatus(bool active) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    state_.brake_active = active;
}

VehicleState VehicleService::getState() const {
    std::lock_guard<std::mutex> lock(state_mutex_);
    return state_;
}

// ─── Serializers ──────────────────────────────────────────────────────────────
std::vector<uint8_t> VehicleService::serializeFloat(float value) {
    std::vector<uint8_t> data(4);
    // Big-endian (SOME/IP network byte order)
    uint32_t raw;
    std::memcpy(&raw, &value, 4);
    data[0] = (raw >> 24) & 0xFF;
    data[1] = (raw >> 16) & 0xFF;
    data[2] = (raw >> 8)  & 0xFF;
    data[3] =  raw        & 0xFF;
    return data;
}

std::vector<uint8_t> VehicleService::serializeUInt16(uint16_t value) {
    return {
        static_cast<uint8_t>((value >> 8) & 0xFF),
        static_cast<uint8_t>(value & 0xFF)
    };
}

std::vector<uint8_t> VehicleService::serializeVehicleInfo() {
    std::lock_guard<std::mutex> lock(state_mutex_);
    std::vector<uint8_t> buf;
    auto append_float = [&](float f) {
        auto v = serializeFloat(f);
        buf.insert(buf.end(), v.begin(), v.end());
    };
    auto append_u16 = [&](uint16_t u) {
        auto v = serializeUInt16(u);
        buf.insert(buf.end(), v.begin(), v.end());
    };
    append_float(state_.speed_kmh);
    append_u16(state_.engine_rpm);
    buf.push_back(state_.gear);
    append_float(state_.fuel_percent);
    append_float(state_.throttle_pos);
    buf.push_back(state_.brake_active ? 0x01 : 0x00);
    append_float(state_.coolant_temp);
    return buf;
}

float VehicleService::deserializeFloat(const std::shared_ptr<vsomeip::message>& msg) {
    auto& payload = msg->get_payload();
    if (payload->get_length() < 4) return 0.0f;
    const uint8_t* d = payload->get_data();
    uint32_t raw = ((uint32_t)d[0] << 24) | ((uint32_t)d[1] << 16)
                 | ((uint32_t)d[2] << 8)  |  (uint32_t)d[3];
    float value;
    std::memcpy(&value, &raw, 4);
    return value;
}
