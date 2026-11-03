<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Accounts</h2>
        <p class="view-sub">Your banks, cards and loans, and what each one holds or owes.</p>
      </div>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
        <button v-if="banks.length" class="btn btn-outline" title="Type in today's balance for every account at once" @click="showCheckIn = true"><Icon name="pencil" :size="15" /> Update balances</button>
        <button v-if="banks.some(b => b.bankAccounts.length)" class="btn btn-outline" @click="showTransfer = true"><Icon name="repeat" :size="15" /> Move money</button>
        <button class="btn btn-outline" @click="showBankModal = true"><Icon name="plus" :size="16" /> Bank</button>
        <button class="btn btn-primary" @click="showAccountModal = true"><Icon name="plus" :size="16" /> Account</button>
      </div>
    </div>

    <div v-if="loading && !result" class="loading">Loading accounts...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else>
      <div v-if="banks.length === 0" class="empty-state">
        <div class="icon"><Icon name="accounts" :size="26" /></div>
        <p>No banks yet. Add a bank to get started.</p>
      </div>

      <div v-for="bank in banks" :key="bank.name" class="card bank-card">
        <div class="card-header">
          <div class="bank-title">
            <span class="bank-mark"><Icon name="accounts" :size="17" /></span>
            <span class="card-title">{{ bank.name }}</span>
            <span class="badge">{{ BANK_TYPES[bank.bankType] ?? bank.bankType }}</span>
          </div>
          <div class="row-actions">
            <span v-if="bank.bankAccounts.length" class="bank-total" title="Total in this bank's accounts">{{ currency(bank.totalBalance) }}</span>
            <RowMenu label="Bank actions" :items="[
              { label: 'Edit bank', icon: 'pencil', action: () => openEditBank(bank) },
              { label: 'Delete bank', icon: 'trash', danger: true, divider: true, action: () => deleteBank(bank.name) },
            ]" />
          </div>
        </div>

        <!-- Bank accounts -->
        <div v-if="bank.bankAccounts.length" style="margin-bottom:1rem">
          <h4>{{ bankAccountsTitle(bank.bankAccounts) }}</h4>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Type</th>
                  <th>Rate</th>
                  <th>Details</th>
                  <th style="text-align:right">Balance</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="acc in bank.bankAccounts" :key="acc.id">
                  <td>
                    {{ acc.accountName }}
                    <span v-if="isSynced(bank.name, acc.accountName)" class="sync-indicator" :title="syncTooltip(bank.name, acc.accountName)">
                      <span class="sync-label">SimpleFIN</span>
                    </span>
                  </td>
                  <td>
                    <span class="badge" :class="GROUP_BADGE[kindInfo(acc.accountType).group]" :title="kindInfo(acc.accountType).hint">{{ accountTypeLabel(acc.accountType) }}</span>
                    <span v-if="acc.paysBills === false" class="restricted-note" title="Not counted as spending money and never used to pay bills">not for bills</span>
                  </td>
                  <td>{{ acc.interestRate > 0 ? pct(acc.interestRate) + (kindInfo(acc.accountType).group === 'invested' ? ' growth' : '') : '—' }}</td>
                  <td class="acct-details">{{ accountDetails(acc) || '—' }}</td>
                  <td style="text-align:right;font-weight:600" :class="acc.balance >= 0 ? 'positive' : 'negative'">{{ currency(acc.balance) }}</td>
                  <td style="text-align:right;white-space:nowrap">
                    <div class="row-actions">
                      <button class="btn btn-outline btn-sm" @click="openUpdateBalance(bank.name, acc.accountName, acc.balance)">Update</button>
                      <RowMenu :items="[
                        { label: 'Edit details', icon: 'pencil', action: () => openEdit(bank.name, acc.accountType as AccountKind, acc) },
                        { label: 'Balance history', icon: 'history', action: () => openHistory(bank.name, acc.accountName, 'bank') },
                        { label: 'SimpleFIN transactions', icon: 'transactions', hidden: !isSynced(bank.name, acc.accountName), action: () => openTransactions(bank.name, acc.accountName) },
                        { label: 'Delete account', icon: 'trash', danger: true, divider: true, action: () => deleteAccount(bank.name, acc.accountName, 'bank') },
                      ]" />
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Credit accounts -->
        <div v-if="bank.creditAccounts.length">
          <h4>Cards &amp; loans</h4>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Status</th>
                  <th>APR</th>
                  <th>Due day</th>
                  <th style="text-align:right">Balance</th>
                  <th style="text-align:right">Limit</th>
                  <th style="text-align:right">Minimum</th>
                  <th>Utilization</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="cc in bank.creditAccounts" :key="cc.id">
                  <td>
                    {{ cc.accountName }}
                    <span v-if="cc.promoOffers && cc.promoOffers.length" class="promo-badge" :title="cc.promoOffers.length + ' promo offer(s)'"><Icon name="tag" :size="11" /> {{ cc.promoOffers.length }}
                    </span>
                    <span v-if="isSynced(bank.name, cc.accountName)" class="sync-indicator" :title="syncTooltip(bank.name, cc.accountName)">
                      <span class="sync-label">SimpleFIN</span>
                    </span>
                  </td>
                  <td><span class="badge cap" :class="statusBadge(cc.status)">{{ cc.status }}</span></td>
                  <td>{{ pct(cc.interestRate) }}</td>
                  <td>{{ cc.paymentDueDate ?? '-' }}</td>
                  <td style="text-align:right;font-weight:600;color:var(--danger)">{{ currency(cc.balance) }}</td>
                  <td style="text-align:right">{{ currency(cc.creditLimit) }}</td>
                  <td style="text-align:right">
                    <button class="link-btn" :title="`${cc.minRuleLabel ?? ''}. Click to match your statement.`" @click="minTarget = { bankName: bank.name, card: cc }">
                      {{ currency(cc.minimumPayment ?? 0) }}
                    </button>
                    <div class="min-rule">{{ cc.minRule ? 'your formula' : 'estimated' }}{{ owesPromo(cc) ? ' + promo payoff' : '' }}</div>
                  </td>
                  <td style="width:120px">
                    <div class="progress-bar">
                      <div class="fill" :style="{ width: utilPct(cc) + '%', background: utilColor(cc) }"></div>
                    </div>
                    <div style="font-size:0.7rem;color:var(--text-muted);text-align:center">{{ utilPct(cc).toFixed(0) }}%</div>
                  </td>
                  <td style="text-align:right;white-space:nowrap">
                    <div class="row-actions">
                      <button class="btn btn-outline btn-sm" @click="openUpdateCredit(bank.name, cc.accountName, cc.balance)">Update</button>
                      <RowMenu :items="[
                        { label: 'Edit details', icon: 'pencil', action: () => openEdit(bank.name, 'credit', cc) },
                        { label: 'Balance history', icon: 'history', action: () => openHistory(bank.name, cc.accountName, 'credit') },
                        { label: 'SimpleFIN transactions', icon: 'transactions', hidden: !isSynced(bank.name, cc.accountName), action: () => openTransactions(bank.name, cc.accountName) },
                        { label: 'Promo offers', icon: 'tag', action: () => openPromos(bank.name, cc) },
                        { label: 'Match minimum payment', icon: 'banknote', action: () => minTarget = { bankName: bank.name, card: cc } },
                        { label: 'Convert to HELOC', icon: 'home', action: () => openConvertToHELOC(bank.name, cc) },
                        { label: 'Delete account', icon: 'trash', danger: true, divider: true, action: () => deleteAccount(bank.name, cc.accountName, 'credit') },
                      ]" />
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Mortgage accounts -->
        <div v-if="bank.mortgageAccounts && bank.mortgageAccounts.length" style="margin-top:1rem">
          <h4>Mortgages</h4>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Status</th>
                  <th>APR</th>
                  <th>Due day</th>
                  <th style="text-align:right">Principal</th>
                  <th style="text-align:right">Monthly payment</th>
                  <th style="text-align:right">P &amp; I</th>
                  <th style="text-align:right">Escrow</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in bank.mortgageAccounts" :key="m.id">
                  <td style="font-weight:500">
                    {{ m.accountName }}
                    <span v-if="isSynced(bank.name, m.accountName)" class="sync-indicator" :title="syncTooltip(bank.name, m.accountName)">
                      <span class="sync-label">SimpleFIN</span>
                    </span>
                  </td>
                  <td><span class="badge cap" :class="m.status === 'active' ? 'badge-success' : 'badge-warning'">{{ m.status }}</span></td>
                  <td>{{ pct(m.interestRate) }}</td>
                  <td>{{ m.paymentDueDate }}</td>
                  <td style="text-align:right;font-weight:600;color:var(--danger)">{{ currency(m.currentPrincipal) }}</td>
                  <td style="text-align:right;font-weight:600">{{ currency(m.totalMonthlyPayment) }}</td>
                  <td style="text-align:right;font-size:0.8rem">
                    <div>P: {{ currency(m.monthlyPrincipal) }}</div>
                    <div>I: {{ currency(m.monthlyInterest) }}</div>
                  </td>
                  <td style="text-align:right">{{ currency(m.escrowMonthly) }}</td>
                  <td style="text-align:right;white-space:nowrap">
                    <div class="row-actions">
                      <button class="btn btn-outline btn-sm" @click="openUpdateLoan(bank.name, m.accountName, m.currentPrincipal, 'mortgage')">Update</button>
                      <RowMenu :items="[
                        { label: 'Payoff & schedule', icon: 'calendar', action: () => openMortgage(bank.name, m.accountName) },
                        { label: 'Pay extra principal', icon: 'trendingDown', action: () => openMortgage(bank.name, m.accountName, 'pay') },
                        { label: 'Edit details', icon: 'pencil', action: () => openEdit(bank.name, 'mortgage', m) },
                        { label: 'Balance history', icon: 'history', action: () => openHistory(bank.name, m.accountName, 'mortgage') },
                        { label: 'SimpleFIN transactions', icon: 'transactions', hidden: !isSynced(bank.name, m.accountName), action: () => openTransactions(bank.name, m.accountName) },
                        { label: 'Delete account', icon: 'trash', danger: true, divider: true, action: () => deleteAccount(bank.name, m.accountName, 'mortgage') },
                      ]" />
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- HELOC accounts -->
        <div v-if="bank.helocAccounts && bank.helocAccounts.length" style="margin-top:1rem">
          <h4>Home equity lines</h4>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Phase</th>
                  <th>APR</th>
                  <th>Due day</th>
                  <th style="text-align:right">Balance</th>
                  <th style="text-align:right">Limit</th>
                  <th style="text-align:right">Available</th>
                  <th style="text-align:right">Min payment</th>
                  <th>Draw ends</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in bank.helocAccounts" :key="h.id">
                  <td style="font-weight:500">
                    {{ h.accountName }}
                    <span v-if="isSynced(bank.name, h.accountName)" class="sync-indicator" :title="syncTooltip(bank.name, h.accountName)">
                      <span class="sync-label">SimpleFIN</span>
                    </span>
                  </td>
                  <td>
                    <span class="badge cap" :class="h.currentPhase === 'draw' ? 'badge-info' : h.currentPhase === 'repayment' ? 'badge-warning' : 'badge-success'">
                      {{ h.currentPhase }}
                    </span>
                  </td>
                  <td>{{ pct(h.interestRate) }}</td>
                  <td>{{ h.paymentDueDate }}</td>
                  <td style="text-align:right;font-weight:600;color:var(--danger)">{{ currency(h.balance) }}</td>
                  <td style="text-align:right">{{ currency(h.creditLimit) }}</td>
                  <td style="text-align:right" :style="{ color: h.currentPhase === 'draw' ? 'var(--success)' : 'var(--text-muted)' }">
                    {{ h.currentPhase === 'draw' ? currency(h.availableCredit) : '—' }}
                  </td>
                  <td style="text-align:right;font-weight:600">
                    {{ currency(h.minimumPayment) }}
                    <div style="font-size:0.7rem;color:var(--text-muted)">
                      {{ h.currentPhase === 'draw' ? 'interest only' : 'P+I' }}
                    </div>
                  </td>
                  <td>{{ fmtDate(h.drawEndDate) }}</td>
                  <td style="text-align:right;white-space:nowrap">
                    <div class="row-actions">
                      <button class="btn btn-outline btn-sm" @click="openUpdateLoan(bank.name, h.accountName, h.balance, 'heloc')">Update</button>
                      <RowMenu :items="[
                        { label: 'Edit details', icon: 'pencil', action: () => openEdit(bank.name, 'heloc', h) },
                        { label: 'Balance history', icon: 'history', action: () => openHistory(bank.name, h.accountName, 'heloc') },
                        { label: 'SimpleFIN transactions', icon: 'transactions', hidden: !isSynced(bank.name, h.accountName), action: () => openTransactions(bank.name, h.accountName) },
                        { label: 'Delete account', icon: 'trash', danger: true, divider: true, action: () => deleteAccount(bank.name, h.accountName, 'heloc') },
                      ]" />
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- Edit Account Modal -->
    <EditAccountModal v-if="editTarget" :kind="editTarget.kind" :bank-name="editTarget.bankName"
                      :account="editTarget.account" :banks="banks" @close="editTarget = null" @saved="onEdited" />

    <!-- Edit Bank Modal -->
    <div v-if="bankEdit" class="modal-overlay" @click.self="bankEdit = null">
      <div class="modal">
        <h3>Edit bank</h3>
        <p style="font-size:0.8rem;color:var(--text-muted);margin:0 0 0.9rem">
          Renaming keeps every account, bill and transaction connected.
        </p>
        <div class="form-group">
          <label>Bank name</label>
          <input v-model="bankEdit.name" />
        </div>
        <div class="form-group">
          <label>Type</label>
          <select v-model="bankEdit.type">
            <option value="traditional">Traditional</option>
            <option value="credit_issuer">Credit issuer</option>
            <option value="mortgage_lender">Mortgage lender</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="bankEdit = null">Cancel</button>
          <button class="btn btn-primary" @click="saveBank" :disabled="!bankEdit.name.trim()">Save</button>
        </div>
      </div>
    </div>

    <!-- Create Bank Modal -->
    <div v-if="showBankModal" class="modal-overlay" @click.self="showBankModal = false">
      <div class="modal">
        <h3>Create bank</h3>
        <div class="form-group">
          <label>Bank name</label>
          <input v-model="newBank.name" placeholder="e.g. Chase Bank" />
        </div>
        <div class="form-group">
          <label>Type</label>
          <select v-model="newBank.type">
            <option value="traditional">Traditional</option>
            <option value="credit_issuer">Credit issuer</option>
            <option value="mortgage_lender">Mortgage lender</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showBankModal = false">Cancel</button>
          <button class="btn btn-primary" @click="createBank" :disabled="!newBank.name">Create</button>
        </div>
      </div>
    </div>

    <!-- Create Account Modal -->
    <div v-if="showAccountModal" class="modal-overlay" @click.self="showAccountModal = false">
      <div class="modal">
        <h3>Create account</h3>
        <div class="form-group">
          <label>Bank</label>
          <select v-model="newAccount.bankName">
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Account name</label>
          <input v-model="newAccount.name" placeholder="e.g. Primary Checking" />
        </div>
        <div class="form-group">
          <label>Account type</label>
          <select v-model="newAccount.type">
            <optgroup v-for="g in KIND_GROUPS" :key="g.group" :label="g.label">
              <option v-for="k in g.kinds" :key="k.value" :value="k.value">{{ k.label }}</option>
            </optgroup>
            <optgroup label="Debt">
              <option value="credit">Credit card</option>
              <option value="heloc">HELOC</option>
              <option value="mortgage">Mortgage</option>
            </optgroup>
          </select>
          <small v-if="isBankKind(newAccount.type)" class="muted">{{ kindInfo(newAccount.type).hint }}</small>
        </div>
        <div v-if="newAccount.type === 'mortgage'" class="form-group">
          <label>Original loan amount</label>
          <input v-model.number="newAccount.originalPrincipal" type="number" step="0.01" min="0" />
          <small v-if="!(Number(newAccount.originalPrincipal) > 0)" style="color:var(--danger)">Original loan amount must be greater than 0.</small>
        </div>
        <div class="form-group">
          <label>{{ newAccount.type === 'credit' ? 'Current Balance' : newAccount.type === 'heloc' ? 'Current Balance Owed' : newAccount.type === 'mortgage' ? 'Current Principal Owed (blank = original amount)' : 'Starting Balance' }}</label>
          <input v-model.number="newAccount.balance" type="number" step="0.01" />
        </div>
        <div v-if="!isBankKind(newAccount.type) || kindInfo(newAccount.type).earns" class="form-group">
          <label>{{ isBankKind(newAccount.type) ? rateLabel(newAccount.type) : 'APR %' }}</label>
          <input v-model.number="newAccount.interestRate" type="number" step="0.01" />
        </div>
        <AccountExtrasFields v-if="isBankKind(newAccount.type)" v-model="newAccount.extras" :type="newAccount.type" />
        <div v-if="newAccount.type === 'credit' || newAccount.type === 'heloc'" class="form-group">
          <label>Credit limit</label>
          <input v-model.number="newAccount.creditLimit" type="number" step="0.01" min="0" />
          <small v-if="!(Number(newAccount.creditLimit) > 0)" style="color:var(--danger)">Credit limit must be greater than 0.</small>
        </div>
        <!-- Credit-card-specific fields -->
        <template v-if="newAccount.type === 'credit'">
          <div class="form-group">
            <label>Payment due day (1-31, optional)</label>
            <input v-model.number="newAccount.paymentDueDate" type="number" min="1" max="31" />
          </div>
          <div class="form-group">
            <label>Statement day (1-31, optional)</label>
            <input v-model.number="newAccount.statementDate" type="number" min="1" max="31" />
          </div>
        </template>
        <!-- Checking / savings: interest posting day -->
        <div v-if="isBankKind(newAccount.type) && (newAccount.interestRate || 0) > 0" class="form-group">
          <label>Interest day (1-31, optional)</label>
          <input v-model.number="newAccount.interestAccrualDate" type="number" min="1" max="31" />
          <small style="color:var(--text-muted)">Day of the month interest posts.</small>
        </div>
        <!-- HELOC-specific fields -->
        <template v-if="newAccount.type === 'heloc'">
          <div class="form-group">
            <label>Draw period (years)</label>
            <input v-model.number="newAccount.drawPeriodYears" type="number" min="1" max="30" step="1" />
            <small style="color:var(--text-muted)">Period during which you can borrow; minimums are interest-only.</small>
          </div>
          <div class="form-group">
            <label>Total term (years)</label>
            <input v-model.number="newAccount.totalTermYears" type="number" min="2" max="40" step="1" />
            <small style="color:var(--text-muted)">Total payback period including draw period.</small>
          </div>
          <div class="form-group">
            <label>HELOC start date</label>
            <input v-model="newAccount.startDate" type="date" />
          </div>
          <div class="form-group">
            <label>Payment due day (1-31)</label>
            <input v-model.number="newAccount.paymentDueDate" type="number" min="1" max="31" />
          </div>
        </template>
        <!-- Mortgage-specific fields -->
        <template v-if="newAccount.type === 'mortgage'">
          <div class="form-group">
            <label>Loan term (years)</label>
            <input v-model.number="newAccount.loanTermYears" type="number" min="1" max="50" step="1" />
          </div>
          <div class="form-group">
            <label>Loan start date (optional)</label>
            <input v-model="newAccount.startDate" type="date" />
          </div>
          <div class="form-group">
            <label>Payment due day (1-31)</label>
            <input v-model.number="newAccount.paymentDueDate" type="number" min="1" max="31" />
          </div>
          <div class="form-group">
            <label>Monthly escrow (optional)</label>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
              <input v-model.number="newAccount.escrowPropertyTax" type="number" step="0.01" min="0" placeholder="Property tax" title="Property tax" />
              <input v-model.number="newAccount.escrowInsurance" type="number" step="0.01" min="0" placeholder="Homeowners insurance" title="Homeowners insurance" />
              <input v-model.number="newAccount.escrowPmi" type="number" step="0.01" min="0" placeholder="PMI" title="PMI" />
              <input v-model.number="newAccount.escrowHoa" type="number" step="0.01" min="0" placeholder="HOA" title="HOA" />
              <input v-model.number="newAccount.escrowOther" type="number" step="0.01" min="0" placeholder="Other" title="Other" />
            </div>
          </div>
          <div class="form-group">
            <label>Home market value (optional)</label>
            <input v-model.number="newAccount.marketValue" type="number" step="0.01" min="0" />
            <small style="color:var(--text-muted)">Used to show equity.</small>
          </div>
          <div class="form-group">
            <label>Pay from (optional)</label>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
              <select v-model="newAccount.sourceBank">
                <option value="">Auto (no preference)</option>
                <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
              </select>
              <select v-model="newAccount.sourceAccount" :disabled="!newAccount.sourceBank">
                <option value="">Select account...</option>
                <option v-for="acc in mortgageSourceAccounts" :key="acc.accountName" :value="acc.accountName">{{ acc.accountName }}</option>
              </select>
            </div>
          </div>
          <div v-if="mortgagePaymentEstimate" style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.75rem">
            Estimated payment: <strong>{{ currency(mortgagePaymentEstimate.total) }}/month</strong>
            ({{ currency(mortgagePaymentEstimate.principalInterest) }} principal &amp; interest + {{ currency(mortgagePaymentEstimate.escrow) }} escrow)
          </div>
        </template>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showAccountModal = false">Cancel</button>
          <button class="btn btn-primary" @click="createAccount" :disabled="!canCreateAccount">Create</button>
        </div>
      </div>
    </div>

    <!-- Update Balance Modal -->
    <div v-if="showBalanceModal" class="modal-overlay" @click.self="showBalanceModal = false">
      <div class="modal">
        <h3>Update balance</h3>
        <p style="margin-bottom:0.75rem;color:var(--text-muted)">{{ updateTarget.bankName }} / {{ updateTarget.accountName }}</p>
        <div class="form-group">
          <label>New balance</label>
          <input v-model.number="updateTarget.newBalance" type="number" step="0.01" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showBalanceModal = false">Cancel</button>
          <button class="btn btn-primary" @click="updateBalance">Update</button>
        </div>
      </div>
    </div>

    <!-- Update Credit Balance Modal -->
    <div v-if="showCreditModal" class="modal-overlay" @click.self="showCreditModal = false">
      <div class="modal">
        <h3>Update credit balance</h3>
        <p style="margin-bottom:0.75rem;color:var(--text-muted)">{{ creditTarget.bankName }} / {{ creditTarget.accountName }}</p>
        <div class="form-group">
          <label>New balance owed</label>
          <input v-model.number="creditTarget.newBalance" type="number" step="0.01" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showCreditModal = false">Cancel</button>
          <button class="btn btn-primary" @click="updateCreditBal">Update</button>
        </div>
      </div>
    </div>

    <!-- Balance History Modal -->
    <div v-if="showHistoryModal" class="modal-overlay" @click.self="showHistoryModal = false">
      <div class="modal" style="max-width:600px">
        <h3>Balance history: {{ historyTarget.accountName }}</h3>
        <div v-if="historyLoading" class="loading">Loading history...</div>
        <div v-else-if="historyEntries.length === 0" class="empty-state" style="padding:1rem">
          <p>No history recorded yet. Update the balance to start tracking.</p>
        </div>
        <div v-else class="table-wrap" style="max-height:400px;overflow-y:auto">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th style="text-align:right">Previous</th>
                <th style="text-align:right">New</th>
                <th style="text-align:right">Change</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(h, i) in historyEntries" :key="i">
                <td style="font-size:0.8rem">{{ fmtDate(h.recordedAt) }}</td>
                <td style="text-align:right">{{ h.previousBalance != null ? currency(h.previousBalance) : '-' }}</td>
                <td style="text-align:right;font-weight:600">{{ currency(h.balance) }}</td>
                <td style="text-align:right;font-weight:600" :class="(h.balance - (h.previousBalance ?? 0)) >= 0 ? 'positive' : 'negative'">
                  {{ (h.balance - (h.previousBalance ?? 0)) >= 0 ? '+' : '' }}{{ currency(h.balance - (h.previousBalance ?? 0)) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showHistoryModal = false">Close</button>
        </div>
      </div>
    </div>

    <!-- Convert Credit to HELOC Modal -->
    <div v-if="showConvertModal" class="modal-overlay" @click.self="showConvertModal = false">
      <div class="modal">
        <h3>Convert to HELOC</h3>
        <p style="margin-bottom:0.75rem;color:var(--text-muted)">
          Convert <strong>{{ convertTarget.accountName }}</strong> ({{ convertTarget.bankName }}) from a credit account to a HELOC.
        </p>
        <p style="margin-bottom:1rem;font-size:0.8rem;color:var(--text-muted)">
          Balance of <strong>{{ currency(convertTarget.balance) }}</strong> and interest rate of <strong>{{ pct(convertTarget.interestRate) }}</strong> will be preserved.
        </p>
        <div class="form-group">
          <label>Draw period (years)</label>
          <input v-model.number="convertTarget.drawYears" type="number" min="1" max="30" step="1" />
          <small style="color:var(--text-muted)">Period during which you can borrow; minimums are interest-only.</small>
        </div>
        <div class="form-group">
          <label>Total term (years)</label>
          <input v-model.number="convertTarget.totalYears" type="number" min="2" max="40" step="1" />
          <small style="color:var(--text-muted)">Total payback period including draw period.</small>
        </div>
        <div class="form-group">
          <label>HELOC start date</label>
          <input v-model="convertTarget.startDate" type="date" />
          <small style="color:var(--text-muted)">When the HELOC was originally opened.</small>
        </div>
        <div class="form-group">
          <label>New account name (optional)</label>
          <input v-model="convertTarget.newName" placeholder="Leave blank to keep same name" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showConvertModal = false">Cancel</button>
          <button class="btn btn-primary" @click="convertToHELOC"
                  :disabled="convertTarget.totalYears <= convertTarget.drawYears">
            Convert
          </button>
        </div>
      </div>
    </div>

    <!-- Update HELOC Balance Modal -->
    <div v-if="showHELOCModal" class="modal-overlay" @click.self="showHELOCModal = false">
      <div class="modal">
        <h3>Update {{ helocTarget.accountType === 'mortgage' ? 'Mortgage Principal' : 'HELOC Balance' }}</h3>
        <p style="margin-bottom:0.75rem;color:var(--text-muted)">{{ helocTarget.bankName }} / {{ helocTarget.accountName }}</p>
        <div class="form-group">
          <label>{{ helocTarget.accountType === 'mortgage' ? 'New Principal Owed' : 'New Balance' }}</label>
          <input v-model.number="helocTarget.newBalance" type="number" step="0.01" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showHELOCModal = false">Cancel</button>
          <button class="btn btn-primary" @click="updateHELOCBal">Update</button>
        </div>
      </div>
    </div>

    <!-- SimpleFIN Transactions Modal (read-only) -->
    <div v-if="showTransactionsModal" class="modal-overlay" @click.self="showTransactionsModal = false">
      <div class="modal" style="max-width:700px">
        <h3>Recent transactions</h3>
        <p style="margin-bottom:0.75rem;color:var(--text-muted)">
          {{ txnTarget.bankName }} / {{ txnTarget.accountName }}
          <span class="badge badge-info" style="margin-left:0.5rem">SimpleFIN · Read Only</span>
        </p>
        <div v-if="txnLoading" class="loading">Fetching transactions from SimpleFIN...</div>
        <div v-else-if="transactions.length === 0" class="empty-state" style="padding:1rem">
          <p>No transactions found for this account in the last 30 days.</p>
        </div>
        <div v-else class="table-wrap" style="max-height:450px;overflow-y:auto">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th style="text-align:right">Amount</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="txn in transactions" :key="txn.id">
                <td style="font-size:0.8rem;white-space:nowrap">{{ fmtDate(txn.posted) }}</td>
                <td>
                  <div>{{ txn.description || txn.payee || '—' }}</div>
                  <div v-if="txn.memo" style="font-size:0.7rem;color:var(--text-muted)">{{ txn.memo }}</div>
                </td>
                <td style="text-align:right;font-weight:600;white-space:nowrap"
                    :class="txn.amount >= 0 ? 'positive' : 'negative'">
                  {{ currency(txn.amount) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showTransactionsModal = false">Close</button>
        </div>
      </div>
    </div>

    <!-- Promo Offers Modal -->
    <div v-if="showPromosModal" class="modal-overlay" @click.self="showPromosModal = false">
      <div class="modal" style="max-width:750px">
        <div class="card-header" style="margin-bottom:1rem">
          <h3 style="margin:0">Promo offers</h3>
          <button class="btn btn-primary btn-sm" @click="openAddPromo()"><Icon name="plus" :size="16" /> Add offer</button>
        </div>
        <p style="margin-bottom:0.75rem;color:var(--text-muted)">
          {{ promoTarget.bankName }} / {{ promoTarget.accountName }}
          · Balance: <strong>{{ currency(promoTarget.balance) }}</strong>
          · Regular: <strong>{{ currency(promoTarget.regularBalance) }}</strong>
        </p>
        <p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:1rem">
          Promos allocate portions of the existing balance for special financing. They do not add to the total balance.
        </p>

        <div v-if="promoTarget.promos.length === 0" class="empty-state" style="padding:1rem">
          <p>No promo offers yet. Add one to track a special financing rate.</p>
        </div>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Promo name</th>
                <th>Months</th>
                <th style="text-align:right">Promo balance</th>
                <th>Status</th>
                <th>Expires</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in promoTarget.promos" :key="p.promoName">
                <td style="font-weight:500">{{ p.promoName }}</td>
                <td>{{ p.monthsInterestFree }} mo</td>
                <td style="text-align:right;font-weight:600">{{ currency(p.promoBalance) }}</td>
                <td>
                  <span class="badge" :class="p.isActive ? 'badge-success' : 'badge-danger'">
                    {{ p.isActive ? 'Active' : 'Expired' }}
                  </span>
                  <span v-if="p.isActive && p.daysRemaining <= 30" class="badge badge-warning" style="margin-left:0.25rem">
                    {{ p.daysRemaining }}d left
                  </span>
                </td>
                <td style="font-size:0.8rem">{{ fmtDate(p.endDate) }}</td>
                <td style="text-align:right;white-space:nowrap">
                  <button v-if="p.promoBalance > 0" class="btn btn-outline btn-sm" @click="openPromoMoney('pay', p)">Pay</button>
                  <RowMenu :items="[
                    { label: 'Add a purchase', icon: 'plus', disabled: !p.isActive, action: () => openPromoMoney('purchase', p) },
                    { label: 'Pay down', icon: 'banknote', disabled: p.promoBalance <= 0, action: () => openPromoMoney('pay', p) },
                    { label: 'Edit offer', icon: 'pencil', action: () => openEditPromo(p) },
                    { label: 'Remove offer', icon: 'trash', danger: true, divider: true, action: () => removePromo(p.promoName) },
                  ]" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Add Promo Sub-form -->
        <div v-if="showAddPromo" class="card" style="margin-top:1rem;padding:1rem;background:var(--bg-card)">
          <h4 style="margin-bottom:0.75rem">{{ editingPromo ? 'Edit Promo Offer' : 'Add Promo Offer' }}</h4>
          <div class="form-group">
            <label>Promo name</label>
            <input v-model="newPromo.promoName" placeholder="e.g. 0% APR 12 months" />
          </div>
          <div class="form-group">
            <label>Months interest-free</label>
            <input v-model.number="newPromo.monthsInterestFree" type="number" min="1" />
          </div>
          <div class="form-group">
            <label>Purchase limit (optional)</label>
            <input v-model.number="newPromo.purchaseLimit" type="number" step="0.01" placeholder="Leave blank for unlimited" />
          </div>
          <div class="form-group">
            <label>Promo balance (portion of existing balance on this promo)</label>
            <input v-model.number="newPromo.promoBalance" type="number" step="0.01" />
          </div>
          <div class="form-group">
            <label>Start date</label>
            <input v-model="newPromo.startDate" type="date" />
          </div>
          <div class="form-group">
            <label>End date (optional, calculated if blank)</label>
            <input v-model="newPromo.endDate" type="date" />
          </div>
          <div class="modal-actions">
            <button class="btn btn-outline" @click="closePromoForm()">Cancel</button>
            <button v-if="editingPromo" class="btn btn-primary" @click="updatePromo" :disabled="!newPromo.promoName || !newPromo.monthsInterestFree">Save</button>
            <button v-else class="btn btn-primary" @click="addPromo" :disabled="!newPromo.promoName || !newPromo.monthsInterestFree">Add</button>
          </div>
        </div>

        <div class="modal-actions" style="margin-top:1rem">
          <button class="btn btn-outline" @click="showPromosModal = false">Close</button>
        </div>
      </div>
    </div>

    <MinPaymentDialog v-if="minTarget" :bank-name="minTarget.bankName" :card="minTarget.card"
                      @close="minTarget = null" @done="refetch()" />
    <TransferDialog :open="showTransfer" :banks="banks" @close="showTransfer = false" @done="refetch()" />
    <BalanceCheckIn :open="showCheckIn" :banks="banks" @close="showCheckIn = false" @done="refetch()" />
    <MortgageTools :open="!!mortgageTarget" :bank-name="mortgageTarget?.bank ?? ''" :account-name="mortgageTarget?.account ?? ''"
                   :initial-tab="mortgageTarget?.tab" :banks="banks" @close="mortgageTarget = null" @done="refetch()" />
    <PromoMoneyDialog :open="!!promoMoney" :mode="promoMoney?.mode ?? 'pay'" :bank-name="promoTarget.bankName"
                      :account-name="promoTarget.accountName" :promo-name="promoMoney?.promo.promoName ?? ''"
                      :promo-balance="promoMoney?.promo.promoBalance ?? 0" :banks="banks"
                      @close="promoMoney = null" @done="refetch()" />
  </div>
</template>

<script setup lang="ts">
import TransferDialog from '../components/TransferDialog.vue'
import BalanceCheckIn from '../components/BalanceCheckIn.vue'
import MortgageTools from '../components/MortgageTools.vue'
import PromoMoneyDialog from '../components/PromoMoneyDialog.vue'
import { useRoute, useRouter } from 'vue-router'
import RowMenu from '../components/RowMenu.vue'
import Icon from '../components/Icon.vue'
import { ref, computed, watch } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import {
  GET_ALL_BANKS, CREATE_BANK, CREATE_ACCOUNT,
  UPDATE_ACCOUNT_BALANCE, UPDATE_CREDIT_BALANCE,
  DELETE_BANK, DELETE_ACCOUNT,
  RECORD_BALANCE_UPDATE, GET_BALANCE_HISTORY,
  GET_SIMPLEFIN_SYNCED_ACCOUNTS,
  CONVERT_CREDIT_TO_HELOC,
  CREATE_HELOC_ACCOUNT,
  CREATE_MORTGAGE_ACCOUNT,
  GET_SIMPLEFIN_TRANSACTIONS,
  ADD_PROMO_OFFER, UPDATE_PROMO_OFFER, REMOVE_PROMO_OFFER,
  UPDATE_BANK,
} from '../graphql/queries'
import { apolloClient } from '../graphql/client'
import { currency, pct, fmtDate, statusBadge, todayISO, accountTypeLabel, num } from '../utils/format'
import { GROUP_BADGE, KIND_GROUPS, isBankKind, kindInfo, rateLabel } from '../utils/accountKinds'
import AccountExtrasFields, { type AccountExtras } from '../components/AccountExtrasFields.vue'
import { runMutation } from '../utils/mutation'
import EditAccountModal, { type AccountKind, type AnyAccount } from '../components/EditAccountModal.vue'
import MinPaymentDialog from '../components/MinPaymentDialog.vue'
import type { Bank, BankAccount, CreditAccount, BalanceHistoryEntry, SimplefinSyncedAccount, SimplefinTransaction, PromoOffer, MutationPayload } from '../types'
import { ask, notify } from '../utils/dialog'


const BANK_TYPES: Record<string, string> = { traditional: 'Bank', credit_issuer: 'Card issuer', mortgage_lender: 'Mortgage lender' }
const { result, loading, error, refetch } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const banks = computed(() => result.value?.allBanks ?? [])

const { result: syncedResult } = useQuery<{ simplefinSyncedAccounts: SimplefinSyncedAccount[] }>(GET_SIMPLEFIN_SYNCED_ACCOUNTS)

// Build a Set of "bankName:accountName" keys for synced accounts
const syncedKeys = computed(() => {
  const set = new Set<string>()
  for (const sa of syncedResult.value?.simplefinSyncedAccounts ?? []) {
    set.add(`${sa.bankName}:${sa.accountName}`)
  }
  return set
})

function isSynced(bankName: string, accountName: string): boolean {
  return syncedKeys.value.has(`${bankName}:${accountName}`)
}

function syncTooltip(bankName: string, accountName: string): string {
  const sa = (syncedResult.value?.simplefinSyncedAccounts ?? []).find(
    s => s.bankName === bankName && s.accountName === accountName
  )
  if (!sa) return ''
  return `Synced via SimpleFIN: ${sa.sfinOrg} / ${sa.sfinName}`
}

// ── Edit account / bank
const editTarget = ref<{ kind: AccountKind; bankName: string; account: AnyAccount } | null>(null)
function openEdit(bankName: string, kind: AccountKind, account: AnyAccount) {
  editTarget.value = { kind, bankName, account }
}
function onEdited() {
  editTarget.value = null
  refetch()
}

const bankEdit = ref<{ original: string; name: string; type: string } | null>(null)
function openEditBank(bank: Bank) {
  bankEdit.value = { original: bank.name, name: bank.name, type: bank.bankType }
}
const { mutate: doUpdateBank } = useMutation<{ updateBank: MutationPayload }>(UPDATE_BANK)
async function saveBank() {
  const b = bankEdit.value
  if (!b) return
  const ok = await runMutation(() => doUpdateBank({ variables: {
    name: b.original, newName: b.name.trim(), bankType: b.type,
  }}), 'updateBank', { failMessage: 'Failed to save the bank' })
  if (!ok) return
  bankEdit.value = null
  refetch()
}

// ── Create bank
const showBankModal = ref(false)
const newBank = ref({ name: '', type: 'traditional' })
const { mutate: doCreateBank } = useMutation<{ createBank: MutationPayload }>(CREATE_BANK)
async function createBank() {
  const ok = await runMutation(
    () => doCreateBank({ variables: { name: newBank.value.name, bankType: newBank.value.type }}),
    'createBank', { failMessage: 'Failed to create bank' },
  )
  if (!ok) return
  newBank.value = { name: '', type: 'traditional' }
  showBankModal.value = false
  refetch()
}

// ── Delete bank
const { mutate: doDeleteBank } = useMutation<{ deleteBank: MutationPayload }>(DELETE_BANK)
async function deleteBank(name: string) {
  if (!(await ask(`Delete bank "${name}" and all its accounts? This can't be undone.`, { title: 'Delete bank', confirmText: 'Delete bank', danger: true }))) return
  const ok = await runMutation(() => doDeleteBank({ variables: { name }}), 'deleteBank', { failMessage: 'Failed to delete bank' })
  if (ok) refetch()
}

function ordinal(n: number) {
  const s = ['th', 'st', 'nd', 'rd'], v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}
/** Short summary of an account's interest day, refill and weekly spending. */
function accountDetails(acc: BankAccount): string {
  const parts: string[] = []
  if ((acc.refillAmount ?? 0) > 0) parts.push(`+${currency(acc.refillAmount!)} on the ${ordinal(acc.refillDay ?? 1)}`)
  if ((acc.weeklySpending ?? 0) > 0) parts.push(`${currency(acc.weeklySpending!)}/wk spent${acc.offsetsEveryday ? ' (part of everyday)' : ''}`)
  if (acc.interestRate > 0 && kindInfo(acc.accountType).earns) {
    parts.push(acc.interestAccrualDate ? `interest on the ${ordinal(acc.interestAccrualDate)}` : 'interest at month end')
  }
  return parts.join(' · ')
}
function bankAccountsTitle(list: BankAccount[]): string {
  const kinds = new Set(list.map(a => a.accountType))
  if ([...kinds].every(k => k === 'checking' || k === 'savings')) return 'Checking & savings'
  return 'Cash & other accounts'
}

// ── Create account
const showAccountModal = ref(false)
function emptyAccount() {
  return {
    bankName: '', name: '', type: 'checking', balance: 0, interestRate: 0, creditLimit: 0,
    drawPeriodYears: 15, totalTermYears: 30, startDate: '',
    paymentDueDate: null as number | string | null,
    statementDate: null as number | string | null,
    interestAccrualDate: null as number | string | null,
    // Mortgage
    originalPrincipal: 0, loanTermYears: 30,
    escrowPropertyTax: null as number | string | null,
    escrowInsurance: null as number | string | null,
    escrowPmi: null as number | string | null,
    escrowHoa: null as number | string | null,
    escrowOther: null as number | string | null,
    marketValue: null as number | string | null,
    sourceBank: '', sourceAccount: '',
    extras: { refillAmount: null, refillDay: null, weeklySpending: null, offsetsEveryday: false } as AccountExtras,
  }
}
const newAccount = ref(emptyAccount())
// Pick a bank so the form can be saved right away
watch([showAccountModal, banks], ([open]) => {
  if (open && !newAccount.value.bankName && banks.value.length) newAccount.value.bankName = banks.value[0].name
})
const needsCreditLimit = computed(() => newAccount.value.type === 'credit' || newAccount.value.type === 'heloc')

const canCreateAccount = computed(() => {
  const a = newAccount.value
  if (!a.name || !a.bankName) return false
  if (needsCreditLimit.value && !(Number(a.creditLimit) > 0)) return false
  if (a.type === 'mortgage') {
    if (!(Number(a.originalPrincipal) > 0)) return false
    if (!!a.sourceBank !== !!a.sourceAccount) return false
  }
  return true
})

/** Optional money input -> number or null (empty inputs give ''). */
function optAmount(v: number | string | null | undefined): number | null {
  if (v === '' || v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const mortgageSourceAccounts = computed(() =>
  banks.value.find(b => b.name === newAccount.value.sourceBank)?.bankAccounts ?? [])

/** Live estimate shown in the form; mirrors MortgageAccount.base_monthly_payment. */
const mortgagePaymentEstimate = computed(() => {
  const a = newAccount.value
  const principal = Number(a.originalPrincipal)
  const months = Math.round(Number(a.loanTermYears) * 12)
  if (!(principal > 0) || !(months > 0)) return null
  const r = Number(a.interestRate || 0) / 100 / 12
  const pi = r === 0 ? principal / months : principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)
  const escrow = [a.escrowPropertyTax, a.escrowInsurance, a.escrowPmi, a.escrowHoa, a.escrowOther]
    .reduce<number>((sum, v) => sum + (optAmount(v) ?? 0), 0)
  return { principalInterest: pi, escrow, total: pi + escrow }
})

/** Optional day-of-month input -> integer or null (empty inputs give ''). */
function optDay(v: number | string | null | undefined): number | null {
  if (v === '' || v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? Math.trunc(n) : null
}

const { mutate: doCreateAccount } = useMutation<{ createAccount: MutationPayload }>(CREATE_ACCOUNT)
const { mutate: doCreateHELOC } = useMutation<{ createHelocAccount: MutationPayload }>(CREATE_HELOC_ACCOUNT)
const { mutate: doCreateMortgage } = useMutation<{ createMortgageAccount: MutationPayload }>(CREATE_MORTGAGE_ACCOUNT)
async function createAccount() {
  const a = newAccount.value
  if (needsCreditLimit.value && !(Number(a.creditLimit) > 0)) {
    notify('Credit limit must be greater than 0', 'error')
    return
  }
  let ok
  if (a.type === 'heloc') {
    ok = await runMutation(() => doCreateHELOC({ variables: {
      bankName: a.bankName,
      accountName: a.name,
      creditLimit: num(a.creditLimit),
      interestRate: num(a.interestRate) ?? 0,
      drawPeriodMonths: (num(a.drawPeriodYears) ?? 15) * 12,
      totalTermMonths: (num(a.totalTermYears) ?? 30) * 12,
      startDate: a.startDate || undefined,
      currentBalance: num(a.balance) ?? 0,
      paymentDueDate: optDay(a.paymentDueDate) ?? 1,
    }}), 'createHelocAccount', { failMessage: 'Failed to create HELOC' })
  } else if (a.type === 'mortgage') {
    ok = await runMutation(() => doCreateMortgage({ variables: {
      bankName: a.bankName,
      accountName: a.name,
      originalPrincipal: num(a.originalPrincipal),
      currentPrincipal: optAmount(a.balance) || null,
      interestRate: num(a.interestRate) ?? 0,
      loanTermMonths: Math.round((num(a.loanTermYears) ?? 30) * 12),
      paymentDueDate: optDay(a.paymentDueDate) ?? 1,
      startDate: a.startDate || null,
      escrowPropertyTax: optAmount(a.escrowPropertyTax),
      escrowInsurance: optAmount(a.escrowInsurance),
      escrowPmi: optAmount(a.escrowPmi),
      escrowHoa: optAmount(a.escrowHoa),
      escrowOther: optAmount(a.escrowOther),
      marketValue: optAmount(a.marketValue),
      preferredSourceBank: a.sourceBank || null,
      preferredSourceAccount: a.sourceAccount || null,
    }}), 'createMortgageAccount', { failMessage: 'Failed to create mortgage' })
  } else {
    const isCredit = a.type === 'credit'
    const x = a.extras
    ok = await runMutation(() => doCreateAccount({ variables: {
      ...(isCredit ? {} : {
        refillAmount: optAmount(x.refillAmount) ?? 0, refillDay: optDay(x.refillDay),
        weeklySpending: optAmount(x.weeklySpending) ?? 0, offsetsEveryday: x.offsetsEveryday,
      }),
      bankName: a.bankName,
      accountName: a.name,
      accountType: a.type,
      balance: num(a.balance) ?? 0,
      interestRate: num(a.interestRate) ?? 0,
      creditLimit: isCredit ? num(a.creditLimit) : undefined,
      paymentDueDate: isCredit ? optDay(a.paymentDueDate) : null,
      statementDate: isCredit ? optDay(a.statementDate) : null,
      interestAccrualDate: !isCredit ? optDay(a.interestAccrualDate) : null,
    }}), 'createAccount', { failMessage: 'Failed to create account' })
  }
  if (!ok) return
  newAccount.value = emptyAccount()
  showAccountModal.value = false
  refetch()
}

// ── Delete account
const { mutate: doDeleteAccount } = useMutation<{ deleteAccount: MutationPayload }>(DELETE_ACCOUNT)
async function deleteAccount(bankName: string, accountName: string, accountType: string) {
  if (!(await ask(`Delete account "${accountName}"? This can't be undone.`, { title: 'Delete account', danger: true }))) return
  const ok = await runMutation(
    () => doDeleteAccount({ variables: { bankName, accountName, accountType }}),
    'deleteAccount', { failMessage: 'Failed to delete account' },
  )
  if (ok) refetch()
}

// ── Update bank account balance (with history)
const showBalanceModal = ref(false)
const updateTarget = ref({ bankName: '', accountName: '', newBalance: 0 })
function openUpdateBalance(bankName: string, accountName: string, current: number) {
  updateTarget.value = { bankName, accountName, newBalance: current }
  showBalanceModal.value = true
}
const { mutate: doRecordUpdate } = useMutation<{ recordBalanceUpdate: MutationPayload }>(RECORD_BALANCE_UPDATE)
async function recordUpdate(bankName: string, accountName: string, newBalance: number | string, accountType: string) {
  const balance = num(newBalance)
  if (balance == null) { notify('Enter the balance', 'error'); return null }
  return runMutation(
    () => doRecordUpdate({ variables: { bankName, accountName, newBalance: balance, accountType }}),
    'recordBalanceUpdate', { failMessage: 'Failed to update balance' },
  )
}
async function updateBalance() {
  const t = updateTarget.value
  if (!(await recordUpdate(t.bankName, t.accountName, t.newBalance, 'bank'))) return
  showBalanceModal.value = false
  refetch()
}

// ── Update credit balance (with history)
const showCreditModal = ref(false)
const creditTarget = ref({ bankName: '', accountName: '', newBalance: 0 })
function openUpdateCredit(bankName: string, accountName: string, current: number) {
  creditTarget.value = { bankName, accountName, newBalance: current }
  showCreditModal.value = true
}
async function updateCreditBal() {
  const t = creditTarget.value
  if (!(await recordUpdate(t.bankName, t.accountName, t.newBalance, 'credit'))) return
  showCreditModal.value = false
  refetch()
}

// ── Balance history viewer
const showHistoryModal = ref(false)
const historyTarget = ref({ bankName: '', accountName: '', accountType: '' })
const historyEntries = ref<BalanceHistoryEntry[]>([])
const historyLoading = ref(false)

async function openHistory(bankName: string, accountName: string, accountType: string) {
  historyTarget.value = { bankName, accountName, accountType }
  historyLoading.value = true
  historyEntries.value = []
  showHistoryModal.value = true
  try {
    const result = await apolloClient.query<{ balanceHistory: BalanceHistoryEntry[] }>({
      query: GET_BALANCE_HISTORY,
      variables: { bankName, accountName, limit: 50 },
      fetchPolicy: 'network-only',
    })
    historyEntries.value = result.data?.balanceHistory ?? []
  } catch { historyEntries.value = [] }
  historyLoading.value = false
}

// ── Helpers
/** A promo still owing: the minimum shown includes what clears it before it expires. */
function owesPromo(cc: CreditAccount) {
  return (cc.promoOffers ?? []).some(p => (p.promoBalance ?? 0) > 0.005 && !p.interestCharged)
}

function utilPct(cc: CreditAccount) {
  return cc.creditLimit > 0 ? (cc.balance / cc.creditLimit) * 100 : 0
}
function utilColor(cc: CreditAccount) {
  const u = utilPct(cc)
  if (u > 80) return 'var(--danger)'
  if (u > 50) return 'var(--warning)'
  return 'var(--success)'
}

// ── Convert Credit to HELOC
const showConvertModal = ref(false)
const convertTarget = ref({
  bankName: '',
  accountName: '',
  balance: 0,
  interestRate: 0,
  drawYears: 15,
  totalYears: 30,
  startDate: '',
  newName: '',
})

function openConvertToHELOC(bankName: string, cc: CreditAccount) {
  convertTarget.value = {
    bankName,
    accountName: cc.accountName,
    balance: cc.balance,
    interestRate: cc.interestRate,
    drawYears: 15,
    totalYears: 30,
    startDate: todayISO(),
    newName: '',
  }
  showConvertModal.value = true
}

const { mutate: doConvertToHELOC } = useMutation<{ convertCreditToHeloc: MutationPayload }>(CONVERT_CREDIT_TO_HELOC)
async function convertToHELOC() {
  const t = convertTarget.value
  if (t.totalYears <= t.drawYears) return
  const ok = await runMutation(() => doConvertToHELOC({ variables: {
    bankName: t.bankName,
    accountName: t.accountName,
    drawPeriodMonths: t.drawYears * 12,
    totalTermMonths: t.totalYears * 12,
    startDate: t.startDate || undefined,
    newAccountName: t.newName || undefined,
  }}), 'convertCreditToHeloc', { failMessage: 'Failed to convert to HELOC' })
  if (!ok) return
  showConvertModal.value = false
  refetch()
}

// ── Update HELOC / mortgage balance
const showHELOCModal = ref(false)
const helocTarget = ref({ bankName: '', accountName: '', newBalance: 0, accountType: 'heloc' as 'heloc' | 'mortgage' })
function openUpdateLoan(bankName: string, accountName: string, current: number, accountType: 'heloc' | 'mortgage') {
  helocTarget.value = { bankName, accountName, newBalance: current, accountType }
  showHELOCModal.value = true
}
async function updateHELOCBal() {
  const t = helocTarget.value
  if (!(await recordUpdate(t.bankName, t.accountName, t.newBalance, t.accountType))) return
  showHELOCModal.value = false
  refetch()
}

// ── SimpleFIN Transactions (read-only)
const showTransactionsModal = ref(false)
const txnTarget = ref({ bankName: '', accountName: '' })
const transactions = ref<SimplefinTransaction[]>([])
const txnLoading = ref(false)

async function openTransactions(bankName: string, accountName: string) {
  txnTarget.value = { bankName, accountName }
  txnLoading.value = true
  transactions.value = []
  showTransactionsModal.value = true
  try {
    const result = await apolloClient.query<{ simplefinTransactions: SimplefinTransaction[] }>({
      query: GET_SIMPLEFIN_TRANSACTIONS,
      variables: { bankName, accountName, days: 30 },
      fetchPolicy: 'network-only',
    })
    transactions.value = result.data?.simplefinTransactions ?? []
  } catch { transactions.value = [] }
  txnLoading.value = false
}

// ── Promo Offers management
const showPromosModal = ref(false)
// Card whose minimum payment is being matched to a statement
const minTarget = ref<{ bankName: string; card: CreditAccount } | null>(null)
const showAddPromo = ref(false)
const editingPromo = ref(false)
const promoTarget = ref({ bankName: '', accountName: '', balance: 0, regularBalance: 0, promos: [] as PromoOffer[] })
const newPromo = ref({
  promoName: '',
  monthsInterestFree: 12,
  purchaseLimit: null as number | null,
  promoBalance: 0,
  startDate: '',
  endDate: '',
})

// ── Money moves (transfers, balance check-in, mortgage tools, promo purchases/payments)
const showTransfer = ref(false)
const showCheckIn = ref(false)
const mortgageTarget = ref<{ bank: string; account: string; tab?: string } | null>(null)
function openMortgage(bank: string, account: string, tab?: string) {
  mortgageTarget.value = { bank, account, tab }
}
const promoMoney = ref<{ mode: 'purchase' | 'pay'; promo: PromoOffer } | null>(null)
function openPromoMoney(mode: 'purchase' | 'pay', promo: PromoOffer) {
  promoMoney.value = { mode, promo }
}
// Keep the open promo list in step with fresh data after a purchase or payment
watch(banks, list => {
  if (!showPromosModal.value) return
  const cc = list.find(b => b.name === promoTarget.value.bankName)?.creditAccounts
    .find(c => c.accountName === promoTarget.value.accountName)
  if (cc) Object.assign(promoTarget.value, { balance: cc.balance, regularBalance: cc.regularBalance, promos: cc.promoOffers ?? [] })
})

// Open a dialog from a link elsewhere (e.g. the command palette): /accounts?action=transfer
const route = useRoute()
const router = useRouter()
watch(() => route.query.action, action => {
  if (action === 'transfer') showTransfer.value = true
  else if (action === 'balances') showCheckIn.value = true
  else if (action === 'add') {
    // /accounts?action=add&q=ebt opens the form with that kind picked
    const kind = typeof route.query.q === 'string' ? route.query.q : ''
    newAccount.value = { ...emptyAccount(), type: isBankKind(kind) || ['credit', 'heloc', 'mortgage'].includes(kind) ? kind : 'checking' }
    showAccountModal.value = true
  } else return
  router.replace({ query: { ...route.query, action: undefined, q: undefined } })
}, { immediate: true })

function openPromos(bankName: string, cc: CreditAccount) {
  promoTarget.value = {
    bankName,
    accountName: cc.accountName,
    balance: cc.balance,
    regularBalance: cc.regularBalance,
    promos: cc.promoOffers ?? [],
  }
  showAddPromo.value = false
  editingPromo.value = false
  showPromosModal.value = true
}

function emptyPromo() {
  return { promoName: '', monthsInterestFree: 12, purchaseLimit: null as number | null, promoBalance: 0, startDate: '', endDate: '' }
}

function openAddPromo() {
  newPromo.value = emptyPromo()
  editingPromo.value = false
  showAddPromo.value = true
}

function closePromoForm() {
  showAddPromo.value = false
  editingPromo.value = false
  newPromo.value = emptyPromo()
}

const editingPromoMonths = ref(0)
function openEditPromo(p: PromoOffer) {
  editingPromoName.value = p.promoName
  editingPromoMonths.value = p.monthsInterestFree
  newPromo.value = {
    promoName: p.promoName,
    monthsInterestFree: p.monthsInterestFree,
    purchaseLimit: p.purchaseLimit,
    promoBalance: p.promoBalance,
    startDate: p.startDate ?? '',
    endDate: p.endDate ?? '',
  }
  editingPromo.value = true
  showAddPromo.value = true
}

const { mutate: doAddPromo } = useMutation<{ addPromoOffer: MutationPayload }>(ADD_PROMO_OFFER)
async function addPromo() {
  const ok = await runMutation(() => doAddPromo({ variables: {
    bankName: promoTarget.value.bankName,
    accountName: promoTarget.value.accountName,
    promoName: newPromo.value.promoName,
    monthsInterestFree: num(newPromo.value.monthsInterestFree) ?? 12,
    purchaseLimit: num(newPromo.value.purchaseLimit) || undefined,
    promoBalance: num(newPromo.value.promoBalance) ?? 0,
    startDate: newPromo.value.startDate || undefined,
    endDate: newPromo.value.endDate || undefined,
  }}), 'addPromoOffer', { failMessage: 'Failed to add promo' })
  if (!ok) return
  closePromoForm()
  await refetch()
  // Refresh promo target from updated data
  refreshPromoTarget()
}

const { mutate: doUpdatePromo } = useMutation<{ updatePromoOffer: MutationPayload }>(UPDATE_PROMO_OFFER)
const editingPromoName = ref('')
async function updatePromo() {
  const p = newPromo.value
  const months = num(p.monthsInterestFree) ?? editingPromoMonths.value
  // New length: let the server work out the end date from the start and the months
  const endDate = months !== editingPromoMonths.value ? undefined : (p.endDate || undefined)
  const ok = await runMutation(() => doUpdatePromo({ variables: {
    bankName: promoTarget.value.bankName,
    accountName: promoTarget.value.accountName,
    promoName: editingPromoName.value,
    newName: p.promoName,
    promoBalance: num(p.promoBalance) ?? 0,
    monthsInterestFree: months,
    purchaseLimit: num(p.purchaseLimit) || 0,
    startDate: p.startDate || undefined,
    endDate,
  }}), 'updatePromoOffer', { failMessage: 'Failed to update promo' })
  if (!ok) return
  closePromoForm()
  await refetch()
  refreshPromoTarget()
}

const { mutate: doRemovePromo } = useMutation<{ removePromoOffer: MutationPayload }>(REMOVE_PROMO_OFFER)
async function removePromo(promoName: string) {
  if (!(await ask(`Remove promo "${promoName}"? Its balance returns to the regular balance.`, { title: 'Remove promo', confirmText: 'Remove', danger: true }))) return
  const ok = await runMutation(() => doRemovePromo({ variables: {
    bankName: promoTarget.value.bankName,
    accountName: promoTarget.value.accountName,
    promoName,
  }}), 'removePromoOffer', { failMessage: 'Failed to remove promo' })
  if (!ok) return
  await refetch()
  refreshPromoTarget()
}

function refreshPromoTarget() {
  const bankData = banks.value.find(b => b.name === promoTarget.value.bankName)
  if (bankData) {
    const cc = bankData.creditAccounts.find(c => c.accountName === promoTarget.value.accountName)
    if (cc) {
      promoTarget.value.balance = cc.balance
      promoTarget.value.regularBalance = cc.regularBalance
      promoTarget.value.promos = cc.promoOffers ?? []
    }
  }
}
</script>

<style scoped>
.link-btn { background: none; border: none; color: inherit; cursor: pointer; font: inherit; padding: 0; text-decoration: underline dotted; }
.min-rule { font-size: 0.7rem; color: var(--text-muted); }
.restricted-note { margin-left: 0.35rem; font-size: 0.7rem; color: var(--text-light); white-space: nowrap; }
.acct-details { font-size: 0.8rem; color: var(--text-muted); max-width: 300px; }
.sync-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.7rem;
  color: var(--primary);
  cursor: help;
  margin-left: 0.35rem;
  vertical-align: middle;
}
.sync-label {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  opacity: 0.8;
}
.promo-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  font-size: 0.7rem;
  color: var(--warning);
  cursor: help;
  margin-left: 0.35rem;
  vertical-align: middle;
}
.bank-card + .bank-card { margin-top: 1.25rem; }
.bank-title { display: flex; align-items: center; gap: 0.6rem; min-width: 0; }
.bank-mark { width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center; background: var(--primary-light); color: var(--primary); flex: 0 0 32px; }
.bank-total { font-weight: 650; font-variant-numeric: tabular-nums; margin-right: 0.25rem; }
.row-actions { display: inline-flex; align-items: center; justify-content: flex-end; gap: 0.35rem; }
.bank-card h4 { margin-top: 1.25rem; }
.bank-card .card-header + div h4 { margin-top: 0; }
</style>
