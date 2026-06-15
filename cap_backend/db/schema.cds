// db/schema.cds — Database Schema for Procurement AI System
namespace procurement.db;

// ─── Vendors Table ───────────────────────────────────────────
entity Vendors {
  key ID          : UUID;
  vendorCode      : String(10);
  name            : String(100);
  category        : String(50);    // Electronics, Office, Furniture
  unitPrice       : Decimal(10,2);
  currency        : String(3) default 'USD';
  minOrderQty     : Integer default 1;
  maxOrderQty     : Integer default 1000;
  leadTimeDays    : Integer default 7;
  rating          : Decimal(3,2);  // 1.00 - 5.00
  isActive        : Boolean default true;
  contactEmail    : String(100);
  country         : String(50);
}

// ─── Budget Table ─────────────────────────────────────────────
entity Budgets {
  key ID          : UUID;
  department      : String(100);
  fiscalYear      : Integer;
  totalBudget     : Decimal(15,2);
  spentAmount     : Decimal(15,2) default 0;
  reservedAmount  : Decimal(15,2) default 0;
  currency        : String(3) default 'USD';
  approvalLimit   : Decimal(15,2); // auto-approve below this
}

// ─── Purchase Orders Table ────────────────────────────────────
entity PurchaseOrders {
  key ID            : UUID;
  poNumber          : String(20);
  vendor            : Association to Vendors;
  itemDescription   : String(500);
  quantity          : Integer;
  unitPrice         : Decimal(10,2);
  totalAmount       : Decimal(15,2);
  currency          : String(3) default 'USD';
  status            : String(20) default 'PENDING';
  // PENDING | APPROVED | REJECTED | UNDER_REVIEW
  rejectionReason   : String(500);
  requestedBy       : String(100);
  requestedByRole   : String(50);
  approvedBy        : String(100);
  createdAt         : Timestamp;
  updatedAt         : Timestamp;
}

// ─── Agent Audit Log ──────────────────────────────────────────
entity AgentLogs {
  key ID          : UUID;
  sessionId       : String(50);
  agentName       : String(50);
  requestText     : LargeString;
  responseText    : LargeString;
  decision        : String(20);
  confidence      : Decimal(3,2);
  userRole        : String(50);
  processingMs    : Integer;
  guardrailHit    : Boolean default false;
  guardrailReason : String(200);
  createdAt       : Timestamp;
}
