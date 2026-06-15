// srv/procurement-service.js
// CAP Service Handler — bridges CDS actions to Python AI backend
const cds = require('@sap/cds');
const http = require('http');

const PYTHON_HOST = process.env.PYTHON_HOST || 'localhost';
const PYTHON_PORT = process.env.PYTHON_PORT || '8000';

// ─── Helper: call Python AI backend ──────────────────────────
async function callPythonBackend(path, method = 'GET', body = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: PYTHON_HOST,
      port: PYTHON_PORT,
      path: path,
      method: method,
      headers: { 'Content-Type': 'application/json' }
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error('Invalid JSON from Python backend')); }
      });
    });

    req.on('error', (err) => reject(err));
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

module.exports = cds.service.impl(async function (srv) {
  // Debug: log incoming request user and event for auth troubleshooting
  srv.before('*', (req) => {
    try {
      const user = req.user || {};
      console.log('[CAP DEBUG] event:', req.event, 'path:', req.path, 'user:', { id: user.id, roles: user.roles });
    } catch (e) {
      console.log('[CAP DEBUG] failed to log req.user', e);
    }
  });
  const { Vendors, Budgets, PurchaseOrders, AgentLogs } = this.entities;

  // ─── processProcurementRequest ─────────────────────────────
  srv.on('processProcurementRequest', async (req) => {
    const { requestText, department } = req.data;
    const userRole = req.user?.roles?.[0] || 'ProcurementOfficer';
    const userName = req.user?.id || 'unknown';

    console.log(`[CAP] processProcurementRequest by ${userName} (${userRole})`);
    console.log(`[CAP] Request: "${requestText}", Department: ${department}`);

    // Forward to Python AI backend
    try {
      const result = await callPythonBackend(
        '/api/process-request',
        'POST',
        {
          request_text: requestText,
          department: department || 'IT Department',
          user_role: userRole,
          user_name: userName
        }
      );

      // If approved — create PO in HANA/SQLite
      if (result.decision === 'APPROVED' && result.vendor_id) {
        const poNumber = `PO-${Date.now()}`;
        await INSERT.into(PurchaseOrders).entries({
          ID:              cds.utils.uuid(),
          poNumber:        poNumber,
          vendor_ID:       result.vendor_id,
          itemDescription: requestText,
          quantity:        result.quantity,
          unitPrice:       result.unit_price,
          totalAmount:     result.total_amount,
          currency:        'USD',
          status:          'APPROVED',
          requestedBy:     userName,
          requestedByRole: userRole,
          approvedBy:      'AI Agent System',
          createdAt:       new Date().toISOString(),
          updatedAt:       new Date().toISOString()
        });
        result.poNumber = poNumber;
        console.log(`[CAP] PO created: ${poNumber}`);
      }

      // Log to AgentLogs
      await INSERT.into(AgentLogs).entries({
        ID:           cds.utils.uuid(),
        sessionId:    result.session_id || cds.utils.uuid(),
        agentName:    'MultiAgentOrchestrator',
        requestText:  requestText,
        responseText: JSON.stringify(result),
        decision:     result.decision,
        confidence:   result.confidence || 0.85,
        userRole:     userRole,
        processingMs: result.processing_ms || 0,
        guardrailHit: result.guardrail_hit || false,
        guardrailReason: result.guardrail_reason || '',
        createdAt:    new Date().toISOString()
      });

      return {
        sessionId:       result.session_id,
        decision:        result.decision,
        summary:         result.summary,
        vendorName:      result.vendor_name,
        quantity:        result.quantity,
        unitPrice:       result.unit_price,
        totalAmount:     result.total_amount,
        budgetAvailable: result.budget_available,
        rejectionReason: result.rejection_reason || '',
        poNumber:        result.poNumber || '',
        agentSteps:      result.agent_steps || []
      };

    } catch (err) {
      console.error('[CAP] Python backend error:', err.message);
      req.error(503, `AI backend unavailable: ${err.message}`);
    }
  });

  // ─── getAvailableVendors ───────────────────────────────────
  srv.on('getAvailableVendors', async (req) => {
    const { category } = req.data;
    const db = await cds.connect.to('db');

    let query = SELECT.from(Vendors)
      .columns('vendorCode','name','category','unitPrice','rating','leadTimeDays as leadTime')
      .where({ isActive: true });

    if (category) {
      query = query.where({ isActive: true, category: category });
    }

    const vendors = await db.run(query);
    console.log(`[CAP] getAvailableVendors: ${vendors.length} results`);
    return vendors;
  });

  // ─── getBudget ─────────────────────────────────────────────
  srv.on('getBudget', async (req) => {
    const { department } = req.data;
    const db = await cds.connect.to('db');

    const budget = await db.run(
      SELECT.one.from(Budgets)
        .where({ department: department, fiscalYear: 2025 })
    );

    if (!budget) {
      req.error(404, `Budget not found for department: ${department}`);
    }

    return budget;
  });

  // ─── checkBudget ───────────────────────────────────────────
  srv.on('checkBudget', async (req) => {
    const { department, amount } = req.data;
    const db = await cds.connect.to('db');

    const budget = await db.run(
      SELECT.one.from(Budgets)
        .where({ department: department, fiscalYear: 2025 })
    );

    if (!budget) {
      return {
        available: false,
        budgetRemaining: 0,
        totalBudget: 0,
        spentAmount: 0,
        message: `No budget found for department: ${department}`
      };
    }

    const remaining = budget.totalBudget - budget.spentAmount - budget.reservedAmount;
    const available = remaining >= amount;

    return {
      available,
      budgetRemaining: remaining,
      totalBudget: budget.totalBudget,
      spentAmount: budget.spentAmount,
      message: available
        ? `Budget available. Remaining: $${remaining.toFixed(2)}`
        : `Insufficient budget. Need $${amount}, available $${remaining.toFixed(2)}`
    };
  });
});
