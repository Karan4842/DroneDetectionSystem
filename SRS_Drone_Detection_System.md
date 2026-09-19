# Software Requirements Specification (SRS)
## Drone Detection System

<div align="center">
  <b>Version 1.0</b>
</div>

---

## Table of Contents
1. Introduction
2. System Overview
3. Technology Stack (Tech Stack)
4. System Architecture & High-Level Design (HLD)
5. Low-Level Design (LLD)
6. Functional Requirements
7. Non-Functional Requirements
8. System Features
9. Suggested Improvements & Future Scope
10. Conclusion

---

## 1. Introduction

### 1.1 Purpose
The purpose of this document is to comprehensively define the requirements, architecture, and design of the Drone Detection System. It encompasses functional and non-functional aspects, technical specifications, and system designs to ensure developers, architects, and stakeholders share a unified understanding of the system's operational expectations. This document spans all necessary details to serve as a complete guide for the project lifecycle.

### 1.2 Scope
With the rapid increase in the use of drones (UAVs) in recent years, security concerns have grown exponentially, particularly in sensitive areas such as airports, military zones, critical infrastructure facilities, and crowded public spaces. Unauthorized drones pose severe threats, including unauthorized surveillance, contraband smuggling, and potential safety/collision hazards.

The Drone Detection System is a multifaceted security solution designed to detect, track, and monitor unauthorized drones in real-time. The system utilizes a multi-sensor approach (incorporating Radar, RF sensors, and Optical/Thermal Cameras) powered by Artificial Intelligence (AI) and Machine Learning (ML) algorithms. Upon detecting a drone, the system tracks its flight path, attempts to classify its payload and model, and immediately alerts relevant authorities to facilitate rapid countermeasures.

The current scope heavily emphasizes detection, tracking, and monitoring, while establishing a scalable foundation for future automated response and mitigation integrations.

### 1.3 Definitions and Acronyms
* **UAV (Unmanned Aerial Vehicle):** Commonly known as a drone; an aircraft operated without a human pilot onboard.
* **AI (Artificial Intelligence):** Technology enabling machines to simulate cognitive functions like pattern recognition and object detection.
* **ML (Machine Learning):** A subset of AI focusing on training algorithms to learn from and make predictions based on data.
* **RF (Radio Frequency):** Electromagnetic wave frequencies used for communications between drones and their controllers.
* **PTZ Camera:** Pan-Tilt-Zoom camera capable of remote directional and zoom control.
* **HLD / LLD:** High-Level Design / Low-Level Design.
* **C-UAS:** Counter-Unmanned Aircraft System.

---

## 2. System Overview

### 2.1 System Description
The Drone Detection System is a robust, multi-layered security framework combining hardware sensors and software intelligence. 
* **Radar Systems:** Help in identifying physical objects in the airspace, providing long-range detection regardless of visibility conditions.
* **RF (Radio Frequency) Sensors:** Detect communication signals and telemetry data exchanged between the drone and its operator's remote controller, often allowing the system to locate the pilot as well.
* **Computer Vision (Cameras):** Optical and thermal PTZ cameras visually confirm the drone's presence, lock onto the target, and feed video streams to computer vision algorithms for visual tracking and classification.

By aggregating and analyzing data from these diverse sources (Sensor Fusion), the system ensures high reliability, maximizes the detection envelope, and significantly minimizes false positives caused by birds or commercial aircraft.

### 2.2 Operating Environment
The software backend will be hosted on scalable cloud infrastructure (or on-premise servers for highly classified zones) running Linux-based operating systems. Edge computing devices will be deployed alongside physical sensors to perform initial data filtering and real-time AI inference. The user dashboard will be accessible via standard modern web browsers on desktop and mobile devices.

---

## 3. Technology Stack (Tech Stack)

To achieve high performance, low latency, and scalable data processing, the following technology stack is recommended for modern development:

