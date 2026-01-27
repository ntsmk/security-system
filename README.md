# Raspberry Pi–Based Office Security System

## Background
This project aims to provide low-cost, low-maintenance situational awareness for a small office environment.
The goal is to build a simple, customizable security solution that avoids the complexity and cost of commercial off-the-shelf systems while meeting basic monitoring needs.
The system is designed to detect potential unauthorized entry and notify staff in real time, including capturing an image of the office when an event occurs.

## Intended Users
All department employees.

## Technology Stack

**Hardware:** Raspberry Pi

**Software:** Python

**Integrations:**
- Camera module (CSI)
- Motion sensor (GPIO)
- Door latch sensor (GPIO)
- Twilio API (WhatsApp notifications)

## System Logic / Workflow

The Raspberry Pi acts as the central controller and evaluates sensor input based on the following logic:
```
IF door latch sensor == OPEN
OR motion sensor == TRUE
THEN
    capture image
    send WhatsApp notification via Twilio
```

## Architecture diagram
<img src="images/diagram.jpg" alt="diagram"/>

## Project Tasks (Execution Order)

### 1. Define Requirements -> Done
- Identify hardware and software requirements
- Research compatible components
- Purchase required hardware
- Test individual hardware components

### 2. Development -> Done
- Implement sensor input handling
- Integrate camera capture
- Integrate WhatsApp notifications using Twilio

### 3. Testing -> In  Progress
- Test full workflow using physical hardware
- Validate notification and image capture behavior

### 4. Deployment
- Install system in the office environment
- Perform final validation and tuning
- Document usage and basic maintenance steps

## Notes
This project prioritizes simplicity, reliability, and maintainability over advanced features.

Future enhancements (e.g., door unlock integration, logging, or cloud dashboards) can be added incrementally if needed.
