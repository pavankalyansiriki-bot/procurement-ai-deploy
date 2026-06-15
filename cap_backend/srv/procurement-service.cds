// srv/procurement-service.cds
// Role-Based Access Control:
//   ProcurementOfficer  — can read vendors, create POs
//   FinanceManager      — can read/update budgets, approve POs
//   BudgetController    — can read all, final budget decisions

using procurement.db from '../db/schema';

// ─── Main Procurement Service ────────────────────────────────
service ProcurementService @(requires: 'authenticated-user') {

  // Vendors — ProcurementOfficer reads, no external writes
  @readonly
  entity Vendors as projection on db.Vendors
    @(restrict: [
      { grant: 'READ', to: ['ProcurementOfficer','FinanceManager','BudgetController'] }
    ])

  // Budgets — allow authenticated users to read budgets in local dev
  @readonly
  entity Budgets as projection on db.Budgets

  // Purchase Orders — full lifecycle
  entity PurchaseOrders as projection on db.PurchaseOrders
    @(restrict: [
      { grant: 'READ',   to: ['ProcurementOfficer','FinanceManager','BudgetController'] },
      { grant: 'CREATE', to: ['ProcurementOfficer'] },
      { grant: 'UPDATE', to: ['FinanceManager','BudgetController'] }
    ])

  // Agent Logs — read-only for all roles
  @readonly
  entity AgentLogs as projection on db.AgentLogs
    @(restrict: [
      { grant: 'READ', to: ['FinanceManager','BudgetController'] }
    ])

  // ─── AI Agent Actions ─────────────────────────────────────
  // Main procurement request — ProcurementOfficer triggers
  @(requires: 'ProcurementOfficer')
  action processProcurementRequest(
    requestText : String,
    department  : String
  ) returns {
    sessionId       : String;
    decision        : String;
    summary         : String;
    vendorName      : String;
    quantity        : Integer;
    unitPrice       : Decimal;
    totalAmount     : Decimal;
    budgetAvailable : Decimal;
    rejectionReason : String;
    poNumber        : String;
    agentSteps      : array of {
      agent    : String;
      result   : String;
      details  : String;
    };
  };

  // Get vendors — ProcurementOfficer only
  @(requires: 'ProcurementOfficer')
  function getAvailableVendors(category: String) returns array of {
    vendorCode  : String;
    name        : String;
    category    : String;
    unitPrice   : Decimal;
    rating      : Decimal;
    leadTime    : Integer;
  };

  // Local budget lookup for authenticated users
  @(requires: 'authenticated-user')
  function getBudget(department: String) returns {
    ID             : String;
    department     : String;
    fiscalYear     : Integer;
    totalBudget    : Decimal;
    spentAmount    : Decimal;
    reservedAmount : Decimal;
    currency       : String;
    approvalLimit  : Decimal;
  };

  // Check budget — FinanceManager + BudgetController
  @(requires: ['FinanceManager','BudgetController'])
  function checkBudget(department: String, amount: Decimal) returns {
    available       : Boolean;
    budgetRemaining : Decimal;
    totalBudget     : Decimal;
    spentAmount     : Decimal;
    message         : String;
  }
}