### 3.1 Frontend (User Interface)
* **Framework:** React.js or Next.js for a dynamic, responsive Single Page Application (SPA).
* **Styling:** Tailwind CSS for rapid, modern, and consistent UI design.
* **Mapping/GIS:** Mapbox GL JS or Leaflet for real-time geospatial tracking and plotting drone coordinates on a live map.
* **State Management:** Redux or Zustand.

### 3.2 Backend (Core Logic & API)
* **Framework:** Python (FastAPI) or Node.js (Express/NestJS). Python is highly recommended due to seamless integration with AI/ML libraries.
* **Real-time Communication:** WebSockets (Socket.io or FastAPI WebSockets) for streaming live alerts and telemetry data to the dashboard with sub-second latency.
* **Task Queues:** Celery with Redis/RabbitMQ for background processing, asynchronous alert dispatching, and heavy data computations.

### 3.3 Artificial Intelligence & Computer Vision
* **Object Detection Models:** YOLOv8 (You Only Look Once) or SSD (Single Shot MultiBox Detector) for real-time visual drone identification.
* **Libraries:** OpenCV for image processing; PyTorch or TensorFlow for model training and inference.
* **Edge Inference:** TensorRT for optimizing AI models to run on edge hardware.

### 3.4 Database & Storage
* **Time-Series Database:** TimescaleDB or InfluxDB. Crucial for storing highly frequent telemetry data (GPS coordinates, altitude, velocity over time).
* **Relational Database:** PostgreSQL for storing user credentials, sensor metadata, system configurations, and alert logs.
* **Blob Storage:** AWS S3 or local file storage for storing video clips and image snapshots of detected drones.

### 3.5 Infrastructure & Hardware Integration
* **Containerization:** Docker & Kubernetes for microservices orchestration and scaling.
* **IoT Protocols:** MQTT (Message Queuing Telemetry Transport) for lightweight, high-throughput communication between hardware sensors and the backend server.
* **Edge Hardware:** NVIDIA Jetson Nano / Xavier for running local computer vision models directly at the camera site.

---

## 4. System Architecture & High-Level Design (HLD)

The HLD provides a macro-level view of the system components and their interactions. The architecture follows a distributed, event-driven IoT model combined with a microservices backend.

### 4.1 Architecture Diagram Flow
1. **Perception Layer (Hardware):**
   * Radar continuously scans the airspace.
   * RF Scanners monitor frequency bands (2.4GHz, 5.8GHz).
   * PTZ Cameras capture visual/thermal video feeds.
2. **Edge Processing Layer:**
   * Edge devices (e.g., NVIDIA Jetson) receive raw sensor data locally.
   * YOLO models run on video feeds to detect bounding boxes of drones.
   * Extraneous data is filtered out. Only positive detections and essential telemetry are sent to the cloud via MQTT.
3. **Core Processing Layer (Cloud Backend):**
   * **Data Ingestion Service:** Receives MQTT streams from all edge nodes.
   * **Sensor Fusion Engine:** Correlates radar blips, RF signals, and visual detections. If an RF signal and a visual detection occur at the same GPS coordinate simultaneously, confidence scores increase significantly.
   * **Tracking Engine:** Calculates speed, trajectory, and predicted flight path.
4. **Application Layer:**
   * **Alerting Service:** Checks if the drone breaches a predefined Geofence/No-Fly Zone. Dispatches SMS/Email/UI alerts immediately.
   * **Database Service:** Persists flight paths to the Time-Series database and logs incidents to the Relational database.
5. **Presentation Layer (Frontend):**
   * Web Dashboard subscribes to WebSocket channels to update the live map, display camera feeds in real-time, and trigger urgent visual alerts.

---

## 5. Low-Level Design (LLD)

The LLD dives into the specific modules, classes, and database schemas required for implementation.

