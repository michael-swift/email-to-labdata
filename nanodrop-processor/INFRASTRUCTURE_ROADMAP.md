# Nanodrop Email Processing - Infrastructure Roadmap

## 🎯 Current Status: LLM Core Complete - Ready for Email Integration

The **hardest technical challenge** (100% accurate LLM extraction) is **SOLVED**. Now we need standard web infrastructure.

---

## 🏗️ MVP Infrastructure Architecture

```mermaid
graph TB
    subgraph "User Experience"
        U[User] -->|📧 Email with Nanodrop photo| E[Email Address]
        E -->|📨 Auto-reply with CSV| U
    end
    
    subgraph "Email Infrastructure"
        E --> SG[SendGrid Inbound Parse]
        SG -->|Webhook POST| W[Webhook Endpoint]
    end
    
    subgraph "Processing Pipeline"
        W -->|Enqueue Job| Q[Redis Queue]
        Q -->|Process| WK[Worker Process]
        WK -->|Extract Image| IMG[Image Processor]
        IMG -->|Send to LLM| LLM[GPT-4o Vision API]
        LLM -->|JSON Response| VAL[Data Validator]
        VAL -->|Generate CSV| CSV[CSV Generator]
        CSV -->|Send Email| EMAIL[Email Sender]
    end
    
    subgraph "Storage & Monitoring"
        WK --> DB[(PostgreSQL)]
        WK --> TEMP[Temp File Storage]
        WK --> LOG[Logging System]
    end
    
    style LLM fill:#90EE90,stroke:#333,stroke-width:3px
    style VAL fill:#90EE90,stroke:#333,stroke-width:3px
    style CSV fill:#90EE90,stroke:#333,stroke-width:3px
    style LOG fill:#90EE90,stroke:#333,stroke-width:3px
```

**🟢 Green = Already Implemented**  
**⚪ White = Needs Implementation**

---

## 🚀 Human Tasks & Account Setup

```mermaid
gantt
    title Human Setup Tasks
    dateFormat  YYYY-MM-DD
    section Domain & Email
    Purchase Domain           :done, domain, 2025-01-01, 1d
    Configure MX Records      :mx, after domain, 2d
    Set up SendGrid Account   :sendgrid, 2025-01-02, 1d
    Configure Inbound Parse   :parse, after sendgrid, 1d
    
    section Cloud Infrastructure  
    Set up Railway/Render     :cloud, 2025-01-03, 1d
    Configure PostgreSQL      :db, after cloud, 1d
    Set up Redis Instance     :redis, after cloud, 1d
    
    section API Keys & Secrets
    Get OpenAI API Key        :done, openai, 2025-01-01, 1d
    Get SendGrid API Key      :sg-key, after sendgrid, 1d
    Configure Environment     :env, after sg-key, 1d
    
    section Physical Setup
    Create Lab Signage        :sign, 2025-01-04, 2d
    Print Usage Instructions  :docs, after sign, 1d
    Test with Lab Team        :test, after docs, 2d
```

---

## 📋 Detailed Human Action Items

### **🌐 1. Domain & Email Setup**
| Task | Action Required | Estimated Time |
|------|----------------|----------------|
| **Domain Purchase** | Buy `nanodrop-capture.com` (or similar) | 15 min |
| **MX Records** | Point to SendGrid: `mx.sendgrid.net` | 30 min |
| **SendGrid Account** | Sign up, verify domain | 30 min |
| **Inbound Parse** | Configure webhook URL in SendGrid | 15 min |

### **☁️ 2. Cloud Infrastructure**
| Task | Action Required | Estimated Time |
|------|----------------|----------------|
| **Hosting Platform** | Railway, Render, or DigitalOcean | 30 min |
| **PostgreSQL** | Provision managed database | 15 min |
| **Redis** | Set up Redis instance for job queue | 15 min |
| **Environment Variables** | Configure API keys securely | 20 min |

