# UMAY — Military Situational Awareness System

> **TÜBİTAK-Supported Deep-Tech Startup** | Active Development

UMAY is a real-time battlefield situational awareness system that brings the spatial intelligence of modern 3D game engines into the physical world. Soldiers equipped with UMAY can see their own position, allied units, and detected threats overlaid on a heads-up display — without ever looking away from the field.

---

## The Problem

Modern infantry units rely on radio communication and physical maps to maintain situational awareness. This creates critical delays, communication gaps, and life-threatening blind spots in dynamic combat environments.

UMAY eliminates these gaps.

---

## What We're Building

### Real-Time Computer Vision Pipeline
- UAV footage is processed in real-time using custom-trained object detection models
- Friend/foe classification and localization on a live battlefield map
- Edge-deployable architecture designed for low-latency field conditions

### Sensor Fusion Architecture
- Integrates GPS, IMU, and visual data streams into a unified spatial model
- Designed for future deployment on embedded AR helmet hardware
- Robust to signal degradation in GPS-denied environments

### Encrypted Voice Communication
- Directional, encrypted voice channel between allied units
- External audio suppression — transmissions stay within the squad
- Ambient sound amplification for enhanced field awareness

### AR Helmet Integration (Upcoming)
- Heads-up display rendering friend/foe positions in 3D space
- Lightweight HUD overlay — no screen, no distraction
- Designed around off-the-shelf AR optics for rapid deployment

---

## Tech Stack

| Layer | Stack |
|---|---|
| Computer Vision | Python, OpenCV, YOLOv8, PyTorch |
| Sensor Fusion | ROS, MAVSDK, custom fusion pipeline |
| Edge Deployment | Jetson Orin Nano, TensorRT |
| Communication | Encrypted P2P protocol |
| Data | Synthetic UAV imagery (Google Earth Studio) |

---

## Team

4-person founding team with backgrounds in:
- AI & Computer Vision (Baykar Technologies, ASELSAN)
- UAV Software Systems (SUAS 2024 — 8th place globally)
- Embedded Systems & Edge Deployment

---

## Status

```
[x] Real-time UAV footage processing
[x] Friend/foe localization pipeline
[x] Sensor fusion architecture design
[ ] AR helmet hardware integration
[ ] Field testing
[ ] Deployment
```

---

## Research & Support

Developed under **TÜBİTAK** (The Scientific and Technological Research Council of Turkey) R&D support program.

---

## Contact

**Izzet Ahmet** — Co-Founder & AI Lead
- GitHub: [@Phoneria](https://github.com/Phoneria)
- LinkedIn: [linkedin.com/in/izzet-ahmet-702176219](https://linkedin.com/in/izzet-ahmet-702176219)
- Email: izzet.ahmet216@gmail.com

---

> *"Situational awareness is not a luxury — it's survival."*
