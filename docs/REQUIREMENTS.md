# CommunicationModels-SD

## Scalable Concert Ticket Acquisition System

---

## 🌍 Environment

* **AWS Academy (mandatory)** – virtual machines provided per student/group

---

## 🎯 1. Objective

Design, implement, and evaluate a **scalable distributed ticket acquisition system** under high load and contention.

You will explore and compare:

* Direct vs indirect communication middleware
* Consistency guarantees under contention
* Scalability and throughput
* Architectural tradeoffs in distributed systems

The system will be evaluated using **fixed benchmark workload files**.

---

## 🧩 2. System Overview

The system manages ticket sales for a concert with **20,000 tickets**.

You must support:

* Two ticket models
* Two communication architectures

---

## 🎟️ 3. Ticket Models

### 3.1 Unnumbered Tickets

* Tickets are identical (e.g., standing area)
* At most **20,000 tickets** can be sold
* Extra purchase attempts must be rejected
* No seat identity

👉 Focus: **throughput and scalability**

---

### 3.2 Numbered Tickets

* Seats numbered from **1 to 20,000**
* Each seat can be sold **at most once**
* Concurrent requests may target the same seat
* Conflicts must be handled correctly

👉 Focus: **consistency under contention**

---

## 🔌 4. Communication Architectures (Mandatory)

You must implement **two system versions**.

---

### 4.1 Direct Communication Architecture

Implement at least one:

* REST (HTTP API)
* XML-RPC
* Pyro

#### ⚠️ Restrictions

* Clients must send requests to a **single entry point**

#### Load Balancing Options

* Server-side load balancing (**preferred**)
* Custom load balancer
* Existing solution (e.g., NGINX)
* Client-side load balancing (round-robin or name server)

👉 NGINX is **recommended for REST implementations**

---

### 4.2 Indirect Communication Architecture

* Use **RabbitMQ (mandatory)**

Architecture:

* Clients send requests to middleware
* Workers process requests asynchronously
* System must ensure coordination and consistency

---

### 4.3 Consistency Backend

Possible approaches:

* Redis (counters)
* Database with transactions
* Eventually consistent database

👉 You are encouraged to experiment and justify your design

---

## ☁️ 5. Execution Environment (Mandatory)

* Must run on **AWS Academy VMs / lab machines**
* One or more VMs per group
* Distributed deployment is encouraged

⚠️ Local-only validation is **not sufficient**

---

### ➕ Additional Requirement 1: Dynamic Scaling

* Workers can be added/removed during execution
* System must:

  * Continue operating
  * Maintain correctness
  * Improve throughput with more workers

---

### ➕ Additional Requirement 2: High Contention Scenario

Modify benchmark:

* **80% of requests target 5% of seats**

Effects:

* Hotspots
* Lock contention
* Throughput degradation
* Queue buildup

You must analyze:

* Why contention affects scalability
* Behavior of both architectures under these conditions

---

### ⭐ Optional: Crash Failures

Simulate failures:

* Kill worker VM
* Kill Redis / DB
* Restart services

System must:

* Prevent overselling
* Avoid lost successful purchases
* Avoid duplicate processing

Include discussion of fault tolerance and tradeoffs

---

## 📊 6. Benchmark Workloads

Provided files:

* `benchmark_unnumbered.txt`
* `benchmark_numbered.txt`

### Format

**Unnumbered**

```
BUY <client_id> <request_id>
```

**Numbered**

```
BUY <client_id> <seat_id> <request_id>
```

Each line = one acquisition attempt

---

## ✅ 7. Correctness Requirements

### Unnumbered

* Exactly **20,000 successful BUYs**
* All additional requests must fail

### Numbered

* Each seat sold **at most once**
* No duplicate successful purchases

⚠️ Any violation = **correctness failure**

---

## 🚀 8. Performance Evaluation

You must report:

* Total execution time
* Throughput (ops/sec)
* Successful vs failed operations
* Scalability (workers / VMs)

### Required Plots

* Throughput vs number of workers
* Direct vs indirect comparison
* Numbered vs unnumbered comparison

---

## 📄 9. Documentation and Report (Mandatory)

### 9.1 System Description

* Architecture overview
* Middleware used
* AWS deployment

### 9.2 Architectural Comparison

* Direct vs indirect communication
* Load balancing strategy
* Consistency mechanisms
* Bottlenecks

### 9.3 Experimental Results

* Performance plots
* Scalability analysis
* Observations

### 9.4 Conceptual Discussion

* Throughput vs consistency tradeoffs
* Impact of contention
* Real-world applicability

---

## 📦 10. Deliverables

* Source code
* Deployment instructions (AWS)
* Benchmark results and plots
* Technical report (PDF)

⚠️ Benchmark files must **not be modified**

---

## 📊 11. Grading Criteria

| Component                 | Weight |
| ------------------------- | ------ |
| Correctness               | 35%    |
| Scalability & Performance | 25%    |
| Architectural Design      | 20%    |
| Documentation & Analysis  | 20%    |