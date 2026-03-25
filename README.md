# CommunicationModels-SD

## 🏗️ Repository Design & Architecture

This document explains the **internal design decisions** and **repository structure** of the project.
It is intended to help developers understand how the system is organized and how different components interact.

---

## 🎯 Design Goals

The repository is structured to achieve the following:

* Clear separation between **business logic** and **communication layers**
* Independent implementations of **direct** and **indirect** architectures
* Reproducible **experiments and benchmarks**
* Easy deployment in **distributed environments (AWS)**
* Maintainability and extensibility

---

## 🧩 High-Level Architecture

The system follows a **modular layered architecture**:

```text
Clients → Communication Layer → Core Logic → Storage Backend
```

* **Communication Layer**: Handles how requests enter the system (REST / RabbitMQ)
* **Core Logic**: Implements ticket acquisition and consistency rules
* **Storage Backend**: Ensures correctness using Redis / database

---

## 📁 Repository Structure

### ⚙️ `src/`

Main source code, organized by responsibility:

#### `common/`

Shared utilities and data models:

* Request/response structures
* Configuration management
* Logging utilities

---

#### `backend/`

Core business logic (shared across all architectures):

* Ticket management logic
* Consistency enforcement (locks, transactions)
* Storage abstraction (Redis / DB)

👉 This is the **single source of truth** for correctness.

---

#### `direct/`

Implementation of the **direct communication architecture**:

* API server (REST / RPC)
* Client implementation
* Load balancing configuration (e.g., NGINX)

👉 Requests are handled **synchronously**.

---

#### `indirect/`

Implementation of the **indirect communication architecture**:

* Producers (clients sending messages)
* Workers (processing requests asynchronously)
* Queue configuration (RabbitMQ)

👉 Requests are handled **asynchronously via messaging**.

---

#### `experiments/`

Tools for evaluation:

* Benchmark execution
* Workload loading
* Metrics collection
* Scalability tests

👉 Ensures experiments are **reproducible and comparable**.

---

### 📊 `benchmarks/`

Input workload files used for evaluation:

* Unnumbered ticket workload
* Numbered ticket workload
* High-contention scenarios

---

### 📈 `results/`

Stores outputs from experiments:

* Raw execution results
* Processed metrics
* Generated plots

---

### 📄 `docs/`

Project documentation:

* Final report
* Architecture diagrams
* Supporting materials and figures

---

### 📜 `scripts/`

Utility scripts for:

* Deployment (AWS)
* Starting/stopping services
* Running benchmarks

---

### 📓 `notebooks/`

Jupyter notebooks for:

* Data exploration
* Visualization
* Debugging experiments

---

### 🧪 `tests/`

Test suite:

* Correctness validation
* Concurrency testing
* API behavior

---

## 🔁 Design Principles

### 1. Separation of Concerns

* Communication logic is isolated from business logic
* Backend logic is reused across architectures

---

### 2. Reusability

* Core logic (`backend/`) is shared by:

  * Direct API servers
  * Indirect workers

---

### 3. Modularity

* Each component can be modified independently
* New communication models can be added easily

---

### 4. Experimentation-Oriented

* Benchmarks and results are first-class components
* Enables systematic comparison between approaches

---

## ⚖️ Architectural Decision

A key design choice is:

> **Single core logic + multiple communication interfaces**

This ensures:

* Consistent behavior across architectures
* Fair performance comparison
* Reduced code duplication

---

## 🚀 Extending the Project

Possible extensions:

* Add new communication middleware (e.g., gRPC)
* Experiment with different consistency models
* Introduce caching or replication strategies
* Improve fault tolerance mechanisms

---

## 🧠 Summary

This repository is designed as a **distributed systems experimentation platform**, where:

* Multiple architectures can be implemented and compared
* Performance and correctness can be systematically evaluated
* The system remains modular, extensible, and reproducible
