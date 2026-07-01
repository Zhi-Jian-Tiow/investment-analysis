## Solution Architecture Document Generation

### Objective

Generate a comprehensive Solution Architecture Document based on the completed Architecture Decision Records.

---

### Prompt

You are a Principal Software Architect responsible for producing a production-quality Solution Architecture Document.

Use:

- Technical Discovery Report
- Architecture Decision Records
- All supplied project documentation

Do not introduce architectural decisions that contradict the supplied inputs.

Every major design decision should be traceable back to the Architecture Decision Records.

---

### Generate a complete Solution Architecture Document containing:

# 1 Executive Summary

# 2 Goals

# 3 Non-goals

# 4 Scope

# 5 Architectural Principles

# 6 Architecture Overview

Include a Mermaid system context diagram.

---

# 7 High-Level Architecture

Include a Mermaid component diagram.

---

# 8 System Components

Describe every component, including:

- Responsibility
- Interfaces
- Dependencies
- Failure modes

---

# 9 Data Flow

Include Mermaid data flow diagrams where appropriate.

---

# 10 Key Workflows

For important workflows, include Mermaid sequence diagrams.

---

# 11 Integration Architecture

Document every external integration.

Include:

- Purpose
- Authentication
- Failure handling
- Retry strategy
- Rate limiting
- Timeouts

---

# 12 Data Architecture

Describe:

- Data ownership
- Persistence strategy
- Data lifecycle
- Consistency model
- Caching strategy

---

# 13 Background Processing

Describe:

- Scheduled jobs
- Asynchronous processing
- Queues
- Workers

Include Mermaid diagrams if useful.

---

# 14 Security Architecture

Include:

- Authentication
- Authorization
- Secrets management
- Encryption
- Network boundaries
- Audit logging

---

# 15 Reliability

Describe:

- Error handling
- Retry mechanisms
- Graceful degradation
- Fault tolerance
- Backup strategy
- Disaster recovery

---

# 16 Scalability

Describe horizontal and vertical scaling considerations.

---

# 17 Observability

Include:

- Logging
- Monitoring
- Metrics
- Alerting
- Tracing

---

# 18 Deployment View

Include a Mermaid deployment diagram.

---

# 19 Risks

---

# 20 Future Evolution

---

### Diagram Requirements

Use Mermaid for every architecture diagram.

Where applicable include:

- System Context Diagram
- Component Diagram
- Container Diagram
- Sequence Diagram
- Deployment Diagram
- Data Flow Diagram

Every diagram must be consistent with the written architecture.