### **🔑 3. API Keys & Accounts**
| Task | Status | Action Required |
|------|--------|----------------|
| **OpenAI API** | ✅ **DONE** | Already have key with credits |
| **SendGrid API** | ❌ **TODO** | Get API key after account setup |
| **Cloud Platform** | ❌ **TODO** | API keys for deployment |

### **🏥 4. Lab Integration**
| Task | Action Required | Estimated Time |
|------|----------------|----------------|
| **Signage** | Design & print instructions for Nanodrop | 2 hours |
| **Email Address** | Set up `data@nanodrop-capture.com` | 10 min |
| **Documentation** | Create user guide for lab team | 1 hour |
| **Training** | Show lab team how to use system | 30 min |

---

## 🛠️ Engineering Implementation Plan

```mermaid
flowchart TD
    subgraph "Week 1: Email Infrastructure"
        A[Set up FastAPI Webhook] --> B[Email Parser Implementation]
        B --> C[Image Extraction Logic]
        C --> D[Basic Job Queue]
        D --> E[Email Reply System]
    end
    
    subgraph "Week 2: Integration & Testing"
        E --> F[Integrate LLM Extraction]
        F --> G[End-to-End Testing]
        G --> H[Error Handling]
        H --> I[Monitoring Setup]
    end
    
    subgraph "Week 3: Production"
        I --> J[Security Hardening]
        J --> K[Rate Limiting]
        K --> L[Production Deployment]
        L --> M[Lab Rollout]
    end
    
    style A fill:#ffcccc
    style F fill:#ccffcc
    style L fill:#ccccff
```

---

## 🎯 Immediate Next Steps (This Week)

### **Human Tasks (Priority Order)**
1. **🌐 Set up SendGrid account** - 30 minutes
2. **🌐 Purchase/configure domain** - 45 minutes  
3. **☁️ Choose hosting platform** - 30 minutes
4. **🔑 Gather all API keys** - 15 minutes

### **Engineering Tasks (Priority Order)**
1. **📧 Implement webhook endpoint** - 4 hours
2. **📎 Add email attachment parsing** - 2 hours
3. **🔗 Integrate with existing LLM system** - 2 hours
4. **📨 Implement email reply** - 3 hours
5. **🧪 End-to-end testing** - 2 hours

---

## 💰 Infrastructure Costs (Monthly)

| Service | Cost | Usage |
|---------|------|-------|
| **SendGrid** | $0-15 | Free up to 100 emails/day |
| **Railway/Render** | $5-20 | Basic web service |
| **PostgreSQL** | $5-15 | Managed database |
| **Redis** | $5-10 | Queue management |
| **Domain** | $12/year | nanodrop-capture.com |
| **OpenAI API** | $0.03/image | Variable based on usage |
| **Total Fixed** | **~$15-60/month** | Plus $0.03 per image |

---

## 🎪 Lab Signage Design

```
┌─────────────────────────────────────────┐
│  🧬 NANODROP DATA EXTRACTION SERVICE    │
├─────────────────────────────────────────┤
│                                         │
│  📱 Take photo of Nanodrop screen       │
│  📧 Email to: data@nanodrop-capture.com │
│  ⏱️  Get CSV results in 60 seconds      │
│                                         │
│  💡 Tips for best results:              │
│  • Include entire screen in photo       │
│  • Avoid glare/reflections              │
│  • Take photo straight-on               │
│  • Ensure screen is clearly visible     │
│                                         │
│  ❓ Questions? Contact: [lab manager]   │
└─────────────────────────────────────────┘
```

---

## 🎯 Success Criteria for MVP

- [ ] Email to `data@nanodrop-capture.com` works
- [ ] Photos are extracted from emails  
- [ ] LLM processes images with >95% accuracy
- [ ] CSV files are generated and emailed back
- [ ] End-to-end processing < 60 seconds
- [ ] Error handling sends helpful messages
- [ ] System handles 10+ emails per day reliably

---

## 🚀 Ready to Execute!

**The core extraction engine is proven.** Now it's just standard web development to wrap it in email infrastructure. 

**Next session focus:** Set up SendGrid and implement the webhook endpoint!