### 5.1 Core Software Modules
* **`SensorGatewayModule`**: Responsible for maintaining MQTT connections with physical sensors. Handles connection drops, retries, and decrypting incoming payloads.
* **`VisionProcessingEngine`**: Contains the `YOLOInference` logic. 
  * Key Methods: `process_frame(image_bytes)`, `extract_bounding_boxes()`, `calculate_confidence_score()`.
* **`GeospatialTracker`**: Converts pixel coordinates from cameras and radial distances from radar into real-world Latitude/Longitude coordinates using geographical calibration matrices.
* **`AlertDispatcher`**: Implements the Observer design pattern. Modules subscribe to threat levels. When `ThreatLevel.CRITICAL` is reached, it simultaneously triggers `send_sms()`, `trigger_siren_api()`, and `push_websocket_notification()`.

### 5.2 Database Schema (Conceptual)

**Table: `Sensors` (PostgreSQL)**
* `sensor_id` (UUID, Primary Key)
* `type` (Enum: RADAR, RF, CAMERA)
* `latitude` (Float)
* `longitude` (Float)
* `status` (Enum: ONLINE, OFFLINE, MAINTENANCE)

**Table: `DroneDetections` (TimescaleDB / Time-Series)**
* `detection_id` (UUID)
* `timestamp` (DateTime, Indexed)
* `drone_identifier` (String - unique tracker ID for continuity)
* `latitude` (Float)
* `longitude` (Float)
* `altitude` (Float)
* `confidence_score` (Float 0-100)
* `source_sensor_id` (Foreign Key -> Sensors)

**Table: `AlertLogs` (PostgreSQL)**
* `alert_id` (UUID)
* `drone_identifier` (String)
* `severity` (Enum: LOW, MEDIUM, HIGH, CRITICAL)
* `message` (Text)
* `timestamp` (DateTime)
* `resolved_status` (Boolean)

---

## 6. Functional Requirements

Functional requirements define what the system *must do*.

1. **Multi-Sensor Data Ingestion:** The system must accept and process data streams from diverse hardware inputs concurrently without dropping critical packets.
2. **Real-time Object Detection:** The visual module must analyze video feeds at a minimum of 30 frames per second (FPS) to successfully identify fast-moving drones.
3. **Sensor Fusion & Correlation:** The system must merge data points from radar, RF, and cameras to establish a single unified "track" for a unique drone, reducing duplicate alerts for the same object.
4. **Geofencing Configurator:** Administrators must be able to draw custom polygonal "No-Fly Zones" (Geofences) dynamically on the dashboard map.
5. **Live Tracking Display:** The dashboard must display a moving icon representing the drone on the map, updating its physical position at least once per second.
6. **Automated Alerting:** When a drone enters a defined geofence, the system must trigger a system-wide alert within 2 seconds.
7. **Threat Classification:** The system shall attempt to classify the drone model (e.g., DJI Phantom, Custom Quadcopter, Fixed-wing) and estimate payload presence if visually identifiable.
8. **Data Logging & Replay:** The system must log all flight trajectories historically and allow users to "replay" past incidents for forensic and investigative analysis.
9. **Role-Based Access Control (RBAC):** The system must support Admin, Operator, and Viewer roles with strictly enforced, distinct permissions.

---

## 7. Non-Functional Requirements

Non-functional requirements define *how well* the system performs its functions.

1. **Accuracy & Precision:** The AI model should maintain a detection accuracy of over 95%, with a false-positive rate remaining below 2% in clear weather conditions.
2. **Latency:** The end-to-end latency from hardware detection to dashboard UI visual alert must not exceed 2.0 seconds.
3. **Scalability:** The backend infrastructure must be capable of handling up to 50 concurrent sensor feeds and tracking up to 100 simultaneous drones without any performance degradation or lag.
4. **Availability:** As a critical security application, the system must guarantee 99.99% uptime (High Availability) through redundancy and failover mechanisms.
5. **Security & Compliance:** All data transmitted between sensors, backend, and frontend must be encrypted using TLS 1.3. Video streams must be securely authenticated. The system must comply with local privacy and surveillance regulations.
6. **Maintainability:** The AI models must be easily hot-swappable to allow for the deployment of newly trained model weights without bringing the entire system or detection capabilities down.

