# GHOST-CLONE
Client-Side Security Testing Framework

## Overview

**GHOST-CLONE** — исследовательский фреймворк для изучения клиентских уязвимостей, поведения браузера и сценариев социальной инженерии в контролируемой и разрешённой среде.

Проект предназначен для:
- security research
- defensive testing
- обучения web-безопасности
- демонстрации рисков client-side атак

Данный репозиторий не является вредоносным программным обеспечением и не предназначен для несанкционированного использования.

---

## Architecture

Фреймворк использует исследовательский reverse-proxy для анализа:
- поведения браузерных сессий
- пользовательского взаимодействия с интерфейсом
- рисков внедрения клиентских скриптов
- последствий компрометации frontend-логики

Использование допускается только в тестовой или лабораторной среде.

![Architecture Diagram](./docs/reverse_proxy_diagram.png)

---

## Core Capabilities

### Proxy and Session Analysis

- Traffic Mirroring  
  Анализ HTTP-трафика и статических ресурсов (HTML, CSS, JS) в тестовой среде.

- Session Visualization  
  Отображение пользовательских действий (скролл, курсор) для исследования UX-рисков.

---

### Client Interaction Testing

- Input Monitoring (Lab Mode)  
  Исследование пользовательского ввода для демонстрации рисков client-side перехвата.

- Media Permissions Research  
  Анализ поведения браузера при запросе доступа к микрофону и камере  
  (только с явного согласия тестируемого пользователя).

- Environment Fingerprinting  
  Сбор обезличенной технической информации:
  - тип браузера
  - разрешение экрана
  - операционная система
  - айпи адресс
---

### Controlled Simulation

- File Delivery Simulation  
  Демонстрация механизмов загрузки файлов в рамках security-обучения.

- Audio and UI Events  
  Тестирование реакции браузера на мультимедиа и UI-события.

- Session Control Demonstration  
  Исследование сценариев временной блокировки интерфейса как примера client-side DoS-рисков.

---

## Project Structure

```text
├── captures/          # Тестовые медиа-артефакты
├── audio_logs/        # Демонстрационные аудиофайлы
├── uploads/           # Файлы для simulation-тестов
├── logs.txt           # Логи исследовательских событий
├── ghost.py           # Основной исследовательский модуль
└── README.md          # Документация

## Installation

Clone the repository:

```bash
git clone https://github.com/waibernavaible/Xphishity.git
cd Xphishity
pip install flask flask-socketio requests beautifulsoup4
python xphishity.py