---

## 8. System Features

The Drone Detection System provides the following primary features for end-users:

### Real-time Monitoring Dashboard
The system provides a tactical command dashboard where users can monitor drone activity live. It features a dark-mode, high-contrast map displaying live sensor statuses, drone trajectories, altitude graphs, and Picture-in-Picture (PiP) live video feeds from PTZ cameras tracking the target. It is designed to present complex data in an instantly understandable format for high-stress security environments.

### Alert Notification System
Whenever a drone is detected entering a restricted zone, the system sends immediate alerts to the concerned authorities. Visual flashing on the UI is accompanied by audible alarms. It integrates with external communication systems via Webhooks, SMS APIs, and Email to notify remote security personnel, enabling rapid response to potential threats.

### Data Logging and Reporting
The system acts as a black box, maintaining an immutable record of all detected drone activities. This data can be queried later for forensic analysis, reporting, or investigation purposes. Users can automatically generate PDF incident reports summarizing flight paths, peak altitudes, and visual snapshots of the intruding drone.

---

## 9. Suggested Improvements & Future Scope

Based on the current project requirements, the following improvements and advanced features are strongly recommended to elevate the project from a standard detection system to an advanced, enterprise-grade security solution. Implementing these will significantly enhance the project's value and technical depth:

1. **Automated Mitigation & Countermeasures (C-UAS):** 
   * **Enhancement:** Integrate the system with active defense mechanisms. Once a drone is confirmed hostile, the system could automatically aim and trigger RF Jammers to sever the controller link, forcing the drone to safely land or return to home.
2. **Pilot Location Triangulation:**
   * **Enhancement:** Enhance the RF sensing capabilities to not only track the drone but also triangulate the physical GPS location of the remote controller (the pilot). This allows law enforcement to apprehend the operator directly, stopping the root cause.
3. **Acoustic Sensor Integration:**
   * **Enhancement:** Add directional microphones to the sensor array. Drones emit specific acoustic signatures (propeller whine). Acoustic sensors can detect drones hiding behind visual obstructions (like buildings, fog, or trees) where cameras and radar might fail.
4. **Swarm Detection Logic:**
   * **Enhancement:** Upgrade the tracking algorithm to recognize and group multiple drones moving in coordinated patterns (drone swarms). Swarms represent a significantly higher threat level and require specialized alerts.
5. **Machine Learning Predictive Pathing:**
   * **Enhancement:** Implement Recurrent Neural Networks (RNNs) or Kalman Filters to analyze a drone's current speed and trajectory to predict its exact location 30-60 seconds in the future. This allows security teams to preemptively position themselves.
6. **ADS-B Database Integration:**
   * **Enhancement:** Integrate with standard aviation databases (ADS-B) to easily differentiate between unauthorized consumer drones and authorized commercial aircraft, helicopters, or police drones. This virtually eliminates false positives caused by standard aircraft.
7. **Mobile Application:**
   * **Enhancement:** Develop a companion native mobile app (iOS/Android) using React Native or Flutter to provide on-the-go push notifications and live camera feeds to patrolling security personnel who are away from the main command center.

---

## 10. Conclusion

In conclusion, the Drone Detection System provides a crucial and highly necessary layer of modern security by leveraging cutting-edge AI, IoT, and sensor technologies. By fulfilling the functional and non-functional requirements outlined in this SRS, the developed system will accurately detect and track unauthorized UAVs, delivering real-time actionable intelligence and timely alerts to authorities. This proactive approach significantly aids in managing potential risks effectively. Furthermore, incorporating the suggested advanced features in future iterations will ensure the system remains resilient, adaptable, and highly effective against rapidly evolving aerial threats in the modern landscape.
